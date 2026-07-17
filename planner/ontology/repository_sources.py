"""Deterministic discovery of the repository documents named by ontology metadata.

This module intentionally knows about locator *kinds*, rather than about the
domain represented by a card.  The compiled repository projection is the only
authority for what is read.
"""

# YAML and generated artifact payloads are intentionally structural at this
# boundary; the compiler owns their detailed schema.
# pyright: reportAny=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownLambdaType=false

from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from planner.ontology.artifacts import OntologyBundle, _is_verified_bundle
from planner.ontology.errors import OntologyInfrastructureError


@dataclass(frozen=True)
class RepositoryDocument:
    """One source document and its compiled mapping instructions."""

    source_id: str
    path: Path
    document: object
    root_class: str
    documents: Mapping[str, object]
    document_key: str | None = None

    @property
    def source_path(self) -> str:
        return self.path.as_posix()


def discover_repository_sources(repository_root: Path, ontology: OntologyBundle) -> tuple[RepositoryDocument, ...]:
    """Discover only the source files declared in a compiled projection map.

    ``ontology`` must be the opaque, verified bundle returned by
    :func:`planner.ontology.artifacts.load_ontology`.  No recursive traversal
    or glob expansion is performed; flat roots enumerate their immediate YAML
    files in lexical order.
    """
    if not _is_verified_bundle(ontology):
        raise OntologyInfrastructureError("Repository discovery requires a verified OntologyBundle")
    return _discover_repository_sources(repository_root, ontology.projection_map)


def _discover_repository_sources(  # noqa: C901, PLR0912
    repository_root: Path, projection: Mapping[str, object]
) -> tuple[RepositoryDocument, ...]:
    """Private structural interpreter used only by focused fixture tests."""

    catalogs = _catalog_paths_mapping(projection)
    projection = _projection_mapping(projection)
    raw_sources = projection.get("sources")
    if not isinstance(raw_sources, list):
        raise OntologyInfrastructureError("Compiled repository projection sources must be a list")
    found: list[RepositoryDocument] = []
    for raw_source in sorted(raw_sources, key=lambda item: str(item.get("id", "")) if isinstance(item, dict) else ""):
        if not isinstance(raw_source, dict):
            raise OntologyInfrastructureError("Compiled repository projection source must be a mapping")
        source_id = _required_text(raw_source, "id")
        locator = raw_source.get("locator")
        if not isinstance(locator, dict):
            raise OntologyInfrastructureError(f"Source {source_id!r} has no locator")
        documents = raw_source.get("documents", {})
        if not isinstance(documents, dict):
            raise OntologyInfrastructureError(f"Source {source_id!r} documents must be a mapping")
        root_class = _required_text(raw_source, "root_class")
        kind = locator.get("kind")
        if kind == "catalog_ref":
            catalog_id = _required_text(locator, "catalog_id")
            relative = catalogs.get(catalog_id)
            if relative is None:
                raise OntologyInfrastructureError(f"Source {source_id!r} references unknown catalog {catalog_id!r}")
            relative = _safe_relative_path(relative, source_id)
            found.append(_load_document(repository_root, source_id, relative, root_class, documents))
        elif kind == "flat_root":
            relative = _safe_relative_path(locator.get("path"), source_id)
            found.extend(_load_flat_root(repository_root, source_id, relative, root_class, documents))
        elif kind == "explicit_path":
            relative = _safe_relative_path(locator.get("path"), source_id)
            found.append(_load_document(repository_root, source_id, relative, root_class, documents))
        elif kind == "explicit_paths":
            paths = locator.get("paths")
            if not isinstance(paths, list) or not paths:
                raise OntologyInfrastructureError(f"Source {source_id!r} explicit_paths must be non-empty")
            for value in sorted(paths, key=str):
                relative = _safe_relative_path(value, source_id)
                found.append(_load_document(repository_root, source_id, relative, root_class, documents))
        else:
            raise OntologyInfrastructureError(f"Unsupported repository source locator for {source_id!r}: {kind!r}")
    return tuple(found)


# Short alias used by callers that already have a repository-source context.
discover_sources = discover_repository_sources


def _load_flat_root(
    repository_root: Path,
    source_id: str,
    relative: str,
    root_class: str,
    documents: Mapping[str, object],
) -> list[RepositoryDocument]:
    root = _display_path(repository_root, relative)
    try:
        root_fd = _open_directory(repository_root, relative)
    except OSError as error:
        raise OntologyInfrastructureError(f"Flat-root source {source_id!r} is not a directory: {relative}") from error
    result: list[RepositoryDocument] = []
    try:
        entries: list[tuple[str, tuple[int, int]]] = []
        for name in sorted(os.listdir(root_fd)):  # noqa: PTH208
            if Path(name).suffix.lower() not in {".yaml", ".yml"}:
                raise OntologyInfrastructureError(f"Unexpected flat-root entry for {source_id!r}: {root / name}")
            try:
                entry_stat = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            except OSError as error:
                raise OntologyInfrastructureError(f"Cannot inspect flat-root entry {root / name}: {error}") from error
            if not stat.S_ISREG(entry_stat.st_mode):
                raise OntologyInfrastructureError(f"Unexpected flat-root entry for {source_id!r}: {root / name}")
            entries.append((name, (entry_stat.st_dev, entry_stat.st_ino)))
        for name, expected_inode in entries:
            result.append(
                _load_document(
                    repository_root,
                    source_id,
                    f"{relative}/{name}",
                    root_class,
                    documents,
                    parent_fd=root_fd,
                    name=name,
                    expected_inode=expected_inode,
                )
            )
    finally:
        os.close(root_fd)
    return result


def _load_document(  # noqa: PLR0913
    repository_root: Path,
    source_id: str,
    relative: str,
    root_class: str,
    documents: Mapping[str, object],
    *,
    parent_fd: int | None = None,
    name: str | None = None,
    expected_inode: tuple[int, int] | None = None,
) -> RepositoryDocument:
    path = _display_path(repository_root, relative)
    owns_parent = parent_fd is None
    try:
        if parent_fd is None:
            parent_fd, name = _open_parent(repository_root, relative)
        assert name is not None
        if expected_inode is None:
            expected_inode = _entry_inode(parent_fd, name, path)
        loaded = yaml.safe_load(_read_document_bytes(parent_fd, name, expected_inode, path))
    except (OSError, UnicodeDecodeError, yaml.YAMLError, OntologyInfrastructureError) as error:
        raise OntologyInfrastructureError(f"Cannot load repository source {relative}: {error}") from error
    finally:
        if owns_parent and parent_fd is not None:
            os.close(parent_fd)
    shape = documents.get("document_shape")
    if shape == "mapping" and not isinstance(loaded, dict):
        raise OntologyInfrastructureError(f"Repository source {relative} must contain a mapping")
    if shape == "keyed-map" and not isinstance(loaded, dict):
        raise OntologyInfrastructureError(f"Repository source {relative} must contain a keyed mapping")
    if shape not in {"mapping", "keyed-map"}:
        raise OntologyInfrastructureError(f"Unsupported document shape for source {source_id!r}: {shape!r}")
    return RepositoryDocument(source_id, path, loaded, root_class, documents)


def _projection(ontology: OntologyBundle) -> dict[str, object]:
    raw = ontology.projection_map
    if not isinstance(raw, Mapping):
        raise OntologyInfrastructureError("Verified ontology bundle has no compiled projection map")
    return _projection_mapping(raw)


def _projection_mapping(raw: Mapping[str, object]) -> dict[str, object]:
    if isinstance(raw.get("repository_projection"), Mapping):
        raw = cast(Mapping[str, object], raw["repository_projection"])
    if not isinstance(raw, Mapping) or not isinstance(raw.get("sources"), list):
        raise OntologyInfrastructureError("Compiled projection map has no repository_projection.sources")
    return cast(dict[str, object], raw)


def _catalog_paths_mapping(raw: Mapping[str, object]) -> dict[str, str]:
    catalogs = raw.get("catalogs")
    result: dict[str, str] = {}
    if isinstance(catalogs, Mapping):
        for catalog_id, path in catalogs.items():
            _add_catalog_path(result, catalog_id, path)
        return result
    if not isinstance(catalogs, list):
        return {}
    for item in catalogs:
        if not isinstance(item, Mapping):
            raise OntologyInfrastructureError("Compiled projection catalog entries must be mappings")
        _add_catalog_path(result, item.get("id"), item.get("path"))
    return result


def _add_catalog_path(result: dict[str, str], catalog_id: object, value: object) -> None:
    if not isinstance(catalog_id, str) or not catalog_id:
        raise OntologyInfrastructureError(f"Compiled projection catalog requires a non-empty id: {catalog_id!r}")
    if catalog_id in result:
        raise OntologyInfrastructureError(f"Duplicate compiled projection catalog id: {catalog_id!r}")
    path = _safe_relative_path(value, f"catalog {catalog_id}")
    if path in result.values():
        raise OntologyInfrastructureError(f"Duplicate compiled projection catalog path: {path!r}")
    result[catalog_id] = path


def _required_text(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise OntologyInfrastructureError(f"Projection metadata requires text field {key!r}")
    return value


def _safe_relative_path(value: object, source_id: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or Path(value).is_absolute():
        raise OntologyInfrastructureError(f"Unsafe locator path for source {source_id!r}: {value!r}")
    path = Path(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise OntologyInfrastructureError(f"Unsafe locator path for source {source_id!r}: {value!r}")
    normalized = path.as_posix()
    if normalized != value:
        raise OntologyInfrastructureError(f"Non-canonical locator path for source {source_id!r}: {value!r}")
    return normalized


def _display_path(repository_root: Path, relative: str) -> Path:
    return repository_root.absolute() / relative


def _open_directory(repository_root: Path, relative: str) -> int:
    root_fd = _open_root(repository_root)
    current_fd = root_fd
    try:
        for component in Path(relative).parts:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _open_parent(repository_root: Path, relative: str) -> tuple[int, str]:
    parts = Path(relative).parts
    if not parts:
        raise OSError("empty source path")
    parent = "/".join(parts[:-1])
    return _open_directory(repository_root, parent) if parent else _open_root(repository_root), parts[-1]


def _open_root(repository_root: Path) -> int:
    absolute = repository_root.absolute()
    current_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        for component in absolute.parts[1:]:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _read_document_bytes(parent_fd: int, name: str, expected_inode: tuple[int, int] | None, path: Path) -> bytes:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent_fd)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise OntologyInfrastructureError(f"Repository source is not a regular file: {path}")
        actual_inode = (opened.st_dev, opened.st_ino)
        if expected_inode is not None and actual_inode != expected_inode:
            raise OntologyInfrastructureError(f"Repository source changed while loading: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _entry_inode(parent_fd: int, name: str, path: Path) -> tuple[int, int]:
    entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISREG(entry.st_mode):
        raise OntologyInfrastructureError(f"Repository source is not a regular file: {path}")
    return entry.st_dev, entry.st_ino
