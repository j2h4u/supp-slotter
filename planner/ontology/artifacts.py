"""Pure, fail-closed loading of the locked ontology artifact set.

This module deliberately knows nothing about LinkML, RDF, or the compiler.  A
runtime process consumes bytes produced by the compiler and proves that those
bytes are the exact, declared set before decoding them.
"""

# Decoded contract values are deliberately compatibility-shaped immutable
# dict/list subclasses; their mutator overrides are runtime guards rather than
# ordinary mutable-container method signatures.
# pyright: reportAny=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportAssignmentType=false, reportArgumentType=false, reportUnannotatedClassAttribute=false, reportCallIssue=false

from __future__ import annotations

import hashlib
import json
import os
import threading
import weakref
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, SupportsIndex, cast

import yaml

from planner.ontology.errors import (
    MALFORMED,
    MISSING,
    STALE,
    UNSAFE_PATH,
    UNSUPPORTED,
    OntologyInfrastructureError,
)

if TYPE_CHECKING:
    from planner.ontology.runtime_program import RuntimeProgram

RUNTIME_VOCABULARY_FORMAT = "supp-slotter.runtime-vocabulary/v2"
ARTIFACT_LOCK_FORMAT = "ontology-artifact-lock-v1"
SCHEMA_VERSION = "2"
_SHA256_HEX_LENGTH = 64
_REQUIRED_OUTPUTS = frozenset({
    "card.schema.json",
    "schema.json",
    "ontology.ttl",
    "shapes.ttl",
    "context.json",
    "projection-map.json",
    "runtime-program.json",
    "runtime-vocabulary.yaml",
})
_REQUIRED_MANIFEST_ARTIFACTS = _REQUIRED_OUTPUTS | {"artifact-lock.json"}


class _FrozenDict(dict[object, object]):
    """A dict-shaped immutable mapping retained for compatibility callers."""

    def _immutable(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("verified ontology artifacts are immutable")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _immutable
    __ior__ = _immutable

    def copy(self) -> _FrozenDict:
        return self

    def __reduce_ex__(self, protocol: SupportsIndex) -> tuple[type[_FrozenDict], tuple[dict[object, object]]]:
        del protocol
        return type(self), (dict(self),)


class _FrozenList(list[object]):
    """A list-shaped immutable sequence retained for compatibility callers."""

    def _immutable(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("verified ontology artifacts are immutable")

    __setitem__ = __delitem__ = __iadd__ = __imul__ = _immutable
    append = clear = extend = insert = pop = remove = reverse = sort = _immutable

    def copy(self) -> _FrozenList:
        return self

    def __reduce_ex__(self, protocol: SupportsIndex) -> tuple[type[_FrozenList], tuple[list[object]]]:
        del protocol
        return type(self), (list(self),)


def _freeze(value: object) -> object:
    if isinstance(value, dict):
        return _FrozenDict({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return _FrozenList(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class OntologyBundle:
    """The verified artifact set and its decoded runtime projection.

    ``artifacts`` contains the exact bytes keyed by the lock's output path.
    ``decoded`` contains JSON/YAML values (and UTF-8 text for Turtle files).
    The compatibility ``runtime_vocabulary`` property is the one canonical
    runtime vocabulary view; it is not independently loaded or regenerated.
    """

    root: Path
    manifest: Mapping[str, object]
    artifact_lock: Mapping[str, object]
    artifacts: Mapping[str, bytes]
    decoded: Mapping[str, object]

    def __copy__(self) -> OntologyBundle:
        """Return an ordinary, deliberately unverified copy."""

        return OntologyBundle(self.root, self.manifest, self.artifact_lock, self.artifacts, self.decoded)

    def __deepcopy__(self, memo: dict[int, object]) -> OntologyBundle:
        """Immutable fields may be shared, but verification provenance may not."""

        del memo
        return self.__copy__()

    @property
    def runtime_vocabulary(self) -> Mapping[str, object]:
        value = self.decoded.get("runtime-vocabulary.yaml")
        if not isinstance(value, dict):
            raise OntologyInfrastructureError(
                "Verified ontology artifact set has no runtime vocabulary",
                code=UNSUPPORTED,
            )
        return cast(Mapping[str, object], value)

    @property
    def runtime_program(self) -> RuntimeProgram:
        """Typed projection decoded from the same verified artifact bytes."""
        from planner.ontology.runtime_program import decode_runtime_program

        value = self.decoded.get("runtime-program.json")
        if not isinstance(value, Mapping):
            raise OntologyInfrastructureError("Verified ontology artifact set has no runtime program", code=UNSUPPORTED)
        return decode_runtime_program(cast(Mapping[str, object], value))

    @property
    def artifact_bytes(self) -> Mapping[str, bytes]:
        """Alias documenting that values are the original verified bytes."""

        return self.artifacts

    @property
    def projection_map(self) -> Mapping[str, object]:
        """Compiled repository projection consumed by generic projectors."""

        value = self.decoded.get("projection-map.json")
        if not isinstance(value, dict):
            raise OntologyInfrastructureError(
                "Verified ontology artifact set has no projection map",
                code=UNSUPPORTED,
            )
        return cast(Mapping[str, object], value)

    @property
    def projection(self) -> Mapping[str, object]:
        """Short alias for callers that use the projection vocabulary."""

        return self.projection_map


_VERIFIED_BUNDLES: dict[int, weakref.ReferenceType[OntologyBundle]] = {}
_VERIFIED_BUNDLES_LOCK = threading.Lock()


def _register_verified_bundle(bundle: OntologyBundle) -> OntologyBundle:
    identity = id(bundle)

    def discard(reference: weakref.ReferenceType[OntologyBundle]) -> None:
        with _VERIFIED_BUNDLES_LOCK:
            if _VERIFIED_BUNDLES.get(identity) is reference:
                del _VERIFIED_BUNDLES[identity]

    reference = weakref.ref(bundle, discard)
    with _VERIFIED_BUNDLES_LOCK:
        _VERIFIED_BUNDLES[identity] = reference
    return bundle


def load_ontology(root: Path) -> OntologyBundle:  # noqa: PLR0914
    """Verify and decode a committed ontology artifact set.

    Every manifest, lock, source, and output file is read at most once.  The
    output bytes retained in the returned bundle are the same bytes hashed and
    decoded, avoiding a time-of-check/time-of-use second read.
    """

    ontology_root = root if isinstance(root, Path) else Path(root)
    manifest_path = ontology_root / "manifest.yaml"
    lock_path = ontology_root / "generated" / "artifact-lock.json"
    manifest, manifest_bytes = _read_mapping(manifest_path, yaml_format=True)
    lock, _lock_bytes = _read_mapping(lock_path, yaml_format=False)
    _validate_contract(manifest, lock)

    repository_root = ontology_root.parent.resolve()
    generated_root = ontology_root / "generated"
    sources = _lock_records(lock, "sources")
    outputs = _lock_records(lock, "outputs")

    # Verify source declarations and hashes before consuming any generated
    # projection.  The manifest itself is included in the source set.
    source_bytes: dict[str, bytes] = {}
    for record in sources:
        relative = _safe_relative(record["path"], "source")
        source_path = _contained_path(repository_root, relative, source_kind="source")
        source_bytes[relative] = (
            manifest_bytes if relative == "ontology/manifest.yaml" else _read_once(source_path, code=MISSING)
        )
        _check_hash(source_bytes[relative], record["sha256"], relative, source=True)

    expected_outputs = _manifest_outputs(manifest)
    locked_outputs = {record["path"] for record in outputs}
    if locked_outputs != expected_outputs:
        raise _error(
            UNSUPPORTED,
            "Artifact lock output set does not equal manifest artifact declaration",
        )

    artifact_bytes: dict[str, bytes] = {}
    decoded: dict[str, object] = {}
    for record in outputs:
        relative = _safe_relative(record["path"], "output")
        path = _contained_path(generated_root, relative, source_kind="output")
        content = _read_once(path, code=MISSING)
        _check_hash(content, record["sha256"], relative, source=False)
        artifact_bytes[relative] = content
        decoded[relative] = _decode_artifact(relative, content)
        _validate_declared_format(relative, decoded[relative])

    runtime = decoded.get("runtime-vocabulary.yaml")
    if not isinstance(runtime, dict):
        raise _error(UNSUPPORTED, "runtime-vocabulary.yaml is not a mapping")
    runtime_map = cast(dict[str, object], runtime)
    if runtime_map.get("format") != manifest.get("runtime_vocabulary_format", RUNTIME_VOCABULARY_FORMAT):
        raise _error(UNSUPPORTED, "Unsupported runtime vocabulary format")
    if runtime_map.get("schema_version") != str(manifest.get("schema_version")):
        raise _error(UNSUPPORTED, "Runtime vocabulary schema version does not match manifest")
    program = decoded.get("runtime-program.json")
    if not isinstance(program, dict):
        raise _error(UNSUPPORTED, "runtime-program.json is not a mapping")
    program_map = cast(dict[str, object], program)
    if program_map.get("schema_version") != str(manifest.get("schema_version")):
        raise _error(UNSUPPORTED, "Runtime program schema version does not match manifest")
    if program_map.get("source_hash") != runtime_map.get("source_hash"):
        raise _error(STALE, "Runtime program source hash does not match runtime vocabulary")
    provenance = program_map.get("provenance")
    if not isinstance(provenance, dict) or set(provenance) != {
        "source", "source_sha256", "manifest_schema_version", "compiler_sha256"
    }:
        raise _error(MALFORMED, "Runtime program provenance is not a mapping")
    policy_paths = [record["path"] for record in sources if record["path"].endswith("runtime-policy.yaml")]
    if len(policy_paths) != 1 or provenance.get("source") != policy_paths[0]:
        raise _error(STALE, "Runtime program provenance source does not match locked runtime policy")
    policy_bytes = source_bytes[policy_paths[0]]
    if provenance.get("source_sha256") != hashlib.sha256(policy_bytes).hexdigest():
        raise _error(STALE, "Runtime program provenance source hash does not match locked source")
    if provenance.get("manifest_schema_version") != str(manifest.get("schema_version")):
        raise _error(STALE, "Runtime program provenance schema version does not match manifest")
    compiler_path = repository_root / "scripts" / "ontology_compiler.py"
    compiler_bytes = _read_once(compiler_path, code=MISSING)
    if provenance.get("compiler_sha256") != hashlib.sha256(compiler_bytes).hexdigest():
        raise _error(STALE, "Runtime program compiler digest does not match the active compiler")
    digest = hashlib.sha256()
    for relative in _manifest_sources(manifest):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source_bytes[relative])
        digest.update(b"\0")
    if program_map.get("source_hash") != digest.hexdigest():
        raise _error(STALE, "Runtime program source-set hash does not match locked sources")
    frozen_artifacts = _FrozenDict(artifact_bytes)
    frozen_decoded = _FrozenDict({key: _freeze(value) for key, value in decoded.items()})
    return _register_verified_bundle(
        OntologyBundle(
            ontology_root,
            cast(Mapping[str, object], _freeze(manifest)),
            cast(Mapping[str, object], _freeze(lock)),
            frozen_artifacts,
            frozen_decoded,
        )
    )


def _is_verified_bundle(value: object) -> bool:
    if type(value) is not OntologyBundle:
        return False
    with _VERIFIED_BUNDLES_LOCK:
        reference = _VERIFIED_BUNDLES.get(id(value))
        return reference is not None and reference() is value


def load_runtime_vocabulary(ontology_root: Path) -> Mapping[str, object]:
    """Compatibility view delegated to :func:`load_ontology`."""

    return load_ontology(ontology_root).runtime_vocabulary


def load_runtime_program(ontology_root: Path) -> RuntimeProgram:
    """Load the typed runtime program from a hash-verified ontology bundle."""

    return load_ontology(ontology_root).runtime_program


def _read_mapping(path: Path, *, yaml_format: bool) -> tuple[dict[str, object], bytes]:
    if _has_symlink_component(path):
        raise _error(UNSAFE_PATH, f"Symlinked ontology path is not trusted: {path}", path)
    content = _read_bytes(path, code=MISSING)
    try:
        value = (
            cast(object, yaml.safe_load(content)) if yaml_format else cast(object, json.loads(content.decode("utf-8")))
        )
    except (UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError) as error:
        raise _error(MALFORMED, f"Malformed ontology contract: {path}: {error}", path) from error
    if not isinstance(value, dict):
        raise _error(MALFORMED, f"Ontology contract must be a mapping: {path}", path)
    return cast(dict[str, object], value), content


def _read_once(path: Path, *, code: str) -> bytes:
    if _has_symlink_component(path):
        raise _error(UNSAFE_PATH, f"Symlinked ontology path is not trusted: {path}", path)
    return _read_bytes(path, code=code)


def _read_bytes(path: Path, *, code: str) -> bytes:  # noqa: C901, PLR0912
    """Read one exact byte sequence through descriptor-relative no-follow opens.

    The pre-open lstat catches symlink components (including broken links), the
    descriptor walk prevents an intermediate parent from being followed, and
    the post-open inode check makes replacement between inspection and open a
    hard infrastructure failure.  The returned bytes are the only bytes used
    for hashing and decoding.
    """

    absolute = path.absolute()
    if _has_symlink_component(absolute):
        raise _error(UNSAFE_PATH, f"Symlinked ontology path is not trusted: {path}", path)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    close_on_exec = getattr(os, "O_CLOEXEC", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    current_fd: int | None = None
    leaf_fd: int | None = None
    try:
        current_fd = os.open(absolute.anchor or ".", os.O_RDONLY | directory | close_on_exec | nofollow)
        components = absolute.parts[1:] if absolute.is_absolute() else absolute.parts
        if not components:
            raise IsADirectoryError(str(path))
        for component in components[:-1]:
            next_fd = os.open(component, os.O_RDONLY | directory | close_on_exec | nofollow, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        leaf_fd = os.open(components[-1], os.O_RDONLY | close_on_exec | nofollow, dir_fd=current_fd)
        opened_stat = os.fstat(leaf_fd)
        path_stat = os.lstat(absolute)
        if (opened_stat.st_dev, opened_stat.st_ino) != (path_stat.st_dev, path_stat.st_ino):
            raise _error(UNSAFE_PATH, f"Ontology path changed while reading: {path}", path)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(leaf_fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    except OntologyInfrastructureError:
        raise
    except FileNotFoundError as error:
        raise _error(code, f"Missing ontology artifact: {path}", path) from error
    except (OSError, ValueError) as error:
        raise _error(code, f"Cannot read ontology artifact: {path}: {error}", path) from error
    finally:
        if leaf_fd is not None:
            os.close(leaf_fd)
        if current_fd is not None:
            os.close(current_fd)


def _validate_contract(manifest: Mapping[str, object], lock: Mapping[str, object]) -> None:
    if manifest.get("schema_version") is None:
        raise _error(MALFORMED, "Ontology manifest is missing schema_version")
    if str(manifest.get("schema_version")) != SCHEMA_VERSION:
        raise _error(UNSUPPORTED, "Unsupported ontology schema version")
    if lock.get("format_version") != ARTIFACT_LOCK_FORMAT:
        raise _error(UNSUPPORTED, "Unsupported ontology artifact lock format")
    if str(lock.get("schema_version")) != str(manifest.get("schema_version")):
        raise _error(UNSUPPORTED, "Artifact lock schema version does not match manifest")
    if not isinstance(manifest.get("artifacts"), list):
        raise _error(MALFORMED, "Ontology manifest artifacts must be a list")
    if not isinstance(lock.get("sources"), list) or not isinstance(lock.get("outputs"), list):
        raise _error(MALFORMED, "Artifact lock sources and outputs must be lists")

    manifest_sources = set(_manifest_sources(manifest))
    lock_sources = {record["path"] for record in _lock_records(lock, "sources")}
    if manifest_sources != lock_sources:
        raise _error(UNSUPPORTED, "Artifact lock source set does not equal manifest source declaration")


def _manifest_sources(manifest: Mapping[str, object]) -> tuple[str, ...]:  # noqa: C901
    declared: list[str] = ["ontology/manifest.yaml"]
    if "sources" in manifest:
        raise _error(MALFORMED, "Ontology manifest uses unsupported sources declaration")
    root = manifest.get("linkml_root")
    modules = manifest.get("linkml_modules")
    catalogs = manifest.get("catalogs")
    if not isinstance(root, str) or not root:
        raise _error(MALFORMED, "Ontology manifest linkml_root must be a non-empty string")
    if not isinstance(modules, list) or not modules or not all(isinstance(item, str) and item for item in modules):
        raise _error(MALFORMED, "Ontology manifest linkml_modules must be a non-empty string list")
    if not isinstance(catalogs, list) or not catalogs:
        raise _error(MALFORMED, "Ontology manifest catalogs must be a non-empty list")
    declared.append(root)
    declared.extend(cast(list[str], modules))
    for item in catalogs:
        if not isinstance(item, dict):
            raise _error(MALFORMED, "Ontology manifest catalog entries must be mappings")
        catalog = cast(dict[str, object], item)
        if set(catalog) != {"id", "role", "path", "root_class"}:
            raise _error(MALFORMED, "Ontology manifest catalog entries have an invalid structure")
        if not all(isinstance(catalog.get(key), str) and catalog[key] for key in ("id", "role", "path", "root_class")):
            raise _error(MALFORMED, "Ontology manifest catalog fields must be non-empty strings")
        declared.append(cast(str, catalog["path"]))
    for path in declared[1:]:
        _safe_relative(path, "manifest source")
    if len(declared) != len(set(declared)):
        raise _error(MALFORMED, "Ontology manifest source declaration contains duplicate paths")
    return tuple(declared)


def _manifest_outputs(manifest: Mapping[str, object]) -> set[str]:
    values = manifest.get("artifacts")
    if not isinstance(values, list) or not values or not all(isinstance(item, str) and item for item in values):
        raise _error(MALFORMED, "Ontology manifest artifacts must be a non-empty string list")
    artifact_values = cast(list[str], values)
    if len(artifact_values) != len(set(artifact_values)):
        raise _error(MALFORMED, "Ontology manifest artifacts contain duplicate paths")
    if set(artifact_values) != _REQUIRED_MANIFEST_ARTIFACTS:
        raise _error(UNSUPPORTED, "Ontology manifest does not declare the complete artifact protocol inventory")
    output_paths = {item for item in artifact_values if item != "artifact-lock.json"}
    for item in output_paths:
        _safe_relative(item, "manifest artifact")
    return output_paths


def _lock_records(lock: Mapping[str, object], key: str) -> list[dict[str, str]]:
    raw = cast(object, lock.get(key))
    if not isinstance(raw, list) or not raw:
        raise _error(MALFORMED, f"Artifact lock {key} must be a non-empty list")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for value in cast(list[object], raw):
        if not isinstance(value, dict):
            raise _error(MALFORMED, f"Artifact lock {key} records require path and sha256")
        record = cast(dict[str, object], value)
        if not isinstance(record.get("path"), str) or not isinstance(record.get("sha256"), str):
            raise _error(MALFORMED, f"Artifact lock {key} records require path and sha256")
        path = cast(str, record["path"])
        _safe_relative(path, key)
        if path in seen:
            raise _error(MALFORMED, f"Artifact lock {key} contains duplicate path {path!r}")
        digest = cast(str, record["sha256"])
        if len(digest) != _SHA256_HEX_LENGTH or any(character not in "0123456789abcdef" for character in digest):
            raise _error(MALFORMED, f"Artifact lock {key} has invalid sha256 for {path!r}")
        seen.add(path)
        records.append({"path": path, "sha256": digest})
    return records


def _safe_relative(value: str, kind: str) -> str:
    if not value or "\\" in value:
        raise _error(UNSAFE_PATH, f"Unsafe {kind} path {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise _error(UNSAFE_PATH, f"Unsafe {kind} path {value!r}")
    normalized = path.as_posix()
    if normalized != value:
        raise _error(UNSAFE_PATH, f"Non-canonical {kind} path {value!r}")
    return normalized


def _contained_path(base: Path, relative: str, *, source_kind: str) -> Path:
    candidate = base / relative
    try:
        candidate.resolve().relative_to(base.resolve())
    except ValueError as error:
        raise _error(
            UNSAFE_PATH, f"{source_kind.title()} path escapes ontology root: {relative!r}", candidate
        ) from error
    if _has_symlink_component(candidate):
        raise _error(UNSAFE_PATH, f"Symlinked {source_kind} path is not trusted: {candidate}", candidate)
    return candidate


def _has_symlink_component(path: Path) -> bool:
    absolute = path.absolute()
    current = Path(absolute.anchor) if absolute.anchor else Path()
    components = absolute.parts[1:] if absolute.is_absolute() else absolute.parts
    for component in components:
        current /= component
        try:
            if current.is_symlink():
                return True
            current.stat()
        except FileNotFoundError:
            # A missing component cannot conceal a later existing symlink in a
            # path supplied by the caller; the eventual open fails closed.
            return False
    return False


def _check_hash(content: bytes, expected: str, relative: str, *, source: bool) -> None:
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected:
        subject = "source" if source else "artifact"
        raise _error(STALE, f"Stale ontology {subject} hash for {relative!r}: expected {expected}, got {actual}")


def _decode_artifact(relative: str, content: bytes) -> object:
    suffix = Path(relative).suffix.lower()
    try:
        if suffix == ".json":
            return cast(object, json.loads(content.decode("utf-8")))
        if suffix == ".yaml" or suffix == ".yml":
            return cast(object, yaml.safe_load(content))
        if suffix == ".ttl":
            # C3 intentionally does not parse RDF; UTF-8 decoding still proves
            # the artifact is a loadable text payload.
            return content.decode("utf-8")
    except (UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError) as error:
        raise _error(MALFORMED, f"Malformed ontology artifact {relative!r}: {error}") from error
    raise _error(UNSUPPORTED, f"Unsupported ontology artifact format: {relative!r}")


def _validate_declared_format(relative: str, decoded: object) -> None:
    if relative in {"card.schema.json", "schema.json"}:
        decoded_map = cast(dict[object, object], decoded) if isinstance(decoded, dict) else None
        if decoded_map is None or decoded_map.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise _error(UNSUPPORTED, f"Unsupported JSON Schema declaration in {relative!r}")
        return
    if relative == "context.json":
        decoded_map = cast(dict[object, object], decoded) if isinstance(decoded, dict) else None
        if decoded_map is None or not isinstance(decoded_map.get("@context"), dict):
            raise _error(UNSUPPORTED, "Unsupported JSON-LD context declaration")
        return
    expected: dict[str, tuple[str, str]] = {
        "projection-map.json": ("format_version", "ontology-projection-map-v1"),
        "runtime-program.json": ("format_version", "ontology-runtime-program-v1"),
        "runtime-vocabulary.yaml": ("format", RUNTIME_VOCABULARY_FORMAT),
    }
    declaration = expected.get(relative)
    if declaration is not None:
        if not isinstance(decoded, dict):
            raise _error(UNSUPPORTED, f"Unsupported content contract for {relative!r}")
        field, value = declaration
        decoded_map = cast(dict[str, object], decoded)
        if decoded_map.get(field) != value:
            raise _error(UNSUPPORTED, f"Unsupported {field} in {relative!r}")
        return
    if relative in {"ontology.ttl", "shapes.ttl"} and (not isinstance(decoded, str) or not decoded.strip()):
        raise _error(UNSUPPORTED, f"Unsupported Turtle declaration in {relative!r}")


def _error(code: str, message: str, path: object | None = None) -> OntologyInfrastructureError:
    return OntologyInfrastructureError(message, code=code, path=path)
