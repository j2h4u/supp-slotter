"""Deterministic build of the committed executable ontology artifacts.

This module is generation-only: it imports LinkML to prove and inspect the
authored schema, while normal planner runtime paths only read the resulting
runtime-vocabulary YAML and RDF/SHACL artifacts.
"""

# ruff: noqa: C901, PLR0912

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Protocol, cast, runtime_checkable
from urllib.parse import urlparse

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from linkml.generators.jsonschemagen import JsonSchemaGenerator
from linkml.generators.shaclgen import ShaclGenerator
from linkml_runtime.linkml_model.meta import Prefix, SchemaDefinition
from linkml_runtime.utils.schemaview import SchemaView
from planner.ontology.errors import OntologyInfrastructureError
from rdflib import BNode, Graph
from rdflib.namespace import RDF, SH
from rdflib.term import Node

_BASE_IRI_KEY = "base_iri"
_MANIFEST_NAME = "manifest.yaml"
_GENERATED_DIR = "generated"
_RUNTIME_FORMAT = "supp-slotter.runtime-vocabulary/v2"
_JSON_SCHEMA_FORMAT = "https://json-schema.org/draft/2020-12/schema"
_ARTIFACT_LOCK_FORMAT = "ontology-artifact-lock-v1"
_PROJECTION_MAP_FORMAT = "ontology-projection-map-v1"
_RUNTIME_PROGRAM_FORMAT = "ontology-runtime-program-v1"
_REPOSITORY_PROJECTION_FORMAT = "repository-projection-v1"
_RDF_TRIPLE_SIZE = 3
_EXPECTED_ARTIFACTS = {
    "card.schema.json",
    "schema.json",
    "ontology.ttl",
    "shapes.ttl",
    "context.json",
    "projection-map.json",
    "runtime-program.json",
    "runtime-vocabulary.yaml",
    "artifact-lock.json",
}
_REPOSITORY_LOCATOR_KINDS = {"flat_root", "explicit_path", "explicit_paths", "catalog_ref"}

# Neutral, declarative condition vocabulary.  The compiler validates shape and
# operand compatibility only; it never evaluates a condition or encodes domain
# semantics in executable callbacks.
_CONDITION_PATH_TYPES: Mapping[str, str] = {
    "planner": "string",
    "food_model": "string",
    "slot_model": "string",
    "intended_use": "string",
    "substrate": "string",
    "product": "string",
    "formulation": "string",
    "requested_value": "string",
    "supported_value": "string",
    "supported_values": "strings",
    "source_kind": "string",
    "source_form": "string",
    "scope_kind": "string",
    "requested_product_id": "string",
    "actual_product_id": "string",
    "left_authority": "string",
    "right_authority": "string",
    "left_source_kind": "string",
    "right_source_kind": "string",
    "left_axis": "string",
    "right_axis": "string",
    "left_policy_id": "string",
    "right_policy_id": "string",
    "left_action": "string",
    "right_action": "string",
    "left_executable": "boolean",
    "right_executable": "boolean",
    "left_eligible": "boolean",
    "right_eligible": "boolean",
    "any_explicit_primary": "boolean",
    "component_primary": "string",
}
_CONDITION_OPERATORS = frozenset({"equals", "contains", "equals_field", "member_of_field", "is_true", "is_false", "all", "any", "not"})

type _RdfTriple = tuple[Node, Node, Node]
type _JsonValue = str | int | float | bool | None | list[_JsonValue] | dict[str, _JsonValue]
type _JsonObject = dict[str, _JsonValue]


@runtime_checkable
class _LinkMLSerializer(Protocol):
    def serialize(self, **kwargs: object) -> object: ...


class _JsonSchemaValidator(Protocol):
    def iter_errors(self, instance: object) -> Iterable[ValidationError]: ...


def compile_ontology(ontology_root: Path) -> dict[Path, bytes]:
    """Pure deterministic compilation of the manifest's declared ontology."""
    manifest = _load_manifest(ontology_root)
    _validate_linkml_root(ontology_root, manifest)
    artifacts = _render_artifacts(ontology_root, manifest)
    declared = _validate_artifact_manifest(manifest)
    rendered = _normalized_artifact_keys(artifacts)
    if declared != rendered:
        raise OntologyInfrastructureError(
            f"Manifest artifact declaration mismatch: {sorted(declared)} != {sorted(artifacts)}"
        )
    return artifacts


def write_artifacts(ontology_root: Path, artifacts: Mapping[Path, bytes]) -> None:
    """Atomically replace the generated artifact set."""
    generated_dir = ontology_root / _GENERATED_DIR
    generated_dir.parent.mkdir(parents=True, exist_ok=True)
    _validate_artifact_keys(artifacts)
    temp = Path(tempfile.mkdtemp(prefix=".generated-", dir=str(generated_dir.parent)))
    backup = generated_dir.parent / f".generated-backup-{os.getpid()}-{temp.name}"
    try:
        for relative_path, content in artifacts.items():
            target = temp / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        if generated_dir.is_symlink():
            raise OntologyInfrastructureError(f"Generated artifact directory must not be a symlink: {generated_dir}")
        if generated_dir.exists():
            os.replace(generated_dir, backup)  # noqa: PTH105
        try:
            os.replace(temp, generated_dir)  # noqa: PTH105
        except Exception:
            if generated_dir.exists():
                shutil.rmtree(generated_dir, ignore_errors=True)
            if backup.exists():
                os.replace(backup, generated_dir)  # noqa: PTH105
            raise
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        if backup.exists() and not generated_dir.exists():
            os.replace(backup, generated_dir)  # noqa: PTH105
        raise


def _validate_artifact_keys(artifacts: Mapping[Path, bytes]) -> None:
    _normalized_artifact_keys(artifacts)


def _normalized_artifact_keys(artifacts: Mapping[Path, bytes]) -> set[Path]:
    normalized: set[Path] = set()
    for key in artifacts:
        if not isinstance(key, (str, Path)):
            raise OntologyInfrastructureError(f"Artifact key must be a path: {key!r}")
        raw = str(key)
        path = _normalized_relative_path(raw, "artifact")
        if path in normalized:
            raise OntologyInfrastructureError(f"Duplicate artifact path: {raw}")
        normalized.add(path)
    return normalized


def _normalized_relative_path(raw: str, kind: str) -> Path:
    path = Path(raw)
    if (
        not raw  # noqa: PLR0916
        or path.is_absolute()
        or raw != path.as_posix()
        or "\\" in raw
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(ch in raw for ch in "*?[]")
        or _GENERATED_DIR in path.parts
    ):
        raise OntologyInfrastructureError(f"Unsafe {kind} path: {raw}")
    return path


def check_artifacts(ontology_root: Path, artifacts: Mapping[Path, bytes]) -> None:
    generated_dir = ontology_root / _GENERATED_DIR
    expected = _normalized_artifact_keys(artifacts)
    if generated_dir.is_symlink():
        raise OntologyInfrastructureError(f"Generated artifact directory must not be a symlink: {generated_dir}")
    actual: set[Path] = set()
    expected_dirs = {parent for path in expected for parent in path.parents if parent != Path()}
    if generated_dir.exists():
        for path in generated_dir.rglob("*"):
            relative = path.relative_to(generated_dir)
            if path.is_symlink():
                raise OntologyInfrastructureError(f"Generated artifact must not be a symlink: {path}")
            if path.is_dir():
                if relative not in expected_dirs:
                    raise OntologyInfrastructureError(f"Unexpected generated artifact directory: {path}")
            elif path.is_file():
                actual.add(relative)
    if actual != expected:
        raise OntologyInfrastructureError(
            f"Generated artifact set mismatch: expected {sorted(expected)}, got {sorted(actual)}"
        )
    _check_fresh(generated_dir, artifacts)


def generate_ontology(ontology_root: Path, *, check: bool = False) -> None:
    """Generate or freshness-check all artifacts declared by the manifest."""
    artifact_bytes = compile_ontology(ontology_root)
    if check:
        check_artifacts(ontology_root, artifact_bytes)
        return
    write_artifacts(ontology_root, artifact_bytes)


def _load_manifest(ontology_root: Path) -> dict[str, object]:
    manifest_path = ontology_root / _MANIFEST_NAME
    if not manifest_path.is_file():
        raise OntologyInfrastructureError(f"Missing canonical ontology manifest: {manifest_path}")
    try:
        loaded = _safe_yaml_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise OntologyInfrastructureError(f"Invalid ontology manifest {manifest_path}: {error}") from error
    if not isinstance(loaded, dict):
        raise OntologyInfrastructureError(f"Ontology manifest must be a mapping: {manifest_path}")
    required = {
        "schema_version",
        _BASE_IRI_KEY,
        "linkml_root",
        "linkml_modules",
        "catalogs",
        "compiler",
    }
    missing = sorted(required - loaded.keys())
    if missing:
        raise OntologyInfrastructureError(f"Ontology manifest is missing required keys: {', '.join(missing)}")
    if loaded[_BASE_IRI_KEY] != "https://j2h4u.github.io/supp-slotter/ontology/v1/":
        raise OntologyInfrastructureError("Ontology manifest has a non-canonical ss base IRI")
    _validate_manifest_paths(ontology_root, cast(Mapping[str, object], loaded))
    return cast(dict[str, object], loaded)


def _validate_manifest_paths(ontology_root: Path, manifest: Mapping[str, object]) -> None:
    """Fail closed on unsafe or undeclared source paths."""
    repository_root = ontology_root.parent.resolve()
    seen_logical: set[str] = set()
    seen_resolved: set[Path] = set()
    root_value = _required_string(manifest, "linkml_root")
    _record_manifest_source(
        root_value, _resolve_manifest_source(ontology_root, root_value, repository_root), seen_logical, seen_resolved
    )
    for value in _required_string_list(manifest, "linkml_modules"):
        _record_manifest_source(
            value, _resolve_manifest_source(ontology_root, value, repository_root), seen_logical, seen_resolved
        )
    catalogs = manifest.get("catalogs", [])
    if not isinstance(catalogs, list):
        raise OntologyInfrastructureError("Manifest catalogs must be a list")
    ids: set[str] = set()
    roles: set[str] = set()
    for catalog in catalogs:
        if not isinstance(catalog, dict):
            raise OntologyInfrastructureError("Manifest catalogs require stable id, path, and root_class")
        catalog_mapping = cast(dict[str, object], catalog)
        if not all(isinstance(catalog_mapping.get(k), str) for k in ("id", "role", "path", "root_class")):
            raise OntologyInfrastructureError("Manifest catalogs require stable id, path, and root_class")
        value = cast(str, catalog_mapping["path"])
        if catalog_mapping["id"] in ids or catalog_mapping["role"] in roles:
            raise OntologyInfrastructureError(f"Unsafe or missing catalog path {value!r}")
        _record_manifest_source(
            value, _resolve_manifest_source(ontology_root, value, repository_root), seen_logical, seen_resolved
        )
        ids.add(cast(str, catalog_mapping["id"]))
        roles.add(cast(str, catalog_mapping["role"]))
    _validate_repository_projection(ontology_root, manifest, cast(list[dict[str, object]], catalogs))
    _validate_artifact_manifest(manifest)


def _validate_repository_projection(  # noqa: PLR0914, PLR0915
    ontology_root: Path,
    manifest: Mapping[str, object],
    catalogs: object,
) -> list[dict[str, object]]:
    """Validate the closed repository projection boundary.

    Repository cards are intentionally not compiler catalogs.  The compiler may
    inspect their shape to prove that a generic projection covers every field,
    but their content never becomes an artifact-lock source or digest input.
    """
    projection = manifest.get("repository_projection")
    if not isinstance(projection, dict):
        raise OntologyInfrastructureError("Manifest repository_projection must be a mapping")
    projection_mapping = cast(Mapping[str, object], projection)
    if set(projection_mapping) != {"format_version", "base_iri", "sources", "mappings"}:
        raise OntologyInfrastructureError(
            "repository_projection requires exactly base_iri, format_version, sources, and mappings"
        )
    if projection_mapping.get("format_version") != _REPOSITORY_PROJECTION_FORMAT:
        raise OntologyInfrastructureError("Manifest repository_projection has an unsupported format_version")
    projection_base = projection_mapping.get(_BASE_IRI_KEY)
    if (
        projection_base != manifest.get(_BASE_IRI_KEY)
        or not isinstance(projection_base, str)
        or not projection_base.endswith("/")
    ):
        raise OntologyInfrastructureError("Manifest repository_projection has an invalid base_iri")
    raw_sources = projection_mapping.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise OntologyInfrastructureError("repository_projection.sources must be a non-empty list")
    mappings = _validate_repository_mappings(projection_mapping.get("mappings"))
    try:
        schema_classes = set(
            SchemaView(str(_source_path(ontology_root, _required_string(manifest, "linkml_root")))).all_classes()
        )
    except Exception as error:
        raise OntologyInfrastructureError(
            f"Cannot inspect LinkML classes for repository projection: {error}"
        ) from error
    catalog_records = cast(list[dict[str, object]], catalogs)
    catalog_by_id = {str(item["id"]): item for item in catalog_records}
    source_ids: set[str] = set()
    logical: set[str] = set()
    resolved_paths: set[Path] = set()
    normalized_sources: list[dict[str, object]] = []
    repository_root = ontology_root.parent.resolve()
    catalog_source_paths = {
        str(item["path"]): _resolve_manifest_source(ontology_root, str(item["path"]), repository_root)
        for item in catalog_records
    }
    for raw_source in cast(list[object], raw_sources):
        if not isinstance(raw_source, dict):
            raise OntologyInfrastructureError("repository_projection sources must be mappings")
        source = cast(Mapping[str, object], raw_source)
        source_id = source.get("id")
        locator = source.get("locator")
        if not isinstance(source_id, str) or not source_id or source_id in source_ids:
            raise OntologyInfrastructureError(f"Repository projection source id is not unique: {source_id!r}")
        if not isinstance(locator, dict):
            raise OntologyInfrastructureError(f"Repository projection source {source_id!r} requires a locator")
        locator_mapping = cast(Mapping[str, object], locator)
        kind = locator_mapping.get("kind")
        if kind not in _REPOSITORY_LOCATOR_KINDS:
            raise OntologyInfrastructureError(f"Repository projection source {source_id!r} has unknown locator")
        allowed_source_keys = {"id", "locator", "root_class"}
        if kind == "catalog_ref":
            allowed_source_keys = {"id", "locator", "root_class"}
        if set(source) - allowed_source_keys or set(locator_mapping) - _locator_keys(cast(str, kind)):
            raise OntologyInfrastructureError(f"Repository projection source {source_id!r} has unsupported fields")
        root_class = source.get("root_class")
        mapping = mappings.get(source_id)
        if mapping is None:
            raise OntologyInfrastructureError(f"Repository projection source {source_id!r} has no mapping")
        mapping_root = mapping.get("root_class")
        if not isinstance(mapping_root, str) or (root_class is not None and root_class != mapping_root):
            raise OntologyInfrastructureError(
                f"Repository projection source {source_id!r} root_class disagrees with mapping"
            )
        if kind != "catalog_ref" and mapping_root not in schema_classes:
            raise OntologyInfrastructureError(f"Repository projection source {source_id!r} has unknown root_class")
        if kind == "catalog_ref":
            catalog_id = locator_mapping.get("catalog_id")
            if not isinstance(catalog_id, str) or catalog_id not in catalog_by_id:
                raise OntologyInfrastructureError(
                    f"Repository projection source {source_id!r} references unknown catalog"
                )
            catalog_root_class = catalog_by_id[catalog_id].get("root_class")
            if mapping_root != catalog_root_class:
                raise OntologyInfrastructureError(
                    f"Repository projection source {source_id!r} mapping root_class disagrees with catalog"
                )
            catalog_role = next((item.get("role") for item in catalog_records if item.get("id") == catalog_id), None)
            mapping_role = mapping.get("catalog_role")
            if mapping_role is not None and mapping_role != catalog_role:
                raise OntologyInfrastructureError(
                    f"Repository projection source {source_id!r} catalog role disagrees with mapping"
                )
            source_record: dict[str, object] = {
                "id": source_id,
                "locator": {"kind": kind, "catalog_id": catalog_id},
            }
            if root_class is not None:
                source_record["root_class"] = root_class
            normalized_sources.append(source_record)
            source_ids.add(source_id)
            continue
        if not isinstance(root_class, str):
            raise OntologyInfrastructureError(f"Repository projection source {source_id!r} requires root_class")
        paths = _repository_locator_paths(locator_mapping, kind)
        if kind == "flat_root":
            root_raw = paths[0]
            root = _safe_repository_path(repository_root, root_raw, directory=True)
            if root.is_symlink():
                raise OntologyInfrastructureError(f"Repository projection root must not be a symlink: {root_raw}")
            children = sorted(root.iterdir(), key=lambda item: item.name)
            for child in children:
                if child.is_symlink() or not child.is_file() or child.suffix != ".yaml":
                    raise OntologyInfrastructureError(f"Unexpected flat_root entry: {child}")
            if not children:
                raise OntologyInfrastructureError(f"Repository projection flat_root is empty: {root_raw}")
            discovered = [child.relative_to(repository_root).as_posix() for child in children]
        else:
            discovered: list[str] = []
            for relative in paths:
                path = _safe_repository_path(repository_root, relative, directory=False)
                if path.is_symlink() or not path.is_file() or path.suffix != ".yaml":
                    raise OntologyInfrastructureError(
                        f"Repository projection source must be a regular YAML file: {relative}"
                    )
                discovered.append(relative)
        for relative in discovered:
            resolved = _safe_repository_path(repository_root, relative, directory=False).resolve()
            if (
                relative in logical
                or resolved in resolved_paths
                or relative in catalog_source_paths
                or resolved in set(catalog_source_paths.values())
            ):
                raise OntologyInfrastructureError(f"Duplicate repository projection source: {relative}")
            logical.add(relative)
            resolved_paths.add(resolved)
        source_record = {"id": source_id, "locator": {"kind": kind}}
        rendered_locator = cast(dict[str, object], source_record["locator"])
        if kind in {"flat_root", "explicit_path"}:
            rendered_locator["path"] = paths[0]
        else:
            rendered_locator["paths"] = paths
        source_record["root_class"] = root_class
        normalized_sources.append(source_record)
        source_ids.add(source_id)
    # A legacy schedule.yaml is deliberately not an undeclared projection input.
    schedule = repository_root / "data" / "schedule.yaml"
    if schedule.exists() or schedule.is_symlink():
        raise OntologyInfrastructureError(f"Undeclared repository source: {schedule}")
    if set(mappings) != source_ids:
        raise OntologyInfrastructureError("Repository projection mappings must match source ids exactly")
    return normalized_sources


def _locator_keys(kind: str) -> set[str]:
    if kind == "catalog_ref":
        return {"kind", "catalog_id"}
    if kind == "explicit_path":
        return {"kind", "path"}
    if kind == "explicit_paths":
        return {"kind", "paths"}
    return {"kind", "path"}


def _validate_repository_mappings(raw: object) -> dict[str, dict[str, object]]:  # noqa: PLR0914, PLR0915
    if not isinstance(raw, list) or not raw:
        raise OntologyInfrastructureError("repository_projection.mappings must be a non-empty list")
    allowed_kinds = {"slot", "alias", "keyed-map", "sequence", "reference", "opaque-value"}
    result: dict[str, dict[str, object]] = {}
    for raw_mapping in cast(list[object], raw):
        if not isinstance(raw_mapping, dict):
            raise OntologyInfrastructureError("repository projection mappings must be mappings")
        mapping = cast(dict[str, object], raw_mapping)
        source_id = mapping.get("source")
        root_class = mapping.get("root_class")
        shape = mapping.get("document_shape")
        instructions = mapping.get("instructions")
        invalid_identity = not isinstance(source_id, str) or not source_id or source_id in result
        invalid_shape = (
            not isinstance(root_class, str) or not root_class or shape not in {"mapping", "keyed-map", "sequence"}
        )
        invalid_instructions = not isinstance(instructions, list) or not instructions
        if invalid_identity or invalid_shape or invalid_instructions:
            raise OntologyInfrastructureError(
                "Repository mapping requires unique source, root_class, shape, and instructions"
            )
        if set(mapping) - {"source", "root_class", "document_shape", "identity", "catalog_role", "instructions"}:
            raise OntologyInfrastructureError(f"Repository mapping {source_id!r} has unsupported fields")
        identity = mapping.get("identity")
        if identity is not None:
            if not isinstance(identity, dict):
                raise OntologyInfrastructureError(f"Repository mapping {source_id!r} identity is invalid")
            identity_mapping = cast(dict[str, object], identity)
            if set(identity_mapping) != {"source", "predicate"}:
                raise OntologyInfrastructureError(f"Repository mapping {source_id!r} identity is invalid")
            if not isinstance(identity_mapping.get("source"), str) or not isinstance(
                identity_mapping.get("predicate"), str
            ):
                raise OntologyInfrastructureError(f"Repository mapping {source_id!r} identity is invalid")
        catalog_role = mapping.get("catalog_role")
        if catalog_role is not None and (not isinstance(catalog_role, str) or not catalog_role):
            raise OntologyInfrastructureError(f"Repository mapping {source_id!r} catalog_role is invalid")
        seen_paths: set[str] = set()
        normalized_instructions: list[dict[str, object]] = []
        for raw_instruction in cast(list[object], instructions):
            if not isinstance(raw_instruction, dict):
                raise OntologyInfrastructureError(f"Repository mapping {source_id!r} instruction is invalid")
            instruction = cast(dict[str, object], raw_instruction)
            kind = instruction.get("kind")
            path = instruction.get("source")
            predicate = instruction.get("predicate")
            if (
                kind not in allowed_kinds
                or not isinstance(path, str)
                or not path
                or not isinstance(predicate, str)
                or not predicate.startswith("https://")
            ):
                raise OntologyInfrastructureError(f"Repository mapping {source_id!r} instruction is invalid")
            if (
                path.startswith("/")
                or "\\" in path
                or ".." in path
                or any(ch in path for ch in "*?")
                or any(not segment for segment in path.split("."))
            ):
                raise OntologyInfrastructureError(f"Repository mapping {source_id!r} instruction path is unsafe")
            if path in seen_paths:
                raise OntologyInfrastructureError(f"Repository mapping {source_id!r} duplicates path {path!r}")
            allowed_instruction_keys = {"kind", "source", "predicate", "target"}
            if set(instruction) - allowed_instruction_keys:
                raise OntologyInfrastructureError(
                    f"Repository mapping {source_id!r} instruction has unsupported fields"
                )
            if "target" in instruction and (
                not isinstance(instruction.get("target"), str) or not instruction["target"]
            ):
                raise OntologyInfrastructureError(f"Repository mapping {source_id!r} reference target is invalid")
            seen_paths.add(path)
            normalized_instructions.append(dict(instruction))
        _reject_ambiguous_mapping_patterns(
            cast(str, source_id), [str(item["source"]) for item in normalized_instructions]
        )
        normalized = dict(mapping)
        normalized["instructions"] = sorted(normalized_instructions, key=lambda item: str(item["source"]))
        result[cast(str, source_id)] = normalized
    return result


def _repository_locator_paths(locator: Mapping[str, object], kind: object) -> list[str]:
    if kind == "explicit_path" or kind == "flat_root":
        value = locator.get("path")
        if not isinstance(value, str):
            raise OntologyInfrastructureError("Repository locator path must be a string")
        return [_validate_repository_locator_string(value)]
    if kind == "explicit_paths":
        values = locator.get("paths")
        if not isinstance(values, list) or not values or not all(isinstance(item, str) for item in values):
            raise OntologyInfrastructureError("Repository explicit_paths locator requires a non-empty string list")
        normalized = [_validate_repository_locator_string(cast(str, item)) for item in values]
        if normalized != sorted(set(normalized)):
            raise OntologyInfrastructureError("Repository explicit_paths must be sorted and unique")
        return normalized
    return []


def _validate_repository_locator_string(value: str) -> str:
    path = Path(value)
    unsafe = (
        not value,
        path.is_absolute(),
        value != path.as_posix(),
        "\\" in value,
        not path.parts,
        any(part in {"", ".", ".."} for part in path.parts),
        any(ch in value for ch in "*?[]"),
        _GENERATED_DIR in path.parts,
        value.endswith("schedule.yaml"),
    )
    if any(unsafe):
        raise OntologyInfrastructureError(f"Unsafe repository locator path {value!r}")
    return value


def _safe_repository_path(repository_root: Path, relative: str, *, directory: bool) -> Path:
    path = repository_root / relative
    try:
        resolved = path.resolve()
    except OSError as error:
        raise OntologyInfrastructureError(f"Cannot resolve repository locator {relative!r}: {error}") from error
    if repository_root not in resolved.parents and resolved != repository_root:
        raise OntologyInfrastructureError(f"Repository locator escapes repository: {relative}")
    current = repository_root
    for part in Path(relative).parts:
        current /= part
        if current.is_symlink():
            raise OntologyInfrastructureError(f"Repository locator may not traverse symlinks: {relative}")
    if directory and not path.is_dir():
        raise OntologyInfrastructureError(f"Repository locator directory is missing: {relative}")
    if not directory and not path.is_file():
        raise OntologyInfrastructureError(f"Repository locator file is missing: {relative}")
    return path


def _resolve_manifest_source(ontology_root: Path, value: str, repository_root: Path) -> Path:
    path = Path(value)
    if (
        not value  # noqa: PLR0916
        or path.is_absolute()
        or value != path.as_posix()
        or "\\" in value
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(ch in value for ch in "*?[]")
        or _GENERATED_DIR in path.parts
    ):
        raise OntologyInfrastructureError(f"Unsafe manifest path {value!r}")
    candidate = repository_root / path
    try:
        resolved = candidate.resolve()
    except OSError as error:
        raise OntologyInfrastructureError(f"Cannot resolve manifest path {value!r}: {error}") from error
    if repository_root not in resolved.parents and resolved != repository_root:
        raise OntologyInfrastructureError(f"Manifest path escapes repository: {value}")
    current = repository_root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise OntologyInfrastructureError(f"Manifest path may not traverse symlinks: {value}")
    if not candidate.is_file():
        raise OntologyInfrastructureError(f"Manifest declares missing ontology source: {candidate}")
    return resolved


def _record_manifest_source(value: str, resolved: Path, logical: set[str], resolved_paths: set[Path]) -> None:
    if value in logical:
        raise OntologyInfrastructureError(f"Duplicate manifest path: {value!r}")
    if resolved in resolved_paths:
        raise OntologyInfrastructureError(f"Manifest paths resolve to the same source: {value!r}")
    logical.add(value)
    resolved_paths.add(resolved)


def _validate_artifact_manifest(manifest: Mapping[str, object]) -> set[Path]:
    artifacts = manifest.get("artifacts")
    if (
        not isinstance(artifacts, list)
        or not artifacts
        or not all(isinstance(item, str) and item for item in artifacts)
    ):
        raise OntologyInfrastructureError("Manifest artifacts must be a non-empty string list")
    normalized: set[Path] = set()
    for raw in cast(list[str], artifacts):
        path = _normalized_relative_path(raw, "artifact")
        if path in normalized:
            raise OntologyInfrastructureError("Manifest artifacts contain duplicate paths")
        normalized.add(path)
    expected = {Path(item) for item in _EXPECTED_ARTIFACTS}
    if normalized != expected:
        raise OntologyInfrastructureError(
            f"Manifest artifacts must declare the exact compiler inventory: {sorted(expected)}"
        )
    return normalized


def _validate_linkml_root(ontology_root: Path, manifest: Mapping[str, object]) -> None:
    root = _source_path(ontology_root, _required_string(manifest, "linkml_root"))
    if not root.is_file():
        raise OntologyInfrastructureError(f"Missing LinkML root declared by manifest: {root}")
    try:
        schema_view = SchemaView(str(root))
        schema = schema_view.schema
    except Exception as error:  # LinkML owns parser/compiler failure details.
        raise OntologyInfrastructureError(f"LinkML cannot load canonical root {root}: {error}") from error
    base_iri = _required_string(manifest, _BASE_IRI_KEY)
    schema_id = schema.id if schema is not None else None
    if schema_id != base_iri:
        raise OntologyInfrastructureError(
            f"LinkML root id must equal canonical ss base IRI ({base_iri}), got {schema_id}"
        )


def _source_path(ontology_root: Path, relative_path: str) -> Path:
    """Resolve a manifest repository-relative source path."""
    return ontology_root.parent / relative_path


def _catalog_path(ontology_root: Path, manifest: Mapping[str, object], role: str) -> Path:
    for item in cast(list[dict[str, object]], manifest["catalogs"]):
        if item.get("role") == role:
            return _source_path(ontology_root, cast(str, item["path"]))
    raise OntologyInfrastructureError(f"Manifest has no catalog role {role!r}")


def _catalog_paths(ontology_root: Path, manifest: Mapping[str, object], role: str) -> list[str]:
    return [_catalog_path(ontology_root, manifest, role).relative_to(ontology_root.parent).as_posix()]


def _render_artifacts(ontology_root: Path, manifest: Mapping[str, object]) -> dict[Path, bytes]:  # noqa: PLR0914
    source_hash = _source_hash(ontology_root, manifest)
    schema_view = _schema_view(ontology_root, manifest)
    vocabulary = _load_yaml_mapping(_catalog_path(ontology_root, manifest, "vocabulary"))
    terms = _normalized_terms(vocabulary)
    categories = _required_mapping(vocabulary, "semantic_categories")
    runtime = _load_runtime_policy(ontology_root, manifest, schema_view)
    scheduling_policies = _load_scheduling_policies(ontology_root, manifest, terms, categories, runtime)
    audit_review_rules = _load_audit_review_rules(ontology_root, manifest, runtime)
    evidence_catalog = _load_evidence_catalog(_catalog_path(ontology_root, manifest, "policies"))
    audit_relation_exemptions = _load_audit_relation_exemptions(ontology_root, manifest)
    scheduling_constraints = _load_scheduling_constraints(
        ontology_root,
        manifest,
        schema_view,
        terms,
        runtime,
    )
    ontology_assertions = _load_ontology_assertions(ontology_root, manifest, terms, schema_view)
    base_iri = _required_string(manifest, _BASE_IRI_KEY)
    header = _header(manifest, source_hash)
    runtime_vocabulary: object = {
        "format": _RUNTIME_FORMAT,
        "schema_version": str(manifest["schema_version"]),
        "base_iri": base_iri,
        "source_hash": source_hash,
        "categories": categories,
        "terms": terms,
        "slot_policy_evidence": evidence_catalog,
        "scheduling_policies": scheduling_policies,
        "audit_review_rules": audit_review_rules,
        "audit_relation_exemptions": audit_relation_exemptions,
        "scheduling_constraints": scheduling_constraints,
        "runtime_policy": runtime.authored,
        "ontology_assertions": ontology_assertions,
    }
    semantic_shapes = _read_custom_shapes(ontology_root, manifest, base_iri)
    card_schema = cast(
        object,
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"{base_iri}generated/card.schema.json",
            "title": "Supp Slotter canonical card",
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "string", "pattern": "^(sub|prd)_[a-z0-9]+$"},
                "name": {"type": "string", "minLength": 1},
                "knowledge": {
                    "type": "object",
                    "properties": {
                        category: {"type": "array", "items": {"type": "string"}}
                        for category in sorted(categories)
                        if category != "schedule_rule"
                    },
                    "additionalProperties": False,
                },
                "schedule": {"type": "object"},
                "schedule_governance": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "required": ["status", "enforcement_cap", "scope", "evidence", "owner", "review_by"],
                        "properties": {
                            "status": {
                                "enum": [
                                    str(item["state"])
                                    for item in cast(list[dict[str, object]], runtime.authored["lifecycle_policies"])
                                ]
                            },
                            "enforcement_cap": {
                                "enum": [
                                    str(item["mode"])
                                    for item in cast(list[dict[str, object]], runtime.authored["enforcement_policies"])
                                ]
                            },
                            "scope": {
                                "type": "object",
                                "minProperties": 1,
                                "additionalProperties": {"type": "string", "minLength": 1},
                            },
                            "evidence": {"type": "array"},
                            "owner": {"type": "string", "minLength": 1},
                            "review_by": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                            "evidence_gap": {"type": "string", "minLength": 1},
                            "retirement_reason": {"type": "string", "minLength": 1},
                        },
                        "additionalProperties": False,
                    },
                },
            },
        },
    )
    schema = _require_schema_definition(schema_view.schema)
    generated_schema_serializer = _require_serializer(JsonSchemaGenerator(schema))
    generated_schema_doc = _json_mapping_from_text(generated_schema_serializer.serialize())
    generated_schema_doc["$schema"] = _JSON_SCHEMA_FORMAT
    generated_schema_doc["$id"] = f"{base_iri}generated/schema.json"
    generated_schema = _json_bytes_no_header(generated_schema_doc)
    generated_shapes = _canonical_shapes(schema_view)
    _validate_repository_projection_coverage(ontology_root, manifest)
    projection_map = _projection_map(schema_view, manifest, base_iri)
    context = _jsonld_context(schema_view, base_iri)
    runtime_program = _runtime_program(ontology_root, manifest, runtime.authored, source_hash)
    artifacts: dict[Path, bytes] = {
        Path("card.schema.json"): _json_bytes_no_header(card_schema),
        Path("schema.json"): generated_schema,
        Path("ontology.ttl"): _ttl_bytes(header, base_iri, categories, terms, schema_view, manifest),
        Path("shapes.ttl"): _shapes_bytes(header, base_iri, generated_shapes, semantic_shapes),
        Path("context.json"): _json_bytes_no_header(context),
        Path("projection-map.json"): _json_bytes_no_header(projection_map),
        Path("runtime-program.json"): _json_bytes_no_header(runtime_program),
        Path("runtime-vocabulary.yaml"): _yaml_bytes(runtime_vocabulary, sort_keys=False),
    }
    artifacts[Path("artifact-lock.json")] = _json_bytes_no_header(_artifact_lock(ontology_root, manifest, artifacts))
    return artifacts


def _schema_view(ontology_root: Path, manifest: Mapping[str, object]) -> SchemaView:
    """Load the one merged LinkML schema graph used by all schema projections."""
    try:
        return SchemaView(str(_source_path(ontology_root, _required_string(manifest, "linkml_root"))))
    except Exception as error:  # LinkML owns parser/compiler failure details.
        raise OntologyInfrastructureError(f"LinkML cannot load canonical root: {error}") from error


def _require_schema_definition(value: object) -> SchemaDefinition:
    if not isinstance(value, SchemaDefinition):
        raise OntologyInfrastructureError("LinkML schema view did not expose a schema definition")
    return value


def _require_serializer(value: object) -> _LinkMLSerializer:
    if not isinstance(value, _LinkMLSerializer):
        raise OntologyInfrastructureError("LinkML generator did not expose a serializer")
    return value


def _json_mapping_from_text(value: object) -> dict[str, object]:
    if not isinstance(value, str):
        raise OntologyInfrastructureError("LinkML serializer returned a non-text document")
    try:
        loaded = cast(object, json.loads(value))
    except json.JSONDecodeError as error:
        raise OntologyInfrastructureError(f"LinkML serializer returned invalid JSON: {error}") from error
    if not isinstance(loaded, dict) or not all(isinstance(key, str) for key in loaded):
        raise OntologyInfrastructureError("LinkML serializer returned a JSON object")
    return cast(dict[str, object], loaded)


def _validated_rdf_triples(value: object) -> list[_RdfTriple]:
    if not isinstance(value, Iterable):
        raise OntologyInfrastructureError("RDF graph query did not return an iterable")
    triples: list[_RdfTriple] = []
    for raw_triple in cast(Iterable[object], value):
        if not isinstance(raw_triple, tuple):
            raise OntologyInfrastructureError("RDF graph query returned an invalid triple")
        raw_tuple = cast(tuple[object, ...], raw_triple)
        if len(raw_tuple) != _RDF_TRIPLE_SIZE or not all(isinstance(node, Node) for node in raw_tuple):
            raise OntologyInfrastructureError("RDF graph query returned an invalid triple")
        triples.append(cast(_RdfTriple, raw_tuple))
    return triples


def _compiler_config(manifest: Mapping[str, object]) -> tuple[str, str, dict[str, str]]:
    compiler = _required_mapping(manifest, "compiler")
    identity = _required_string(compiler, "id")
    version = _required_string(compiler, "version")
    raw_tools = _required_mapping(compiler, "tool_versions")
    tools: dict[str, str] = {}
    for name, tool_version in raw_tools.items():
        if not isinstance(name, str) or not isinstance(tool_version, str) or not name or not tool_version:
            raise OntologyInfrastructureError("Compiler tool_versions must map non-empty names to versions")
        tools[name] = tool_version
    return identity, version, dict(sorted(tools.items()))


def _manifest_source_paths(manifest: Mapping[str, object]) -> list[str]:
    paths = ["ontology/" + _MANIFEST_NAME, _required_string(manifest, "linkml_root")]
    paths.extend(_required_string_list(manifest, "linkml_modules"))
    paths.extend(str(c["path"]) for c in cast(list[dict[str, object]], manifest.get("catalogs", [])))
    return paths


def _source_records(ontology_root: Path, manifest: Mapping[str, object]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for relative_path in sorted(set(_manifest_source_paths(manifest))):
        path = ontology_root.parent / relative_path
        if not path.is_file():
            raise OntologyInfrastructureError(f"Manifest declares missing ontology source: {path}")
        records.append({"path": relative_path, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return records


def _artifact_lock(
    ontology_root: Path, manifest: Mapping[str, object], artifacts: Mapping[Path, bytes]
) -> dict[str, object]:
    identity, version, tools = _compiler_config(manifest)
    return {
        "format_version": _ARTIFACT_LOCK_FORMAT,
        "schema_version": str(manifest["schema_version"]),
        "compiler": {"identity": identity, "version": version, "tools": tools},
        "sources": _source_records(ontology_root, manifest),
        "outputs": [
            {"path": str(path), "sha256": hashlib.sha256(content).hexdigest()}
            for path, content in sorted(artifacts.items(), key=lambda item: str(item[0]))
            if str(path) != "artifact-lock.json"
        ],
    }


def _projection_map(schema_view: SchemaView, manifest: Mapping[str, object], base_iri: str) -> dict[str, object]:
    classes: list[dict[str, object]] = []
    for name in sorted(schema_view.all_classes()):
        slots: list[dict[str, object]] = []
        for slot_name in sorted(schema_view.class_slots(name)):
            slot = schema_view.induced_slot(slot_name, name)
            slots.append({
                "name": slot_name,
                "range": slot.range,
                "multivalued": bool(slot.multivalued),
                "required": bool(slot.required),
                "inlined": bool(slot.inlined),
                "inlined_as_list": bool(slot.inlined_as_list),
            })
        classes.append({"name": name, "uri": f"{base_iri}{name}", "slots": slots})
    catalogs = [
        {
            "id": str(item["id"]),
            "role": str(item["role"]),
            "path": str(item["path"]),
            "root_class": str(item["root_class"]),
        }
        for item in cast(list[dict[str, object]], manifest["catalogs"])
    ]
    catalogs.sort(key=lambda item: str(item["id"]))
    repository = _repository_projection_map(manifest, base_iri)
    return {
        "format_version": _PROJECTION_MAP_FORMAT,
        "schema_version": str(manifest["schema_version"]),
        "schema_root": f"{base_iri}supp_slotter",
        "classes": classes,
        "catalogs": catalogs,
        "repository_projection": repository,
    }


def _repository_projection_map(manifest: Mapping[str, object], base_iri: str) -> dict[str, object]:
    """Render the manifest-authored generic repository projection."""
    projection = cast(Mapping[str, object], manifest["repository_projection"])
    mappings = _validate_repository_mappings(projection["mappings"])
    raw_sources = cast(list[object], projection["sources"])
    sources: list[dict[str, object]] = []
    for raw_source in raw_sources:
        source = cast(Mapping[str, object], raw_source)
        source_id = cast(str, source["id"])
        root_class = source.get("root_class")
        locator = cast(Mapping[str, object], source["locator"])
        kind = cast(str, locator["kind"])
        rendered_locator: dict[str, object] = {"kind": kind}
        if kind == "catalog_ref":
            rendered_locator["catalog_id"] = locator["catalog_id"]
        else:
            paths = _repository_locator_paths(locator, kind)
            if kind in {"flat_root", "explicit_path"}:
                rendered_locator["path"] = paths[0]
            else:
                rendered_locator["paths"] = paths
        records = cast(dict[str, object], mappings[source_id]).copy()
        records.pop("source", None)
        source_record: dict[str, object] = {"id": source_id, "locator": rendered_locator, "documents": records}
        source_record["root_class"] = root_class or records["root_class"]
        sources.append(source_record)
    sources.sort(key=lambda item: str(item["id"]))
    return {
        "format_version": _REPOSITORY_PROJECTION_FORMAT,
        "base_iri": cast(str, projection[_BASE_IRI_KEY]),
        "sources": sources,
    }


def _validate_repository_projection_coverage(  # noqa: PLR0914
    ontology_root: Path, manifest: Mapping[str, object]
) -> None:
    """Check every discovered YAML container and leaf against authored mappings."""
    repository_root = ontology_root.parent.resolve()
    projection = cast(Mapping[str, object], manifest["repository_projection"])
    catalogs = cast(list[dict[str, object]], manifest["catalogs"])
    mappings = _validate_repository_mappings(projection["mappings"])
    catalog_paths = {str(item["id"]): str(item["path"]) for item in catalogs}
    seen_ids: set[tuple[str, str]] = set()
    for raw_source in cast(list[object], projection["sources"]):
        source = cast(Mapping[str, object], raw_source)
        source_id = cast(str, source["id"])
        mapping = mappings[source_id]
        locator = cast(Mapping[str, object], source["locator"])
        kind = cast(str, locator["kind"])
        if kind == "catalog_ref":
            catalog_id = cast(str, locator["catalog_id"])
            catalog_path = catalog_paths[catalog_id]
            catalog_file = _safe_repository_path(repository_root, catalog_path, directory=False)
            document = _safe_yaml_load(catalog_file.read_text(encoding="utf-8"))
            _validate_mapping_document(document, mapping, catalog_file, seen_ids, source_id)
            continue
        paths = _repository_locator_paths(locator, kind)
        if kind == "flat_root":
            root = _safe_repository_path(repository_root, paths[0], directory=True)
            files = sorted(root.iterdir(), key=lambda item: item.name)
        else:
            files = [_safe_repository_path(repository_root, path, directory=False) for path in paths]
        for file_path in files:
            try:
                document = _safe_yaml_load(file_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, yaml.YAMLError) as error:
                raise OntologyInfrastructureError(
                    f"Cannot load repository projection document {file_path}: {error}"
                ) from error
            _validate_mapping_document(document, mapping, file_path, seen_ids, source_id)


def _validate_mapping_document(
    document: object,
    mapping: Mapping[str, object],
    source_path: Path,
    seen_ids: set[tuple[str, str]],
    source_id: str,
) -> None:
    shape = mapping["document_shape"]
    if shape not in {"mapping", "keyed-map"} or not isinstance(document, dict):
        raise OntologyInfrastructureError(f"Repository document shape disagrees with mapping: {source_path}")
    mapping_document = cast(Mapping[str, object], document)
    root_class = cast(str, mapping["root_class"])
    identity = mapping.get("identity")
    if isinstance(identity, dict):
        identity_source = cast(str, identity["source"])
        if identity_source == "<key>":
            identifiers = list(mapping_document)
        else:
            value = mapping_document.get(identity_source)
            identifiers = [value] if isinstance(value, str) else []
        if not identifiers or not all(isinstance(item, str) and item for item in identifiers):
            raise OntologyInfrastructureError(f"Repository document lacks a stable id: {source_path}")
        for identifier in identifiers:
            key = (root_class, identifier)
            if key in seen_ids:
                raise OntologyInfrastructureError(f"Duplicate repository document id {identifier!r} in {source_id}")
            seen_ids.add(key)
    actual = _leaf_paths(mapping_document)
    patterns = [str(item["source"]) for item in cast(list[dict[str, object]], mapping["instructions"])]
    unknown = sorted({path for path in actual if not any(_mapping_path_matches(pattern, path) for pattern in patterns)})
    if unknown:
        raise OntologyInfrastructureError(
            f"Repository projection has unmapped fields in {source_path}: {', '.join(unknown)}"
        )


def _mapping_path_matches(pattern: str, actual: str) -> bool:
    pattern_parts = pattern.split(".")
    actual_parts = actual.split(".")
    if len(pattern_parts) != len(actual_parts):
        return False
    for expected, observed in zip(pattern_parts, actual_parts, strict=True):
        if expected == observed:
            continue
        if expected == "<key>" and not observed.endswith("[]"):
            continue
        if expected == "<key>[]" and observed.endswith("[]"):
            continue
        if expected != observed:
            return False
    return True


def _reject_ambiguous_mapping_patterns(source_id: str, patterns: list[str]) -> None:
    """Reject patterns that can select the same structural node."""
    for index, left in enumerate(patterns):
        left_parts = left.split(".")
        for right in patterns[index + 1 :]:
            right_parts = right.split(".")
            if len(left_parts) != len(right_parts):
                continue
            if all(_mapping_tokens_compatible(a, b) for a, b in zip(left_parts, right_parts, strict=True)):
                raise OntologyInfrastructureError(
                    f"Repository mapping {source_id!r} has ambiguous compatible paths {left!r} and {right!r}"
                )


def _mapping_tokens_compatible(left: str, right: str) -> bool:
    if left == right:
        return True
    if left == "<key>":
        return right == "<key>" or not right.endswith("[]")
    if right == "<key>":
        return not left.endswith("[]")
    if left == "<key>[]":
        return right == "<key>[]" or right.endswith("[]")
    if right == "<key>[]":
        return left.endswith("[]")
    return False


def _unique_record_values(records: Sequence[Mapping[str, object]], field: str, label: str) -> set[str]:
    values: set[str] = set()
    for record in records:
        value = record.get(field)
        if not isinstance(value, str) or not value:
            raise OntologyInfrastructureError(f"Runtime {label} requires non-empty {field}")
        if value in values:
            raise OntologyInfrastructureError(f"Runtime {label} has duplicate {field} {value!r}")
        values.add(value)
    return values


def _validate_runtime_condition(value: object, label: str, *, allow_empty: bool = False) -> None:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a condition list" if allow_empty else "a non-empty condition list"
        raise OntologyInfrastructureError(f"Runtime {label} must be {qualifier}")
    for index, raw in enumerate(value):
        _validate_runtime_condition_node(raw, f"{label}[{index}]")


def _validate_runtime_condition_node(value: object, label: str) -> None:
    if not isinstance(value, dict):
        raise OntologyInfrastructureError(f"Runtime {label} condition must be a mapping")
    operator = value.get("operator")
    if not isinstance(operator, str) or operator not in _CONDITION_OPERATORS:
        raise OntologyInfrastructureError(f"Runtime {label} has unknown condition operator")
    if operator in {"equals", "contains", "equals_field", "member_of_field", "is_true", "is_false"}:
        expected = {"operator", "field", "value"} if operator in {"equals", "contains", "equals_field", "member_of_field"} else {"operator", "field"}
        if set(value) != expected:
            raise OntologyInfrastructureError(f"Runtime {label} has invalid keys for {operator}")
        field = value.get("field")
        field_type = _CONDITION_PATH_TYPES.get(field) if isinstance(field, str) else None
        if field_type is None:
            raise OntologyInfrastructureError(f"Runtime {label} references unknown condition path")
        if operator in {"equals_field", "member_of_field"}:
            other = value.get("value")
            other_type = _CONDITION_PATH_TYPES.get(other) if isinstance(other, str) else None
            compatible = field_type == other_type if operator == "equals_field" else field_type == "string" and other_type == "strings"
            if not compatible:
                raise OntologyInfrastructureError(f"Runtime {label} cross-field operands are incompatible")
        elif operator in {"is_true", "is_false"}:
            if field_type != "boolean":
                raise OntologyInfrastructureError(f"Runtime {label} boolean operator requires boolean path")
        elif operator == "contains":
            if field_type != "string" or not isinstance(value.get("value"), str) or not value["value"]:
                raise OntologyInfrastructureError(f"Runtime {label} contains operand is incompatible")
        elif field_type == "string":
            if not isinstance(value.get("value"), str) or not value["value"]:
                raise OntologyInfrastructureError(f"Runtime {label} requires a string operand")
        elif field_type == "boolean" and not isinstance(value.get("value"), bool):
            raise OntologyInfrastructureError(f"Runtime {label} requires a boolean operand")
        return
    if set(value) != {"operator", "conditions"} or not isinstance(value.get("conditions"), list) or not value["conditions"]:
        raise OntologyInfrastructureError(f"Runtime {label} logical condition requires non-empty conditions")
    if operator == "not" and len(value["conditions"]) != 1:
        raise OntologyInfrastructureError(f"Runtime {label} not requires one child")
    for index, child in enumerate(value["conditions"]):
        _validate_runtime_condition_node(child, f"{label}.conditions[{index}]")


@dataclass(frozen=True)
class _RuntimePolicyRecords:
    protocol: dict[str, object]
    fact_fields: list[dict[str, object]]
    schedule_axes: list[dict[str, object]]
    assignment_axes: list[dict[str, object]]
    lifecycle: list[dict[str, object]]
    enforcement: list[dict[str, object]]
    dimensions: list[dict[str, object]]
    scope_rules: list[dict[str, object]]
    authorities: list[dict[str, object]]
    component_authority: list[dict[str, object]]
    competition_rules: list[dict[str, object]]
    enforcement_projection: list[dict[str, object]]
    effect_remaps: list[dict[str, object]]
    execution_gates: list[dict[str, object]]
    scope_outcomes: list[dict[str, object]]
    constraint_governance: dict[str, object]
    evidence_format: _EvidenceUriFormat
    constraint_lifecycle: list[dict[str, object]]
    constraint_enforcement: list[dict[str, object]]
    constraint_execution_gates: list[dict[str, object]]
    constraint_allowed_pairs: list[dict[str, object]]
    constraint_execution_policies: list[dict[str, object]]
    degradation: list[dict[str, object]]
    precedence: list[dict[str, object]]
    capabilities: list[dict[str, object]]
    governance: dict[str, object]
    scoring: dict[str, object]
    projection: list[dict[str, object]]


@dataclass(frozen=True)
class _RuntimePolicyCore:
    lifecycle_states: set[str]
    enforcement_modes: set[str]
    scope_keys: tuple[str, ...]
    scope_values: Mapping[str, frozenset[str]]
    enforcement_ranks: Mapping[str, int]
    enforcement_executable: Mapping[str, bool]
    enforcement_modes_by_role: Mapping[str, str]
    execution_gates: Mapping[str, Mapping[str, object]]
    degradation_rules: Mapping[tuple[str, str], Mapping[str, object]]


def _runtime_records(source: Mapping[str, object], slot: str) -> list[dict[str, object]]:
    raw = source.get(slot)
    if not isinstance(raw, list) or not raw:
        raise OntologyInfrastructureError(f"Runtime policy requires non-empty {slot}")
    out: list[dict[str, object]] = []
    ids: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise OntologyInfrastructureError(f"Runtime policy {slot} records must be mappings")
        row = dict(cast(Mapping[str, object], item))
        identifier = _required_string(row, "id")
        if identifier in ids:
            raise OntologyInfrastructureError(f"Runtime policy {slot} has duplicate id {identifier!r}")
        ids.add(identifier)
        out.append(row)
    return out


def _runtime_nested_records(parent: Mapping[str, object], slot: str) -> list[dict[str, object]]:
    raw = parent.get(slot)
    label = f"constraint_governance.{slot}"
    if not isinstance(raw, list) or not raw:
        raise OntologyInfrastructureError(f"Runtime policy requires non-empty {label}")
    out: list[dict[str, object]] = []
    ids: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise OntologyInfrastructureError(f"Runtime policy {label} records must be mappings")
        row = dict(cast(Mapping[str, object], item))
        identifier = _required_string(row, "id")
        if identifier in ids:
            raise OntologyInfrastructureError(f"Runtime policy {label} has duplicate id {identifier!r}")
        ids.add(identifier)
        out.append(row)
    return out


def _runtime_policy_constraint_records(
    source: Mapping[str, object],
) -> tuple[
    dict[str, object],
    _EvidenceUriFormat,
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    raw_governance = source.get("constraint_governance")
    if not isinstance(raw_governance, dict):
        raise OntologyInfrastructureError("Runtime policy requires constraint_governance mapping")
    constraint_governance = dict(cast(Mapping[str, object], raw_governance))
    raw_format = constraint_governance.get("evidence_format")
    if not isinstance(raw_format, dict):
        raise OntologyInfrastructureError("Runtime policy constraint_governance requires evidence_format mapping")
    evidence_format = cast(Mapping[str, object], raw_format)
    scheme = _required_string(evidence_format, "scheme")
    uri_flags: dict[str, bool] = {}
    for field in ("require_host", "forbid_userinfo"):
        value = evidence_format.get(field)
        if not isinstance(value, bool):
            raise OntologyInfrastructureError(
                f"Runtime policy constraint_governance.evidence_format requires boolean {field}"
            )
        uri_flags[field] = value
    return (
        constraint_governance,
        _EvidenceUriFormat(scheme, uri_flags["require_host"], uri_flags["forbid_userinfo"]),
        _runtime_nested_records(constraint_governance, "lifecycle_states"),
        _runtime_nested_records(constraint_governance, "enforcement_modes"),
        _runtime_nested_records(constraint_governance, "execution_gates"),
        _runtime_nested_records(constraint_governance, "allowed_pairs"),
        _runtime_nested_records(constraint_governance, "execution_policies"),
    )


def _load_runtime_policy_records(
    ontology_root: Path, manifest: Mapping[str, object], schema_view: SchemaView
) -> _RuntimePolicyRecords:
    source = _load_yaml_mapping(_catalog_path(ontology_root, manifest, "runtime_policy"))
    _validate_linkml_instance(schema_view, "RuntimePolicyCatalog", source)
    protocol = source.get("protocol")
    if not isinstance(protocol, dict):
        raise OntologyInfrastructureError("Runtime policy requires authored protocol inventory")
    protocol_map = dict(cast(Mapping[str, object], protocol))
    record_lists = {
        "fact_fields": _runtime_records(source, "fact_fields"),
        "schedule_axes": _runtime_records(source, "schedule_axes"),
        "assignment_axes": _runtime_records(source, "assignment_axes"),
        "lifecycle": _runtime_records(source, "lifecycle_policies"),
        "enforcement": _runtime_records(source, "enforcement_policies"),
        "dimensions": _runtime_records(source, "scope_dimensions"),
        "scope_rules": _runtime_records(source, "scope_rules"),
        "authorities": _runtime_records(source, "authorities"),
        "component_authority": _runtime_records(source, "component_authority_rules"),
        "competition_rules": _runtime_records(source, "competition_rules"),
        "enforcement_projection": _runtime_records(source, "enforcement_projection"),
        "effect_remaps": _runtime_records(source, "effect_remaps"),
        "execution_gates": _runtime_records(source, "execution_gates"),
        "scope_outcomes": _runtime_records(source, "scope_outcomes"),
    }
    (
        constraint_governance,
        evidence_format,
        constraint_lifecycle,
        constraint_enforcement,
        constraint_execution_gates,
        constraint_allowed_pairs,
        constraint_execution_policies,
    ) = _runtime_policy_constraint_records(source)
    record_lists.update({
        "degradation": _runtime_records(source, "degradation_rules"),
        "precedence": _runtime_records(source, "constraint_precedence"),
        "capabilities": _runtime_records(source, "capability_rules"),
    })
    governance = source.get("assignment_governance")
    scoring = source.get("effect_scoring")
    if not isinstance(governance, dict) or not isinstance(scoring, dict):
        raise OntologyInfrastructureError("Runtime policy requires assignment_governance and effect_scoring mappings")
    governance_map = dict(cast(Mapping[str, object], governance))
    scoring_map = dict(cast(Mapping[str, object], scoring))
    if governance_map.get("required") is not True:
        raise OntologyInfrastructureError("Runtime policy must require assignment governance")
    projection = _runtime_records(source, "runtime_projection")
    return _RuntimePolicyRecords(
        protocol_map,
        record_lists["fact_fields"],
        record_lists["schedule_axes"],
        record_lists["assignment_axes"],
        record_lists["lifecycle"],
        record_lists["enforcement"],
        record_lists["dimensions"],
        record_lists["scope_rules"],
        record_lists["authorities"],
        record_lists["component_authority"],
        record_lists["competition_rules"],
        record_lists["enforcement_projection"],
        record_lists["effect_remaps"],
        record_lists["execution_gates"],
        record_lists["scope_outcomes"],
        constraint_governance,
        evidence_format,
        constraint_lifecycle,
        constraint_enforcement,
        constraint_execution_gates,
        constraint_allowed_pairs,
        constraint_execution_policies,
        record_lists["degradation"],
        record_lists["precedence"],
        record_lists["capabilities"],
        governance_map,
        scoring_map,
        projection,
    )


def _validate_runtime_lifecycle(
    records: _RuntimePolicyRecords, lifecycle_states: set[str]
) -> dict[str, Mapping[str, object]]:
    lifecycle_ranks: set[int] = set()
    lifecycle_by_state: dict[str, Mapping[str, object]] = {}
    for row in records.lifecycle:
        state = _required_string(row, "state")
        rank = row.get("rank")
        executable = row.get("executable")
        if (
            not isinstance(rank, int)
            or isinstance(rank, bool)
            or rank in lifecycle_ranks
            or not isinstance(executable, bool)
        ):
            raise OntologyInfrastructureError(f"Runtime lifecycle policy {row['id']!r} has invalid or duplicate rank")
        lifecycle_ranks.add(rank)
        lifecycle_by_state[state] = row
    return lifecycle_by_state


def _validate_runtime_enforcement(records: _RuntimePolicyRecords) -> tuple[dict[str, int], dict[str, bool]]:
    ranks: set[int] = set()
    enforcement_ranks: dict[str, int] = {}
    enforcement_executable: dict[str, bool] = {}
    for row in records.enforcement:
        rank = row.get("rank")
        executable = row.get("executable")
        if (
            not isinstance(rank, int)
            or isinstance(rank, bool)
            or rank in ranks
            or not isinstance(executable, bool)
        ):
            raise OntologyInfrastructureError(f"Runtime enforcement policy {row['id']!r} has invalid or duplicate rank")
        ranks.add(rank)
        mode = _required_string(row, "mode")
        enforcement_ranks[mode] = rank
        enforcement_executable[mode] = executable
    return enforcement_ranks, enforcement_executable


def _validate_runtime_scope(
    records: _RuntimePolicyRecords,
) -> tuple[list[str], dict[str, frozenset[str]]]:
    scope_keys: list[str] = []
    scope_values: dict[str, frozenset[str]] = {}
    for dimension in records.dimensions:
        key = _required_string(dimension, "key")
        values = dimension.get("values")
        typed_values = cast(list[object], values) if isinstance(values, list) else None
        if (
            typed_values is None
            or not typed_values
            or key in scope_keys
            or any(not isinstance(value, str) or not value for value in typed_values)
            or len(set(typed_values)) != len(typed_values)
        ):
            raise OntologyInfrastructureError(f"Runtime policy has invalid scope dimension {key!r}")
        scope_keys.append(key)
        scope_values[key] = frozenset(cast(list[str], typed_values))
    return scope_keys, scope_values


def _validate_runtime_fact_fields(records: _RuntimePolicyRecords) -> None:
    declared: dict[str, str] = {}
    for row in records.fact_fields:
        if set(row) != {"id", "field", "value_type"}:
            raise OntologyInfrastructureError(f"Runtime fact field {row['id']!r} has invalid keys")
        field = _required_string(row, "field")
        value_type = _required_string(row, "value_type")
        if field in declared or value_type not in {"string", "strings", "boolean"}:
            raise OntologyInfrastructureError(f"Runtime fact field {row['id']!r} is invalid")
        declared[field] = value_type
    if declared != _CONDITION_PATH_TYPES:
        raise OntologyInfrastructureError("Runtime fact fields must exactly declare the condition vocabulary")


def _mirror_runtime_condition(value: object) -> object:
    if isinstance(value, list):
        return [_mirror_runtime_condition(item) for item in value]
    if not isinstance(value, dict):
        return value
    mirrored: dict[str, object] = {}
    for key, item in cast(Mapping[str, object], value).items():
        if key in {"field", "value"} and isinstance(item, str):
            if item.startswith("left_"):
                item = f"right_{item[5:]}"
            elif item.startswith("right_"):
                item = f"left_{item[6:]}"
        mirrored[key] = _mirror_runtime_condition(item)
    return mirrored


def _validate_runtime_competition_mirrors(records: _RuntimePolicyRecords) -> None:
    semantic_rows = [row for row in records.competition_rules if row.get("conditions") != []]
    for row in semantic_rows:
        action = row.get("action_code")
        if action not in {"left_wins", "right_wins"}:
            raise OntologyInfrastructureError(
                f"Runtime competition rule {row['id']!r} must declare an oriented winner"
            )
        mirrored_action = "right_wins" if action == "left_wins" else "left_wins"
        mirrored_conditions = _mirror_runtime_condition(row["conditions"])
        if not any(
            candidate.get("action_code") == mirrored_action
            and candidate.get("reason_code") == row.get("reason_code")
            and candidate.get("conditions") == mirrored_conditions
            for candidate in semantic_rows
            if candidate is not row
        ):
            raise OntologyInfrastructureError(
                f"Runtime competition rule {row['id']!r} has no explicit mirrored orientation"
            )


def _runtime_component_authority_case(value: object, label: str) -> tuple[bool, str]:
    if not isinstance(value, list) or len(value) != 2:
        raise OntologyInfrastructureError(f"Runtime {label} must contain exactly one clause for each authority dimension")
    explicit: bool | None = None
    primary: str | None = None
    for index, raw_clause in enumerate(value):
        if not isinstance(raw_clause, dict):
            raise OntologyInfrastructureError(f"Runtime {label}[{index}] must be a mapping")
        field = raw_clause.get("field")
        if field == "any_explicit_primary":
            if set(raw_clause) != {"operator", "field"} or raw_clause.get("operator") not in {"is_true", "is_false"}:
                raise OntologyInfrastructureError(f"Runtime {label}[{index}] must be an is_true/is_false clause for any_explicit_primary")
            if explicit is not None:
                raise OntologyInfrastructureError(f"Runtime {label} has duplicate any_explicit_primary clauses")
            explicit = raw_clause["operator"] == "is_true"
        elif field == "component_primary":
            if set(raw_clause) != {"operator", "field", "value"} or raw_clause.get("operator") != "equals":
                raise OntologyInfrastructureError(f"Runtime {label}[{index}] must be an equals clause for component_primary")
            value = raw_clause.get("value")
            if value not in {"true", "false", "unset"}:
                raise OntologyInfrastructureError(f"Runtime {label}[{index}] component_primary must be true, false, or unset")
            if primary is not None:
                raise OntologyInfrastructureError(f"Runtime {label} has duplicate component_primary clauses")
            primary = cast(str, value)
        else:
            raise OntologyInfrastructureError(f"Runtime {label}[{index}] references an unknown component authority dimension")
    if explicit is None or primary is None:
        raise OntologyInfrastructureError(f"Runtime {label} must cover any_explicit_primary and component_primary exactly once")
    return explicit, primary


def _validate_runtime_component_authority(records: _RuntimePolicyRecords) -> None:
    rows = records.component_authority
    if not rows:
        raise OntologyInfrastructureError("Runtime component authority table must be non-empty")
    expected_cases = {
        (explicit, primary)
        for explicit in (False, True)
        for primary in ("true", "false", "unset")
    }
    priorities: set[int] = set()
    keys = {"id", "priority", "conditions", "outcome"}
    seen_cases: dict[tuple[bool, str], str] = {}
    for row in rows:
        identifier = row.get("id", "<unknown>")
        if set(row) != keys:
            raise OntologyInfrastructureError(f"Runtime component authority rule {identifier!r} has invalid keys")
        priority = row.get("priority")
        outcome = row.get("outcome")
        if not isinstance(priority, int) or isinstance(priority, bool) or priority in priorities:
            raise OntologyInfrastructureError(f"Runtime component authority rule {identifier!r} has invalid priority")
        if outcome not in {"primary", "secondary"}:
            raise OntologyInfrastructureError(f"Runtime component authority rule {identifier!r} has invalid outcome")
        priorities.add(priority)
        conditions = row.get("conditions")
        label = f"component authority rule {identifier}.conditions"
        _validate_runtime_condition(conditions, label)
        case = _runtime_component_authority_case(conditions, label)
        if case in seen_cases:
            raise OntologyInfrastructureError(f"Runtime component authority table duplicates state {case!r} in {seen_cases[case]!r} and {identifier!r}")
        seen_cases[case] = cast(str, identifier)
    if set(seen_cases) != expected_cases:
        raise OntologyInfrastructureError(
            f"Runtime component authority table must contain exactly the six canonical component states "
            f"(missing={sorted(expected_cases - set(seen_cases))}, extra={sorted(set(seen_cases) - expected_cases)})"
        )


def _validate_runtime_flat_tables(
    records: _RuntimePolicyRecords,
    core_modes: set[str],
    main_effect_roles: set[str],
    score_levels: set[str],
) -> None:
    """Validate the generic scheduling tables without interpreting domain policy."""
    axes: set[str] = set()
    for row in records.schedule_axes:
        axis = _required_string(row, "axis")
        values = row.get("values")
        if axis in axes or not isinstance(values, list) or not values or any(not isinstance(v, str) or not v for v in values):
            raise OntologyInfrastructureError(f"Runtime schedule axis {row['id']!r} is invalid")
        axes.add(axis)
    assignment_axes: set[str] = set()
    assignment_orders: set[int] = set()
    for row in records.assignment_axes:
        if set(row) != {"id", "axis", "order", "assignment_source", "assignment_field"}:
            raise OntologyInfrastructureError(f"Runtime assignment axis {row['id']!r} has invalid keys")
        axis = _required_string(row, "axis")
        order = row.get("order")
        _required_string(row, "assignment_source")
        assignment_field = _required_string(row, "assignment_field")
        if (
            axis in assignment_axes
            or not isinstance(order, int)
            or isinstance(order, bool)
            or order in assignment_orders
            or assignment_field != axis
        ):
            raise OntologyInfrastructureError(f"Runtime assignment axis {row['id']!r} is invalid")
        assignment_axes.add(axis)
        assignment_orders.add(order)
    if assignment_orders != set(range(len(records.assignment_axes))):
        raise OntologyInfrastructureError("Runtime assignment axis order must be contiguous from zero")
    outcome_ids = {cast(str, row["id"]) for row in records.scope_outcomes}
    rule_ids = {row["id"] for row in records.scope_rules}
    for row in records.dimensions:
        refs = row.get("rule_ids")
        default = _required_string(row, "default_outcome")
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in rule_ids for ref in refs):
            raise OntologyInfrastructureError(f"Runtime scope dimension {row['id']!r} has invalid rule_ids")
        if default not in outcome_ids:
            raise OntologyInfrastructureError(f"Runtime scope dimension {row['id']!r} has unknown default outcome")
    for row in records.scope_rules:
        _required_string(row, "outcome")
        priority = row.get("priority")
        conditions = row.get("conditions")
        if row["outcome"] not in outcome_ids or not isinstance(priority, int) or isinstance(priority, bool):
            raise OntologyInfrastructureError(f"Runtime scope rule {row['id']!r} is invalid")
        _validate_runtime_condition(conditions, f"scope rule {row['id']}.conditions")
    for dimension in records.dimensions:
        priorities: set[int] = set()
        for rule_id in cast(list[str], dimension["rule_ids"]):
            rule = next(rule for rule in records.scope_rules if rule["id"] == rule_id)
            priority = cast(int, rule["priority"])
            if priority in priorities:
                raise OntologyInfrastructureError(
                    f"Runtime scope dimension {dimension['id']!r} has duplicate rule priority {priority!r}"
                )
            priorities.add(priority)
    authority_priorities: set[int] = set()
    authority_ranks: set[int] = set()
    authority_values: set[str] = set()
    authority_keys = {"id", "priority", "conditions", "authority", "enforcement_cap", "score_weight", "control_rank", "action_code", "reason_code"}
    for row in records.authorities:
        if set(row) != authority_keys:
            raise OntologyInfrastructureError(f"Runtime authority rule {row['id']!r} has invalid keys")
        priority = row.get("priority")
        rank = row.get("control_rank")
        weight = row.get("score_weight")
        authority = _required_string(row, "authority")
        cap = _required_string(row, "enforcement_cap")
        _required_string(row, "action_code")
        _required_string(row, "reason_code")
        if (
            not isinstance(priority, int)
            or isinstance(priority, bool)
            or priority in authority_priorities
            or not isinstance(rank, int)
            or isinstance(rank, bool)
            or rank in authority_ranks
            or not isinstance(weight, (int, float))
            or isinstance(weight, bool)
            or not isfinite(float(weight))
            or not 0 < weight <= 1
            or authority in authority_values
            or cap not in core_modes
        ):
            raise OntologyInfrastructureError(f"Runtime authority rule {row['id']!r} is invalid")
        authority_priorities.add(priority)
        authority_ranks.add(rank)
        authority_values.add(authority)
        _validate_runtime_condition(row.get("conditions"), f"authority rule {row['id']}.conditions")
    _validate_runtime_component_authority(records)
    competition_priorities: set[int] = set()
    fallback_count = 0
    competition_keys = {"id", "priority", "conditions", "action_code", "reason_code"}
    for row in records.competition_rules:
        if set(row) != competition_keys:
            raise OntologyInfrastructureError(f"Runtime competition rule {row['id']!r} has invalid keys")
        priority = row.get("priority")
        conditions = row.get("conditions")
        _required_string(row, "action_code")
        _required_string(row, "reason_code")
        if not isinstance(priority, int) or isinstance(priority, bool) or priority in competition_priorities:
            raise OntologyInfrastructureError(f"Runtime competition rule {row['id']!r} is invalid")
        competition_priorities.add(priority)
        _validate_runtime_condition(conditions, f"competition rule {row['id']}.conditions", allow_empty=True)
        if conditions == []:
            fallback_count += 1
            if row["action_code"] != "no_action" or priority != min(cast(list[int], [cast(int, item["priority"]) for item in records.competition_rules])):
                raise OntologyInfrastructureError("Runtime competition fallback must be lowest-priority no_action")
    if fallback_count != 1:
        raise OntologyInfrastructureError("Runtime competition rules require exactly one explicit fallback")
    _validate_runtime_competition_mirrors(records)
    projection_modes: set[str] = set()
    for row in records.enforcement_projection:
        mode = _required_string(row, "mode")
        if mode in projection_modes or mode not in core_modes:
            raise OntologyInfrastructureError(f"Runtime enforcement projection {row['id']!r} is invalid")
        projection_modes.add(mode)
        effect_role = _required_string(row, "effect_role")
        if effect_role not in main_effect_roles:
            raise OntologyInfrastructureError(f"Runtime enforcement projection {row['id']!r} has unknown effect_role")
    if projection_modes != core_modes:
        raise OntologyInfrastructureError("Runtime enforcement projection must cover every enforcement mode exactly once")
    remap_pairs: set[tuple[str, str | None]] = set()
    score_values = {
        _required_string(cast(Mapping[str, object], row), "level"): cast(int, cast(Mapping[str, object], row)["score"])
        for row in cast(list[object], records.scoring["scores"])
        if isinstance(row, dict)
    }
    maximum_score_magnitude = max(abs(value) for value in score_values.values())
    remap_keys = {"id", "mode", "level", "projected_level", "score_enabled", "block_behavior", "level_code", "block_code", "default_code"}
    for row in records.effect_remaps:
        if set(row) != remap_keys:
            raise OntologyInfrastructureError(f"Runtime effect remap {row['id']!r} has invalid keys")
        mode = _required_string(row, "mode")
        level_value = row.get("level")
        level = _required_string(row, "level") if level_value is not None else None
        projected = row.get("projected_level")
        enabled = row.get("score_enabled")
        behavior = row.get("block_behavior")
        for code in ("level_code", "block_code", "default_code"):
            _required_string(row, code)
        if (
            mode not in core_modes
            or (level is not None and level not in score_levels)
            or not isinstance(enabled, bool)
            or behavior not in {"preserve", "suppress"}
            or (projected is not None and projected not in score_levels)
            or enabled != (projected is not None)
        ):
            raise OntologyInfrastructureError(f"Runtime effect remap {row['id']!r} is invalid")
        if behavior == "preserve" and projected != level:
            raise OntologyInfrastructureError(f"Runtime effect remap {row['id']!r} must preserve its level")
        if level is None and projected is not None:
            raise OntologyInfrastructureError(f"Runtime block-only effect remap {row['id']!r} may not invent a score level")
        if level is not None and enabled and behavior == "suppress" and abs(score_values[level]) == maximum_score_magnitude:
            if abs(score_values[cast(str, projected)]) >= maximum_score_magnitude:
                raise OntologyInfrastructureError(f"Runtime effect remap {row['id']!r} must downgrade a strong level")
        if (mode, level) in remap_pairs:
            raise OntologyInfrastructureError(f"Runtime effect remap {row['id']!r} duplicates mode/level pair")
        remap_pairs.add((mode, level))
    if remap_pairs != {(mode, level) for mode in core_modes for level in (*score_levels, None)}:
        raise OntologyInfrastructureError("Runtime effect remaps must cover every enforcement-mode/effect-level pair, including block-only effects")
    remap_profiles = {
        mode: {
            (cast(bool, row["score_enabled"]), cast(str, row["block_behavior"]))
            for row in records.effect_remaps
            if row["mode"] == mode and row["level"] is not None
        }
        for mode in core_modes
    }
    if any(len(profile) != 1 for profile in remap_profiles.values()):
        raise OntologyInfrastructureError("Runtime effect remap mechanics must be consistent within each mode")
    profile_counts = {
        profile: sum(1 for value in remap_profiles.values() if value == profile)
        for profile in set(map(frozenset, remap_profiles.values()))
    }
    expected_profiles = {
        frozenset({(False, "suppress")}): 2,
        frozenset({(True, "suppress")}): 1,
        frozenset({(True, "preserve")}): 1,
    }
    if profile_counts != expected_profiles:
        raise OntologyInfrastructureError("Runtime effect remaps have invalid enforcement profiles")


def _validate_runtime_execution_gates(
    records: _RuntimePolicyRecords,
    lifecycle_states: set[str],
    lifecycle_by_state: Mapping[str, Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    gate_states: set[str] = set()
    execution_gates: dict[str, Mapping[str, object]] = {}
    for gate in records.execution_gates:
        state = _required_string(gate, "lifecycle_state")
        _required_string(gate, "evidence_requirement")
        if (
            state not in lifecycle_states
            or state in gate_states
            or not isinstance(gate.get("executable"), bool)
            or gate["executable"] != lifecycle_by_state[state]["executable"]
        ):
            raise OntologyInfrastructureError(f"Runtime execution gate references unknown lifecycle state {state!r}")
        gate_states.add(state)
        execution_gates[state] = gate
    if gate_states != lifecycle_states:
        raise OntologyInfrastructureError("Runtime execution gates must cover every lifecycle state exactly once")
    return execution_gates


def _validate_runtime_outcomes(records: _RuntimePolicyRecords) -> None:
    _unique_record_values(records.scope_outcomes, "outcome", "scope outcome")
    _unique_record_values(records.scope_outcomes, "scope_action", "scope outcome")
    for outcome in records.scope_outcomes:
        _required_string(outcome, "direct_product")
        _required_string(outcome, "formulation")


def _validate_runtime_degradation(
    records: _RuntimePolicyRecords, lifecycle_states: set[str], enforcement_modes: set[str]
) -> dict[tuple[str, str], Mapping[str, object]]:
    degradation_rules: dict[tuple[str, str], Mapping[str, object]] = {}
    for rule in records.degradation:
        if set(rule) != {"id", "lifecycle_state", "incoming_mode", "effective_mode"}:
            raise OntologyInfrastructureError(f"Runtime degradation rule {rule['id']!r} has invalid keys")
        state = _required_string(rule, "lifecycle_state")
        incoming = _required_string(rule, "incoming_mode")
        effective = _required_string(rule, "effective_mode")
        key = (state, incoming)
        if (
            state not in lifecycle_states
            or incoming not in enforcement_modes
            or effective not in enforcement_modes
            or key in degradation_rules
        ):
            raise OntologyInfrastructureError(f"Runtime degradation rule {rule['id']!r} has unknown cross-reference")
        degradation_rules[key] = rule
    expected = {(state, mode) for state in lifecycle_states for mode in enforcement_modes}
    if set(degradation_rules) != expected:
        raise OntologyInfrastructureError(
            "Runtime degradation rules must cover every lifecycle-state/incoming-mode pair exactly once"
        )
    return degradation_rules


def _validate_runtime_core(records: _RuntimePolicyRecords) -> _RuntimePolicyCore:
    _validate_runtime_fact_fields(records)
    lifecycle_states = _unique_record_values(records.lifecycle, "state", "lifecycle policy")
    enforcement_modes = _unique_record_values(records.enforcement, "mode", "enforcement policy")
    roles = _unique_record_values(records.enforcement, "effect_role", "enforcement policy")
    enforcement_modes_by_role = {cast(str, row["effect_role"]): cast(str, row["mode"]) for row in records.enforcement}
    lifecycle_by_state = _validate_runtime_lifecycle(records, lifecycle_states)
    enforcement_ranks, enforcement_executable = _validate_runtime_enforcement(records)
    scope_keys, scope_values = _validate_runtime_scope(records)
    execution_gates = _validate_runtime_execution_gates(records, lifecycle_states, lifecycle_by_state)
    _validate_runtime_outcomes(records)
    degradation_rules = _validate_runtime_degradation(records, lifecycle_states, enforcement_modes)
    return _RuntimePolicyCore(
        lifecycle_states,
        enforcement_modes,
        tuple(scope_keys),
        scope_values,
        enforcement_ranks,
        enforcement_executable,
        {role: enforcement_modes_by_role[role] for role in roles},
        execution_gates,
        degradation_rules,
    )


def _validate_runtime_constraints(
    records: _RuntimePolicyRecords,
    main_effect_roles: set[str],
) -> _ConstraintRuntime:
    lifecycle_states = _unique_record_values(records.constraint_lifecycle, "state", "constraint lifecycle policy")
    enforcement_modes = _unique_record_values(records.constraint_enforcement, "mode", "constraint enforcement policy")
    for row in records.constraint_enforcement:
        effect_role = _required_string(row, "effect_role")
        if effect_role not in main_effect_roles:
            raise OntologyInfrastructureError(
                f"Runtime constraint enforcement {row['id']!r} has unknown effect_role"
            )
    lifecycle_by_state = {cast(str, row["state"]): row for row in records.constraint_lifecycle}
    ranks: set[int] = set()
    for row in records.constraint_lifecycle:
        rank = row.get("rank")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank in ranks:
            raise OntologyInfrastructureError(f"Runtime constraint lifecycle policy {row['id']!r} has invalid rank")
        ranks.add(rank)
    gate_states: set[str] = set()
    execution_gates: dict[str, Mapping[str, object]] = {}
    for gate in records.constraint_execution_gates:
        state = _required_string(gate, "lifecycle_state")
        if (
            state not in lifecycle_states
            or state in gate_states
            or not isinstance(gate.get("executable"), bool)
            or gate["executable"] != lifecycle_by_state[state]["executable"]
        ):
            raise OntologyInfrastructureError(
                f"Runtime constraint execution gate references unknown lifecycle state {state!r}"
            )
        _required_string(gate, "evidence_requirement")
        gate_states.add(state)
        execution_gates[state] = gate
    if gate_states != lifecycle_states:
        raise OntologyInfrastructureError(
            "Runtime constraint execution gates must cover every lifecycle state exactly once"
        )
    allowed_pairs: set[tuple[str, str]] = set()
    for pair in records.constraint_allowed_pairs:
        state = _required_string(pair, "lifecycle_state")
        mode = _required_string(pair, "enforcement_mode")
        key = (state, mode)
        if state not in lifecycle_states or mode not in enforcement_modes or key in allowed_pairs:
            raise OntologyInfrastructureError(f"Runtime constraint allowed pair {pair['id']!r} is invalid")
        allowed_pairs.add(key)
    if not allowed_pairs:
        raise OntologyInfrastructureError("Runtime constraint governance requires allowed_pairs")
    execution_policies: dict[str, Mapping[str, object]] = {}
    for policy in records.constraint_execution_policies:
        operation = _required_string(policy, "operation")
        if operation in execution_policies:
            raise OntologyInfrastructureError(
                f"Runtime constraint execution policies duplicate operation {operation!r}"
            )
        direction = _required_string(policy, "match_direction")
        if direction not in {"symmetric", "directed"}:
            raise OntologyInfrastructureError(
                f"Runtime constraint execution policy {policy['id']!r} has invalid match_direction"
            )
        if _required_string(policy, "aggregation") != "distinct_constraint":
            raise OntologyInfrastructureError(
                f"Runtime constraint execution policy {policy['id']!r} has invalid aggregation"
            )
        if _required_string(policy, "selector_resolution") != "require_nonempty":
            raise OntologyInfrastructureError(
                f"Runtime constraint execution policy {policy['id']!r} has invalid selector_resolution"
            )
        for field in ("blocks_slots", "scores_advisory"):
            if not isinstance(policy.get(field), bool):
                raise OntologyInfrastructureError(
                    f"Runtime constraint execution policy {policy['id']!r} requires boolean {field}"
                )
        score_delta = policy.get("score_delta")
        if not isinstance(score_delta, int) or isinstance(score_delta, bool):
            raise OntologyInfrastructureError(
                f"Runtime constraint execution policy {policy['id']!r} requires integer score_delta"
            )
        if policy["scores_advisory"] and score_delta > 0:
            raise OntologyInfrastructureError(
                f"Runtime constraint execution policy {policy['id']!r} cannot reward advisory matches"
            )
        execution_policies[operation] = policy
    return _ConstraintRuntime(
        lifecycle_states,
        enforcement_modes,
        allowed_pairs,
        execution_gates,
        records.evidence_format,
        execution_policies,
    )


def _validate_runtime_precedence(records: _RuntimePolicyRecords, core: _RuntimePolicyCore) -> None:
    precedence_keys: set[str] = set()
    for row in records.precedence:
        key = _required_string(row, "key")
        rank = row.get("rank")
        if (
            key not in core.enforcement_modes
            or key in precedence_keys
            or not isinstance(rank, int)
            or isinstance(rank, bool)
        ):
            raise OntologyInfrastructureError(f"Runtime constraint precedence row {row['id']!r} is invalid")
        expected_rank = core.enforcement_ranks[key]
        if rank != expected_rank:
            raise OntologyInfrastructureError(
                f"Runtime precedence rank for {key!r} must derive from enforcement policy rank {expected_rank!r}"
            )
        precedence_keys.add(key)
    if precedence_keys != core.enforcement_modes:
        raise OntologyInfrastructureError(
            "Runtime constraint precedence must cover every enforcement mode exactly once"
        )


def _validate_runtime_capabilities(records: _RuntimePolicyRecords, core: _RuntimePolicyCore) -> set[str]:
    near_values: set[str] = set()
    capability_pairs: set[tuple[object, object]] = set()
    capability_keys = {"id", "planner", "food_model", "base_slot_models", "slot_models", "product_scope", "formulations", "near_to_model"}
    for capability in records.capabilities:
        if set(capability) != capability_keys:
            raise OntologyInfrastructureError(f"Runtime capability {capability['id']!r} has invalid keys")
        references = {"planner": capability.get("planner"), "food_model": capability.get("food_model")}
        for key, value in references.items():
            if value not in core.scope_values.get(key, frozenset()):
                raise OntologyInfrastructureError(f"Runtime capability {capability['id']!r} has invalid {key} value")
        pair = (references["planner"], references["food_model"])
        if pair in capability_pairs:
            raise OntologyInfrastructureError(f"Runtime capability {capability['id']!r} duplicates planner/food_model")
        capability_pairs.add(pair)
        for key, dimension_key in (
            ("base_slot_models", "slot_model"),
            ("slot_models", "slot_model"),
            ("product_scope", "product"),
            ("formulations", "formulation"),
        ):
            values = capability.get(key)
            typed_values = cast(list[object], values) if isinstance(values, list) else None
            if (
                typed_values is None
                or not typed_values
                or any(value not in core.scope_values.get(dimension_key, frozenset()) for value in typed_values)
            ):
                raise OntologyInfrastructureError(f"Runtime capability {capability['id']!r} has invalid {key}")
            if len(set(typed_values)) != len(typed_values):
                raise OntologyInfrastructureError(f"Runtime capability {capability['id']!r} has duplicate {key}")
        base_models = set(cast(list[object], capability["base_slot_models"]))
        slot_models = set(cast(list[object], capability["slot_models"]))
        if not base_models <= slot_models or capability["food_model"] not in base_models:
            raise OntologyInfrastructureError(
                f"Runtime capability {capability['id']!r} base_slot_models must include its food_model and be supported"
            )
        near_models = capability.get("near_to_model")
        if not isinstance(near_models, list) or not near_models:
            raise OntologyInfrastructureError(
                f"Runtime capability {capability['id']!r} requires near_to_model mappings"
            )
        nears: set[str] = set()
        allowed_models = set(cast(list[object], capability["slot_models"]))
        for mapping in cast(list[object], near_models):
            if not isinstance(mapping, dict):
                raise OntologyInfrastructureError("Runtime near_to_model entries must be mappings")
            near = _required_string(cast(Mapping[str, object], mapping), "near")
            model = _required_string(cast(Mapping[str, object], mapping), "model")
            if (
                near in nears
                or near not in core.scope_values.get("slot_model", frozenset())
                or model not in allowed_models
            ):
                raise OntologyInfrastructureError(
                    f"Runtime capability {capability['id']!r} has invalid near_to_model mapping"
                )
            nears.add(near)
            near_values.add(near)
    return near_values


def _validate_runtime_scoring(records: _RuntimePolicyRecords) -> set[str]:
    scores = records.scoring.get("scores")
    if not isinstance(scores, list) or not scores:
        raise OntologyInfrastructureError("Runtime policy requires effect score records")
    score_levels: set[str] = set()
    for score in scores:
        if not isinstance(score, dict):
            raise OntologyInfrastructureError("Runtime effect scores must be mappings")
        level = _required_string(cast(Mapping[str, object], score), "level")
        value = cast(Mapping[str, object], score).get("score")
        if not isinstance(value, int) or isinstance(value, bool) or level in score_levels:
            raise OntologyInfrastructureError(f"Runtime effect score {level!r} is invalid")
        score_levels.add(level)
    balance_weight = records.scoring.get("balance_weight")
    if (
        not isinstance(balance_weight, (int, float))
        or isinstance(balance_weight, bool)
        or not isfinite(float(balance_weight))
        or balance_weight < 0
    ):
        raise OntologyInfrastructureError("Runtime effect scoring requires non-negative finite balance_weight")
    prefer_with_bonus = records.scoring.get("prefer_with_bonus")
    if not isinstance(prefer_with_bonus, int) or isinstance(prefer_with_bonus, bool) or prefer_with_bonus < 0:
        raise OntologyInfrastructureError("Runtime effect scoring requires non-negative integer prefer_with_bonus")
    advisory_delta = records.scoring.get("advisory_constraint_score_delta")
    if not isinstance(advisory_delta, int) or isinstance(advisory_delta, bool) or advisory_delta > 0:
        raise OntologyInfrastructureError("Runtime effect scoring requires non-positive integer advisory_constraint_score_delta")
    direction = _required_string(records.scoring, "advisory_match_direction")
    if direction not in {"symmetric", "directed"}:
        raise OntologyInfrastructureError("Runtime effect scoring advisory_match_direction must be symmetric or directed")
    return score_levels


def _validate_runtime_tail(records: _RuntimePolicyRecords, core: _RuntimePolicyCore) -> tuple[set[str], set[str]]:
    _validate_runtime_precedence(records, core)
    near_values = _validate_runtime_capabilities(records, core)
    secondary_cap = records.governance.get("secondary_enforcement_cap")
    if secondary_cap is not None and secondary_cap not in core.enforcement_modes:
        raise OntologyInfrastructureError("Runtime assignment governance secondary_enforcement_cap is unknown")
    score_levels = _validate_runtime_scoring(records)
    _validate_runtime_flat_tables(records, core.enforcement_modes, set(core.enforcement_modes_by_role), score_levels)
    return near_values, score_levels


def _load_runtime_policy(
    ontology_root: Path, manifest: Mapping[str, object], schema_view: SchemaView
) -> _PolicyRuntime:
    """Load the typed runtime policy that is authoritative for planner mechanics."""
    records = _load_runtime_policy_records(ontology_root, manifest, schema_view)
    core = _validate_runtime_core(records)
    constraints = _validate_runtime_constraints(records, set(core.enforcement_modes_by_role))
    near_values, score_levels = _validate_runtime_tail(records, core)
    normalized: dict[str, object] = {
        "protocol": records.protocol,
        "fact_fields": list(records.fact_fields),
        "schedule_axes": list(records.schedule_axes),
        "assignment_axes": list(records.assignment_axes),
        "lifecycle_policies": list(records.lifecycle),
        "enforcement_policies": list(records.enforcement),
        "scope_dimensions": list(records.dimensions),
        "scope_rules": list(records.scope_rules),
        "authorities": list(records.authorities),
        "component_authority_rules": list(records.component_authority),
        "competition_rules": list(records.competition_rules),
        "enforcement_projection": list(records.enforcement_projection),
        "effect_remaps": list(records.effect_remaps),
        "assignment_governance": records.governance,
        "effect_scoring": {**records.scoring, "scores": list(cast(list[object], records.scoring["scores"]))},
        "execution_gates": list(records.execution_gates),
        "scope_outcomes": list(records.scope_outcomes),
        "constraint_governance": {
            **records.constraint_governance,
            "lifecycle_states": list(records.constraint_lifecycle),
            "enforcement_modes": list(records.constraint_enforcement),
            "execution_gates": list(records.constraint_execution_gates),
            "allowed_pairs": list(records.constraint_allowed_pairs),
            "execution_policies": list(records.constraint_execution_policies),
        },
        "degradation_rules": list(records.degradation),
        "constraint_precedence": list(records.precedence),
        "capability_rules": list(records.capabilities),
        "runtime_projection": list(records.projection),
    }
    return _PolicyRuntime(
        authored=normalized,
        scope_keys=core.scope_keys,
        scope_values=core.scope_values,
        lifecycle_states=core.lifecycle_states,
        enforcement_modes=core.enforcement_modes,
        enforcement_ranks=core.enforcement_ranks,
        enforcement_executable=core.enforcement_executable,
        enforcement_modes_by_role=core.enforcement_modes_by_role,
        execution_gates=core.execution_gates,
        degradation_rules=core.degradation_rules,
        near_values=near_values,
        score_levels=score_levels,
        constraints=constraints,
    )


def _slot_with_range(schema_view: SchemaView, class_name: str, range_name: str) -> str:
    matches = [
        slot
        for slot in schema_view.class_slots(class_name)
        if schema_view.induced_slot(slot, class_name).range == range_name
    ]
    if len(matches) != 1:
        raise OntologyInfrastructureError(f"{class_name} must define exactly one {range_name} relationship")
    return matches[0]


def _validate_linkml_instance(schema_view: SchemaView, class_name: str, instance: Mapping[str, object]) -> None:
    """Validate one authored instance against the generated LinkML class contract."""
    schema = _require_schema_definition(schema_view.schema)
    document = _json_mapping_from_text(_require_serializer(JsonSchemaGenerator(schema)).serialize())
    definitions = document.get("$defs")
    if not isinstance(definitions, dict) or class_name not in definitions:
        raise OntologyInfrastructureError(f"LinkML schema has no generated class {class_name}")
    typed_definitions = cast(_JsonObject, definitions)
    validator_schema: _JsonObject = {
        "$schema": _JSON_SCHEMA_FORMAT,
        "$ref": f"#/$defs/{class_name}",
        "$defs": typed_definitions,
    }
    validator: _JsonSchemaValidator = cast(
        _JsonSchemaValidator,
        Draft202012Validator(validator_schema),
    )
    errors = sorted(
        validator.iter_errors(dict(instance)),
        key=lambda item: [str(path) for path in item.path],
    )
    if errors:
        detail = "; ".join(error.message for error in errors[:3])
        raise OntologyInfrastructureError(f"Invalid {class_name} instance: {detail}")


def _leaf_paths(value: object, prefix: str = "") -> list[str]:
    """Return structural paths, retaining keys so authored ``<key>`` matches them."""
    if isinstance(value, dict):
        out: list[str] = []
        for raw_key, item in cast(Mapping[object, object], value).items():
            if not isinstance(raw_key, str):
                raise OntologyInfrastructureError("Repository YAML mapping keys must be strings")
            child_prefix = f"{prefix}.{raw_key}" if prefix else raw_key
            if isinstance(item, dict) and not item:
                out.append(child_prefix + "{}")
            else:
                out.extend(_leaf_paths(cast(object, item), child_prefix))
        return out
    if isinstance(value, list):
        if not value:
            return [prefix + "[]"]
        out = []
        for item in cast(list[object], value):
            out.extend(_leaf_paths(item, prefix + "[]"))
        return out
    return [prefix]


def _jsonld_context(schema_view: SchemaView, base_iri: str) -> dict[str, object]:
    context: dict[str, object] = {"ss": base_iri, "@vocab": base_iri, "id": "@id", "type": "@type"}
    for name in sorted(schema_view.all_classes()):
        context[name] = {"@id": f"{base_iri}{name}"}
    for name in sorted(schema_view.all_slots()):
        context[name] = {"@id": f"{base_iri}slot/{name}"}
    return {"@context": context}


def _runtime_projection_source(policy: Mapping[str, object], source: object) -> object:
    if not isinstance(source, str) or not source:
        raise OntologyInfrastructureError("Runtime projection source must be a non-empty string")
    current: object = policy
    for segment in source.split("."):
        if not segment or not isinstance(current, Mapping) or segment not in current:
            raise OntologyInfrastructureError(f"Runtime projection source is missing: {source}")
        current = current[segment]
    return current


def _runtime_projection_tree(
    policy: Mapping[str, object],
    descriptors: object,
    rules: list[dict[str, object]],
    tables: list[dict[str, object]],
    *,
    seen_targets: set[str] | None = None,
    seen_descriptor_ids: set[str] | None = None,
    seen_table_ids: set[str] | None = None,
    seen_sources: dict[str, str] | None = None,
    path: tuple[str, ...] = (),
) -> dict[str, object]:
    if not isinstance(descriptors, list) or not descriptors:
        raise OntologyInfrastructureError("Runtime policy requires non-empty runtime_projection descriptors")
    projected: dict[str, object] = {}
    if seen_targets is None:
        seen_targets = set()
    if seen_descriptor_ids is None:
        seen_descriptor_ids = set()
    if seen_table_ids is None:
        seen_table_ids = set()
    if seen_sources is None:
        seen_sources = {}
    for raw_descriptor in cast(list[object], descriptors):
        if not isinstance(raw_descriptor, Mapping):
            raise OntologyInfrastructureError("Runtime projection descriptors must be mappings")
        descriptor = cast(Mapping[str, object], raw_descriptor)
        descriptor_id = descriptor.get("id")
        target = descriptor.get("target")
        if not isinstance(descriptor_id, str) or not descriptor_id:
            raise OntologyInfrastructureError("Runtime projection descriptor requires id")
        if not isinstance(target, str) or not target:
            raise OntologyInfrastructureError(f"Runtime projection {descriptor_id!r} requires target")
        if descriptor_id in seen_descriptor_ids:
            raise OntologyInfrastructureError(f"Runtime projection has duplicate descriptor id {descriptor_id!r}")
        seen_descriptor_ids.add(descriptor_id)
        qualified_target = ".".join((*path, target))
        if qualified_target in seen_targets:
            raise OntologyInfrastructureError(
                f"Runtime projection has duplicate output path {qualified_target!r}"
            )
        seen_targets.add(qualified_target)
        children = descriptor.get("children")
        source = descriptor.get("source")
        if (children is None) == (source is None):
            raise OntologyInfrastructureError(
                f"Runtime projection {descriptor_id!r} requires exactly one of source or children"
            )
        if children is not None:
            value = _runtime_projection_tree(
                policy,
                children,
                rules,
                tables,
                seen_targets=seen_targets,
                seen_descriptor_ids=seen_descriptor_ids,
                seen_table_ids=seen_table_ids,
                seen_sources=seen_sources,
                path=(*path, target),
            )
        else:
            if not isinstance(source, str) or not source:
                raise OntologyInfrastructureError(f"Runtime projection {descriptor_id!r} source is invalid")
            previous_target = seen_sources.get(source)
            if previous_target == qualified_target:
                raise OntologyInfrastructureError(
                    f"Runtime projection source {source!r} is duplicated at {qualified_target!r}"
                )
            # Reusing one authored source is explicit and safe only when each
            # descriptor writes a distinct fully-qualified output path.
            seen_sources[source] = qualified_target
            value = _runtime_projection_source(policy, source)
        kind = descriptor.get("kind")
        if kind is not None and (not isinstance(kind, str) or not kind):
            raise OntologyInfrastructureError(f"Runtime projection {descriptor_id!r} kind is invalid")
        if isinstance(kind, str):
            if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
                raise OntologyInfrastructureError(
                    f"Runtime projection {descriptor_id!r} kind requires a list of mappings"
                )
            rules.extend([{"kind": kind, **dict(cast(Mapping[str, object], item))} for item in value])
        emit_table = descriptor.get("emit_table", False)
        if not isinstance(emit_table, bool):
            raise OntologyInfrastructureError(f"Runtime projection {descriptor_id!r} emit_table is invalid")
        if emit_table:
            if not isinstance(value, list) or not value or not all(isinstance(item, Mapping) for item in value):
                raise OntologyInfrastructureError(
                    f"Runtime projection {descriptor_id!r} table requires a non-empty list of mappings"
                )
            if descriptor_id in seen_table_ids:
                raise OntologyInfrastructureError(f"Runtime projection has duplicate table id {descriptor_id!r}")
            seen_table_ids.add(descriptor_id)
            rows = value
            tables.append({"id": descriptor_id, "rows": rows})
        projected[target] = value
    return projected


def _runtime_program(
    ontology_root: Path,
    manifest: Mapping[str, object],
    policy: Mapping[str, object],
    source_hash: str,
) -> dict[str, object]:
    """Render a deterministic, provenance-bearing executable runtime program."""
    policy_path = _catalog_path(ontology_root, manifest, "runtime_policy")
    policy_bytes = policy_path.read_bytes()
    try:
        relative_source = policy_path.relative_to(ontology_root.parent).as_posix()
    except ValueError as error:
        raise OntologyInfrastructureError("Manifest runtime policy path must be repository-relative") from error
    rules: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    projected = _runtime_projection_tree(policy, policy.get("runtime_projection"), rules, tables)
    protocol = policy.get("protocol")
    if not isinstance(protocol, Mapping):
        raise OntologyInfrastructureError("Runtime policy requires authored protocol inventory")
    protocol_map = dict(cast(Mapping[str, object], protocol))
    required_protocol = {"condition_classes", "action_classes", "gate_classes", "policy_class"}
    if set(protocol_map) != required_protocol:
        raise OntologyInfrastructureError("Runtime policy protocol inventory has an invalid shape")
    for field in ("condition_classes", "action_classes", "gate_classes"):
        values = protocol_map[field]
        if not isinstance(values, list) or not values or not all(isinstance(item, str) and item for item in values):
            raise OntologyInfrastructureError(f"Runtime policy protocol {field} must be a non-empty list of strings")
    if not isinstance(protocol_map["policy_class"], str) or not protocol_map["policy_class"]:
        raise OntologyInfrastructureError("Runtime policy protocol policy_class must be a non-empty string")
    program = {
        "format_version": _RUNTIME_PROGRAM_FORMAT,
        "schema_version": str(manifest["schema_version"]),
        "source_hash": source_hash,
        "provenance": {
            "source": relative_source,
            "source_sha256": hashlib.sha256(policy_bytes).hexdigest(),
            "manifest_schema_version": str(manifest["schema_version"]),
            "compiler_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "protocol": protocol_map,
        # The descriptor tree is the sole authored topology.  Keep the
        # compiler output generic so adding a policy branch requires only a
        # descriptor edit, not another Python section.
        "projection": projected,
        "rules": rules,
        "tables": tables,
    }
    _validate_runtime_program_output(program)
    return program


def _validate_runtime_program_output(program: Mapping[str, object]) -> None:
    """Validate the closed generic runtime-program envelope before emission."""
    required = {
        "format_version", "schema_version", "source_hash", "provenance", "protocol", "projection", "rules", "tables"
    }
    if set(program) != required:
        raise OntologyInfrastructureError("Runtime program has an invalid top-level shape")
    provenance = program["provenance"]
    if not isinstance(provenance, Mapping) or set(provenance) != {
        "source", "source_sha256", "manifest_schema_version", "compiler_sha256"
    }:
        raise OntologyInfrastructureError("Runtime program provenance has an invalid shape")
    for key in provenance:
        if not isinstance(provenance[key], str) or not provenance[key]:
            raise OntologyInfrastructureError(f"Runtime program provenance {key} must be a non-empty string")
    projection = program["projection"]
    if not isinstance(projection, Mapping):
        raise OntologyInfrastructureError("Runtime program projection must be a mapping")
    rules = program["rules"]
    if not isinstance(rules, list):
        raise OntologyInfrastructureError("Runtime program rules must be a list")
    rule_ids: set[tuple[str, str]] = set()
    for index, item in enumerate(rules):
        if not isinstance(item, Mapping):
            raise OntologyInfrastructureError(f"Runtime program rule {index} must be a mapping")
        identifier = item.get("id")
        kind = item.get("kind")
        if not isinstance(identifier, str) or not identifier or not isinstance(kind, str) or not kind:
            raise OntologyInfrastructureError(f"Runtime program rule {index} requires id and kind")
        key = (kind, identifier)
        if key in rule_ids:
            raise OntologyInfrastructureError(f"Runtime program has duplicate rule id {kind}:{identifier}")
        rule_ids.add(key)
    tables = program["tables"]
    if not isinstance(tables, list) or not tables:
        raise OntologyInfrastructureError("Runtime program tables must be a non-empty list")
    table_ids: set[str] = set()
    for index, item in enumerate(tables):
        if not isinstance(item, Mapping) or set(item) != {"id", "rows"}:
            raise OntologyInfrastructureError(f"Runtime program table {index} has an invalid shape")
        identifier = item.get("id")
        rows = item.get("rows")
        if not isinstance(identifier, str) or not identifier or identifier in table_ids:
            raise OntologyInfrastructureError(f"Runtime program table {index} has an invalid or duplicate id")
        if not isinstance(rows, list) or not rows or not all(isinstance(row, Mapping) for row in rows):
            raise OntologyInfrastructureError(f"Runtime program table {identifier!r} requires non-empty mapping rows")
        table_ids.add(identifier)


def _canonical_shapes(schema_view: SchemaView) -> str:  # noqa: PLR0914, PLR0915
    """Canonicalize LinkML SHACL output (including generated blank nodes)."""
    schema = _require_schema_definition(schema_view.schema)
    serializer = _require_serializer(ShaclGenerator(schema))
    generated = serializer.serialize()
    if not isinstance(generated, str):
        raise OntologyInfrastructureError("LinkML SHACL serializer returned a non-text document")
    graph = Graph()
    graph.parse(data=generated, format="turtle")
    # LinkML assigns presentation-only sh:order values while iterating sets of
    # slots.  They are not validation semantics and otherwise make equivalent
    # graphs differ across fresh interpreter processes.
    order_triples = _validated_rdf_triples(graph.triples((None, SH.order, None)))
    for triple in order_triples:
        graph.remove(triple)
    # The same set iteration also changes the order of members in RDF lists
    # used by generated ``sh:or``/``sh:ignoredProperties`` constraints.  Those
    # lists are set-like in this generated contract; rewrite each list's
    # members in lexical RDF term order while preserving its list nodes.
    list_first = {subject: obj for subject, _, obj in _validated_rdf_triples(graph.triples((None, RDF.first, None)))}
    list_rest = {subject: obj for subject, _, obj in _validated_rdf_triples(graph.triples((None, RDF.rest, None)))}
    list_heads = {
        obj for _, predicate, obj in _validated_rdf_triples(graph) if predicate != RDF.rest and obj in list_first
    }
    for head in list_heads:
        nodes: list[Node] = []
        current = head
        while current in list_first and current not in nodes:
            nodes.append(current)
            current = list_rest.get(current, RDF.nil)
        if not nodes or current != RDF.nil:
            continue
        members = sorted((list_first[node] for node in nodes), key=lambda item: item.n3())
        for node, member in zip(nodes, members, strict=True):
            graph.remove((node, RDF.first, None))
            graph.add((node, RDF.first, member))
    graph_triples = _validated_rdf_triples(graph)
    bnodes = {node for triple in graph_triples for node in triple if isinstance(node, BNode)}
    labels: dict[BNode, str] = dict.fromkeys(bnodes, "_")

    def token(node: object) -> str:
        if isinstance(node, BNode):
            return f"_:{labels[node]}"
        if not isinstance(node, Node):
            raise OntologyInfrastructureError("RDF graph contains an invalid node")
        return node.n3()

    # Iterative neighborhood hashing gives each SHACL property/list node a
    # stable identity based only on graph content, never parser-generated
    # blank-node IDs or set iteration order.
    for _ in range(max(1, len(bnodes))):
        updated: dict[BNode, str] = {}
        for node in bnodes:
            neighborhood: list[str] = []
            for subject, predicate, obj in graph_triples:
                if subject == node:
                    neighborhood.append(f"out|{predicate.n3()}|{token(obj)}")
                if obj == node:
                    neighborhood.append(f"in|{token(subject)}|{predicate.n3()}")
            updated[node] = hashlib.sha256("\n".join(sorted(neighborhood)).encode("utf-8")).hexdigest()
        labels = updated
        if len(set(labels.values())) == len(labels):
            break
    if len(set(labels.values())) != len(labels):
        raise OntologyInfrastructureError("Generated SHACL contains symmetric blank-node components")
    triples = sorted(
        " ".join(token(node) for node in (subject, predicate, obj)) + " ." for subject, predicate, obj in graph_triples
    )
    prefixes = "\n".join(sorted(line for line in generated.splitlines() if line.startswith("@prefix ")))
    prefixes_value = cast(object, schema.prefixes)
    if not isinstance(prefixes_value, dict):
        raise OntologyInfrastructureError("LinkML schema has no prefix mapping")
    prefix_entry = cast(Mapping[object, object], prefixes_value).get("ss")
    if not isinstance(prefix_entry, Prefix):
        raise OntologyInfrastructureError("LinkML schema has no ss prefix")
    base_iri = str(prefix_entry.prefix_reference)
    aliases = [
        f"<{base_iri}{name}Shape> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/ns/shacl#NodeShape> ."
        for name in sorted(schema_view.all_classes())
    ]
    aliases.extend(
        f"<{base_iri}{name}Shape> <http://www.w3.org/ns/shacl#targetClass> <{base_iri}{name}> ."
        for name in sorted(schema_view.all_classes())
    )
    return prefixes + "\n\n" + "\n".join(sorted([*triples, *aliases])) + "\n"


def _source_hash(ontology_root: Path, manifest: Mapping[str, object]) -> str:
    paths = ["ontology/" + _MANIFEST_NAME, _required_string(manifest, "linkml_root")]
    paths.extend(_required_string_list(manifest, "linkml_modules"))
    paths.extend(str(c["path"]) for c in cast(list[dict[str, object]], manifest.get("catalogs", [])))
    digest = hashlib.sha256()
    for relative_path in paths:
        path = ontology_root.parent / relative_path
        if not path.is_file():
            raise OntologyInfrastructureError(f"Manifest declares missing ontology source: {path}")
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _normalized_terms(vocabulary: Mapping[str, object]) -> list[dict[str, object]]:
    categories = _required_mapping(vocabulary, "semantic_categories")
    raw_terms = vocabulary.get("terms")
    if not isinstance(raw_terms, list):
        raise OntologyInfrastructureError("vocabulary.yaml terms must be a list")
    normalized: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for raw_term in raw_terms:
        if not isinstance(raw_term, dict):
            raise OntologyInfrastructureError("Each ontology term must be a mapping")
        term = cast(dict[str, object], raw_term)
        slug = _required_string(term, "slug")
        category = _required_string(term, "semantic_category")
        if category not in categories:
            raise OntologyInfrastructureError(f"Term {slug!r} has unknown semantic category {category!r}")
        key = (category, slug)
        if key in seen:
            raise OntologyInfrastructureError(f"Duplicate ontology term {category}:{slug}")
        seen.add(key)
        category_metadata = _required_mapping(cast(Mapping[str, object], categories), category)
        assertion_kind = term.get("assertion_kind")
        if assertion_kind is not None and (not isinstance(assertion_kind, str) or not assertion_kind):
            raise OntologyInfrastructureError(f"Term {category}:{slug} has an invalid assertion_kind")
        normalized_term: dict[str, object] = {
            "slug": slug,
            "label": _required_string(term, "label"),
            "description": _required_string(term, "description"),
            "semantic_category": category,
            "allowed_predicates": _required_string_list(category_metadata, "allowed_predicates"),
            "ontoclean_profile": _required_string(category_metadata, "ontoclean_profile"),
        }
        if assertion_kind is not None:
            normalized_term["assertion_kind"] = assertion_kind
        normalized.append(normalized_term)
    return sorted(normalized, key=lambda item: (str(item["semantic_category"]), str(item["slug"])))


def _scheduling_policy_category_aliases(categories: Mapping[str, object]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for canonical, metadata in categories.items():
        if not isinstance(canonical, str) or not isinstance(metadata, dict):
            continue
        predicates = cast(Mapping[str, object], metadata).get("allowed_predicates")
        if isinstance(predicates, list):
            for predicate in predicates:
                if isinstance(predicate, str) and predicate.startswith("schedule."):
                    aliases[predicate.split(".", maxsplit=1)[1]] = canonical
    return aliases


def _load_scheduling_policies(
    ontology_root: Path,
    manifest: Mapping[str, object],
    terms: Sequence[Mapping[str, object]],
    categories: Mapping[str, object],
    policy_runtime: _PolicyRuntime,
) -> dict[str, dict[str, object]]:
    """Load the planner policy contract from manifest-owned canonical sources.

    The deliberately broad name includes risk warnings: they are planner policy
    facts, even though they do not affect slot scoring.  Runtime consumers get a
    stable flat ``category:term`` key and never need a separate card registry.
    """
    known_terms = {(str(term["semantic_category"]), str(term["slug"])): term for term in terms}
    category_aliases = _scheduling_policy_category_aliases(categories)
    runtime = _governance_runtime_from_policy(policy_runtime)
    policies: dict[str, dict[str, object]] = {}
    for relative_path in _catalog_paths(ontology_root, manifest, "policies"):
        source = _load_yaml_mapping(_source_path(ontology_root, relative_path))
        raw_policies = _required_mapping(source, "scheduling_policies")
        governance = _policy_governance_defaults(source, relative_path)
        evidence_catalog = _required_mapping(source, "slot_policy_evidence")
        for key, raw_policy in raw_policies.items():
            if not isinstance(key, str) or key.count(":") != 1:
                raise OntologyInfrastructureError(f"Policy key must be category:term in {relative_path}: {key!r}")
            category, term = key.split(":", maxsplit=1)
            term_metadata = known_terms.get((category_aliases.get(category, category), term))
            if term_metadata is None:
                raise OntologyInfrastructureError(f"Policy {key!r} has no controlled vocabulary term")
            if str(term_metadata["semantic_category"]) not in categories:
                raise OntologyInfrastructureError(f"Policy {key!r} must target a controlled semantic category")
            if key in policies:
                raise OntologyInfrastructureError(f"Duplicate canonical scheduling policy {key!r}")
            if not isinstance(raw_policy, dict):
                raise OntologyInfrastructureError(f"Policy {key!r} must be a mapping")
            policies[key] = _normalize_scheduling_policy(
                key,
                cast(Mapping[str, object], raw_policy),
                _SchedulingPolicyContext(
                    term_metadata,
                    governance,
                    evidence_catalog,
                    runtime,
                    policy_runtime.near_values,
                    policy_runtime.score_levels,
                ),
            )
    return dict(sorted(policies.items()))


def _load_audit_review_rules(
    ontology_root: Path, manifest: Mapping[str, object], policy_runtime: _PolicyRuntime
) -> list[dict[str, object]]:
    rules: list[dict[str, object]] = []
    seen: set[str] = set()
    for relative_path in _catalog_paths(ontology_root, manifest, "policies"):
        source = _load_yaml_mapping(_source_path(ontology_root, relative_path))
        raw_rules = _required_mapping(source, "audit_review_rules")
        context = _AuditReviewContext(_required_mapping(source, "slot_policy_evidence"), policy_runtime)
        for rule_id, raw in raw_rules.items():
            if not isinstance(rule_id, str) or not rule_id.startswith("audit_") or rule_id in seen:
                raise OntologyInfrastructureError(
                    f"Audit review rule id must be unique and start with audit_: {rule_id!r}"
                )
            if not isinstance(raw, dict):
                raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} must be a mapping")
            rules.append(
                _normalize_audit_review_rule(
                    rule_id,
                    cast(Mapping[str, object], raw),
                    context,
                )
            )
            seen.add(rule_id)
    return sorted(rules, key=lambda item: str(item["id"]))


def _normalize_audit_review_rule(
    rule_id: str,
    raw_mapping: Mapping[str, object],
    context: _AuditReviewContext,
) -> dict[str, object]:
    allowed = {
        "priority",
        "axis",
        "predicate",
        "subjects",
        "message",
        "action",
        "effects",
        "status",
        "enforcement",
        "scope",
        "evidence",
        "owner",
        "review_by",
        "evidence_gap",
        "retirement_reason",
    }
    extras = sorted(set(raw_mapping) - allowed)
    if extras:
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} has unsupported fields: {', '.join(extras)}")
    axis = raw_mapping.get("axis")
    if axis not in {"intake", "timing", "activity"}:
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} axis is invalid")
    predicate = raw_mapping.get("predicate")
    if predicate != "reviewed_disposition_present":
        raise OntologyInfrastructureError(
            f"Audit review rule {rule_id!r} predicate must be reviewed_disposition_present"
        )
    priority = raw_mapping.get("priority")
    if not isinstance(priority, int) or isinstance(priority, bool) or priority < 0:
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} priority must be a non-negative integer")
    subjects_raw = raw_mapping.get("subjects")
    if not isinstance(subjects_raw, dict):
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} subjects must be a mapping")
    expected_scope = raw_mapping.get("scope")
    if not isinstance(expected_scope, dict):
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} scope must be a mapping")
    governance_runtime = _governance_runtime_from_policy(context.policy_runtime)
    executable_lifecycle_states = {
        state for state, gate in context.policy_runtime.execution_gates.items() if gate.get("executable") is True
    }
    if raw_mapping.get("status") in executable_lifecycle_states and not subjects_raw:
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} requires live subjects")
    subjects: dict[str, dict[str, object]] = {}
    for subject_id, disposition in subjects_raw.items():
        if not isinstance(subject_id, str) or not subject_id.startswith("sub_") or not isinstance(disposition, dict):
            raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} has invalid subject disposition")
        subjects[subject_id] = _normalize_audit_subject(
            rule_id,
            cast(Mapping[str, object], disposition),
            context,
            cast(Mapping[str, object], expected_scope),
        )
    return {
        "id": rule_id,
        "priority": priority,
        "axis": axis,
        "predicate": predicate,
        "subjects": dict(sorted(subjects.items())),
        "message": _required_string(raw_mapping, "message"),
        "action": _required_string(raw_mapping, "action"),
        "effects": [],
        **_normalize_record_governance(
            f"audit rule {rule_id}",
            raw_mapping,
            _RecordGovernanceContext(
                catalog=context.evidence_catalog,
                effects=[],
                warning=raw_mapping.get("enforcement") == governance_runtime.enforcement_modes_by_role.get("warning"),
                runtime=governance_runtime,
            ),
        ),
    }


def _normalize_audit_subject(
    rule_id: str,
    raw: Mapping[str, object],
    context: _AuditReviewContext,
    expected_scope: Mapping[str, object],
) -> dict[str, object]:
    disposition = raw.get("disposition")
    if disposition == "governed_assignment":
        if set(raw) != {"disposition"}:
            raise OntologyInfrastructureError(
                f"Audit review rule {rule_id!r} governed assignment must contain only disposition"
            )
        return {"disposition": disposition}
    allowed = {"disposition", "status", "scope", "evidence", "owner", "review_by", "evidence_gap"}
    required = allowed - {"evidence_gap"}
    if disposition != "reviewed_no_assignment" or set(raw) - allowed or not required <= set(raw):
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} has invalid disposition shape")
    status = raw.get("status")
    evidence = raw.get("evidence")
    executable_lifecycle_states = {
        state for state, gate in context.policy_runtime.execution_gates.items() if gate.get("executable") is True
    }
    if not isinstance(status, str) or status not in executable_lifecycle_states or raw.get("scope") != expected_scope:
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} no-assignment lifecycle/scope is invalid")
    if not isinstance(evidence, list):
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} no-assignment evidence must be a list")
    _validate_evidence_entries(f"audit rule {rule_id} subject", cast(list[object], evidence), context.evidence_catalog)
    gap = raw.get("evidence_gap")
    requirement = context.policy_runtime.execution_gates[cast(str, status)].get("evidence_requirement")
    if requirement == "required" and not evidence:
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} approved no-assignment requires evidence")
    if requirement == "evidence_or_gap" and not evidence and (not isinstance(gap, str) or not gap):
        raise OntologyInfrastructureError(
            f"Audit review rule {rule_id!r} pending no-assignment requires evidence or gap"
        )
    if not isinstance(raw.get("owner"), str) or not raw["owner"]:
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} no-assignment owner is invalid")
    review_by = raw.get("review_by")
    if not isinstance(review_by, str) or len(review_by) != 10:  # noqa: PLR2004
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} no-assignment review_by is invalid")
    return dict(raw)


def _validate_evidence_entries(context: str, evidence: list[object], catalog: Mapping[str, object]) -> None:
    for item_obj in evidence:
        if not isinstance(item_obj, dict):
            raise OntologyInfrastructureError(f"{context} evidence entries must be mappings")
        item = cast(Mapping[str, object], item_obj)
        if set(item) != {"source", "supports", "limitations"}:
            raise OntologyInfrastructureError(f"{context} evidence entries require source/supports/limitations")
        if item.get("source") not in catalog:
            raise OntologyInfrastructureError(f"{context} references unknown evidence source {item.get('source')!r}")
        if any(not isinstance(item.get(key), str) or not item[key] for key in ("supports", "limitations")):
            raise OntologyInfrastructureError(f"{context} evidence entries require supports and limitations")


def _load_audit_relation_exemptions(ontology_root: Path, manifest: Mapping[str, object]) -> list[dict[str, object]]:
    exemptions: list[dict[str, object]] = []
    seen: set[str] = set()
    seen_selectors: set[tuple[str, str, str]] = set()
    for relative_path in _catalog_paths(ontology_root, manifest, "policies"):
        source = _load_yaml_mapping(_source_path(ontology_root, relative_path))
        raw_exemptions = _required_mapping(source, "audit_relation_exemptions")
        governance = _policy_governance_defaults(source, relative_path)
        for exemption_id, raw in raw_exemptions.items():
            if (
                not isinstance(exemption_id, str)
                or not exemption_id.startswith("audit_relation_")
                or exemption_id in seen
            ):
                raise OntologyInfrastructureError(
                    f"Audit relation exemption id must be unique and start with audit_relation_: {exemption_id!r}"
                )
            if not isinstance(raw, dict):
                raise OntologyInfrastructureError(f"Audit relation exemption {exemption_id!r} must be a mapping")
            raw_mapping = cast(Mapping[str, object], raw)
            allowed = {"relation_type", "source_selector_key", "target_selector_key", "rationale", "action"}
            extras = sorted(set(raw_mapping) - allowed)
            if extras:
                raise OntologyInfrastructureError(
                    f"Audit relation exemption {exemption_id!r} has unsupported fields: {', '.join(extras)}"
                )
            relation_type = _required_string(raw_mapping, "relation_type")
            source_key = _required_string(raw_mapping, "source_selector_key")
            target_key = _required_string(raw_mapping, "target_selector_key")
            selector_key = (relation_type, source_key, target_key)
            if selector_key in seen_selectors:
                raise OntologyInfrastructureError(
                    f"Duplicate audit relation exemption selector: {relation_type} {source_key} -> {target_key}"
                )
            normalized: dict[str, object] = {
                "id": exemption_id,
                "relation_type": relation_type,
                "source_selector_key": source_key,
                "target_selector_key": target_key,
                "rationale": _required_string(raw_mapping, "rationale"),
                "action": _required_string(raw_mapping, "action"),
                **governance,
            }
            exemptions.append(normalized)
            seen.add(exemption_id)
            seen_selectors.add(selector_key)
    return sorted(exemptions, key=lambda item: str(item["id"]))


def _policy_governance_defaults(source: Mapping[str, object], relative_path: str) -> dict[str, object]:
    raw = source.get("governance_defaults")
    if isinstance(raw, dict):
        return cast(dict[str, object], raw)
    return {}


@dataclass(frozen=True)
class _GovernanceRuntime:
    scope_keys: Sequence[str]
    scope_values: Mapping[str, frozenset[str]]
    lifecycle_states: set[str]
    enforcement_modes: set[str]
    enforcement_ranks: Mapping[str, int]
    enforcement_executable: Mapping[str, bool]
    enforcement_modes_by_role: Mapping[str, str]
    execution_gates: Mapping[str, Mapping[str, object]]
    degradation_rules: Mapping[tuple[str, str], Mapping[str, object]]


@dataclass(frozen=True)
class _EvidenceUriFormat:
    scheme: str
    require_host: bool
    forbid_userinfo: bool


@dataclass(frozen=True)
class _ConstraintRuntime:
    lifecycle_states: set[str]
    enforcement_modes: set[str]
    allowed_pairs: set[tuple[str, str]]
    execution_gates: Mapping[str, Mapping[str, object]]
    evidence_format: _EvidenceUriFormat
    execution_policies: Mapping[str, Mapping[str, object]]


@dataclass(frozen=True)
class _PolicyRuntime:
    authored: dict[str, object]
    scope_keys: tuple[str, ...]
    scope_values: Mapping[str, frozenset[str]]
    lifecycle_states: set[str]
    enforcement_modes: set[str]
    enforcement_ranks: Mapping[str, int]
    enforcement_executable: Mapping[str, bool]
    enforcement_modes_by_role: Mapping[str, str]
    execution_gates: Mapping[str, Mapping[str, object]]
    degradation_rules: Mapping[tuple[str, str], Mapping[str, object]]
    near_values: set[str]
    score_levels: set[str]
    constraints: _ConstraintRuntime


@dataclass(frozen=True)
class _AuditReviewContext:
    evidence_catalog: Mapping[str, object]
    policy_runtime: _PolicyRuntime


@dataclass(frozen=True)
class _RecordGovernanceContext:
    catalog: Mapping[str, object]
    runtime: _GovernanceRuntime
    effects: list[object]
    warning: bool


@dataclass(frozen=True)
class _SchedulingPolicyContext:
    term_metadata: Mapping[str, object]
    governance: Mapping[str, object]
    evidence_catalog: Mapping[str, object]
    runtime: _GovernanceRuntime
    near_values: set[str]
    score_levels: set[str]


def _governance_runtime_from_policy(policy_runtime: _PolicyRuntime) -> _GovernanceRuntime:
    return _GovernanceRuntime(
        scope_keys=policy_runtime.scope_keys,
        scope_values=policy_runtime.scope_values,
        lifecycle_states=policy_runtime.lifecycle_states,
        enforcement_modes=policy_runtime.enforcement_modes,
        enforcement_ranks=policy_runtime.enforcement_ranks,
        enforcement_executable=policy_runtime.enforcement_executable,
        enforcement_modes_by_role=policy_runtime.enforcement_modes_by_role,
        execution_gates=policy_runtime.execution_gates,
        degradation_rules=policy_runtime.degradation_rules,
    )


def _normalize_scheduling_policy(
    key: str,
    raw: Mapping[str, object],
    policy_context: _SchedulingPolicyContext,
) -> dict[str, object]:
    allowed = {
        "applies_when",
        "effects",
        "warning",
        "action",
        "status",
        "enforcement",
        "scope",
        "evidence",
        "owner",
        "review_by",
        "evidence_gap",
        "retirement_reason",
    }
    extras = sorted(set(raw) - allowed)
    if extras:
        raise OntologyInfrastructureError(f"Policy {key!r} has unsupported fields: {', '.join(extras)}")
    normalized: dict[str, object] = {
        "label": _required_string(policy_context.term_metadata, "label"),
        "description": _required_string(policy_context.term_metadata, "description"),
        "applies_when": _required_string(raw, "applies_when"),
    }
    effects_raw = raw.get("effects", [])
    if not isinstance(effects_raw, list):
        raise OntologyInfrastructureError(f"Policy {key!r} effects must be a list")
    normalized["effects"] = [
        _normalize_policy_effect(key, cast(object, item), policy_context.near_values, policy_context.score_levels)
        for item in effects_raw
    ]
    warning = raw.get("warning", False)
    if not isinstance(warning, bool):
        raise OntologyInfrastructureError(f"Policy {key!r} warning must be boolean")
    normalized["warning"] = warning
    action = raw.get("action")
    if action is not None:
        if not isinstance(action, str) or not action:
            raise OntologyInfrastructureError(f"Policy {key!r} action must be a non-empty string")
        normalized["action"] = action
    normalized.update(
        _normalize_record_governance(
            f"policy {key}",
            raw,
            _RecordGovernanceContext(
                catalog=policy_context.evidence_catalog,
                effects=cast(list[object], normalized["effects"]),
                warning=warning,
                runtime=policy_context.runtime,
            ),
        )
    )
    return normalized


def _load_evidence_catalog(source_path: Path) -> dict[str, dict[str, object]]:
    source = _load_yaml_mapping(source_path)
    raw = _required_mapping(source, "slot_policy_evidence")
    out: dict[str, dict[str, object]] = {}
    for key, item in raw.items():
        if not isinstance(key, str) or not isinstance(item, dict):
            raise OntologyInfrastructureError("Evidence catalog keys and records must be mappings")
        record = cast(Mapping[str, object], item)
        allowed = {"kind", "url", "ref", "title", "supports", "limitations"}
        if set(record) - allowed or ("url" in record) == ("ref" in record):
            raise OntologyInfrastructureError(f"Evidence {key!r} must contain exactly one of url/ref")
        kind = _required_string(record, "kind")
        if kind not in {
            "authoritative_instruction",
            "primary_human",
            "systematic_review",
            "regulatory_context",
            "operational_contract",
        }:
            raise OntologyInfrastructureError(f"Evidence {key!r} has invalid kind")
        if "url" in record:
            value = _required_string(record, "url")
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.netloc:
                raise OntologyInfrastructureError(f"Evidence {key!r} url must be HTTPS")
        else:
            value = _required_string(record, "ref")
            if value.startswith(("/", "http")):
                raise OntologyInfrastructureError(f"Evidence {key!r} ref must be repository-relative")
        for text_field in ("title", "supports", "limitations"):
            _required_string(record, text_field)
        out[key] = {
            k: record[k] for k in ("kind", "url" if "url" in record else "ref", "title", "supports", "limitations")
        }
    return dict(sorted(out.items()))


def _normalize_record_governance(
    context: str,
    raw: Mapping[str, object],
    governance_context: _RecordGovernanceContext,
) -> dict[str, object]:
    runtime = governance_context.runtime
    status, enforcement = _governance_status(context, raw, runtime.lifecycle_states, runtime.enforcement_modes)
    scope = _governance_scope(context, raw, runtime.scope_keys, runtime.scope_values)
    evidence = _governance_evidence(context, raw, governance_context.catalog)
    _validate_governance_evidence_lifecycle(context, raw, status, evidence, runtime.execution_gates)
    _validate_governance_effects(
        context,
        status,
        enforcement,
        runtime.enforcement_ranks,
        runtime.degradation_rules,
    )
    _validate_review_date(context, raw)
    actual_enforcement = _declared_enforcement(
        governance_context.effects,
        governance_context.warning,
        runtime.enforcement_modes_by_role,
    )
    _validate_governance_execution_gate(
        context,
        status,
        actual_enforcement,
        runtime.execution_gates,
        runtime.enforcement_executable,
    )
    if actual_enforcement != enforcement:
        raise OntologyInfrastructureError(f"{context} enforcement does not match effects")
    return _governance_result(raw, status, enforcement, scope, evidence)


def _governance_status(
    context: str,
    raw: Mapping[str, object],
    lifecycle_states: set[str] | None,
    enforcement_modes: set[str] | None,
) -> tuple[str, str]:
    status = _required_string(raw, "status")
    enforcement = _required_string(raw, "enforcement")
    if lifecycle_states is None or enforcement_modes is None:
        raise OntologyInfrastructureError(f"{context} requires runtime policy vocabularies")
    if status not in lifecycle_states or enforcement not in enforcement_modes:
        raise OntologyInfrastructureError(f"{context} has invalid status/enforcement")
    return status, enforcement


def _governance_scope(
    context: str,
    raw: Mapping[str, object],
    scope_keys: Sequence[str],
    scope_values: Mapping[str, frozenset[str]],
) -> Mapping[str, object]:
    scope = cast(Mapping[str, object], _required_mapping(raw, "scope"))
    if (
        not scope
        or set(scope) - set(scope_keys)
        or any(
            not isinstance(v, str) or not v or v not in scope_values.get(key, frozenset()) for key, v in scope.items()
        )
    ):
        raise OntologyInfrastructureError(f"{context} has invalid scope")
    return scope


def _governance_evidence(context: str, raw: Mapping[str, object], catalog: Mapping[str, object]) -> list[object]:
    evidence = raw.get("evidence")
    if not isinstance(evidence, list):
        raise OntologyInfrastructureError(f"{context} evidence must be a list")
    for item_obj in cast(list[object], evidence):
        _validate_governance_evidence_item(context, item_obj, catalog)
    return cast(list[object], evidence)


def _validate_governance_evidence_item(context: str, item_obj: object, catalog: Mapping[str, object]) -> None:
    if not isinstance(item_obj, dict):
        raise OntologyInfrastructureError(f"{context} evidence entries must be source/supports/limitations mappings")
    item = cast(Mapping[str, object], item_obj)
    if set(item) - {"source", "supports", "limitations"}:
        raise OntologyInfrastructureError(f"{context} evidence entries must be source/supports/limitations mappings")
    source = item.get("source")
    if not isinstance(source, str) or source not in catalog:
        raise OntologyInfrastructureError(f"{context} references unknown evidence source {source!r}")
    if any(not isinstance(item.get(key), str) or not item[key] for key in ("supports", "limitations")):
        raise OntologyInfrastructureError(f"{context} evidence entries require supports and limitations")


def _validate_governance_evidence_lifecycle(
    context: str,
    raw: Mapping[str, object],
    status: str,
    evidence: list[object],
    execution_gates: Mapping[str, Mapping[str, object]],
) -> None:
    gate = execution_gates.get(status)
    if gate is None:
        raise OntologyInfrastructureError(f"{context} has no execution gate for status {status!r}")
    requirement = _required_string(gate, "evidence_requirement")
    if requirement == "required" and not evidence:
        raise OntologyInfrastructureError(f"{context} status {status!r} requires non-empty evidence")
    if requirement == "evidence_or_gap" and not evidence and not raw.get("evidence_gap"):
        raise OntologyInfrastructureError(f"{context} status {status!r} requires evidence or evidence_gap")
    if requirement == "prohibited" and (evidence or raw.get("evidence_gap")):
        raise OntologyInfrastructureError(f"{context} status {status!r} prohibits evidence and evidence_gap")


def _validate_governance_effects(
    context: str,
    status: str,
    enforcement: str,
    enforcement_ranks: Mapping[str, int],
    degradation_rules: Mapping[tuple[str, str], Mapping[str, object]],
) -> None:
    rule = degradation_rules.get((status, enforcement))
    if rule is None:
        raise OntologyInfrastructureError(
            f"{context} has no degradation rule for status/enforcement {(status, enforcement)!r}"
        )
    effective = _required_string(rule, "effective_mode")
    if enforcement not in enforcement_ranks or effective not in enforcement_ranks:
        raise OntologyInfrastructureError(f"{context} has unknown enforcement degradation vocabulary")


def _validate_governance_execution_gate(
    context: str,
    status: str,
    actual_enforcement: str,
    execution_gates: Mapping[str, Mapping[str, object]],
    enforcement_executable: Mapping[str, bool],
) -> None:
    gate = execution_gates.get(status)
    if gate is None or not isinstance(gate.get("executable"), bool):
        raise OntologyInfrastructureError(f"{context} has no valid execution gate for status {status!r}")
    actual_executable = enforcement_executable.get(actual_enforcement)
    if actual_executable is None:
        raise OntologyInfrastructureError(f"{context} has unknown executable enforcement vocabulary")
    if gate["executable"] is False and actual_executable:
        raise OntologyInfrastructureError(
            f"{context} status {status!r} is non-executable but effects require executable enforcement"
        )


def _validate_review_date(context: str, raw: Mapping[str, object]) -> None:
    if "review_by" not in raw or not isinstance(raw["review_by"], str) or len(raw["review_by"]) != 10:  # noqa: PLR2004
        raise OntologyInfrastructureError(f"{context} review_by must be YYYY-MM-DD")


def _declared_enforcement(effects: list[object], warning: bool, modes_by_role: Mapping[str, str]) -> str:
    role = "none"
    if any(isinstance(e, dict) and cast(Mapping[str, object], e).get("block") is True for e in effects):
        role = "blocking"
    elif effects:
        role = "scored"
    elif warning:
        role = "warning"
    if role not in modes_by_role:
        raise OntologyInfrastructureError(f"Missing runtime enforcement mode for effect role {role!r}")
    return modes_by_role[role]


def _governance_result(
    raw: Mapping[str, object],
    status: str,
    enforcement: str,
    scope: Mapping[str, object],
    evidence: list[object],
) -> dict[str, object]:
    result = {
        "status": status,
        "enforcement": enforcement,
        "scope": dict(scope),
        "evidence": evidence,
        "owner": _required_string(raw, "owner"),
        "review_by": raw["review_by"],
    }
    for key in ("evidence_gap", "retirement_reason"):
        if key in raw:
            result[key] = raw[key]
    return result


def _load_scheduling_constraints(
    ontology_root: Path,
    manifest: Mapping[str, object],
    schema_view: SchemaView,
    terms: Sequence[Mapping[str, object]],
    policy_runtime: _PolicyRuntime,
) -> dict[str, dict[str, object]]:
    """Load first-class, governed planner constraints from manifest-owned sources.

    Constraints intentionally model operational scheduling decisions separately
    from ontology relations.  They preserve legacy behavior without asserting
    biochemical incompatibility or category disjointness.
    """
    known_terms = {(str(term["semantic_category"]), str(term["slug"])) for term in terms}
    constraint_runtime = policy_runtime.constraints
    constraints: dict[str, dict[str, object]] = {}
    legacy_ids: set[str] = set()
    for relative_path in _catalog_paths(ontology_root, manifest, "constraints"):
        source = _load_yaml_mapping(_source_path(ontology_root, relative_path))
        _validate_linkml_instance(schema_view, "SchedulingConstraintCatalog", source)
        raw_constraints = _required_mapping(source, "scheduling_constraints")
        for constraint_id, raw_constraint in raw_constraints.items():
            if not isinstance(constraint_id, str):
                raise OntologyInfrastructureError(f"Scheduling constraint id must be a string: {constraint_id!r}")
            if constraint_id in constraints or not isinstance(raw_constraint, dict):
                raise OntologyInfrastructureError(f"Duplicate or malformed scheduling constraint {constraint_id!r}")
            normalized = _normalize_scheduling_constraint(
                constraint_id,
                cast(Mapping[str, object], raw_constraint),
                known_terms,
                constraint_runtime,
            )
            legacy_id = str(normalized["legacy_relation_id"])
            if legacy_id in legacy_ids:
                raise OntologyInfrastructureError(
                    f"Duplicate legacy relation id in scheduling constraints: {legacy_id}"
                )
            legacy_ids.add(legacy_id)
            constraints[constraint_id] = normalized
    authored_operations = {str(constraint["operation"]) for constraint in constraints.values()}
    orphan_operations = sorted(set(constraint_runtime.execution_policies) - authored_operations)
    if orphan_operations:
        raise OntologyInfrastructureError(
            "Runtime constraint execution policies are not referenced by authored constraints: "
            + ", ".join(orphan_operations)
        )
    return constraints


def _normalize_scheduling_constraint(
    constraint_id: str,
    raw: Mapping[str, object],
    known_terms: set[tuple[str, str]],
    runtime: _ConstraintRuntime,
) -> dict[str, object]:
    assertion_type = _required_string(raw, "assertion_type")
    operation = _required_string(raw, "operation")
    if operation not in runtime.execution_policies:
        raise OntologyInfrastructureError(
            f"Scheduling constraint {constraint_id!r} references unknown operation {operation!r}"
        )
    if _required_string(raw, "enforcement") not in runtime.enforcement_modes:
        raise OntologyInfrastructureError(f"Scheduling constraint {constraint_id!r} has invalid enforcement")
    normalized = {
        "legacy_relation_id": _required_string(raw, "legacy_relation_id"),
        "assertion_type": assertion_type,
        "operation": operation,
        "enforcement": _required_string(raw, "enforcement"),
        **_normalize_constraint_governance(
            f"Scheduling constraint {constraint_id!r}",
            raw,
            runtime,
        ),
        "source_selector": _normalize_constraint_selector(constraint_id, raw.get("source_selector"), known_terms),
        "target_selector": _normalize_constraint_selector(constraint_id, raw.get("target_selector"), known_terms),
        "rationale": _required_string(raw, "rationale"),
    }
    action = raw.get("action")
    semantic_note = raw.get("semantic_note")
    if semantic_note is not None:
        if not isinstance(semantic_note, str) or not semantic_note:
            raise OntologyInfrastructureError(
                f"Scheduling constraint {constraint_id!r} semantic_note must be non-empty"
            )
        normalized["semantic_note"] = semantic_note
    if action is not None:
        if not isinstance(action, str) or not action:
            raise OntologyInfrastructureError(f"Scheduling constraint {constraint_id!r} action must be non-empty")
        normalized["action"] = action
    return normalized


def _load_ontology_assertions(
    ontology_root: Path,
    manifest: Mapping[str, object],
    terms: Sequence[Mapping[str, object]],
    schema_view: SchemaView,
) -> dict[str, dict[str, object]]:
    """Load non-blocking assertions separately from planner constraints.

    The source is intentionally the planner's current relations document: the
    generated projection adds formal semantics without introducing a duplicate
    source or changing today's planner consumer.
    """
    known_terms = {(str(term["semantic_category"]), str(term["slug"])) for term in terms}
    assertions: dict[str, dict[str, object]] = {}
    for relative_path in _catalog_paths(ontology_root, manifest, "assertions"):
        source = _load_yaml_mapping(_source_path(ontology_root, relative_path))
        governance = _policy_governance_defaults(source, relative_path)
        raw_assertions = source.get("relations")
        if not isinstance(raw_assertions, list):
            raise OntologyInfrastructureError(f"Assertion source {relative_path} must contain a relations list")
        for raw_assertion in raw_assertions:
            if not isinstance(raw_assertion, dict):
                raise OntologyInfrastructureError(f"Assertion source {relative_path} contains a non-mapping record")
            _validate_linkml_instance(
                schema_view, "RelationAssertion", _linkml_relation_instance(cast(Mapping[str, object], raw_assertion))
            )
            normalized = _normalize_ontology_assertion(
                cast(Mapping[str, object], raw_assertion), known_terms, governance
            )
            assertion_id = str(normalized["id"])
            if assertion_id in assertions:
                raise OntologyInfrastructureError(f"Duplicate canonical ontology assertion id: {assertion_id}")
            assertions[assertion_id] = normalized
    return dict(sorted(assertions.items()))


def _normalize_ontology_assertion(
    raw: Mapping[str, object], known_terms: set[tuple[str, str]], governance: Mapping[str, object]
) -> dict[str, object]:
    allowed = {
        "id",
        "type",
        "reason",
        "action",
        "severity",
        "source_selector",
        "target_selector",
        "assertion_kind",
        "semantic_family",
    }
    extras = sorted(set(raw) - allowed)
    if extras:
        raise OntologyInfrastructureError(f"Ontology assertion has unsupported fields: {', '.join(extras)}")
    assertion_id = _required_string(raw, "id")
    relation_type = _required_string(raw, "type")
    assertion_kind = _required_string(raw, "assertion_kind")
    semantic_family = _required_string(raw, "semantic_family")
    source_selector = _normalize_constraint_selector(assertion_id, raw.get("source_selector"), known_terms)
    target_selector = _normalize_constraint_selector(assertion_id, raw.get("target_selector"), known_terms)
    normalized: dict[str, object] = {
        "id": assertion_id,
        "relation_type": relation_type,
        "assertion_kind": assertion_kind,
        "semantic_family": semantic_family,
        **governance,
        "source_selector": source_selector,
        "target_selector": target_selector,
        "reason": _required_string(raw, "reason"),
    }
    for key in ("action", "severity"):
        value = raw.get(key)
        if value is not None:
            if not isinstance(value, str) or not value:
                raise OntologyInfrastructureError(f"Ontology assertion {assertion_id} {key} must be a non-empty string")
            normalized[key] = value
    return normalized


def _linkml_relation_instance(raw: Mapping[str, object]) -> dict[str, object]:
    """Adapt the legacy relation selector spelling to its LinkML field name."""
    result = dict(raw)
    for endpoint in ("source_selector", "target_selector"):
        selector = result.get(endpoint)
        if isinstance(selector, dict):
            normalized = dict(cast(Mapping[str, object], selector))
            if "term" in normalized:
                normalized["assertion_term"] = normalized.pop("term")
            result[endpoint] = normalized
    return result


def _normalize_constraint_governance(
    context: str,
    raw: Mapping[str, object],
    runtime: _ConstraintRuntime,
) -> dict[str, object]:
    """Validate the explicit lifecycle/enforcement matrix for constraints."""
    status = _required_string(raw, "status")
    enforcement = _required_string(raw, "enforcement")
    if (
        status not in runtime.lifecycle_states
        or enforcement not in runtime.enforcement_modes
        or (status, enforcement) not in runtime.allowed_pairs
    ):
        raise OntologyInfrastructureError(f"{context} has unknown status/enforcement value: {status}+{enforcement}")
    evidence = raw.get("evidence")
    if not isinstance(evidence, list):
        raise OntologyInfrastructureError(f"{context} evidence must be a list")
    evidence_items = cast(list[object], evidence)
    for index, item in enumerate(evidence_items):
        _validate_constraint_evidence_uri(context, index, item, runtime.evidence_format)
    gate = runtime.execution_gates.get(status)
    if gate is None:
        raise OntologyInfrastructureError(f"{context} has no authored execution gate for status {status!r}")
    requirement = _required_string(gate, "evidence_requirement")
    evidence_gap = raw.get("evidence_gap")
    if evidence_gap is not None and (not isinstance(evidence_gap, str) or not evidence_gap):
        raise OntologyInfrastructureError(f"{context} evidence_gap must be a non-empty string")
    if requirement == "required" and not evidence_items:
        raise OntologyInfrastructureError(f"{context} requires non-empty evidence")
    if requirement == "prohibited" and (evidence_items or evidence_gap is not None):
        raise OntologyInfrastructureError(f"{context} prohibits evidence")
    if requirement == "evidence_or_gap" and not evidence_items and evidence_gap is None:
        raise OntologyInfrastructureError(f"{context} requires evidence or evidence_gap")
    normalized = {
        "legacy_preserved": cast(bool, raw["legacy_preserved"]),
        "status": status,
        "owner": _required_string(raw, "owner"),
        "review_by": _required_string(raw, "review_by"),
        "evidence": evidence_items,
    }
    if evidence_gap is not None:
        normalized["evidence_gap"] = evidence_gap
    return normalized


def _validate_constraint_evidence_uri(
    context: str,
    index: int,
    item: object,
    evidence_format: _EvidenceUriFormat,
) -> None:
    message = f"{context} evidence[{index}] must be a string {evidence_format.scheme.upper()} URL"
    if not isinstance(item, str):
        raise OntologyInfrastructureError(message)
    parsed = urlparse(item)
    if parsed.scheme != evidence_format.scheme:
        raise OntologyInfrastructureError(message)
    if evidence_format.require_host and not parsed.netloc:
        raise OntologyInfrastructureError(message)
    if evidence_format.forbid_userinfo and (parsed.username is not None or parsed.password is not None):
        raise OntologyInfrastructureError(message)


def _normalize_constraint_selector(
    constraint_id: str, raw: object, known_terms: set[tuple[str, str]]
) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise OntologyInfrastructureError(f"Scheduling constraint {constraint_id!r} selector must be a mapping")
    selector = cast(Mapping[str, object], raw)
    entity = selector.get("entity")
    if isinstance(entity, dict) and set(selector) == {"entity"}:
        entity_map = cast(Mapping[str, object], entity)
        keys = set(entity_map)
        if keys not in ({"id"}, {"name"}):
            raise OntologyInfrastructureError(
                f"Scheduling constraint {constraint_id!r} entity selector must use one id or name"
            )
        key = next(iter(keys))
        return {"entity": {key: _required_string(entity_map, key)}}
    if set(selector) == {"category", "term"}:
        category = _required_string(selector, "category")
        term = _required_string(selector, "term")
        if (category, term) not in known_terms:
            raise OntologyInfrastructureError(
                f"Scheduling constraint {constraint_id!r} has unknown selector {category}:{term}"
            )
        return {"category": category, "term": term}
    raise OntologyInfrastructureError(
        f"Scheduling constraint {constraint_id!r} selector must be entity or category/term"
    )


def _normalize_policy_effect(key: str, raw: object, near_values: set[str], score_levels: set[str]) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise OntologyInfrastructureError(f"Policy {key!r} effect must be a mapping")
    effect = cast(Mapping[str, object], raw)
    extras = sorted(set(effect) - {"match", "level", "block"})
    if extras:
        raise OntologyInfrastructureError(f"Policy {key!r} effect has unsupported fields: {', '.join(extras)}")
    normalized: dict[str, object] = {"match": _normalize_policy_match(key, effect.get("match"), near_values)}
    level = _normalize_policy_level(key, effect.get("level"), score_levels)
    if level is not None:
        normalized["level"] = level
    block = _normalize_policy_block(key, effect.get("block"))
    if block is not None:
        normalized["block"] = block
    if len(normalized) == 1:
        raise OntologyInfrastructureError(f"Policy {key!r} effect must set level or block")
    return normalized


def _normalize_policy_match(key: str, raw: object, near_values: set[str]) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise OntologyInfrastructureError(f"Policy {key!r} effect match must be a mapping")
    match_map = cast(Mapping[str, object], raw)
    match_extras = sorted(set(match_map) - {"near", "food"})
    if match_extras or not match_map:
        detail = ", ".join(match_extras) if match_extras else "empty match"
        raise OntologyInfrastructureError(f"Policy {key!r} effect has invalid match: {detail}")
    normalized_match: dict[str, object] = {}
    if "near" in match_map:
        near = match_map["near"]
        if near not in near_values:
            raise OntologyInfrastructureError(f"Policy {key!r} has invalid slot proximity {near!r}")
        normalized_match["near"] = near
    if "food" in match_map:
        food = match_map["food"]
        if not isinstance(food, bool):
            raise OntologyInfrastructureError(f"Policy {key!r} food match must be boolean")
        normalized_match["food"] = food
    return normalized_match


def _normalize_policy_level(key: str, level: object, score_levels: set[str]) -> str | None:
    if level is None:
        return None
    if level not in score_levels:
        raise OntologyInfrastructureError(f"Policy {key!r} has invalid score level {level!r}")
    return cast(str, level)


def _normalize_policy_block(key: str, block: object) -> bool | None:
    if block is None:
        return None
    if not isinstance(block, bool):
        raise OntologyInfrastructureError(f"Policy {key!r} block must be boolean")
    return block


def _read_custom_shapes(ontology_root: Path, manifest: Mapping[str, object], base_iri: str) -> str:
    files = _catalog_paths(ontology_root, manifest, "custom_shapes")
    contents: list[str] = []
    for relative_path in files:
        path = _source_path(ontology_root, relative_path)
        source = path.read_text(encoding="utf-8")
        if base_iri not in source:
            raise OntologyInfrastructureError(f"Custom SHACL source has no canonical ss base IRI: {path}")
        contents.append(source.rstrip())
    return "\n\n".join(contents) + "\n"


def _ttl_bytes(  # noqa: PLR0913, PLR0917
    header: str,
    base_iri: str,
    categories: Mapping[str, object],
    terms: Sequence[Mapping[str, object]],
    schema_view: SchemaView,
    manifest: Mapping[str, object],
) -> bytes:
    lines = [
        header.rstrip(),
        f"@prefix ss: <{base_iri}> .",
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "",
    ]
    lines.extend([
        f"<{base_iri}> a ss:Ontology ;",
        f"  ss:schemaVersion {_ttl_literal(str(manifest['schema_version']))} .",
        "",
    ])
    for class_name in sorted(schema_view.all_classes()):
        class_uri = f"{base_iri}{class_name}"
        lines.extend([f"<{class_uri}> a ss:SchemaClass ;", f"  ss:name {_ttl_literal(class_name)} .", ""])
    for slot_name in sorted(schema_view.all_slots()):
        slot_uri = f"{base_iri}{slot_name}"
        lines.extend([f"<{slot_uri}> a ss:SchemaSlot ;", f"  ss:name {_ttl_literal(slot_name)} .", ""])
    for catalog in sorted(cast(list[dict[str, object]], manifest["catalogs"]), key=lambda item: str(item["id"])):
        catalog_id = str(catalog["id"])
        lines.extend([
            f"<{base_iri}catalog/{catalog_id}> a ss:Catalog ;",
            f"  ss:catalogRole {_ttl_literal(str(catalog['role']))} ;",
            f"  ss:catalogPath {_ttl_literal(str(catalog['path']))} ;",
            f"  ss:catalogRootClass {_ttl_literal(str(catalog['root_class']))} .",
            "",
        ])
    lines.extend(f"ss:{category} a ss:SemanticCategory ." for category in sorted(categories))
    lines.append("")
    for term in terms:
        category = str(term["semantic_category"])
        slug = str(term["slug"])
        label = _ttl_literal(str(term["label"]))
        profile = str(term["ontoclean_profile"])
        lines.extend([
            f"<{base_iri}term/{category}/{slug}> a ss:OntologyTerm ;",
            f"  ss:semanticCategory ss:{category} ;",
            f"  ss:ontocleanProfile ss:{profile} ;",
            *([f"  ss:assertionKind ss:{term['assertion_kind']} ;"] if "assertion_kind" in term else []),
            f"  ss:label {label} .",
            "",
        ])
    return ("\n".join(lines).rstrip() + "\n").encode("utf-8")


def _shapes_bytes(header: str, base_iri: str, generated_shapes: str, semantic_shapes: str) -> bytes:
    return (
        header
        + f"@prefix ss: <{base_iri}> .\n\n"
        + generated_shapes.rstrip()
        + "\n\n"
        + semantic_shapes.rstrip()
        + "\n"
    ).encode("utf-8")


def _header(manifest: Mapping[str, object], source_hash: str) -> str:
    return (
        f"# generated-by: scripts/generate_ontology.py\n"
        f"# schema-version: {manifest['schema_version']}\n"
        f"# source-hash: {source_hash}\n"
    )


def _json_bytes(value: object, header: str) -> bytes:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return (header + payload).encode("utf-8")


def _json_bytes_no_header(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _yaml_bytes(value: object, *, sort_keys: bool = True) -> bytes:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=sort_keys).encode("utf-8")


def _check_fresh(generated_dir: Path, expected: Mapping[Path, bytes]) -> None:
    for relative_path, content in expected.items():
        current = generated_dir / relative_path
        if not current.is_file() or current.read_bytes() != content:
            raise OntologyInfrastructureError(f"Stale or missing generated ontology artifact: {current}")


def _load_yaml_mapping(path: Path) -> dict[str, object]:
    try:
        loaded = _safe_yaml_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise OntologyInfrastructureError(f"Cannot load ontology source {path}: {error}") from error
    if not isinstance(loaded, dict):
        raise OntologyInfrastructureError(f"Ontology source must be a mapping: {path}")
    return cast(dict[str, object], loaded)


def _required_string(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise OntologyInfrastructureError(f"Expected non-empty string {key!r} in ontology source")
    return value


def _required_string_list(mapping: Mapping[str, object], key: str) -> list[str]:
    value = mapping.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise OntologyInfrastructureError(f"Expected non-empty string list {key!r} in ontology source")
    return cast(list[str], value)


def _required_mapping(mapping: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise OntologyInfrastructureError(f"Expected mapping {key!r} in ontology source")
    return cast(Mapping[str, object], value)


def _ttl_literal(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _safe_yaml_load(text: str) -> object:
    return cast(object, yaml.safe_load(text))
