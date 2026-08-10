"""Deterministic build of the committed executable ontology artifacts.

This module is generation-only: it imports LinkML to prove and inspect the
authored schema, while normal planner runtime paths only read the resulting
runtime-vocabulary YAML and RDF/SHACL artifacts.
"""

# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false

# ruff: noqa: C901, PLR0912

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast, runtime_checkable
from urllib.parse import quote

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from linkml.generators.jsonschemagen import JsonSchemaGenerator
from linkml.generators.shaclgen import ShaclGenerator
from linkml_runtime.linkml_model.meta import AnonymousClassExpression, Prefix, SchemaDefinition, SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.glue_capabilities import (
    IMPLEMENTED_EFFECT_MATCH_VALUE_HANDLERS,
    IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS,
    IMPLEMENTED_RELATION_ENDPOINT_SELECTOR_KINDS,
    IMPLEMENTED_RELATION_PRESENCE_TRUTH_TABLE,
    IMPLEMENTED_RELATION_SELECTOR_FORMS,
)
from planner.ontology.runtime_program import RUNTIME_PROJECTION_FIELDS
from planner.yaml_io import safe_load_yaml
from rdflib import BNode, Graph, Literal
from rdflib.namespace import RDF, SH
from rdflib.term import Node, URIRef

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
    "dashboard.schema.json",
    "product.schema.json",
    "relations.schema.json",
    "pillboxes.schema.json",
    "schema.json",
    "stacks.schema.json",
    "ontology.ttl",
    "shapes.ttl",
    "context.json",
    "projection-map.json",
    "runtime-program.json",
    "runtime-vocabulary.yaml",
    "artifact-lock.json",
}
_REPOSITORY_LOCATOR_KINDS = {"flat_root", "explicit_path", "explicit_paths", "catalog_ref"}

_ONTOCLEAN_RIGIDITY_VALUES = frozenset({"rigid", "anti_rigid"})
_ONTOCLEAN_DEPENDENCE_VALUES = frozenset({"independent", "dependent"})

_CONDITION_OPERATORS = frozenset({
    "equals",
    "contains",
    "equals_field",
    "member_of_field",
    "is_true",
    "is_false",
    "all",
    "any",
    "not",
})
_CONDITION_VALUE_TYPES = frozenset({"string", "strings", "boolean"})

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
        not raw
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
        loaded = _safe_yaml_load(manifest_path.read_text(encoding="utf-8"), path=manifest_path)
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


def _validate_repository_projection(
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
    declared_artifacts = manifest.get("artifacts")
    if not isinstance(declared_artifacts, list) or not all(isinstance(item, str) for item in declared_artifacts):
        raise OntologyInfrastructureError("Manifest artifacts must be declared before repository projection metadata")
    for source_id, mapping in mappings.items():
        maintenance = mapping.get("maintenance")
        if isinstance(maintenance, Mapping) and maintenance.get("schema_artifact") not in declared_artifacts:
            raise OntologyInfrastructureError(
                f"Repository mapping {source_id!r} maintenance schema artifact is not declared"
            )
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
    # A user-authored schedule.yaml is deliberately not an undeclared projection input.
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


def _validate_repository_mappings(raw: object) -> dict[str, dict[str, object]]:
    if not isinstance(raw, list) or not raw:
        raise OntologyInfrastructureError("repository_projection.mappings must be a non-empty list")
    allowed_kinds = {
        "slot",
        "alias",
        "keyed-map",
        "sequence",
        "reference",
        "opaque-value",
        "inlined-node",
        "path-token",
    }
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
        if set(mapping) - {
            "source",
            "root_class",
            "document_shape",
            "identity",
            "catalog_role",
            "maintenance",
            "instructions",
        }:
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
        maintenance = mapping.get("maintenance")
        if maintenance is not None:
            if not isinstance(maintenance, dict) or set(maintenance) != {"role", "label", "schema_artifact"}:
                raise OntologyInfrastructureError(f"Repository mapping {source_id!r} maintenance metadata is invalid")
            if not all(isinstance(maintenance.get(key), str) and maintenance[key] for key in maintenance):
                raise OntologyInfrastructureError(f"Repository mapping {source_id!r} maintenance metadata is invalid")
        seen_instructions: set[tuple[str, str, str | None, str | None]] = set()
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
            allowed_instruction_keys = {"kind", "source", "predicate", "target", "subject", "token", "token_index"}
            if set(instruction) - allowed_instruction_keys:
                raise OntologyInfrastructureError(
                    f"Repository mapping {source_id!r} instruction has unsupported fields"
                )
            if "target" in instruction and (
                not isinstance(instruction.get("target"), str) or not instruction["target"]
            ):
                raise OntologyInfrastructureError(f"Repository mapping {source_id!r} reference target is invalid")
            if kind == "inlined-node" and "target" not in instruction:
                raise OntologyInfrastructureError(f"Repository mapping {source_id!r} inlined node target is invalid")
            if "subject" in instruction and (
                not isinstance(instruction.get("subject"), str) or not instruction["subject"]
            ):
                raise OntologyInfrastructureError(f"Repository mapping {source_id!r} instruction subject is invalid")
            if kind == "path-token":
                token = instruction.get("token")
                token_index = instruction.get("token_index", 0)
                if (
                    not isinstance(token, str)
                    or token not in cast(str, path).split(".")
                    or isinstance(token_index, bool)
                    or not isinstance(token_index, int)
                    or token_index < 0
                    or cast(str, path).split(".").count(token) <= token_index
                ):
                    raise OntologyInfrastructureError(
                        f"Repository mapping {source_id!r} path-token instruction is invalid"
                    )
            instruction_key = (
                cast(str, path),
                cast(str, kind),
                cast(str | None, instruction.get("subject")),
                cast(str | None, instruction.get("predicate")),
            )
            if instruction_key in seen_instructions:
                raise OntologyInfrastructureError(f"Repository mapping {source_id!r} duplicates instruction {path!r}")
            seen_instructions.add(instruction_key)
            normalized_instructions.append(dict(instruction))
        node_sources = {str(item["source"]) for item in normalized_instructions if item.get("kind") == "inlined-node"}
        for instruction in normalized_instructions:
            subject = instruction.get("subject")
            if subject is not None and subject not in node_sources:
                raise OntologyInfrastructureError(
                    f"Repository mapping {source_id!r} instruction references unknown inlined subject {subject!r}"
                )
        _reject_ambiguous_mapping_patterns(
            cast(str, source_id),
            [str(item["source"]) for item in normalized_instructions if item.get("subject") is None],
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
        not value
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


def _load_relation_types(
    ontology_root: Path, manifest: Mapping[str, object], schema_view: SchemaView
) -> dict[str, dict[str, object]]:
    source = _load_yaml_mapping(_catalog_path(ontology_root, manifest, "relation_types"))
    _validate_linkml_instance(schema_view, "RelationCatalog", _linkml_catalog_instance("RelationCatalog", source))
    raw = source.get("relation_types")
    if not isinstance(raw, list) or not raw:
        raise OntologyInfrastructureError("relation types must be a non-empty list")
    result: dict[str, dict[str, object]] = {}
    seen_orders: dict[int, str] = {}
    seen_semantics: dict[tuple[object, ...], str] = {}
    for item in cast(list[object], raw):
        if not isinstance(item, Mapping):
            raise OntologyInfrastructureError("relation type records must be mappings")
        row = dict(cast(Mapping[str, object], item))
        identifier = _required_string(row, "id")
        if set(row) != {
            "id",
            "label",
            "order",
            "directional",
            "source_selector_forms",
            "target_selector_forms",
        }:
            raise OntologyInfrastructureError(
                f"relation type {identifier!r} has unsupported or missing metadata fields"
            )
        if _required_string(row, "label") == "":
            raise OntologyInfrastructureError(f"relation type {identifier!r} requires non-empty label")
        if identifier in result:
            raise OntologyInfrastructureError(f"duplicate relation type {identifier!r}")
        order = row.get("order")
        if isinstance(order, bool) or not isinstance(order, int):
            raise OntologyInfrastructureError(f"relation type {identifier!r} requires integer order")
        previous_order = seen_orders.get(order)
        if previous_order is not None:
            raise OntologyInfrastructureError(
                f"relation types have duplicate semantic order {order!r}: {previous_order!r} and {identifier!r}"
            )
        directional = row.get("directional")
        if not isinstance(directional, bool):
            raise OntologyInfrastructureError(f"relation type {identifier!r} requires strict boolean directional")
        source_forms: list[str] = []
        target_forms: list[str] = []
        for side, raw_forms in (
            ("source", row.get("source_selector_forms")),
            ("target", row.get("target_selector_forms")),
        ):
            if not isinstance(raw_forms, list) or not raw_forms:
                raise OntologyInfrastructureError(
                    f"relation type {identifier!r} requires non-empty {side}_selector_forms"
                )
            if any(not isinstance(form, str) or form not in {"term", "entity"} for form in raw_forms):
                raise OntologyInfrastructureError(f"relation type {identifier!r} has invalid {side}_selector_forms")
            forms = [form for form in raw_forms if isinstance(form, str)]
            if len(set(forms)) != len(forms):
                raise OntologyInfrastructureError(f"relation type {identifier!r} duplicates {side}_selector_forms")
            if side == "source":
                source_forms = forms
            else:
                target_forms = forms
        semantic = (order, directional, tuple(source_forms), tuple(target_forms))
        previous_semantic = seen_semantics.get(semantic)
        if previous_semantic is not None:
            raise OntologyInfrastructureError(
                f"relation types have duplicate semantic key {semantic!r}: {previous_semantic!r} and {identifier!r}"
            )
        seen_orders[order] = identifier
        seen_semantics[semantic] = identifier
        result[identifier] = row
    return dict(sorted(result.items()))


def _validate_relation_warning_filter_values(
    runtime: Mapping[str, object], assertions: Mapping[str, Mapping[str, object]]
) -> None:
    rules = runtime.get("relation_warning_rules")
    if not isinstance(rules, list):
        return
    for raw in cast(list[object], rules):
        if not isinstance(raw, Mapping):
            continue
        field = raw.get("filter_field")
        value = raw.get("filter_value")
        if field not in {"assertion_kind", "semantic_family"} or not isinstance(value, str):
            raise OntologyInfrastructureError("relation warning rule filter is invalid")
        if not any(item.get(field) == value for item in assertions.values()):
            raise OntologyInfrastructureError(f"relation warning filter value is not authored: {value}")


def _render_artifacts(ontology_root: Path, manifest: Mapping[str, object]) -> dict[Path, bytes]:
    source_hash = _source_hash(ontology_root, manifest)
    schema_view = _schema_view(ontology_root, manifest)
    _validate_manifest_catalog_root_classes(manifest, schema_view)
    vocabulary = _load_yaml_mapping(_catalog_path(ontology_root, manifest, "vocabulary"))
    if "terms" not in vocabulary:
        raise OntologyInfrastructureError("Vocabulary catalog requires a terms catalog")
    _validate_linkml_instance(
        schema_view, "VocabularyCatalog", _linkml_catalog_instance("VocabularyCatalog", vocabulary)
    )
    _validate_linkml_instance(
        schema_view,
        "OntoCleanCatalog",
        _linkml_catalog_instance(
            "OntoCleanCatalog",
            _load_yaml_mapping(_catalog_path(ontology_root, manifest, "ontoclean")),
        ),
    )
    ontoclean_profiles = _load_ontoclean_profiles(ontology_root, manifest, schema_view)
    categories = _required_mapping(vocabulary, "semantic_categories")
    _validate_semantic_categories(categories, ontoclean_profiles)
    terms = _normalized_terms(vocabulary, ontoclean_profiles)
    relation_types = _load_relation_types(ontology_root, manifest, schema_view)
    runtime = _load_runtime_policy(ontology_root, manifest, schema_view, set(relation_types))
    scheduling_policies = _load_scheduling_policies(ontology_root, manifest, schema_view, terms, categories, runtime)
    schedule_presentation = _load_schedule_presentation(ontology_root, manifest, scheduling_policies, categories)
    scheduling_constraints = _load_scheduling_constraints(
        ontology_root,
        manifest,
        schema_view,
        terms,
        runtime,
    )
    ontology_assertions = _load_ontology_assertions(
        ontology_root,
        manifest,
        terms,
        schema_view,
        runtime.constraints.selector_kinds,
        relation_types,
        _load_substance_identity_registry(ontology_root),
    )
    _validate_relation_warning_filter_values(runtime.authored, ontology_assertions)
    base_iri = _required_string(manifest, _BASE_IRI_KEY)
    _add_authored_card_fields(schema_view, runtime.authored, categories, base_iri)
    header = _header(manifest, source_hash)
    runtime_vocabulary: object = {
        "format": _RUNTIME_FORMAT,
        "schema_version": str(manifest["schema_version"]),
        "base_iri": base_iri,
        "source_hash": source_hash,
        "categories": categories,
        "ontoclean_profiles": ontoclean_profiles,
        "terms": terms,
        "scheduling_policies": scheduling_policies,
        "schedule_presentation": schedule_presentation,
        "scheduling_constraints": scheduling_constraints,
        "relation_types": relation_types,
        "runtime_policy": runtime.authored,
        "ontology_assertions": ontology_assertions,
    }
    semantic_shapes = _read_custom_shapes(ontology_root, manifest, base_iri, categories)
    generated_schema_doc = _generated_json_schema_document(schema_view)
    generated_schema_doc["$schema"] = _JSON_SCHEMA_FORMAT
    generated_schema_doc["$id"] = f"{base_iri}generated/schema.json"
    _apply_relation_type_enum(generated_schema_doc, relation_types)
    _apply_card_uniqueness(generated_schema_doc, schema_view, categories)
    generated_schema = _json_bytes_no_header(generated_schema_doc)
    card_schema = _catalog_schema(
        generated_schema_doc, base_iri, "card.schema.json", "SubstanceCard", "Supp Slotter canonical substance card"
    )
    product_schema = _product_schema(generated_schema_doc, schema_view, base_iri)
    dashboard_schema = _dashboard_schema(generated_schema_doc, schema_view, manifest, base_iri, categories)
    relations_schema = _relations_schema(generated_schema_doc, schema_view, base_iri)
    pillboxes_schema = _pillboxes_schema(generated_schema_doc, schema_view, runtime, base_iri)
    stacks_schema = _stacks_schema(generated_schema_doc, schema_view, manifest, base_iri)
    generated_shapes = _canonical_shapes(schema_view, relation_types)
    _validate_repository_projection_coverage(ontology_root, manifest)
    projection_map = _projection_map(schema_view, manifest, base_iri)
    context = _jsonld_context(schema_view, base_iri)
    runtime_program = _runtime_program(ontology_root, manifest, runtime.authored, source_hash)
    artifacts: dict[Path, bytes] = {
        Path("card.schema.json"): _json_bytes_no_header(card_schema),
        Path("dashboard.schema.json"): _json_bytes_no_header(dashboard_schema),
        Path("product.schema.json"): _json_bytes_no_header(product_schema),
        Path("relations.schema.json"): _json_bytes_no_header(relations_schema),
        Path("pillboxes.schema.json"): _json_bytes_no_header(pillboxes_schema),
        Path("schema.json"): generated_schema,
        Path("stacks.schema.json"): _json_bytes_no_header(stacks_schema),
        Path("ontology.ttl"): _ttl_bytes(
            header,
            base_iri,
            categories,
            terms,
            relation_types,
            scheduling_policies,
            scheduling_constraints,
            runtime.authored,
            ontoclean_profiles,
            schema_view,
            manifest,
        ),
        Path("shapes.ttl"): _shapes_bytes(header, base_iri, generated_shapes, semantic_shapes),
        Path("context.json"): _json_bytes_no_header(context),
        Path("projection-map.json"): _json_bytes_no_header(projection_map),
        Path("runtime-program.json"): _json_bytes_no_header(runtime_program),
        Path("runtime-vocabulary.yaml"): _yaml_bytes(runtime_vocabulary, sort_keys=False),
    }
    artifacts[Path("artifact-lock.json")] = _json_bytes_no_header(_artifact_lock(ontology_root, manifest, artifacts))
    return artifacts


def _catalog_schema(
    generated_schema: Mapping[str, object],
    base_iri: str,
    filename: str,
    root_class: str,
    title: str,
) -> dict[str, object]:
    """Return a generated schema rooted at one manifest-facing LinkML class."""

    schema = dict(generated_schema)
    schema["$id"] = f"{base_iri}generated/{filename}"
    schema["title"] = title
    schema["$ref"] = f"#/$defs/{root_class}"
    return schema


def _product_schema(
    generated_schema: Mapping[str, object], schema_view: SchemaView, base_iri: str
) -> dict[str, object]:
    """Project the product card and its authored component identity rule."""
    schema = _catalog_schema(
        generated_schema,
        base_iri,
        "product.schema.json",
        "ProductCard",
        "Supp Slotter canonical product card",
    )
    uniqueness = _annotation_text(schema_view, "ProductCard", "component_uniqueness")
    source = _annotation_text(schema_view, "ProductCard", "component_uniqueness_source")
    field = _annotation_text(schema_view, "ProductCard", "component_uniqueness_field")
    schema["x-supp-slotter-validation"] = {
        "product_component_substance_uniqueness": {
            "source": source,
            "field": field,
            "scope": "record",
            "uniqueness": uniqueness,
        }
    }
    return schema


def _relations_schema(
    generated_schema: Mapping[str, object], schema_view: SchemaView, base_iri: str
) -> dict[str, object]:
    """Project the relation catalog and its authored record identity rule."""
    schema = _catalog_schema(
        generated_schema,
        base_iri,
        "relations.schema.json",
        "RelationAssertionCatalog",
        "Supp Slotter relation assertion catalog",
    )
    uniqueness = _annotation_text(schema_view, "RelationAssertionCatalog", "relation_id_uniqueness")
    source = _annotation_text(schema_view, "RelationAssertionCatalog", "relation_id_uniqueness_source")
    field = _annotation_text(schema_view, "RelationAssertionCatalog", "relation_id_uniqueness_field")
    if uniqueness != "required":
        raise OntologyInfrastructureError("Relation assertion id uniqueness must be required")
    schema["x-supp-slotter-validation"] = {
        "relation_id_uniqueness": {
            "source": source,
            "field": field,
            "scope": "global",
            "uniqueness": uniqueness,
        }
    }
    return schema


def _apply_card_uniqueness(
    generated_schema: dict[str, object], schema_view: SchemaView, categories: Mapping[str, object]
) -> None:
    """Apply authored uniqueness annotations to generated array contracts."""
    assertion_uniqueness = _annotation_text(schema_view, "CardKnowledge", "assertion_value_uniqueness")
    if assertion_uniqueness != "required":
        raise OntologyInfrastructureError("CardKnowledge assertion_value_uniqueness must be required")
    definitions = generated_schema.get("$defs")
    if not isinstance(definitions, dict):
        raise OntologyInfrastructureError("Generated LinkML schema has no class definitions")
    knowledge = definitions.get("CardKnowledge")
    if not isinstance(knowledge, Mapping) or not isinstance(knowledge.get("properties"), dict):
        raise OntologyInfrastructureError("Generated LinkML schema is missing CardKnowledge properties")
    properties = cast(dict[str, object], knowledge["properties"])
    fields = _knowledge_namespaces(categories)
    for field in fields:
        property_schema = properties.get(field)
        if not isinstance(property_schema, dict):
            raise OntologyInfrastructureError(f"Generated CardKnowledge field {field!r} is missing")
        property_schema["uniqueItems"] = True


def _class_annotations(schema_view: SchemaView, class_name: str) -> Mapping[str, object]:
    class_definition = schema_view.get_class(class_name)
    if class_definition is None:
        raise OntologyInfrastructureError(f"Ontology schema has no class {class_name}")
    annotations = class_definition.annotations
    if not isinstance(annotations, Mapping):
        raise OntologyInfrastructureError(f"Ontology class {class_name} annotations are malformed")
    return cast(Mapping[str, object], annotations)


def _annotation_text(schema_view: SchemaView, class_name: str, name: str) -> str:
    value = _class_annotations(schema_view, class_name).get(name)
    extracted = getattr(value, "value", value)
    if not isinstance(extracted, str) or not extracted.strip():
        raise OntologyInfrastructureError(f"Ontology validation annotation {class_name}.{name} is missing")
    return extracted


def _definition_property(
    generated_schema: Mapping[str, object], class_name: str, property_name: str
) -> dict[str, object]:
    definitions = generated_schema.get("$defs")
    if not isinstance(definitions, Mapping):
        raise OntologyInfrastructureError("Generated LinkML schema has no class definitions")
    definition = definitions.get(class_name)
    if not isinstance(definition, Mapping):
        raise OntologyInfrastructureError(f"Generated LinkML schema has no class {class_name}")
    properties = definition.get("properties")
    if not isinstance(properties, Mapping) or property_name not in properties:
        raise OntologyInfrastructureError(f"Generated {class_name} definition has no property {property_name}")
    property_schema = properties[property_name]
    if not isinstance(property_schema, Mapping):
        raise OntologyInfrastructureError(f"Generated {class_name}.{property_name} schema is malformed")
    return cast(dict[str, object], property_schema)


def _required_annotation_fields(schema_view: SchemaView, class_name: str, name: str) -> list[str]:
    fields = [field.strip() for field in _annotation_text(schema_view, class_name, name).split(",")]
    if not fields or any(not field for field in fields):
        raise OntologyInfrastructureError(f"Ontology validation annotation {class_name}.{name} is malformed")
    return fields


def _dashboard_schema(
    generated_schema: Mapping[str, object],
    schema_view: SchemaView,
    manifest: Mapping[str, object],
    base_iri: str,
    categories: Mapping[str, object],
) -> dict[str, object]:
    """Generate the authored dashboard YAML projection from the Dashboard model."""
    del manifest
    dashboard_required = _required_annotation_fields(schema_view, "Dashboard", "source_required")
    alternatives = _required_annotation_fields(schema_view, "Dashboard", "source_any_of")
    if len(alternatives) < 2:
        raise OntologyInfrastructureError("Dashboard source_any_of requires at least two fields")
    knowledge_categories = sorted(_knowledge_namespaces(categories))
    if not knowledge_categories:
        raise OntologyInfrastructureError("Dashboard selectors require at least one knowledge category")
    selector_properties = {
        "category": {
            **_definition_property(generated_schema, "DashboardSelector", "category"),
            "minLength": 1,
            "enum": knowledge_categories,
        },
        "term": {**_definition_property(generated_schema, "DashboardSelector", "selector_term"), "minLength": 1},
    }
    selector_schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["category", "term"],
        "properties": selector_properties,
    }
    selector_uniqueness = _annotation_text(schema_view, "Dashboard", "selector_uniqueness")
    context_uniqueness = _annotation_text(schema_view, "Dashboard", "declares_context_uniqueness")
    if selector_uniqueness != "required" or context_uniqueness != "required":
        raise OntologyInfrastructureError("Dashboard selector and context uniqueness must be required")
    properties: dict[str, object] = {
        "id": _definition_property(generated_schema, "Dashboard", "id"),
        "name": {**_definition_property(generated_schema, "Dashboard", "label"), "minLength": 1},
        "description": {**_definition_property(generated_schema, "Dashboard", "description"), "minLength": 1},
        "selectors": {
            **_definition_property(generated_schema, "Dashboard", "selectors"),
            "minItems": 1,
            "items": selector_schema,
            "uniqueItems": True,
        },
        "declares_context": {
            **_definition_property(generated_schema, "Dashboard", "declares_context"),
            "uniqueItems": True,
        },
    }
    for source_name, canonical_name in (("benefit", "benefit_description"), ("risk", "risk_description")):
        properties[source_name] = {
            "type": "object",
            "additionalProperties": False,
            "required": ["description"],
            "properties": {
                "description": {
                    **_definition_property(generated_schema, "Dashboard", canonical_name),
                    "type": "string",
                    "minLength": 1,
                }
            },
        }
    return {
        "$schema": _JSON_SCHEMA_FORMAT,
        "$id": f"{base_iri}generated/dashboard.schema.json",
        "title": "Supp Slotter canonical dashboard source contract",
        "type": "object",
        "additionalProperties": False,
        "required": dashboard_required,
        "anyOf": [{"required": [field]} for field in alternatives],
        "properties": properties,
    }


def _stacks_schema(
    generated_schema: Mapping[str, object], schema_view: SchemaView, manifest: Mapping[str, object], base_iri: str
) -> dict[str, object]:
    """Generate the keyed stack YAML projection from the authored Stack model."""
    del manifest
    key_pattern = _annotation_text(schema_view, "Stack", "source_key_pattern")
    uniqueness = _annotation_text(schema_view, "Stack", "entry_uniqueness")
    if uniqueness != "required":
        raise OntologyInfrastructureError("Stack entry_uniqueness must be required")
    product_pattern = _definition_property(generated_schema, "ProductCard", "id").get("pattern")
    if not isinstance(product_pattern, str) or not product_pattern:
        raise OntologyInfrastructureError("ProductCard id pattern is required for stack references")
    return {
        "$schema": _JSON_SCHEMA_FORMAT,
        "$id": f"{base_iri}generated/stacks.schema.json",
        "title": "Supp Slotter canonical stack source contract",
        "type": "object",
        "additionalProperties": False,
        "patternProperties": {
            key_pattern: {
                "type": "array",
                "uniqueItems": True,
                "items": {"type": "string", "pattern": product_pattern},
            }
        },
    }


def _pillboxes_schema(
    generated_schema: Mapping[str, object],
    schema_view: SchemaView,
    runtime: _PolicyRuntime,
    base_iri: str,
) -> dict[str, object]:
    """Project the authored Pillbox/Slot model onto the keyed YAML source shape."""
    definitions = generated_schema.get("$defs")
    if not isinstance(definitions, Mapping):
        raise OntologyInfrastructureError("Generated LinkML schema has no class definitions")
    pillbox_definition = definitions.get("Pillbox")
    slot_definition = definitions.get("Slot")
    if not isinstance(pillbox_definition, Mapping) or not isinstance(slot_definition, Mapping):
        raise OntologyInfrastructureError("Generated LinkML schema is missing Pillbox or Slot")
    pillbox_properties = pillbox_definition.get("properties")
    slot_properties = slot_definition.get("properties")
    if not isinstance(pillbox_properties, Mapping) or not isinstance(slot_properties, Mapping):
        raise OntologyInfrastructureError("Generated Pillbox/Slot definitions have no properties")
    required_pillbox = pillbox_definition.get("required")
    required_slot = slot_definition.get("required")
    if not isinstance(required_pillbox, list) or not isinstance(required_slot, list):
        raise OntologyInfrastructureError("Generated Pillbox/Slot definitions have no required fields")
    if not {"label", "stack", "slots"}.issubset(set(required_pillbox)):
        raise OntologyInfrastructureError("Pillbox model must require label, stack, and slots")
    if not {"label", "order"}.issubset(set(required_slot)):
        raise OntologyInfrastructureError("Slot model must require label and order")
    dimensions: dict[str, dict[str, object]] = {}
    for dimension, value_type in runtime.effect_match_dimensions.items():
        slot_field = runtime.effect_match_slot_fields.get(dimension)
        if slot_field is None:
            raise OntologyInfrastructureError(
                f"Effect-match dimension {dimension!r} has no authored Slot projection field"
            )
        handler = IMPLEMENTED_EFFECT_MATCH_VALUE_HANDLERS.get(value_type)
        if handler == "boolean":
            dimensions[slot_field] = {"type": "boolean"}
        elif handler == "capability_values":
            dimensions[slot_field] = {
                "type": "string",
                "minLength": 1,
                "enum": sorted(runtime.near_values),
            }
        else:
            raise OntologyInfrastructureError(f"Unsupported effect-match value handler for {dimension!r}")
    source_slot_properties: dict[str, object] = {
        "label": {**cast(Mapping[str, object], slot_properties["label"]), "minLength": 1},
        "order": cast(object, slot_properties["order"]),
        **dict(dimensions),
    }
    pillbox_label_property = {**cast(Mapping[str, object], pillbox_properties["label"]), "minLength": 1}
    slot_order = schema_view.induced_slot("order", "Slot")
    slot_class = schema_view.get_class("Slot")
    pillbox_class = schema_view.get_class("Pillbox")
    if slot_class is None or pillbox_class is None:
        raise OntologyInfrastructureError("Generated LinkML schema is missing Pillbox or Slot classes")
    slot_annotation = slot_class.annotations
    pillbox_annotation = pillbox_class.annotations

    def annotation_value(annotations: object, key: str) -> str:
        value = cast(Mapping[str, object], annotations).get(key)
        extracted = getattr(value, "value", None)
        if not isinstance(extracted, str) or not extracted:
            raise OntologyInfrastructureError(f"Ontology validation annotation {key!r} is missing")
        return extracted

    schema: dict[str, object] = {
        "$schema": _JSON_SCHEMA_FORMAT,
        "$id": f"{base_iri}generated/pillboxes.schema.json",
        "title": "Supp Slotter canonical pillbox source contract",
        "type": "object",
        "minProperties": 1,
        "propertyNames": {"pattern": "^[a-z][a-z0-9_]*$"},
        "additionalProperties": False,
        "patternProperties": {
            "^[a-z][a-z0-9_]*$": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "stack", "slots"],
                "properties": {
                    "label": pillbox_label_property,
                    "stack": {"type": "string", "minLength": 1},
                    "slots": {
                        "type": "object",
                        "minProperties": 1,
                        "propertyNames": {"pattern": "^[a-z][a-z0-9_]*$"},
                        "additionalProperties": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["label", "order", *dimensions.keys()],
                            "properties": source_slot_properties,
                        },
                    },
                },
            }
        },
        "x-supp-slotter-validation": {
            "stack_linkage": {
                "source": "<pillbox_key>",
                "source_field": "stack",
                "target_class": "Stack",
                "semantics": annotation_value(pillbox_annotation, "stack_linkage"),
            },
            "slot_identity": {
                "source": "<pillbox_key>.slots.<slot_key>",
                "scope": annotation_value(slot_annotation, "identity_scope"),
                "uniqueness": annotation_value(slot_annotation, "identity_uniqueness"),
            },
            "slot_order": {
                "field": "order",
                "scope": annotation_value(slot_annotation, "order_scope"),
                "source": "<pillbox_key>.slots.<slot_key>",
                "uniqueness": annotation_value(slot_annotation, "order_uniqueness"),
                "minimum": slot_order.minimum_value,
            },
        },
    }
    if not isinstance(slot_order.minimum_value, int) or isinstance(slot_order.minimum_value, bool):
        raise OntologyInfrastructureError("Slot order must declare an integer minimum")
    return schema


_CARD_FIELD_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_CANONICAL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_CANONICAL_PREDICATE_NAMESPACES = frozenset({"knowledge", "schedule"})


def _add_authored_card_fields(
    schema_view: SchemaView,
    runtime_policy: Mapping[str, object],
    categories: Mapping[str, object],
    base_iri: str,
) -> None:
    """Project authored assignment and vocabulary predicates into card schemas.

    ``model.yaml`` deliberately contains only the card envelopes.  This
    compiler boundary is the one place that turns the authored domain catalogs
    into concrete LinkML properties; runtime code must not maintain a second
    list of card fields.
    """

    axes = runtime_policy.get("assignment_axes")
    if not isinstance(axes, list) or not axes:
        raise OntologyInfrastructureError("Runtime policy requires non-empty assignment_axes")
    schedule_fields: dict[str, Mapping[str, object]] = {}
    for raw_axis in axes:
        if not isinstance(raw_axis, Mapping):
            raise OntologyInfrastructureError("Runtime assignment axis records must be mappings")
        axis = cast(Mapping[str, object], raw_axis)
        field = _required_string(axis, "assignment_field")
        _validate_card_field_name(field, "assignment axis")
        if axis.get("assignment_source") != "schedule":
            continue
        if field in schedule_fields:
            raise OntologyInfrastructureError(f"Duplicate generated schedule card field {field!r}")
        schedule_fields[field] = axis

    knowledge_fields: dict[str, Mapping[str, object]] = {}
    schedule_predicates: dict[str, str] = {}
    for category, raw_metadata in categories.items():
        if not isinstance(category, str) or not isinstance(raw_metadata, Mapping):
            raise OntologyInfrastructureError("Semantic category records must be mappings")
        metadata = cast(Mapping[str, object], raw_metadata)
        predicates = metadata.get("allowed_predicates")
        if not isinstance(predicates, list) or not predicates:
            raise OntologyInfrastructureError(f"Semantic category {category!r} requires allowed_predicates")
        for raw_predicate in predicates:
            if not isinstance(raw_predicate, str) or raw_predicate.count(".") != 1:
                raise OntologyInfrastructureError(
                    f"Semantic category {category!r} has malformed predicate {raw_predicate!r}"
                )
            namespace, field = raw_predicate.split(".", maxsplit=1)
            _validate_card_field_name(field, f"semantic category {category!r}")
            if namespace == "knowledge":
                owner = knowledge_fields.get(field)
                if owner is not None and owner is not metadata:
                    raise OntologyInfrastructureError(
                        f"Knowledge card field {field!r} is declared by multiple semantic categories"
                    )
                knowledge_fields[field] = metadata
            elif namespace == "schedule":
                if field in schedule_predicates and schedule_predicates[field] != category:
                    raise OntologyInfrastructureError(
                        f"Schedule predicate {field!r} is declared by multiple semantic categories"
                    )
                schedule_predicates[field] = category
            else:
                raise OntologyInfrastructureError(
                    f"Semantic category {category!r} uses unsupported predicate namespace {namespace!r}"
                )

    missing_axes = sorted(set(schedule_predicates) - set(schedule_fields))
    if missing_axes:
        raise OntologyInfrastructureError(
            "Semantic schedule predicates have no authored assignment-axis backing: " + ", ".join(missing_axes)
        )
    cross_container_collisions = sorted(set(schedule_fields) & set(knowledge_fields))
    if cross_container_collisions:
        raise OntologyInfrastructureError(
            "Card field is declared in both schedule and knowledge envelopes: " + ", ".join(cross_container_collisions)
        )

    for field, axis in sorted(schedule_fields.items()):
        _add_card_slot(
            schema_view,
            class_name="CardSchedule",
            field=field,
            base_iri=base_iri,
            cardinality=axis,
            default_maximum=1,
        )
    for field, category in sorted(knowledge_fields.items()):
        _add_card_slot(
            schema_view,
            class_name="CardKnowledge",
            field=field,
            base_iri=base_iri,
            cardinality=category,
            default_maximum=None,
        )


def _validate_card_field_name(field: str, owner: str) -> None:
    if not _CARD_FIELD_PATTERN.fullmatch(field):
        raise OntologyInfrastructureError(f"{owner} has invalid card field name {field!r}")


def _add_card_slot(
    schema_view: SchemaView,
    *,
    class_name: str,
    field: str,
    base_iri: str,
    cardinality: Mapping[str, object],
    default_maximum: int | None,
) -> None:
    existing = set(schema_view.all_slots())
    class_slots = set(schema_view.class_slots(class_name))
    if field in class_slots:
        raise OntologyInfrastructureError(f"Generated card field collides with authored {class_name}.{field}")
    minimum, maximum, multivalued = _card_cardinality(cardinality, default_maximum)
    definition = SlotDefinition(
        name=field,
        description=f"Authored card assertion field {field}.",
        from_schema=base_iri,
        slot_uri=f"{base_iri}{field}",
        range="string",
        multivalued=multivalued,
        inlined_as_list=multivalued,
        minimum_cardinality=minimum,
        maximum_cardinality=maximum,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    if field in existing:
        # A few generic protocol slots (for example ``kind`` and ``effect``)
        # are intentionally untyped elsewhere in the merged LinkML graph.
        # Keep those globals untouched and apply the authored card shape as
        # class-local usage; typed or multivalued collisions are unsafe.
        global_slot = schema_view.get_slot(field)
        if global_slot is None:
            raise OntologyInfrastructureError(f"Generated card field global slot is missing: {field!r}")
        if global_slot.range is not None or bool(global_slot.multivalued):
            raise OntologyInfrastructureError(f"Generated card field collides with global slot {field!r}")
        card_class = schema_view.get_class(class_name)
        if card_class is None or card_class.slot_usage is None:
            raise OntologyInfrastructureError(f"Generated card class is missing slot usage: {class_name}")
        card_class.slot_usage[field] = definition
    else:
        schema_view.add_slot(definition)
    card_class = schema_view.get_class(class_name)
    if card_class is None or card_class.slots is None:
        raise OntologyInfrastructureError(f"Generated card class is missing slots: {class_name}")
    card_class.slots.append(field)
    # JsonSchemaGenerator starts from the manifest root and reloads imported
    # modules.  Re-export the modified imported definitions on that root so
    # generated artifacts see the same compiler projection.
    schema = schema_view.schema
    if schema is None or schema.slots is None or schema.classes is None:
        raise OntologyInfrastructureError("Generated LinkML schema is missing slot/class containers")
    schema.slots[field] = definition
    schema.classes[class_name] = card_class


def _card_cardinality(source: Mapping[str, object], default_maximum: int | None) -> tuple[int | None, int | None, bool]:
    legacy = set(source) & {"cardinality"}
    if legacy:
        raise OntologyInfrastructureError(
            "Card field uses removed legacy cardinality fields: " + ", ".join(sorted(legacy))
        )
    raw_multivalued = source.get("multivalued", True)
    if not isinstance(raw_multivalued, bool):
        raise OntologyInfrastructureError("Card field multivalued must be boolean")
    minimum = source.get("minimum_cardinality")
    maximum = source.get("maximum_cardinality", default_maximum)
    if minimum is not None and (not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0):
        raise OntologyInfrastructureError("Card field minimum_cardinality must be a non-negative integer")
    if maximum is not None and (not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 0):
        raise OntologyInfrastructureError("Card field maximum_cardinality must be a non-negative integer")
    if maximum is not None and minimum is not None and minimum > maximum:
        raise OntologyInfrastructureError("Card field minimum_cardinality exceeds maximum_cardinality")
    # Card assertions are represented as arrays even when the effective
    # maximum is one. Their acceptance is governed by min/max; multivalued is
    # retained only as the LinkML container representation.
    return minimum, maximum, raw_multivalued


def _schema_view(ontology_root: Path, manifest: Mapping[str, object]) -> SchemaView:
    """Load the one merged LinkML schema graph used by all schema projections."""
    try:
        return SchemaView(str(_source_path(ontology_root, _required_string(manifest, "linkml_root"))))
    except Exception as error:  # LinkML owns parser/compiler failure details.
        raise OntologyInfrastructureError(f"LinkML cannot load canonical root: {error}") from error


def _validate_manifest_catalog_root_classes(manifest: Mapping[str, object], schema_view: SchemaView) -> None:
    """Ensure manifest catalog roots name real LinkML classes, not Python-only contracts."""
    schema_classes = set(schema_view.all_classes())
    for catalog in cast(list[dict[str, object]], manifest["catalogs"]):
        root_class = str(catalog["root_class"])
        if root_class == "ShapesGraph":
            continue
        if root_class not in schema_classes:
            raise OntologyInfrastructureError(
                f"Manifest catalog {catalog['id']!r} references unknown root_class {root_class!r}"
            )


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


def _validate_repository_projection_coverage(ontology_root: Path, manifest: Mapping[str, object]) -> None:
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
            document = _safe_yaml_load(catalog_file.read_text(encoding="utf-8"), path=catalog_file)
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
                document = _safe_yaml_load(file_path.read_text(encoding="utf-8"), path=file_path)
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


def _validate_runtime_condition(
    value: object,
    label: str,
    condition_path_types: Mapping[str, str],
    *,
    allow_empty: bool = False,
) -> None:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a condition list" if allow_empty else "a non-empty condition list"
        raise OntologyInfrastructureError(f"Runtime {label} must be {qualifier}")
    for index, raw in enumerate(value):
        _validate_runtime_condition_node(raw, f"{label}[{index}]", condition_path_types)


def _validate_runtime_condition_node(value: object, label: str, condition_path_types: Mapping[str, str]) -> None:
    if not isinstance(value, dict):
        raise OntologyInfrastructureError(f"Runtime {label} condition must be a mapping")
    operator = value.get("operator")
    if not isinstance(operator, str) or operator not in _CONDITION_OPERATORS:
        raise OntologyInfrastructureError(f"Runtime {label} has unknown condition operator")
    if operator in {"equals", "contains", "equals_field", "member_of_field", "is_true", "is_false"}:
        expected = (
            {"operator", "field", "value"}
            if operator in {"equals", "contains", "equals_field", "member_of_field"}
            else {"operator", "field"}
        )
        if set(value) != expected:
            raise OntologyInfrastructureError(f"Runtime {label} has invalid keys for {operator}")
        field = value.get("field")
        field_type = condition_path_types.get(field) if isinstance(field, str) else None
        if field_type is None:
            raise OntologyInfrastructureError(f"Runtime {label} references unknown condition path")
        if operator in {"equals_field", "member_of_field"}:
            other = value.get("value")
            other_type = condition_path_types.get(other) if isinstance(other, str) else None
            compatible = (
                field_type == other_type
                if operator == "equals_field"
                else field_type == "string" and other_type == "strings"
            )
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
    if (
        set(value) != {"operator", "conditions"}
        or not isinstance(value.get("conditions"), list)
        or not value["conditions"]
    ):
        raise OntologyInfrastructureError(f"Runtime {label} logical condition requires non-empty conditions")
    if operator == "not" and len(value["conditions"]) != 1:
        raise OntologyInfrastructureError(f"Runtime {label} not requires one child")
    for index, child in enumerate(value["conditions"]):
        _validate_runtime_condition_node(child, f"{label}.conditions[{index}]", condition_path_types)


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


# These are the semantic identities consumed by runtime lookup and matching.
# ``id`` remains a technical provenance key; it must never be the only
# uniqueness guard for a catalog whose records can have distinct IDs but the
# same executable meaning.
_RUNTIME_SEMANTIC_KEYS: Mapping[str, tuple[tuple[str, ...], ...]] = {
    "source_kind_values": (("source_kind",),),
    "effect_match_dimensions": (("key",), ("slot_field",)),
    "assignment_axes": (("axis",), ("order",)),
    "constraint_execution_policies": (("operation",),),
    "warning_types": (("warning_type",),),
    "warning_emitters": (("emitter",),),
    "warning_trait_actions": (("trait_id",),),
    "concern_catalog": (("concern_kind",),),
    "relation_warning_rules": (("relation_kind", "filter_field", "filter_value", "active_side", "reverse_output"),),
    "relation_presence_statuses": (("status",), ("source_active", "target_active")),
    "selector_form_capabilities": (("selector_form",),),
}


def _validate_runtime_semantic_keys(
    records: Mapping[str, Sequence[Mapping[str, object]]],
) -> None:
    """Reject duplicate executable identities independently of record IDs."""
    for slot, key_sets in _RUNTIME_SEMANTIC_KEYS.items():
        rows = records[slot]
        for fields in key_sets:
            seen: dict[tuple[object, ...], int] = {}
            for index, row in enumerate(rows):
                key = tuple(row.get(field) for field in fields)
                if any(value is None for value in key):
                    raise OntologyInfrastructureError(
                        f"Runtime {slot}[{index}] is missing semantic key fields: {', '.join(fields)}"
                    )
                previous = seen.get(key)
                if previous is not None:
                    rendered = ":".join(repr(value) for value in key)
                    raise OntologyInfrastructureError(
                        f"Runtime {slot} has duplicate semantic key ({', '.join(fields)})={rendered} "
                        f"at rows {previous} and {index}"
                    )
                seen[key] = index


@dataclass(frozen=True)
class _ConstraintRuntime:
    execution_policies: Mapping[str, Mapping[str, object]]
    selector_kinds: set[str]


@dataclass(frozen=True)
class _PolicyRuntime:
    authored: dict[str, object]
    assignment_axes: set[str]
    near_values: set[str]
    score_levels: set[str]
    effect_match_dimensions: Mapping[str, str]
    effect_match_slot_fields: Mapping[str, str]
    constraints: _ConstraintRuntime


@dataclass(frozen=True)
class _SchedulingPolicyContext:
    term_metadata: Mapping[str, object]
    near_values: set[str]
    score_levels: set[str]
    effect_match_dimensions: Mapping[str, str]


def _load_runtime_policy(
    ontology_root: Path, manifest: Mapping[str, object], schema_view: SchemaView, relation_types: set[str]
) -> _PolicyRuntime:
    source = _load_yaml_mapping(_catalog_path(ontology_root, manifest, "runtime_policy"))
    _validate_linkml_instance(schema_view, "RuntimePolicyCatalog", source)
    required_mappings = ("glue_contract", "effect_scoring", "prefer_with_policy")
    if any(not isinstance(source.get(key), dict) for key in required_mappings):
        raise OntologyInfrastructureError("Runtime policy requires glue_contract, scoring, and preferences")
    records = {
        key: _runtime_records(source, key)
        for key in (
            "source_kind_values",
            "effect_match_dimensions",
            "assignment_axes",
            "constraint_execution_policies",
            "warning_types",
            "warning_emitters",
            "warning_trait_actions",
            "concern_catalog",
            "relation_warning_rules",
            "relation_presence_statuses",
            "selector_form_capabilities",
        )
    }
    _validate_runtime_glue_contract(cast(Mapping[str, object], source["glue_contract"]))
    _validate_runtime_record_shapes(records)
    _validate_runtime_semantic_keys(records)
    _validate_runtime_relation_presence_contract(
        cast(Mapping[str, object], source["glue_contract"]),
        records["relation_presence_statuses"],
    )
    _validate_runtime_source_kind_contract(
        cast(Mapping[str, object], source["glue_contract"]), records["source_kind_values"]
    )
    scoring = cast(Mapping[str, object], source["effect_scoring"])
    scores = scoring.get("scores")
    if not isinstance(scores, list) or not scores:
        raise OntologyInfrastructureError("Runtime effect_scoring requires non-empty scores")
    score_levels = {
        _required_string(cast(Mapping[str, object], row), "level")
        for row in cast(list[object], scores)
        if isinstance(row, Mapping)
    }
    assignment_axes = {_required_string(row, "axis") for row in records["assignment_axes"]}
    raw_near_values = source.get("slot_near_values")
    if (
        not isinstance(raw_near_values, list)
        or not raw_near_values
        or not all(isinstance(value, str) and value for value in raw_near_values)
    ):
        raise OntologyInfrastructureError("Runtime policy slot_near_values must be a non-empty list of strings")
    near_values = set(cast(list[str], raw_near_values))
    if len(near_values) != len(raw_near_values):
        raise OntologyInfrastructureError("Runtime policy slot_near_values must not contain duplicates")
    effect_match_dimensions: dict[str, str] = {}
    effect_match_slot_fields: dict[str, str] = {}
    for row in records["effect_match_dimensions"]:
        key = _required_string(row, "key")
        slot_field = _required_string(row, "slot_field")
        _validate_card_field_name(slot_field, "effect-match Slot projection")
        if key in effect_match_dimensions:
            raise OntologyInfrastructureError(f"Runtime effect-match dimension key is duplicated: {key!r}")
        if slot_field in effect_match_slot_fields.values():
            raise OntologyInfrastructureError(f"Runtime effect-match slot field is duplicated: {slot_field!r}")
        if slot_field in {"id", "label", "order"}:
            raise OntologyInfrastructureError(
                f"Runtime effect-match slot field conflicts with a technical Slot field: {slot_field!r}"
            )
        effect_match_dimensions[key] = _required_string(row, "value_type")
        effect_match_slot_fields[key] = slot_field
    execution = {_required_string(row, "operation"): row for row in records["constraint_execution_policies"]}
    # Endpoint selector kinds are execution grammar.  Keep this closed over
    # the runtime glue registry; decorative kinds must not enter the compiled
    # ontology without an actual typed handler.
    selector_kinds = set(IMPLEMENTED_RELATION_ENDPOINT_SELECTOR_KINDS)
    selector_forms = tuple(_required_string(row, "selector_form") for row in records["selector_form_capabilities"])
    if selector_forms != IMPLEMENTED_RELATION_SELECTOR_FORMS:
        raise OntologyInfrastructureError(
            "Runtime selector form capabilities must exactly match executable selector forms; "
            "unknown selector form or missing executable selector"
        )
    endpoint_kinds = {_required_string(row, "endpoint_kind") for row in records["selector_form_capabilities"]}
    if endpoint_kinds != set(IMPLEMENTED_RELATION_ENDPOINT_SELECTOR_KINDS):
        raise OntologyInfrastructureError(
            "Runtime selector form capabilities must exactly match executable endpoint kinds"
        )
    emitter_ids = tuple(_required_string(row, "emitter") for row in records["warning_emitters"])
    expected_emitter_ids = IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS["warning_emitter_ids"]
    if set(emitter_ids) != set(expected_emitter_ids) or len(emitter_ids) != len(expected_emitter_ids):
        raise OntologyInfrastructureError("Runtime warning emitters must exactly match executable emitter IDs")
    for row in records["relation_warning_rules"]:
        if _required_string(row, "relation_kind") not in relation_types:
            raise OntologyInfrastructureError("Runtime relation warning rule references unknown relation type")
    return _PolicyRuntime(
        authored=dict(source),
        assignment_axes=assignment_axes,
        near_values=near_values,
        score_levels=score_levels,
        effect_match_dimensions=effect_match_dimensions,
        effect_match_slot_fields=effect_match_slot_fields,
        constraints=_ConstraintRuntime(execution, selector_kinds),
    )


def _validate_runtime_glue_contract(glue: Mapping[str, object]) -> None:
    if not glue:
        raise OntologyInfrastructureError("Runtime glue_contract must not be empty")
    for field, allowed in IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS.items():
        values = glue.get(field)
        if not isinstance(values, list) or tuple(values) != allowed:
            raise OntologyInfrastructureError(
                f"Runtime glue_contract {field} must exactly match executable capabilities"
            )
    endpoint_kinds = glue.get("relation_endpoint_selector_kinds")
    if not isinstance(endpoint_kinds, list) or tuple(endpoint_kinds) != IMPLEMENTED_RELATION_ENDPOINT_SELECTOR_KINDS:
        raise OntologyInfrastructureError(
            "Runtime glue_contract relation_endpoint_selector_kinds must exactly match executable capabilities"
        )
    truth = glue.get("relation_presence_truth_table")
    if not isinstance(truth, list):
        raise OntologyInfrastructureError("Runtime glue_contract relation presence truth table must be a list")
    states: list[tuple[bool, bool]] = []
    for index, raw_state in enumerate(truth):
        if not isinstance(raw_state, Mapping):
            raise OntologyInfrastructureError(
                f"Runtime glue_contract relation presence truth table row {index} must be a mapping"
            )
        source_active = raw_state.get("source_active")
        target_active = raw_state.get("target_active")
        if not isinstance(source_active, bool) or not isinstance(target_active, bool):
            raise OntologyInfrastructureError(
                "Runtime glue_contract relation presence truth table booleans must be strict booleans"
            )
        state = (source_active, target_active)
        if state in states:
            raise OntologyInfrastructureError(
                f"Runtime glue_contract relation presence truth table has duplicate state {state!r}"
            )
        states.append(state)
    expected_truth = set(IMPLEMENTED_RELATION_PRESENCE_TRUTH_TABLE)
    if set(states) != expected_truth:
        raise OntologyInfrastructureError(
            "Runtime glue_contract relation presence truth table must have exact unique four-state coverage"
        )


def _validate_runtime_record_shapes(records: Mapping[str, Sequence[Mapping[str, object]]]) -> None:
    for slot, rows in records.items():
        if not rows:
            raise OntologyInfrastructureError(f"Runtime policy requires non-empty {slot}")
        ids = [row.get("id") for row in rows]
        if any(not isinstance(identifier, str) or not identifier for identifier in ids) or len(set(ids)) != len(ids):
            raise OntologyInfrastructureError(f"Runtime policy {slot} has invalid or duplicate ids")
    for row in records["assignment_axes"]:
        legacy = set(row) & {"cardinality", "multivalued"}
        if legacy:
            raise OntologyInfrastructureError(
                "Runtime assignment axes use removed legacy cardinality fields: " + ", ".join(sorted(legacy))
            )
        if not isinstance(row.get("order"), int) or isinstance(row.get("order"), bool):
            raise OntologyInfrastructureError("Runtime assignment axes require integer order")
        if "minimum_cardinality" not in row or "maximum_cardinality" not in row:
            raise OntologyInfrastructureError(
                "Runtime assignment axes require minimum_cardinality and maximum_cardinality"
            )
        minimum = row["minimum_cardinality"]
        maximum = row["maximum_cardinality"]
        if minimum is not None and (not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0):
            raise OntologyInfrastructureError("Runtime assignment axes require non-negative minimum_cardinality")
        if maximum is not None and (not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 0):
            raise OntologyInfrastructureError("Runtime assignment axes require non-negative maximum_cardinality")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise OntologyInfrastructureError("Runtime assignment axis minimum_cardinality exceeds maximum_cardinality")
    for row in records["constraint_execution_policies"]:
        if not isinstance(row.get("blocks_slots"), bool) or not isinstance(row.get("scores_advisory"), bool):
            raise OntologyInfrastructureError("Runtime constraint execution policy booleans are required")
    boolean_fields = {
        "relation_warning_rules": ("reverse_output",),
        "relation_presence_statuses": ("source_active", "target_active"),
        "selector_form_capabilities": ("show_match_details",),
    }
    for slot, fields in boolean_fields.items():
        for row in records[slot]:
            if any(not isinstance(row.get(field), bool) for field in fields):
                raise OntologyInfrastructureError(f"Runtime {slot} boolean fields are required")


def _validate_runtime_relation_presence_contract(
    glue: Mapping[str, object], statuses: Sequence[Mapping[str, object]]
) -> None:
    """Require one executable status for each endpoint-presence truth state."""
    truth = glue.get("relation_presence_truth_table")
    if not isinstance(truth, list):
        raise OntologyInfrastructureError("Runtime relation presence truth table must be a list")
    expected = {
        (state.get("source_active"), state.get("target_active"))
        for state in cast(list[object], truth)
        if isinstance(state, Mapping)
    }
    actual = {(row.get("source_active"), row.get("target_active")) for row in statuses}
    if actual != expected:
        raise OntologyInfrastructureError(
            "Runtime relation_presence_statuses must have exact unique four-state coverage"
        )


def _validate_runtime_source_kind_contract(glue: Mapping[str, object], rows: Sequence[Mapping[str, object]]) -> None:
    source_kinds = glue.get("source_kinds")
    if not isinstance(source_kinds, list) or not all(isinstance(value, str) and value for value in source_kinds):
        raise OntologyInfrastructureError("Runtime glue_contract source_kinds must be strings")
    authored = {_required_string(row, "source_kind") for row in rows}
    if set(source_kinds) != authored:
        raise OntologyInfrastructureError("Runtime glue_contract source_kinds must match source_kind_values")
    source_kind_roles = glue.get("source_kind_roles")
    if not isinstance(source_kind_roles, list) or not all(
        isinstance(value, str) and value for value in source_kind_roles
    ):
        raise OntologyInfrastructureError("Runtime glue_contract source_kind_roles must be strings")
    declared_roles = set(source_kind_roles)
    applied_roles = {
        role for row in rows for role in cast(Sequence[object], row.get("applies_to", [])) if isinstance(role, str)
    }
    if not applied_roles.issubset(declared_roles):
        unknown = sorted(applied_roles - declared_roles)
        raise OntologyInfrastructureError(f"Runtime source_kind_values reference undeclared roles: {unknown}")


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
    document = _generated_json_schema_document(schema_view)
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


def _generated_json_schema_document(schema_view: SchemaView) -> dict[str, object]:
    """Generate JSON Schema while preserving LinkML zero-cardinality conditions.

    LinkML emits ``oneOf`` for ``exactly_one_of`` but its JSON Schema generator
    currently drops ``maximum_cardinality: 0`` from branch slot conditions.
    Restore those formally authored exclusions generically so downstream
    validators enforce the same class expression as LinkML and SHACL.
    """
    schema = _require_schema_definition(schema_view.schema)
    document = _json_mapping_from_text(_require_serializer(JsonSchemaGenerator(schema)).serialize())
    definitions = document.get("$defs")
    if not isinstance(definitions, dict):
        raise OntologyInfrastructureError("Generated LinkML JSON Schema has no $defs")
    for class_name, class_definition in schema_view.all_classes().items():
        expressions = cast(list[AnonymousClassExpression], class_definition.exactly_one_of or [])
        if not expressions:
            continue
        generated_class = definitions.get(class_name)
        if not isinstance(generated_class, dict):
            raise OntologyInfrastructureError(f"Generated LinkML JSON Schema has no class {class_name}")
        branches = generated_class.get("oneOf")
        if not isinstance(branches, list) or len(branches) != len(expressions):
            raise OntologyInfrastructureError(f"Generated LinkML JSON Schema lost {class_name} exactly_one_of")
        for expression, branch in zip(expressions, branches, strict=True):
            if not isinstance(branch, dict):
                raise OntologyInfrastructureError(f"Generated LinkML JSON Schema has malformed {class_name} branch")
            raw_conditions = expression.slot_conditions or {}
            if not isinstance(raw_conditions, dict):
                raise OntologyInfrastructureError(f"LinkML {class_name} slot conditions must be a mapping")
            conditions = cast(dict[object, SlotDefinition], raw_conditions)
            forbidden = sorted(
                str(slot_name) for slot_name, condition in conditions.items() if condition.maximum_cardinality == 0
            )
            if forbidden:
                branch["not"] = {"anyOf": [{"required": [slot_name]} for slot_name in forbidden]}
    _tighten_relation_selector_schema(definitions)
    return document


def _apply_relation_type_enum(
    generated_schema: dict[str, object], relation_types: Mapping[str, Mapping[str, object]]
) -> None:
    """Inject the authored relation catalog IDs into the generated schema.

    Relation type identifiers are runtime vocabulary, not LinkML model
    structure.  The catalog is validated before this projection, so it is the
    sole source of the closed JSON-Schema enum used by loaders and consumers.
    """

    definitions = generated_schema.get("$defs")
    if not isinstance(definitions, dict):
        raise OntologyInfrastructureError("Generated LinkML schema has no class/type definitions")
    relation_type = definitions.get("RelationType")
    if not isinstance(relation_type, dict):
        raise OntologyInfrastructureError("Generated LinkML schema has no RelationType definition")
    values = sorted(relation_types)
    if not values:
        raise OntologyInfrastructureError("Relation type catalog must not be empty")
    relation_type["type"] = "string"
    relation_type["enum"] = values


def _tighten_relation_selector_schema(definitions: Mapping[str, object]) -> None:
    """Make authored relation selector scalar branches strict and non-null.

    LinkML represents optional scalar slots as ``string | null`` in JSON
    Schema.  The relation selector union already provides the optionality at
    the branch level, so accepting null here would create a third state that
    the compiler and runtime deliberately reject.  Keep this invariant in
    the generated artifact rather than relying on each loader to compensate.
    """
    fields_by_class = {
        "RelationAssertionEntitySelector": ("entity_id", "name"),
        "RelationAssertionSelector": ("category", "term"),
    }
    for class_name, fields in fields_by_class.items():
        raw_definition = definitions.get(class_name)
        if not isinstance(raw_definition, dict):
            raise OntologyInfrastructureError(f"Generated LinkML JSON Schema has no class {class_name}")
        properties = raw_definition.get("properties")
        if not isinstance(properties, dict):
            raise OntologyInfrastructureError(f"Generated {class_name} has no properties")
        for field in fields:
            property_schema = properties.get(field)
            if not isinstance(property_schema, dict):
                raise OntologyInfrastructureError(f"Generated {class_name} field {field!r} is missing")
            property_schema["type"] = "string"
            property_schema["minLength"] = 1
            property_schema["pattern"] = r"\S"
    selector_definition = definitions["RelationAssertionSelector"]
    if not isinstance(selector_definition, dict):
        raise OntologyInfrastructureError("Generated LinkML JSON Schema has no class RelationAssertionSelector")
    selector_properties = selector_definition.get("properties")
    if not isinstance(selector_properties, dict):
        raise OntologyInfrastructureError("Generated RelationAssertionSelector has no properties")
    entity_schema = selector_properties.get("entity")
    if not isinstance(entity_schema, dict):
        raise OntologyInfrastructureError("Generated RelationAssertionSelector entity field is missing")
    selector_properties["entity"] = {"$ref": "#/$defs/RelationAssertionEntitySelector"}


def _linkml_catalog_instance(class_name: str, source: Mapping[str, object]) -> Mapping[str, object]:
    """Return the LinkML validation view for keyed-map catalog YAML."""
    if class_name == "VocabularyCatalog":
        categories = _required_mapping(source, "semantic_categories")
        return {
            "semantic_categories": _keyed_record_map(categories),
            # The profile is derived from the category in authored YAML, but
            # is a required OntologyTerm field in the LinkML instance shape.
            "terms": _term_records(source.get("terms", []), categories),
        }
    if class_name == "OntoCleanCatalog":
        return {"ontoclean_profiles": _keyed_record_map(_required_mapping(source, "ontoclean_profiles"))}
    if class_name == "SchedulingPolicyCatalog":
        return {
            "scheduling_policies": _keyed_record_map(_required_mapping(source, "scheduling_policies")),
            "schedule_presentation": source.get("schedule_presentation"),
        }
    if class_name == "RelationCatalog":
        return {"relation_types": source.get("relation_types", [])}
    if class_name == "RelationAssertionCatalog":
        return {"relations": source.get("relations", [])}
    return source


def _keyed_record_map(source: Mapping[str, object]) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for identifier, value in source.items():
        if not isinstance(identifier, str) or not isinstance(value, Mapping):
            raise OntologyInfrastructureError("Keyed ontology catalog records must map string ids to mappings")
        record = dict(cast(Mapping[str, object], value))
        embedded_id = record.get("id")
        if "id" in record and embedded_id != identifier:
            raise OntologyInfrastructureError(
                f"Keyed ontology catalog record {identifier!r} has mismatched embedded id {embedded_id!r}"
            )
        if identifier in records:
            raise OntologyInfrastructureError(f"Duplicate canonical ontology catalog id: {identifier!r}")
        records[identifier] = {"id": identifier, **record}
    return records


def _term_records(source: object, categories: Mapping[str, object]) -> list[dict[str, object]]:
    if not isinstance(source, list):
        raise OntologyInfrastructureError("Vocabulary terms must be a list")
    if not source:
        raise OntologyInfrastructureError("Vocabulary terms must not be empty")
    records: list[dict[str, object]] = []
    for index, value in enumerate(source):
        if not isinstance(value, Mapping):
            raise OntologyInfrastructureError(f"Vocabulary term record {index} must be a mapping")
        record = dict(cast(Mapping[str, object], value))
        unknown = set(record) - {"slug", "label", "description", "semantic_category"}
        if unknown:
            raise OntologyInfrastructureError(
                f"Vocabulary term record {index} has unsupported fields: {', '.join(sorted(map(str, unknown)))}"
            )
        category = _required_string(record, "semantic_category")
        slug = _required_string(record, "slug")
        category_metadata = _required_mapping(categories, category)
        records.append({
            "id": f"{category}:{slug}",
            "ontoclean_profile": _required_string(category_metadata, "ontoclean_profile"),
            **record,
        })
    return records


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
    *,
    seen_targets: set[str] | None = None,
    seen_descriptor_ids: set[str] | None = None,
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
    if seen_sources is None:
        seen_sources = {}
    expected_targets = RUNTIME_PROJECTION_FIELDS.get(".".join(path), frozenset())
    if not expected_targets:
        raise OntologyInfrastructureError(
            f"Runtime projection descriptor path {'.'.join(path) or '<root>'!r} is not executable"
        )
    descriptor_targets: set[str] = set()
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
        if target not in expected_targets:
            raise OntologyInfrastructureError(
                f"Runtime projection target {'.'.join((*path, target))!r} is not executable"
            )
        descriptor_targets.add(target)
        if descriptor_id in seen_descriptor_ids:
            raise OntologyInfrastructureError(f"Runtime projection has duplicate descriptor id {descriptor_id!r}")
        seen_descriptor_ids.add(descriptor_id)
        qualified_target = ".".join((*path, target))
        if qualified_target in seen_targets:
            raise OntologyInfrastructureError(f"Runtime projection has duplicate output path {qualified_target!r}")
        seen_targets.add(qualified_target)
        children = descriptor.get("children")
        source = descriptor.get("source")
        if (children is None) == (source is None):
            raise OntologyInfrastructureError(
                f"Runtime projection {descriptor_id!r} requires exactly one of source or children"
            )
        if children is not None:
            if ".".join((*path, target)) not in RUNTIME_PROJECTION_FIELDS:
                raise OntologyInfrastructureError(
                    f"Runtime projection {descriptor_id!r} target {'.'.join((*path, target))!r} cannot have children"
                )
            value = _runtime_projection_tree(
                policy,
                children,
                seen_targets=seen_targets,
                seen_descriptor_ids=seen_descriptor_ids,
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
        projected[target] = value
    if descriptor_targets != expected_targets:
        missing = ", ".join(sorted(expected_targets - descriptor_targets))
        raise OntologyInfrastructureError(
            f"Runtime projection path {'.'.join(path) or '<root>'!r} has incomplete executable targets"
            + (f": missing {missing}" if missing else "")
        )
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
    projected = _runtime_projection_tree(policy, policy.get("runtime_projection"))
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
        # The descriptor tree is the sole authored topology.  Keep the
        # compiler output generic so adding a policy branch requires only a
        # descriptor edit, not another Python section.
        "projection": projected,
    }
    _validate_runtime_program_output(program)
    # Compile-time parity check: the same closed DTO decoder used by planner
    # runtime must accept the emitted projection, so source mutations cannot
    # produce silently ignored branches or row fields.
    from planner.ontology.runtime_program import decode_runtime_program

    decode_runtime_program(program)
    return program


def _validate_runtime_program_output(program: Mapping[str, object]) -> None:
    """Validate the closed generic runtime-program envelope before emission."""
    required = {
        "format_version",
        "schema_version",
        "source_hash",
        "provenance",
        "projection",
    }
    if set(program) != required:
        raise OntologyInfrastructureError("Runtime program has an invalid top-level shape")
    provenance = program["provenance"]
    if not isinstance(provenance, Mapping) or set(provenance) != {
        "source",
        "source_sha256",
        "manifest_schema_version",
        "compiler_sha256",
    }:
        raise OntologyInfrastructureError("Runtime program provenance has an invalid shape")
    for key in provenance:
        if not isinstance(provenance[key], str) or not provenance[key]:
            raise OntologyInfrastructureError(f"Runtime program provenance {key} must be a non-empty string")
    projection = program["projection"]
    if not isinstance(projection, Mapping):
        raise OntologyInfrastructureError("Runtime program projection must be a mapping")


def _canonical_shapes(schema_view: SchemaView, relation_types: Mapping[str, Mapping[str, object]]) -> str:
    """Canonicalize LinkML SHACL output (including generated blank nodes)."""
    schema = _require_schema_definition(schema_view.schema)
    serializer = _require_serializer(ShaclGenerator(schema))
    generated = serializer.serialize()
    if not isinstance(generated, str):
        raise OntologyInfrastructureError("LinkML SHACL serializer returned a non-text document")
    graph = Graph()
    graph.parse(data=generated, format="turtle")
    _apply_relation_type_shacl_enum(graph, schema_view, relation_types)
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


def _apply_relation_type_shacl_enum(
    graph: Graph, schema_view: SchemaView, relation_types: Mapping[str, Mapping[str, object]]
) -> None:
    """Project catalog relation IDs into LinkML's generated SHACL enum."""

    schema = _require_schema_definition(schema_view.schema)
    prefixes_value = cast(object, schema.prefixes)
    if not isinstance(prefixes_value, dict):
        raise OntologyInfrastructureError("LinkML schema has no prefix mapping")
    prefix_entry = cast(Mapping[object, object], prefixes_value).get("ss")
    if not isinstance(prefix_entry, Prefix):
        raise OntologyInfrastructureError("LinkML schema has no ss prefix")
    relation_path = URIRef(f"{prefix_entry.prefix_reference}relation_type")
    enum_property = next(
        (
            property_node
            for shape in graph.subjects(RDF.type, SH.NodeShape)
            for property_node in graph.objects(shape, SH.property)
            if (property_node, SH.path, relation_path) in graph
        ),
        None,
    )
    if enum_property is None:
        raise OntologyInfrastructureError("Generated SHACL has no relation_type property shape")
    old_heads = list(graph.objects(enum_property, SH["in"]))
    for old_head in old_heads:
        graph.remove((enum_property, SH["in"], old_head))
    values = sorted(relation_types)
    if not values:
        raise OntologyInfrastructureError("Relation type catalog must not be empty")
    nodes = [BNode() for _ in values]
    for index, (node, value) in enumerate(zip(nodes, values, strict=True)):
        graph.add((node, RDF.first, Literal(value)))
        graph.add((node, RDF.rest, nodes[index + 1] if index + 1 < len(nodes) else RDF.nil))
    graph.add((enum_property, SH["in"], nodes[0]))


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


def _load_ontoclean_profiles(
    ontology_root: Path, manifest: Mapping[str, object], schema_view: SchemaView
) -> dict[str, dict[str, object]]:
    """Load and execute the OntoClean profile catalog.

    Profiles are keyed records: the map key is their only canonical identity.
    The small consistency rules below are the OntoClean semantics used by this
    ontology, rather than decorative copies of the profile fields.
    """

    source = _load_yaml_mapping(_catalog_path(ontology_root, manifest, "ontoclean"))
    raw_profiles = _required_mapping(source, "ontoclean_profiles")
    profiles = _keyed_record_map(raw_profiles)
    for profile_id, profile in profiles.items():
        _validate_canonical_name(profile_id, "OntoClean profile key")
        unknown = set(profile) - {"id", "rigidity", "supplies_identity", "dependence"}
        if unknown:
            raise OntologyInfrastructureError(
                f"OntoClean profile {profile_id!r} has unsupported fields: {', '.join(sorted(map(str, unknown)))}"
            )
        rigidity = _required_string(profile, "rigidity")
        dependence = _required_string(profile, "dependence")
        supplies_identity = profile.get("supplies_identity")
        if rigidity not in _ONTOCLEAN_RIGIDITY_VALUES:
            raise OntologyInfrastructureError(f"OntoClean profile {profile_id!r} has invalid rigidity {rigidity!r}")
        if dependence not in _ONTOCLEAN_DEPENDENCE_VALUES:
            raise OntologyInfrastructureError(f"OntoClean profile {profile_id!r} has invalid dependence {dependence!r}")
        if not isinstance(supplies_identity, bool):
            raise OntologyInfrastructureError(f"OntoClean profile {profile_id!r} supplies_identity must be boolean")
        if rigidity == "anti_rigid" and supplies_identity:
            raise OntologyInfrastructureError(f"OntoClean profile {profile_id!r} is anti-rigid but supplies identity")
        if dependence == "independent" and not supplies_identity:
            raise OntologyInfrastructureError(
                f"OntoClean profile {profile_id!r} is independent but does not supply identity"
            )
        if supplies_identity and (rigidity != "rigid" or dependence != "independent"):
            raise OntologyInfrastructureError(
                f"OntoClean profile {profile_id!r} identity supply requires rigid independent semantics"
            )
        if rigidity == "anti_rigid" and dependence != "dependent":
            raise OntologyInfrastructureError(
                f"OntoClean profile {profile_id!r} anti-rigid semantics require dependence"
            )
    return dict(sorted(profiles.items()))


def _normalized_terms(
    vocabulary: Mapping[str, object], profiles: Mapping[str, Mapping[str, object]]
) -> list[dict[str, object]]:
    categories = _required_mapping(vocabulary, "semantic_categories")
    raw_terms = vocabulary.get("terms")
    if not isinstance(raw_terms, list):
        raise OntologyInfrastructureError("Vocabulary catalog terms must be a list")
    if not raw_terms:
        raise OntologyInfrastructureError("Vocabulary catalog terms must not be empty")
    normalized: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    allowed_fields = {"slug", "label", "description", "semantic_category"}
    for index, raw_term in enumerate(raw_terms):
        if not isinstance(raw_term, Mapping):
            raise OntologyInfrastructureError(f"Vocabulary term {index} must be a mapping")
        term = cast(dict[str, object], raw_term)
        unknown = set(term) - allowed_fields
        if unknown:
            raise OntologyInfrastructureError(
                f"Vocabulary term {index} has unsupported fields: {', '.join(sorted(map(str, unknown)))}"
            )
        slug = _required_string(term, "slug")
        category = _required_string(term, "semantic_category")
        _validate_canonical_name(slug, f"Vocabulary term {index} slug")
        _validate_canonical_name(category, f"Vocabulary term {index} semantic_category")
        if category not in categories:
            raise OntologyInfrastructureError(f"Term {slug!r} has unknown semantic category {category!r}")
        key = (category, slug)
        if key in seen:
            raise OntologyInfrastructureError(f"Duplicate ontology term {category}:{slug}")
        seen.add(key)
        category_metadata = _required_mapping(cast(Mapping[str, object], categories), category)
        profile_id = _required_string(category_metadata, "ontoclean_profile")
        if profile_id not in profiles:
            raise OntologyInfrastructureError(
                f"Semantic category {category!r} references unknown OntoClean profile {profile_id!r}"
            )
        normalized_term: dict[str, object] = {
            "slug": slug,
            "label": _required_string(term, "label"),
            "description": _required_string(term, "description"),
            "semantic_category": category,
            "allowed_predicates": _required_string_list(category_metadata, "allowed_predicates"),
            "ontoclean_profile": profile_id,
        }
        normalized.append(normalized_term)
    return sorted(normalized, key=lambda item: (str(item["semantic_category"]), str(item["slug"])))


def _validate_semantic_categories(
    categories: Mapping[str, object], profiles: Mapping[str, Mapping[str, object]]
) -> None:
    """Validate category identity before projecting any runtime vocabulary.

    A category is a canonical namespace, not an arbitrary label for another
    predicate.  Keeping the key, predicate namespace, and predicate suffix in
    one identity prevents selectors and assertions from resolving against a
    different card field than the authored category claims.
    """

    if not categories:
        raise OntologyInfrastructureError("Vocabulary semantic_categories must not be empty")
    for category, raw_metadata in categories.items():
        if not isinstance(category, str):
            raise OntologyInfrastructureError("Vocabulary semantic category keys must be strings")
        _validate_canonical_name(category, "Semantic category key")
        if not isinstance(raw_metadata, Mapping):
            raise OntologyInfrastructureError(f"Semantic category {category!r} must be a mapping")
        metadata = cast(Mapping[str, object], raw_metadata)
        profile_id = _required_string(metadata, "ontoclean_profile")
        profile = profiles.get(profile_id)
        if profile is None:
            raise OntologyInfrastructureError(
                f"Semantic category {category!r} references unknown OntoClean profile {profile_id!r}"
            )
        predicates = metadata.get("allowed_predicates")
        if not isinstance(predicates, list) or not predicates:
            raise OntologyInfrastructureError(
                f"Semantic category {category!r} allowed_predicates must be a non-empty list"
            )
        seen: set[str] = set()
        namespaces: set[str] = set()
        for raw_predicate in predicates:
            if not isinstance(raw_predicate, str) or not raw_predicate.strip():
                raise OntologyInfrastructureError(
                    f"Semantic category {category!r} has an invalid allowed predicate {raw_predicate!r}"
                )
            if raw_predicate in seen:
                raise OntologyInfrastructureError(
                    f"Semantic category {category!r} has duplicate allowed predicate {raw_predicate!r}"
                )
            seen.add(raw_predicate)
            if raw_predicate.count(".") != 1:
                raise OntologyInfrastructureError(
                    f"Semantic category {category!r} has malformed predicate {raw_predicate!r}"
                )
            namespace, suffix = raw_predicate.split(".", maxsplit=1)
            if namespace not in _CANONICAL_PREDICATE_NAMESPACES or not _CANONICAL_NAME_PATTERN.fullmatch(suffix):
                raise OntologyInfrastructureError(
                    f"Semantic category {category!r} has non-canonical predicate {raw_predicate!r}"
                )
            if suffix != category:
                raise OntologyInfrastructureError(
                    f"Semantic category {category!r} does not match predicate suffix {suffix!r}"
                )
            namespaces.add(namespace)
        if len(namespaces) != 1:
            raise OntologyInfrastructureError(f"Semantic category {category!r} must declare homogeneous predicates")
        supplies_identity = profile.get("supplies_identity")
        has_identity_predicate = "knowledge.kind" in predicates
        if supplies_identity is not has_identity_predicate:
            raise OntologyInfrastructureError(
                f"Semantic category {category!r} OntoClean identity semantics disagree with its predicates"
            )


def _validate_canonical_name(value: str, owner: str) -> None:
    if not _CANONICAL_NAME_PATTERN.fullmatch(value):
        raise OntologyInfrastructureError(f"{owner} must be a canonical namespace/slug: {value!r}")


def _load_scheduling_policies(  # noqa: PLR0917
    ontology_root: Path,
    manifest: Mapping[str, object],
    schema_view: SchemaView,
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
    policies: dict[str, dict[str, object]] = {}
    for relative_path in _catalog_paths(ontology_root, manifest, "policies"):
        source = _load_yaml_mapping(_source_path(ontology_root, relative_path))
        _validate_linkml_instance(
            schema_view,
            "SchedulingPolicyCatalog",
            _linkml_catalog_instance("SchedulingPolicyCatalog", source),
        )
        raw_policies = _required_mapping(source, "scheduling_policies")
        for key, raw_policy in raw_policies.items():
            if not isinstance(key, str) or key.count(":") != 1:
                raise OntologyInfrastructureError(f"Policy key must be category:term in {relative_path}: {key!r}")
            raw_policy = raw_policy if isinstance(raw_policy, Mapping) else None
            if raw_policy is None:
                raise OntologyInfrastructureError(f"Policy {key!r} must be a mapping")
            namespace, term_key = key.split(":", maxsplit=1)
            term = _required_string(raw_policy, "term")
            if term != term_key:
                raise OntologyInfrastructureError(
                    f"Policy {key!r} term must match its canonical key component: {term!r}"
                )
            term_metadata = known_terms.get((namespace, term))
            if term_metadata is None:
                raise OntologyInfrastructureError(
                    f"Policy {key!r} references unknown canonical vocabulary term {namespace}:{term}"
                )
            if str(term_metadata["semantic_category"]) not in categories:
                raise OntologyInfrastructureError(f"Policy {key!r} must target a controlled semantic category")
            if key in policies:
                raise OntologyInfrastructureError(f"Duplicate canonical scheduling policy {key!r}")
            policies[key] = _normalize_scheduling_policy(
                key,
                cast(Mapping[str, object], raw_policy),
                _SchedulingPolicyContext(
                    term_metadata,
                    policy_runtime.near_values,
                    policy_runtime.score_levels,
                    policy_runtime.effect_match_dimensions,
                ),
            )
    # Assignment axes are the executable schedule surface.  Keep this
    # bidirectional: every accepted schedule term must have one policy, while
    # policy keys are already checked above against the canonical vocabulary.
    accepted_schedule_terms = {
        (str(term["semantic_category"]), str(term["slug"]))
        for term in terms
        if any(
            f"schedule.{axis}" in cast(list[object], term.get("allowed_predicates", []))
            for axis in policy_runtime.assignment_axes
        )
    }
    executable_policy_terms = {
        (namespace, policy_id.split(":", maxsplit=1)[1])
        for policy_id in policies
        if (namespace := policy_id.split(":", maxsplit=1)[0]) in policy_runtime.assignment_axes
    }
    missing = sorted(accepted_schedule_terms - executable_policy_terms)
    extra = sorted(executable_policy_terms - accepted_schedule_terms)
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append("missing policies for " + ", ".join(f"{category}:{slug}" for category, slug in missing))
        if extra:
            details.append(
                "policies for non-schedule terms " + ", ".join(f"{category}:{slug}" for category, slug in extra)
            )
        raise OntologyInfrastructureError("Scheduling policy coverage is not bidirectional: " + "; ".join(details))
    return dict(sorted(policies.items()))


def _normalize_scheduling_policy(
    key: str, raw: Mapping[str, object], context: _SchedulingPolicyContext
) -> dict[str, object]:
    allowed = {"term", "applies_when", "effects", "warning", "action"}
    extras = sorted(set(raw) - allowed)
    if extras:
        raise OntologyInfrastructureError(f"Policy {key!r} has unsupported fields: {', '.join(extras)}")
    effects = raw.get("effects")
    if not isinstance(effects, list):
        raise OntologyInfrastructureError(f"Policy {key!r} effects must be a list")
    warning = raw.get("warning")
    if not isinstance(warning, bool):
        raise OntologyInfrastructureError(f"Policy {key!r} warning must be boolean")
    normalized: dict[str, object] = {
        "term": _required_string(raw, "term"),
        "label": _required_string(context.term_metadata, "label"),
        "description": _required_string(context.term_metadata, "description"),
        "applies_when": _required_string(raw, "applies_when"),
        "effects": [
            _normalize_policy_effect(
                key,
                item,
                context.near_values,
                context.score_levels,
                context.effect_match_dimensions,
            )
            for item in cast(list[object], effects)
        ],
        "warning": warning,
    }
    if "action" in raw:
        normalized["action"] = _required_string(raw, "action")
    return normalized


def _normalize_policy_effect(
    key: str,
    raw: object,
    near_values: set[str],
    score_levels: set[str],
    effect_match_dimensions: Mapping[str, str],
) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        raise OntologyInfrastructureError(f"Policy {key!r} effect must be a mapping")
    effect = cast(Mapping[str, object], raw)
    extras = sorted(set(effect) - {"match", "level"})
    if extras:
        raise OntologyInfrastructureError(f"Policy {key!r} effect has unsupported fields: {', '.join(extras)}")
    match = effect.get("match")
    if not isinstance(match, Mapping) or not match or set(match) - set(effect_match_dimensions):
        raise OntologyInfrastructureError(f"Policy {key!r} effect match is invalid")
    normalized_match: dict[str, object] = {}
    for name, value in cast(Mapping[str, object], match).items():
        value_type = effect_match_dimensions.get(name)
        if value_type is None:
            raise OntologyInfrastructureError(f"Policy {key!r} effect match is invalid")
        normalized_match[name] = _normalize_policy_match_value(key, name, value, value_type, near_values)
    normalized: dict[str, object] = {"match": normalized_match}
    level = _normalize_policy_level(key, effect.get("level"), score_levels)
    if level is not None:
        normalized["level"] = level
    if len(normalized) == 1:
        raise OntologyInfrastructureError(f"Policy {key!r} effect must set level")
    return normalized


def _normalize_policy_match_value(
    policy_key: str, dimension_key: str, value: object, value_type: str, near_values: set[str]
) -> str | bool:
    handler = IMPLEMENTED_EFFECT_MATCH_VALUE_HANDLERS.get(value_type)
    if handler is None:
        raise OntologyInfrastructureError(
            f"Policy {policy_key!r} effect match dimension {dimension_key!r} has unsupported value type {value_type!r}"
        )
    if handler == "capability_values":
        if not isinstance(value, str) or value not in near_values:
            raise OntologyInfrastructureError(f"Policy {policy_key!r} has invalid {dimension_key} value {value!r}")
        return value
    if handler == "boolean":
        if not isinstance(value, bool):
            raise OntologyInfrastructureError(f"Policy {policy_key!r} {dimension_key} match must be boolean")
        return value
    raise OntologyInfrastructureError(
        f"Policy {policy_key!r} effect match dimension {dimension_key!r} has unsupported match handler {handler!r}"
    )


def _load_schedule_presentation(
    ontology_root: Path,
    manifest: Mapping[str, object],
    scheduling_policies: Mapping[str, object],
    categories: Mapping[str, object],
) -> dict[str, object]:
    configured: dict[str, object] | None = None
    for relative_path in _catalog_paths(ontology_root, manifest, "policies"):
        source = _load_yaml_mapping(_source_path(ontology_root, relative_path))
        raw_presentation = source.get("schedule_presentation")
        if raw_presentation is None:
            continue
        if configured is not None:
            raise OntologyInfrastructureError("schedule_presentation must be declared in exactly one policy catalog")
        if not isinstance(raw_presentation, dict):
            raise OntologyInfrastructureError("schedule_presentation must be a mapping")
        configured = _normalize_schedule_presentation(
            cast(Mapping[str, object], raw_presentation),
            scheduling_policies,
            categories,
        )
    if configured is None:
        raise OntologyInfrastructureError("policy catalog must declare schedule_presentation")
    return configured


def _normalize_schedule_presentation(
    raw: Mapping[str, object],
    scheduling_policies: Mapping[str, object],
    categories: Mapping[str, object],
) -> dict[str, object]:
    if set(raw) != {"concern_annotations", "review_tags", "active_fact_index", "zero_effect"}:
        raise OntologyInfrastructureError("schedule_presentation has unsupported fields")
    concern_annotations = _required_mapping(raw, "concern_annotations")
    review_tags = _required_mapping(raw, "review_tags")
    active_fact_index = _required_mapping(raw, "active_fact_index")
    zero_effect = _required_mapping(raw, "zero_effect")
    if set(concern_annotations) != {"include_kinds", "labels"}:
        raise OntologyInfrastructureError("schedule_presentation.concern_annotations has unsupported fields")
    if set(review_tags) != {"include_namespaces", "exclude_policy_ids"}:
        raise OntologyInfrastructureError("schedule_presentation.review_tags has unsupported fields")
    if set(active_fact_index) != {"include_namespaces", "labels"}:
        raise OntologyInfrastructureError("schedule_presentation.active_fact_index has unsupported fields")
    if set(zero_effect) != {"condition", "template"}:
        raise OntologyInfrastructureError("schedule_presentation.zero_effect has unsupported fields")
    condition = _required_string(zero_effect, "condition")
    if condition != "no_nonzero_effects":
        raise OntologyInfrastructureError("schedule_presentation.zero_effect.condition must be 'no_nonzero_effects'")
    template = _required_string(zero_effect, "template")
    include_namespaces = _required_unique_string_list(review_tags, "include_namespaces")
    exclude_policy_ids = _required_unique_string_list(review_tags, "exclude_policy_ids")
    fact_index_namespaces = _required_unique_string_list(active_fact_index, "include_namespaces")
    concern_kinds = _required_unique_string_list(concern_annotations, "include_kinds")
    policy_ids = set(scheduling_policies)
    policy_namespaces = {item.split(":", maxsplit=1)[0] for item in policy_ids if ":" in item}
    knowledge_namespaces = _knowledge_namespaces(categories)
    concern_labels = _presentation_labels(concern_annotations, "labels", set(concern_kinds), "concern kind")
    fact_labels = _presentation_labels(
        active_fact_index,
        "labels",
        set(fact_index_namespaces),
        "active fact namespace",
    )
    if set(include_namespaces) - policy_namespaces:
        raise OntologyInfrastructureError("schedule_presentation.review_tags includes unknown namespace")
    if set(fact_index_namespaces) - knowledge_namespaces:
        raise OntologyInfrastructureError("schedule_presentation.active_fact_index includes unknown namespace")
    if set(exclude_policy_ids) - policy_ids:
        raise OntologyInfrastructureError("schedule_presentation.review_tags excludes unknown policy")
    return {
        "concern_annotations": {"include_kinds": concern_kinds, "labels": concern_labels},
        "review_tags": {"include_namespaces": include_namespaces, "exclude_policy_ids": exclude_policy_ids},
        "active_fact_index": {"include_namespaces": fact_index_namespaces, "labels": fact_labels},
        "zero_effect": {"condition": condition, "template": template},
    }


def _presentation_labels(
    parent: Mapping[str, object],
    field: str,
    expected_keys: set[str],
    label_kind: str,
) -> list[dict[str, str]]:
    """Decode an authored presentation label catalog without deriving text from IDs."""
    raw_labels = parent.get(field)
    if not isinstance(raw_labels, list):
        raise OntologyInfrastructureError(f"schedule_presentation {label_kind} labels must be a list")
    labels: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_labels):
        if not isinstance(raw, Mapping):
            raise OntologyInfrastructureError(f"schedule_presentation {label_kind} label {index} must be a mapping")
        row = cast(Mapping[str, object], raw)
        if set(row) != {"key", "label"}:
            raise OntologyInfrastructureError(
                f"schedule_presentation {label_kind} label {index} has unsupported fields"
            )
        key = _required_string(row, "key")
        label = _required_string(row, "label")
        if key in seen:
            raise OntologyInfrastructureError(f"duplicate schedule_presentation {label_kind} label {key!r}")
        seen.add(key)
        labels.append({"key": key, "label": label})
    if seen != expected_keys:
        missing = sorted(expected_keys - seen)
        extra = sorted(seen - expected_keys)
        details = []
        if missing:
            details.append("missing " + ", ".join(repr(item) for item in missing))
        if extra:
            details.append("unknown " + ", ".join(repr(item) for item in extra))
        raise OntologyInfrastructureError(
            f"schedule_presentation {label_kind} labels are incomplete ({'; '.join(details)})"
        )
    return labels


def _knowledge_namespaces(categories: Mapping[str, object]) -> set[str]:
    return {
        namespace
        for namespace, raw in categories.items()
        if isinstance(namespace, str)
        and isinstance(raw, Mapping)
        and isinstance(raw.get("allowed_predicates"), list)
        and f"knowledge.{namespace}" in cast(list[object], raw["allowed_predicates"])
    }


def _load_scheduling_constraints(
    ontology_root: Path,
    manifest: Mapping[str, object],
    schema_view: SchemaView,
    terms: Sequence[Mapping[str, object]],
    policy_runtime: _PolicyRuntime,
) -> dict[str, dict[str, object]]:
    known_terms = {(str(term["semantic_category"]), str(term["slug"])) for term in terms}
    result: dict[str, dict[str, object]] = {}
    for relative_path in _catalog_paths(ontology_root, manifest, "constraints"):
        source = _load_yaml_mapping(_source_path(ontology_root, relative_path))
        _validate_linkml_instance(schema_view, "SchedulingConstraintCatalog", source)
        raw = _required_mapping(source, "scheduling_constraints")
        for identifier, value in raw.items():
            if not isinstance(identifier, str) or identifier in result or not isinstance(value, Mapping):
                raise OntologyInfrastructureError(f"Scheduling constraint {identifier!r} is malformed or duplicated")
            row = cast(Mapping[str, object], value)
            allowed = {
                "operation",
                "source_selector",
                "target_selector",
                "rationale",
                "action",
                "blocks_slots",
                "scores_advisory",
                "score_delta",
            }
            if set(row) - allowed:
                raise OntologyInfrastructureError(f"Scheduling constraint {identifier!r} has unsupported fields")
            operation = _required_string(row, "operation")
            if operation not in policy_runtime.constraints.execution_policies:
                raise OntologyInfrastructureError(f"Scheduling constraint {identifier!r} references unknown operation")
            normalized: dict[str, object] = {
                "operation": operation,
                "source_selector": _normalize_constraint_selector(identifier, row.get("source_selector"), known_terms),
                "target_selector": _normalize_constraint_selector(identifier, row.get("target_selector"), known_terms),
                "rationale": _required_string(row, "rationale"),
                "action": _required_string(row, "action"),
            }
            for field in ("blocks_slots", "scores_advisory"):
                if field in row and not isinstance(row[field], bool):
                    raise OntologyInfrastructureError(f"Scheduling constraint {identifier!r} {field} must be boolean")
                if field in row:
                    normalized[field] = row[field]
            if "score_delta" in row:
                if isinstance(row["score_delta"], bool) or not isinstance(row["score_delta"], int):
                    raise OntologyInfrastructureError(
                        f"Scheduling constraint {identifier!r} score_delta must be integer"
                    )
                normalized["score_delta"] = row["score_delta"]
            result[identifier] = normalized
    return dict(sorted(result.items()))


def _normalize_constraint_selector(
    constraint_id: str, raw: object, known_terms: set[tuple[str, str]]
) -> dict[str, object]:
    return _normalize_relation_selector(
        owner_kind="Scheduling constraint",
        owner_id=constraint_id,
        raw=raw,
        known_terms=known_terms,
        allow_entity_name=False,
    )


def _normalize_relation_selector(
    *,
    owner_kind: str,
    owner_id: str,
    raw: object,
    known_terms: set[tuple[str, str]],
    allow_entity_name: bool,
) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        raise OntologyInfrastructureError(f"{owner_kind} {owner_id!r} selector must be a mapping")
    selector = cast(Mapping[str, object], raw)
    entity = selector.get("entity")
    if isinstance(entity, Mapping) and set(selector) == {"entity"}:
        entity_map = cast(Mapping[str, object], entity)
        if set(entity_map) not in ({"entity_id"}, {"name"}):
            raise OntologyInfrastructureError(f"{owner_kind} {owner_id!r} entity selector is invalid")
        field = next(iter(entity_map))
        if field == "name" and not allow_entity_name:
            raise OntologyInfrastructureError(f"{owner_kind} {owner_id!r} entity selector requires stable entity_id")
        return {"entity": {field: _required_string(entity_map, field)}}
    if set(selector) == {"category", "term"}:
        category = _required_string(selector, "category")
        term = _required_string(selector, "term")
        if (category, term) not in known_terms:
            raise OntologyInfrastructureError(f"{owner_kind} {owner_id!r} has unknown selector")
        return {"category": category, "term": term}
    raise OntologyInfrastructureError(f"{owner_kind} {owner_id!r} selector is invalid")


def _load_ontology_assertions(  # noqa: PLR0917
    ontology_root: Path,
    manifest: Mapping[str, object],
    terms: Sequence[Mapping[str, object]],
    schema_view: SchemaView,
    selector_kinds: set[str],
    relation_types: Mapping[str, Mapping[str, object]],
    substance_registry: Mapping[str, str],
) -> dict[str, dict[str, object]]:
    known_terms = {(str(term["semantic_category"]), str(term["slug"])) for term in terms}
    names_to_ids: dict[str, list[str]] = {}
    for substance_id, name in substance_registry.items():
        names_to_ids.setdefault(name, []).append(substance_id)
    for ids in names_to_ids.values():
        ids.sort()
    result: dict[str, dict[str, object]] = {}
    seen_directionless: dict[tuple[str, frozenset[str]], str] = {}
    for relative_path in _catalog_paths(ontology_root, manifest, "assertions"):
        source = _load_yaml_mapping(_source_path(ontology_root, relative_path))
        _validate_linkml_instance(
            schema_view,
            "RelationAssertionCatalog",
            _linkml_catalog_instance("RelationAssertionCatalog", source),
        )
        raw = source.get("relations")
        if not isinstance(raw, list):
            raise OntologyInfrastructureError(f"Assertion source {relative_path} must contain relations")
        for item in cast(list[object], raw):
            if not isinstance(item, Mapping):
                raise OntologyInfrastructureError("Assertion record must be a mapping")
            row = cast(Mapping[str, object], item)
            identifier = _required_string(row, "id")
            if identifier in result:
                raise OntologyInfrastructureError(f"Duplicate canonical ontology assertion id: {identifier}")
            allowed = {
                "id",
                "relation_type",
                "reason",
                "action",
                "severity",
                "source_selector",
                "target_selector",
                "assertion_kind",
                "semantic_family",
            }
            if set(row) - allowed:
                raise OntologyInfrastructureError(f"Ontology assertion {identifier!r} has unsupported fields")
            normalized: dict[str, object] = {
                "id": identifier,
                "relation_type": _required_string(row, "relation_type"),
                "assertion_kind": _required_string(row, "assertion_kind"),
                "semantic_family": _required_string(row, "semantic_family"),
                "source_selector": _normalize_assertion_selector(
                    identifier, row.get("source_selector"), known_terms, substance_registry, names_to_ids
                ),
                "target_selector": _normalize_assertion_selector(
                    identifier, row.get("target_selector"), known_terms, substance_registry, names_to_ids
                ),
                "reason": _required_string(row, "reason"),
            }
            relation_type = cast(str, normalized["relation_type"])
            relation_contract = relation_types.get(relation_type)
            if relation_contract is None:
                raise OntologyInfrastructureError(
                    f"Ontology assertion {identifier!r} references unknown relation type {relation_type!r}"
                )
            _validate_relation_assertion_selector_forms(
                identifier,
                relation_contract,
                cast(Mapping[str, object], normalized["source_selector"]),
                cast(Mapping[str, object], normalized["target_selector"]),
            )
            if not cast(bool, relation_contract["directional"]):
                source_key = _normalized_relation_selector_key(
                    cast(Mapping[str, object], normalized["source_selector"]), substance_registry, names_to_ids
                )
                target_key = _normalized_relation_selector_key(
                    cast(Mapping[str, object], normalized["target_selector"]), substance_registry, names_to_ids
                )
                directionless_key = (relation_type, frozenset((source_key, target_key)))
                previous = seen_directionless.get(directionless_key)
                if previous is not None:
                    raise OntologyInfrastructureError(
                        f"Ontology assertion {identifier!r} uses direction for non-directional relation type "
                        f"{relation_type!r}; endpoints duplicate {previous!r}"
                    )
                seen_directionless[directionless_key] = identifier
            for field in ("action", "severity"):
                if field in row:
                    normalized[field] = _required_string(row, field)
            result[identifier] = normalized
    return dict(sorted(result.items()))


def _normalize_assertion_selector(
    assertion_id: str,
    raw: object,
    known_terms: set[tuple[str, str]],
    substance_registry: Mapping[str, str],
    names_to_ids: Mapping[str, Sequence[str]],
) -> dict[str, object]:
    selector = _normalize_relation_selector(
        owner_kind="Ontology assertion",
        owner_id=assertion_id,
        raw=raw,
        known_terms=known_terms,
        allow_entity_name=True,
    )
    entity = selector.get("entity")
    if not isinstance(entity, Mapping):
        return selector
    entity_map = cast(Mapping[str, object], entity)
    if "entity_id" in entity_map:
        entity_id = _required_string(entity_map, "entity_id")
        if entity_id not in substance_registry:
            raise OntologyInfrastructureError(
                f"Ontology assertion {assertion_id!r} references unknown substance entity_id {entity_id!r}"
            )
        return {"entity": {"entity_id": entity_id}}
    name = _required_string(entity_map, "name")
    ids = names_to_ids.get(name)
    if not ids:
        raise OntologyInfrastructureError(
            f"Ontology assertion {assertion_id!r} references unknown substance name {name!r}"
        )
    # Names are authored family selectors, even when the current registry has
    # only one matching form.  Freezing a unique name to today's ID would make
    # a later same-name form invisible until the ontology assertion is edited.
    return {"entity": {"name": name}}


def _validate_relation_assertion_selector_forms(
    assertion_id: str,
    relation_type: Mapping[str, object],
    source_selector: Mapping[str, object],
    target_selector: Mapping[str, object],
) -> None:
    for side, selector in (("source", source_selector), ("target", target_selector)):
        forms = relation_type.get(f"{side}_selector_forms")
        if not isinstance(forms, list):
            raise OntologyInfrastructureError(
                f"Relation type {relation_type.get('id')!r} has malformed {side}_selector_forms"
            )
        actual = "entity" if "entity" in selector else "term"
        if actual not in forms:
            raise OntologyInfrastructureError(
                f"Ontology assertion {assertion_id!r} uses {actual} {side} selector, "
                f"but relation type {relation_type.get('id')!r} allows {', '.join(cast(str, form) for form in forms)}"
            )


def _normalized_relation_selector_key(
    selector: Mapping[str, object],
    substance_registry: Mapping[str, str],
    names_to_ids: Mapping[str, Sequence[str]],
) -> str:
    entity = selector.get("entity")
    if isinstance(entity, Mapping):
        if "entity_id" in entity:
            entity_id = _required_string(entity, "entity_id")
            if entity_id not in substance_registry:
                raise OntologyInfrastructureError(f"Unknown substance entity_id {entity_id!r}")
            return f"entity:{entity_id}"
        name = _required_string(entity, "name")
        ids = names_to_ids.get(name)
        if not ids:
            raise OntologyInfrastructureError(f"Unknown substance name {name!r}")
        return f"entity:{','.join(ids)}"
    return f"term:{selector.get('category')}:{selector.get('term')}"


def _load_substance_identity_registry(ontology_root: Path) -> dict[str, str]:
    """Load the complete authored substance identity registry for compilation."""
    directory = ontology_root.parent / "data" / "substances"
    if not directory.is_dir():
        return {}
    registry: dict[str, str] = {}
    for path in sorted(directory.glob("*.yaml")):
        record = _load_yaml_mapping(path)
        substance_id = _required_string(record, "id")
        name = _required_string(record, "name")
        previous = registry.get(substance_id)
        if previous is not None:
            raise OntologyInfrastructureError(f"Duplicate authored substance entity_id {substance_id!r}")
        registry[substance_id] = name
    return registry


def _normalize_policy_level(key: str, level: object, score_levels: set[str]) -> str | None:
    if level is None:
        return None
    if level not in score_levels:
        raise OntologyInfrastructureError(f"Policy {key!r} has invalid score level {level!r}")
    return cast(str, level)


def _read_custom_shapes(
    ontology_root: Path,
    manifest: Mapping[str, object],
    base_iri: str,
    categories: Mapping[str, object],
) -> str:
    files = _catalog_paths(ontology_root, manifest, "custom_shapes")
    contents: list[str] = []
    for relative_path in files:
        path = _source_path(ontology_root, relative_path)
        source = path.read_text(encoding="utf-8")
        if base_iri not in source:
            raise OntologyInfrastructureError(f"Custom SHACL source has no canonical ss base IRI: {path}")
        contents.append(source.rstrip())
    contents.append(_semantic_category_shape(base_iri, categories))
    return "\n\n".join(contents) + "\n"


def _semantic_category_shape(base_iri: str, categories: Mapping[str, object]) -> str:
    """Generate category/profile registry constraints from authored vocabulary."""
    values = " ".join(_ttl_literal(category) for category in sorted(categories))
    return "\n".join((
        f"<{base_iri}KnowledgeAssertionCategoryShape>",
        "  a sh:NodeShape ;",
        f"  sh:targetClass <{base_iri}KnowledgeAssertion> ;",
        "  sh:property [",
        f"    sh:path <{base_iri}knowledge_category> ;",
        f"    sh:in ( {values} )",
        "  ] .",
        "",
        f"<{base_iri}semantic_category_registry>",
        "  a sh:NodeShape ;",
        '  sh:name "semantic_category_registry" ;',
        f"  sh:targetClass <{base_iri}SemanticCategory> ;",
        "  sh:property [",
        f"    sh:path <{base_iri}id> ; sh:datatype <http://www.w3.org/2001/XMLSchema#string> ;",
        "    sh:minCount 1 ; sh:maxCount 1",
        "  ] ;",
        "  sh:property [",
        f"    sh:path <{base_iri}allowed_predicates> ; sh:datatype <http://www.w3.org/2001/XMLSchema#string> ;",
        "    sh:minCount 1",
        "  ] ;",
        "  sh:property [",
        f"    sh:path <{base_iri}ontoclean_profile> ;",
        "    sh:nodeKind <http://www.w3.org/ns/shacl#IRI> ;",
        f"    sh:class <{base_iri}OntoCleanProfile> ;",
        "    sh:minCount 1 ; sh:maxCount 1",
        "  ] ;",
        "  sh:sparql [",
        '    sh:message "[semantic_category_registry] category identity and allowed predicate must use the canonical namespace and suffix" ;',
        '    sh:select """',
        f"      PREFIX ss: <{base_iri}>",
        "      SELECT $this WHERE {",
        "        $this ss:id ?id ; ss:allowed_predicates ?allowed .",
        "        FILTER (",
        f'          STR($this) != CONCAT("{base_iri}", STR(?id)) ||',
        '          !(STR(?allowed) = CONCAT("knowledge.", STR(?id)) || STR(?allowed) = CONCAT("schedule.", STR(?id)))',
        "        )",
        "      }",
        '    """',
        "  ] .",
        "",
        f"<{base_iri}ontoclean_profile_registry>",
        "  a sh:NodeShape ;",
        '  sh:name "ontoclean_profile_registry" ;',
        f"  sh:targetClass <{base_iri}OntoCleanProfile> ;",
        "  sh:property [",
        f"    sh:path <{base_iri}id> ; sh:datatype <http://www.w3.org/2001/XMLSchema#string> ;",
        "    sh:minCount 1 ; sh:maxCount 1",
        "  ] ;",
        "  sh:property [",
        f'    sh:path <{base_iri}rigidity> ; sh:in ( "rigid" "anti_rigid" ) ;',
        "    sh:minCount 1 ; sh:maxCount 1",
        "  ] ;",
        "  sh:property [",
        f'    sh:path <{base_iri}dependence> ; sh:in ( "independent" "dependent" ) ;',
        "    sh:minCount 1 ; sh:maxCount 1",
        "  ] ;",
        "  sh:property [",
        f"    sh:path <{base_iri}supplies_identity> ; sh:datatype <http://www.w3.org/2001/XMLSchema#boolean> ;",
        "    sh:minCount 1 ; sh:maxCount 1",
        "  ] ;",
        "  sh:sparql [",
        '    sh:message "[ontoclean_profile_registry] OntoClean interlocks must be internally consistent" ;',
        '    sh:select """',
        f"      PREFIX ss: <{base_iri}>",
        "      SELECT $this WHERE {",
        "        $this ss:rigidity ?rigidity ; ss:dependence ?dependence ; ss:supplies_identity ?supplies .",
        "        FILTER (",
        '          (?rigidity = "anti_rigid" && ?supplies = true) ||',
        '          (?dependence = "independent" && ?supplies = false) ||',
        '          (?supplies = true && (?rigidity != "rigid" || ?dependence != "independent")) ||',
        '          (?rigidity = "anti_rigid" && ?dependence != "dependent")',
        "        )",
        "      }",
        '    """',
        "  ] .",
        "",
        f"<{base_iri}ontology_term_required_fields>",
        "  a sh:NodeShape ;",
        '  sh:name "ontology_term_required_fields" ;',
        f"  sh:targetClass <{base_iri}OntologyTerm> ;",
        "  sh:property [",
        f"    sh:path <{base_iri}id> ; sh:datatype <http://www.w3.org/2001/XMLSchema#string> ;",
        "    sh:minCount 1 ; sh:maxCount 1 ; sh:minLength 1",
        "  ] ;",
        "  sh:property [",
        f"    sh:path <{base_iri}slug> ; sh:datatype <http://www.w3.org/2001/XMLSchema#string> ;",
        "    sh:minCount 1 ; sh:maxCount 1 ; sh:minLength 1",
        "  ] ;",
        "  sh:property [",
        f"    sh:path <{base_iri}label> ; sh:datatype <http://www.w3.org/2001/XMLSchema#string> ;",
        "    sh:minCount 1 ; sh:maxCount 1 ; sh:minLength 1",
        "  ] ;",
        "  sh:property [",
        f"    sh:path <{base_iri}description> ; sh:datatype <http://www.w3.org/2001/XMLSchema#string> ;",
        "    sh:minCount 1 ; sh:maxCount 1 ; sh:minLength 1",
        "  ] ;",
        "  sh:property [",
        f"    sh:path <{base_iri}semantic_category> ; sh:nodeKind <http://www.w3.org/ns/shacl#IRI> ;",
        f"    sh:class <{base_iri}SemanticCategory> ; sh:minCount 1 ; sh:maxCount 1",
        "  ] ;",
        "  sh:property [",
        f"    sh:path <{base_iri}ontoclean_profile> ; sh:nodeKind <http://www.w3.org/ns/shacl#IRI> ;",
        f"    sh:class <{base_iri}OntoCleanProfile> ; sh:minCount 1 ; sh:maxCount 1",
        "  ] .",
        "",
        f"<{base_iri}term_registered_category_profile>",
        "  a sh:NodeShape ;",
        '  sh:name "term_registered_category_profile" ;',
        f"  sh:targetClass <{base_iri}OntologyTerm> ;",
        "  sh:sparql [",
        '    sh:message "[term_registered_category_profile] term profile and canonical id must match the semantic category" ;',
        '    sh:select """',
        f"      PREFIX ss: <{base_iri}>",
        "      SELECT $this WHERE {",
        "        {",
        "          $this ss:semantic_category ?category ; ss:ontoclean_profile ?profile .",
        "          FILTER NOT EXISTS { ?category ss:ontoclean_profile ?profile }",
        "        } UNION {",
        "          $this ss:id ?id ; ss:slug ?slug ; ss:semantic_category ?category .",
        "          ?category ss:id ?category_id .",
        '          FILTER (STR(?id) != CONCAT(STR(?category_id), ":", STR(?slug)))',
        "        }",
        "      }",
        '    """',
        "  ] .",
    ))


def _ttl_bytes(  # noqa: PLR0917
    header: str,
    base_iri: str,
    categories: Mapping[str, object],
    terms: Sequence[Mapping[str, object]],
    relation_types: Mapping[str, Mapping[str, object]],
    scheduling_policies: Mapping[str, Mapping[str, object]],
    scheduling_constraints: Mapping[str, Mapping[str, object]],
    runtime_policy: Mapping[str, object],
    ontoclean_profiles: Mapping[str, Mapping[str, object]],
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
        f"  ss:schema_version {_ttl_literal(str(manifest['schema_version']))} .",
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
            f"  ss:catalog_role {_ttl_literal(str(catalog['role']))} ;",
            f"  ss:catalog_path {_ttl_literal(str(catalog['path']))} ;",
            f"  ss:catalog_root_class {_ttl_literal(str(catalog['root_class']))} .",
            "",
        ])
    for profile_id, profile in sorted(ontoclean_profiles.items()):
        profile_uri = f"{base_iri}ontoclean-profile/{_ttl_iri_path(profile_id)}"
        lines.extend([
            f"<{profile_uri}> a ss:OntoCleanProfile ;",
            f"  ss:id {_ttl_literal(profile_id)} ;",
            f"  ss:rigidity {_ttl_literal(str(profile['rigidity']))} ;",
            f"  ss:supplies_identity {_ttl_bool(cast(bool, profile['supplies_identity']))} ;",
            f"  ss:dependence {_ttl_literal(str(profile['dependence']))} .",
            "",
        ])
    for category in sorted(categories):
        metadata = categories[category]
        if not isinstance(metadata, Mapping):
            raise OntologyInfrastructureError(f"Semantic category {category!r} metadata is malformed")
        profile_id = _required_string(cast(Mapping[str, object], metadata), "ontoclean_profile")
        predicates = metadata.get("allowed_predicates")
        if not isinstance(predicates, list) or not predicates or not all(isinstance(item, str) for item in predicates):
            raise OntologyInfrastructureError(f"Semantic category {category!r} requires allowed_predicates")
        category_uri = f"{base_iri}{_ttl_iri_path(category)}"
        profile_uri = f"{base_iri}ontoclean-profile/{_ttl_iri_path(profile_id)}"
        lines.extend([
            f"<{category_uri}> a ss:SemanticCategory ;",
            f"  ss:id {_ttl_literal(category)} ;",
            f"  ss:ontoclean_profile <{profile_uri}> ;",
            "  ss:allowed_predicates",
        ])
        for index, predicate in enumerate(cast(list[str], predicates)):
            suffix = "," if index < len(predicates) - 1 else " ."
            lines.append(f"  {_ttl_literal(predicate)}{suffix}")
        lines.append("")

    for relation_id, relation in sorted(relation_types.items()):
        relation_uri = f"{base_iri}relation-type/{_ttl_iri_path(relation_id)}"
        order = relation.get("order")
        if isinstance(order, bool) or not isinstance(order, int):
            raise OntologyInfrastructureError(f"Relation type {relation_id!r} has malformed order")
        lines.extend([
            f"<{relation_uri}> a ss:OperationalRelationType ;",
            f"  ss:id {_ttl_literal(relation_id)} ;",
            f"  ss:label {_ttl_literal(str(relation['label']))} ;",
            f"  ss:order {order} ;",
            f"  ss:directional {_ttl_bool(cast(bool, relation['directional']))} .",
        ])
        for field in ("source_selector_forms", "target_selector_forms"):
            forms = relation.get(field)
            if not isinstance(forms, list):
                raise OntologyInfrastructureError(f"Relation type {relation_id!r} has malformed {field}")
            lines.extend(f"<{relation_uri}> ss:{field} {_ttl_literal(str(form))} ." for form in forms)
        lines.append("")

    axes = runtime_policy.get("assignment_axes")
    if not isinstance(axes, list):
        raise OntologyInfrastructureError("Runtime policy assignment_axes must be a list")
    for raw_axis in axes:
        if not isinstance(raw_axis, Mapping):
            raise OntologyInfrastructureError("Runtime assignment axis metadata is malformed")
        axis = cast(Mapping[str, object], raw_axis)
        axis_name = _required_string(axis, "axis")
        axis_id = _required_string(axis, "id")
        assignment_source = _required_string(axis, "assignment_source")
        assignment_field = _required_string(axis, "assignment_field")
        axis_uri = f"{base_iri}assignment-axis/{_ttl_iri_path(axis_id)}"
        lines.extend([
            f"<{axis_uri}> ss:id {_ttl_literal(axis_id)} ;",
            f"  ss:axis {_ttl_literal(axis_name)} ;",
            f"  ss:assignment_source {_ttl_literal(assignment_source)} ;",
            f"  ss:assignment_field {_ttl_literal(assignment_field)} .",
            "",
        ])
    lines.append("")
    for term in terms:
        category = str(term["semantic_category"])
        slug = str(term["slug"])
        label = _ttl_literal(str(term["label"]))
        profile = str(term["ontoclean_profile"])
        lines.extend([
            f"<{base_iri}term/{category}/{slug}> a ss:OntologyTerm ;",
            f"  ss:id {_ttl_literal(f'{category}:{slug}')} ;",
            f"  ss:slug {_ttl_literal(slug)} ;",
            f"  ss:semantic_category ss:{category} ;",
            f"  ss:ontoclean_profile <{base_iri}ontoclean-profile/{_ttl_iri_path(profile)}> ;",
            f"  ss:label {label} ;",
            f"  ss:description {_ttl_literal(str(term['description']))} .",
            "",
        ])
    for policy_id, policy in sorted(scheduling_policies.items()):
        policy_uri = f"{base_iri}policy/{_ttl_iri_path(policy_id)}"
        category, slug = policy_id.split(":", maxsplit=1)
        lines.extend([
            f"<{policy_uri}> a ss:SchedulingPolicyRecord ;",
            f"  ss:id {_ttl_literal(policy_id)} ;",
            f"  ss:term <{base_iri}term/{category}/{slug}> ;",
            f"  ss:applies_when {_ttl_literal(str(policy['applies_when']))} ;",
            f"  ss:warning {_ttl_bool(cast(bool, policy['warning']))} .",
            "",
        ])
        action = policy.get("action")
        if isinstance(action, str) and action:
            lines.extend([
                f"<{policy_uri}> ss:action {_ttl_literal(action)} .",
                "",
            ])
        for index, effect in enumerate(cast(list[object], policy["effects"])):
            if not isinstance(effect, Mapping):
                continue
            effect_uri = f"{policy_uri}/effect/{index}"
            effect_mapping = cast(Mapping[str, object], effect)
            lines.extend([
                f"<{effect_uri}> a ss:SchedulingPolicyEffectRecord .",
                f"<{policy_uri}> ss:effects <{effect_uri}> .",
            ])
            level = effect_mapping.get("level")
            if isinstance(level, str):
                lines.extend([
                    f"<{effect_uri}> ss:level {_ttl_literal(level)} .",
                ])
            match = effect_mapping.get("match")
            if isinstance(match, Mapping):
                match_uri = f"{effect_uri}/match"
                lines.extend([
                    f"<{match_uri}> a ss:SchedulingPolicyEffectMatch .",
                    f"<{effect_uri}> ss:match <{match_uri}> .",
                ])
                for key, value in sorted(cast(Mapping[str, object], match).items()):
                    lines.extend([
                        f"<{match_uri}> ss:{_ttl_local_name(str(key))} {_ttl_value(value)} .",
                    ])
            lines.append("")
    for constraint_id, constraint in sorted(scheduling_constraints.items()):
        constraint_uri = f"{base_iri}constraint/{_ttl_iri_path(constraint_id)}"
        lines.extend([
            f"<{constraint_uri}> a ss:SchedulingConstraintRecord ;",
            f"  ss:id {_ttl_literal(constraint_id)} ;",
            f"  ss:operation {_ttl_literal(str(constraint['operation']))} ;",
            f"  ss:rationale {_ttl_literal(str(constraint['rationale']))} ;",
            f"  ss:action {_ttl_literal(str(constraint['action']))} .",
            "",
        ])
        for field in ("blocks_slots", "scores_advisory", "score_delta"):
            value = constraint.get(field)
            if isinstance(value, bool):
                lines.extend([f"<{constraint_uri}> ss:{field} {_ttl_bool(value)} .", ""])
            elif isinstance(value, int) and not isinstance(value, bool):
                lines.extend([f"<{constraint_uri}> ss:{field} {value} .", ""])
        for side in ("source_selector", "target_selector"):
            selector = constraint.get(side)
            if isinstance(selector, Mapping):
                lines.extend(
                    _ttl_selector_node_lines(
                        base_iri,
                        constraint_uri,
                        side,
                        cast(Mapping[str, object], selector),
                        selector_class="SchedulingConstraintSelector",
                        entity_selector_class="SchedulingConstraintEntitySelector",
                    )
                )
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
        loaded = _safe_yaml_load(path.read_text(encoding="utf-8"), path=path)
    except (OSError, yaml.YAMLError) as error:
        raise OntologyInfrastructureError(f"Cannot load ontology source {path}: {error}") from error
    if not isinstance(loaded, dict):
        raise OntologyInfrastructureError(f"Ontology source must be a mapping: {path}")
    return cast(dict[str, object], loaded)


def _required_string(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OntologyInfrastructureError(f"Expected non-empty string {key!r} in ontology source")
    return value


def _required_string_list(mapping: Mapping[str, object], key: str) -> list[str]:
    value = mapping.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise OntologyInfrastructureError(f"Expected non-empty string list {key!r} in ontology source")
    return cast(list[str], value)


def _required_unique_string_list(mapping: Mapping[str, object], key: str) -> list[str]:
    value = _required_string_list(mapping, key)
    if len(value) != len(set(value)):
        raise OntologyInfrastructureError(f"Expected unique string list {key!r} in ontology source")
    return value


def _required_mapping(mapping: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise OntologyInfrastructureError(f"Expected mapping {key!r} in ontology source")
    return cast(Mapping[str, object], value)


def _ttl_literal(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _ttl_bool(value: bool) -> str:
    return "true" if value else "false"


def _ttl_value(value: object) -> str:
    if isinstance(value, bool):
        return _ttl_bool(value)
    return _ttl_literal(str(value))


def _ttl_selector_facts(selector: Mapping[str, object]) -> list[tuple[str, object]]:
    entity = selector.get("entity")
    if isinstance(entity, Mapping):
        entity_map = cast(Mapping[str, object], entity)
        if "entity_id" in entity_map:
            return [("entity_id", entity_map["entity_id"])]
        if "name" in entity_map:
            return [("name", entity_map["name"])]
    if "category" in selector and "term" in selector:
        return [("category", selector["category"]), ("term", selector["term"])]
    return []


def _ttl_selector_node_lines(
    base_iri: str,
    owner_uri: str,
    side: str,
    selector: Mapping[str, object],
    *,
    selector_class: str,
    entity_selector_class: str,
) -> list[str]:
    selector_uri = f"{owner_uri}/{side}"
    lines = [
        f"<{selector_uri}> a ss:{selector_class} .",
        f"<{owner_uri}> ss:{side} <{selector_uri}> .",
    ]
    entity = selector.get("entity")
    if isinstance(entity, Mapping):
        entity_uri = f"{selector_uri}/entity"
        entity_map = cast(Mapping[str, object], entity)
        lines.extend([
            f"<{entity_uri}> a ss:{entity_selector_class} .",
            f"<{selector_uri}> ss:entity <{entity_uri}> .",
        ])
        for predicate, value in _ttl_selector_facts({"entity": entity_map}):
            if predicate == "entity_id":
                lines.append(f"<{entity_uri}> ss:entity_id <{base_iri}substance/{_ttl_iri_path(str(value))}> .")
            else:
                lines.append(f"<{entity_uri}> ss:{predicate} {_ttl_value(value)} .")
        lines.append("")
        return lines
    for predicate, value in _ttl_selector_facts(selector):
        lines.append(f"<{selector_uri}> ss:{predicate} {_ttl_value(value)} .")
    lines.append("")
    return lines


def _ttl_iri_path(value: str) -> str:
    return quote(value, safe="-._~")


def _ttl_local_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")


def _safe_yaml_load(text: str, *, path: Path) -> object:
    return cast(object, safe_load_yaml(text, path=path))
