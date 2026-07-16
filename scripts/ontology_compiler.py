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
from pathlib import Path
from typing import Protocol, cast, runtime_checkable
from urllib.parse import urlparse

import yaml
from linkml.generators.jsonschemagen import JsonSchemaGenerator
from linkml.generators.shaclgen import ShaclGenerator
from linkml_runtime.linkml_model.meta import Prefix, SchemaDefinition
from linkml_runtime.utils.schemaview import SchemaView
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_contract import runtime_assertions
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
_ALLOWED_SCOPE_KEYS = {"planner", "food_model", "slot_model", "intended_use", "substrate", "product", "formulation"}
_REPOSITORY_LOCATOR_KINDS = {"flat_root", "explicit_path", "explicit_paths", "catalog_ref"}
_POLICY_STATUSES = {"approved", "review_pending", "retired"}
_POLICY_ENFORCEMENTS = {"none", "preference", "advisory", "block"}
_POLICY_TERM_CATEGORIES = {"intake": "schedule_rule", "timing": "schedule_rule", "activity": "schedule_rule"}
_POLICY_SEMANTIC_CATEGORIES = {"schedule_rule", "risk"}
_ASSERTION_KINDS_BY_CATEGORY = {"context": {"clinical_exposure_context"}}
_ASSERTION_FAMILIES_BY_TYPE = {
    "balance": {"nutrient_balance_review_signal"},
    "supports": {
        "biochemical_mechanism_assertion",
        "absorption_interaction_claim",
        "nutritional_adequacy_advisory",
    },
    "review_with": {"clinical_review_signal"},
}
_ASSERTION_KIND_BY_TYPE = {
    "balance": "clinical_review_signal",
    "supports": "ontology_assertion",
    "review_with": "clinical_review_signal",
}

type _RdfTriple = tuple[Node, Node, Node]


@runtime_checkable
class _LinkMLSerializer(Protocol):
    def serialize(self, **kwargs: object) -> object: ...


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
    if set(projection_mapping) != {"format_version", "sources", "mappings"}:
        raise OntologyInfrastructureError(
            "repository_projection requires exactly format_version, sources, and mappings"
        )
    if projection_mapping.get("format_version") != _REPOSITORY_PROJECTION_FORMAT:
        raise OntologyInfrastructureError("Manifest repository_projection has an unsupported format_version")
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
    vocabulary = _load_yaml_mapping(_catalog_path(ontology_root, manifest, "vocabulary"))
    terms = _normalized_terms(vocabulary)
    categories = _required_mapping(vocabulary, "semantic_categories")
    scheduling_policies = _load_scheduling_policies(ontology_root, manifest, terms)
    audit_review_rules = _load_audit_review_rules(ontology_root, manifest)
    evidence_catalog = _load_evidence_catalog(_catalog_path(ontology_root, manifest, "policies"))
    audit_relation_exemptions = _load_audit_relation_exemptions(ontology_root, manifest)
    scheduling_constraints = _load_scheduling_constraints(ontology_root, manifest, terms)
    ontology_assertions = _load_ontology_assertions(ontology_root, manifest, terms)
    base_iri = _required_string(manifest, _BASE_IRI_KEY)
    schema_view = _schema_view(ontology_root, manifest)
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
        "assertions": runtime_assertions(),
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
                            "status": {"enum": sorted(_POLICY_STATUSES)},
                            "enforcement_cap": {"enum": sorted(_POLICY_ENFORCEMENTS)},
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
    runtime_program = _runtime_program(manifest)
    artifacts: dict[Path, bytes] = {
        Path("card.schema.json"): _json_bytes_no_header(card_schema),
        Path("schema.json"): generated_schema,
        Path("ontology.ttl"): _ttl_bytes(header, base_iri, categories, terms, schema_view, manifest),
        Path("shapes.ttl"): _shapes_bytes(header, base_iri, generated_shapes, semantic_shapes),
        Path("context.json"): _json_bytes_no_header(context),
        Path("projection-map.json"): _json_bytes_no_header(projection_map),
        Path("runtime-program.json"): _json_bytes_no_header(runtime_program),
        Path("runtime-vocabulary.yaml"): _yaml_bytes(runtime_vocabulary),
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
    return {"format_version": _REPOSITORY_PROJECTION_FORMAT, "sources": sources}


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
        if expected == "<key>" or (expected.startswith("<key>") and observed.endswith(expected[5:])):
            continue
        if expected != observed:
            return False
    return True


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


def _runtime_program(manifest: Mapping[str, object]) -> dict[str, object]:
    return {
        "format_version": _RUNTIME_PROGRAM_FORMAT,
        "schema_version": str(manifest["schema_version"]),
        "protocol": {
            "condition_classes": ["Condition"],
            "action_classes": ["Action"],
            "gate_classes": ["LifecycleGate", "PrecedenceRule", "TableLookup"],
        },
        "rules": [],
        "tables": [],
    }


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
        if assertion_kind is not None:
            allowed_assertion_kinds = _ASSERTION_KINDS_BY_CATEGORY.get(category, set())
            if not isinstance(assertion_kind, str) or assertion_kind not in allowed_assertion_kinds:
                raise OntologyInfrastructureError(
                    f"Term {category}:{slug} has assertion_kind incompatible with its semantic category"
                )
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


def _load_scheduling_policies(
    ontology_root: Path, manifest: Mapping[str, object], terms: Sequence[Mapping[str, object]]
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
        raw_policies = _required_mapping(source, "scheduling_policies")
        governance = _policy_governance_defaults(source, relative_path)
        evidence_catalog = _required_mapping(source, "slot_policy_evidence")
        for key, raw_policy in raw_policies.items():
            if not isinstance(key, str) or key.count(":") != 1:
                raise OntologyInfrastructureError(f"Policy key must be category:term in {relative_path}: {key!r}")
            category, term = key.split(":", maxsplit=1)
            term_metadata = known_terms.get((_POLICY_TERM_CATEGORIES.get(category, category), term))
            if term_metadata is None:
                raise OntologyInfrastructureError(f"Policy {key!r} has no controlled vocabulary term")
            if str(term_metadata["semantic_category"]) not in _POLICY_SEMANTIC_CATEGORIES:
                raise OntologyInfrastructureError(
                    f"Policy {key!r} must target a schedule_rule or risk term, not a biological or context assertion"
                )
            if key in policies:
                raise OntologyInfrastructureError(f"Duplicate canonical scheduling policy {key!r}")
            if not isinstance(raw_policy, dict):
                raise OntologyInfrastructureError(f"Policy {key!r} must be a mapping")
            policies[key] = _normalize_scheduling_policy(
                key, cast(Mapping[str, object], raw_policy), term_metadata, governance, evidence_catalog
            )
    return dict(sorted(policies.items()))


def _load_audit_review_rules(ontology_root: Path, manifest: Mapping[str, object]) -> list[dict[str, object]]:
    rules: list[dict[str, object]] = []
    seen: set[str] = set()
    for relative_path in _catalog_paths(ontology_root, manifest, "policies"):
        source = _load_yaml_mapping(_source_path(ontology_root, relative_path))
        raw_rules = _required_mapping(source, "audit_review_rules")
        evidence_catalog = _required_mapping(source, "slot_policy_evidence")
        for rule_id, raw in raw_rules.items():
            if not isinstance(rule_id, str) or not rule_id.startswith("audit_") or rule_id in seen:
                raise OntologyInfrastructureError(
                    f"Audit review rule id must be unique and start with audit_: {rule_id!r}"
                )
            if not isinstance(raw, dict):
                raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} must be a mapping")
            raw_mapping = cast(Mapping[str, object], raw)
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
                raise OntologyInfrastructureError(
                    f"Audit review rule {rule_id!r} has unsupported fields: {', '.join(extras)}"
                )
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
                raise OntologyInfrastructureError(
                    f"Audit review rule {rule_id!r} priority must be a non-negative integer"
                )
            subjects_raw = raw_mapping.get("subjects")
            if not isinstance(subjects_raw, dict):
                raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} subjects must be a mapping")
            if raw_mapping.get("status") != "retired" and not subjects_raw:
                raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} requires live subjects")
            subjects: dict[str, dict[str, object]] = {}
            for subject_id, disposition in subjects_raw.items():
                if (
                    not isinstance(subject_id, str)
                    or not subject_id.startswith("sub_")
                    or not isinstance(disposition, dict)
                ):
                    raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} has invalid subject disposition")
                subjects[subject_id] = _normalize_audit_subject(
                    rule_id, cast(Mapping[str, object], disposition), evidence_catalog
                )
            normalized: dict[str, object] = {
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
                    evidence_catalog,
                    effects=[],
                    warning=raw_mapping.get("enforcement") == "advisory",
                ),
            }
            rules.append(normalized)
            seen.add(rule_id)
    return sorted(rules, key=lambda item: str(item["id"]))


def _normalize_audit_subject(
    rule_id: str,
    raw: Mapping[str, object],
    evidence_catalog: Mapping[str, object],
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
    if status not in {"approved", "review_pending"} or raw.get("scope") != {"planner": "audit"}:
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} no-assignment lifecycle/scope is invalid")
    if not isinstance(evidence, list):
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} no-assignment evidence must be a list")
    _validate_evidence_entries(f"audit rule {rule_id} subject", cast(list[object], evidence), evidence_catalog)
    gap = raw.get("evidence_gap")
    if status == "approved" and not evidence:
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} approved no-assignment requires evidence")
    if status == "review_pending" and not evidence and (not isinstance(gap, str) or not gap):
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


def _normalize_scheduling_policy(
    key: str,
    raw: Mapping[str, object],
    term_metadata: Mapping[str, object],
    governance: Mapping[str, object],
    evidence_catalog: Mapping[str, object],
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
        "label": _required_string(term_metadata, "label"),
        "description": _required_string(term_metadata, "description"),
        "applies_when": _required_string(raw, "applies_when"),
    }
    effects_raw = raw.get("effects", [])
    if not isinstance(effects_raw, list):
        raise OntologyInfrastructureError(f"Policy {key!r} effects must be a list")
    normalized["effects"] = [_normalize_policy_effect(key, cast(object, item)) for item in effects_raw]
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
            f"policy {key}", raw, evidence_catalog, effects=cast(list[object], normalized["effects"]), warning=warning
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
    catalog: Mapping[str, object],
    *,
    effects: list[object],
    warning: bool = False,
) -> dict[str, object]:
    status, enforcement = _governance_status(context, raw)
    scope = _governance_scope(context, raw)
    evidence = _governance_evidence(context, raw, catalog)
    _validate_governance_evidence_lifecycle(context, raw, status, evidence)
    _validate_governance_effects(context, status, enforcement, effects, warning)
    _validate_review_date(context, raw)
    if _declared_enforcement(effects, warning) != enforcement:
        raise OntologyInfrastructureError(f"{context} enforcement does not match effects")
    return _governance_result(raw, status, enforcement, scope, evidence)


def _governance_status(context: str, raw: Mapping[str, object]) -> tuple[str, str]:
    status = _required_string(raw, "status")
    enforcement = _required_string(raw, "enforcement")
    if status not in _POLICY_STATUSES or enforcement not in _POLICY_ENFORCEMENTS:
        raise OntologyInfrastructureError(f"{context} has invalid status/enforcement")
    return status, enforcement


def _governance_scope(context: str, raw: Mapping[str, object]) -> Mapping[str, object]:
    scope = cast(Mapping[str, object], _required_mapping(raw, "scope"))
    if not scope or set(scope) - _ALLOWED_SCOPE_KEYS or any(not isinstance(v, str) or not v for v in scope.values()):
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
    context: str, raw: Mapping[str, object], status: str, evidence: list[object]
) -> None:
    if status == "approved" and not evidence:
        raise OntologyInfrastructureError(f"{context} approved records require non-empty evidence")
    if status == "review_pending" and not evidence and not raw.get("evidence_gap"):
        raise OntologyInfrastructureError(f"{context} pending records require evidence or evidence_gap")


def _validate_governance_effects(
    context: str, status: str, enforcement: str, effects: list[object], warning: bool
) -> None:
    if status == "retired" and (effects or warning or enforcement != "none"):
        raise OntologyInfrastructureError(
            f"{context} retired records must have empty effects, no warning, and enforcement none"
        )
    if status == "review_pending" and enforcement == "block":
        raise OntologyInfrastructureError(f"{context} review_pending records cannot block")


def _validate_review_date(context: str, raw: Mapping[str, object]) -> None:
    if "review_by" not in raw or not isinstance(raw["review_by"], str) or len(raw["review_by"]) != 10:  # noqa: PLR2004
        raise OntologyInfrastructureError(f"{context} review_by must be YYYY-MM-DD")


def _declared_enforcement(effects: list[object], warning: bool) -> str:
    if any(isinstance(e, dict) and cast(Mapping[str, object], e).get("block") is True for e in effects):
        return "block"
    if effects:
        return "preference"
    return "advisory" if warning else "none"


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
    ontology_root: Path, manifest: Mapping[str, object], terms: Sequence[Mapping[str, object]]
) -> dict[str, dict[str, object]]:
    """Load first-class, governed planner constraints from manifest-owned sources.

    Constraints intentionally model operational scheduling decisions separately
    from ontology relations.  They preserve legacy behavior without asserting
    biochemical incompatibility or category disjointness.
    """
    known_terms = {(str(term["semantic_category"]), str(term["slug"])) for term in terms}
    constraints: dict[str, dict[str, object]] = {}
    legacy_ids: set[str] = set()
    for relative_path in _catalog_paths(ontology_root, manifest, "constraints"):
        source = _load_yaml_mapping(_source_path(ontology_root, relative_path))
        raw_constraints = _required_mapping(source, "scheduling_constraints")
        for constraint_id, raw_constraint in raw_constraints.items():
            if not isinstance(constraint_id, str) or not constraint_id.startswith("sc_"):
                raise OntologyInfrastructureError(f"Scheduling constraint id must start with sc_: {constraint_id!r}")
            if constraint_id in constraints or not isinstance(raw_constraint, dict):
                raise OntologyInfrastructureError(f"Duplicate or malformed scheduling constraint {constraint_id!r}")
            normalized = _normalize_scheduling_constraint(
                constraint_id, cast(Mapping[str, object], raw_constraint), known_terms
            )
            legacy_id = str(normalized["legacy_relation_id"])
            if legacy_id in legacy_ids:
                raise OntologyInfrastructureError(
                    f"Duplicate legacy relation id in scheduling constraints: {legacy_id}"
                )
            legacy_ids.add(legacy_id)
            constraints[constraint_id] = normalized
    return dict(sorted(constraints.items()))


def _normalize_scheduling_constraint(
    constraint_id: str, raw: Mapping[str, object], known_terms: set[tuple[str, str]]
) -> dict[str, object]:
    allowed = {
        "legacy_relation_id",
        "assertion_type",
        "effect",
        "enforcement",
        "legacy_preserved",
        "status",
        "owner",
        "review_by",
        "evidence",
        "scope",
        "source_selector",
        "target_selector",
        "rationale",
        "semantic_note",
        "action",
    }
    extras = sorted(set(raw) - allowed)
    if extras:
        raise OntologyInfrastructureError(
            f"Scheduling constraint {constraint_id!r} has unsupported fields: {', '.join(extras)}"
        )
    if _required_string(raw, "assertion_type") != "clinical_scheduling_constraint":
        raise OntologyInfrastructureError(
            f"Scheduling constraint {constraint_id!r} must be a clinical_scheduling_constraint"
        )
    if _required_string(raw, "effect") != "separate_slots":
        raise OntologyInfrastructureError(f"Scheduling constraint {constraint_id!r} has unsupported effect")
    if _required_string(raw, "enforcement") not in {"block", "advisory", "review"}:
        raise OntologyInfrastructureError(f"Scheduling constraint {constraint_id!r} has invalid enforcement")
    normalized = {
        "legacy_relation_id": _required_string(raw, "legacy_relation_id"),
        "assertion_type": "clinical_scheduling_constraint",
        "effect": "separate_slots",
        "enforcement": _required_string(raw, "enforcement"),
        **_normalize_constraint_governance(f"Scheduling constraint {constraint_id!r}", raw),
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
    ontology_root: Path, manifest: Mapping[str, object], terms: Sequence[Mapping[str, object]]
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
    allowed_families = _ASSERTION_FAMILIES_BY_TYPE.get(relation_type)
    if allowed_families is None:
        raise OntologyInfrastructureError(
            f"Ontology assertion {assertion_id} has unsupported relation type {relation_type!r}; "
            "hard scheduling behavior belongs only in scheduling_constraints"
        )
    assertion_kind = _required_string(raw, "assertion_kind")
    if assertion_kind != _ASSERTION_KIND_BY_TYPE[relation_type]:
        raise OntologyInfrastructureError(
            f"Ontology assertion {assertion_id} has assertion_kind incompatible with {relation_type}"
        )
    semantic_family = _required_string(raw, "semantic_family")
    if semantic_family not in allowed_families:
        raise OntologyInfrastructureError(
            f"Ontology assertion {assertion_id} has semantic_family incompatible with {relation_type}"
        )
    source_selector = _normalize_constraint_selector(assertion_id, raw.get("source_selector"), known_terms)
    target_selector = _normalize_constraint_selector(assertion_id, raw.get("target_selector"), known_terms)
    _validate_assertion_endpoints(assertion_id, semantic_family, source_selector, target_selector)
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


def _validate_assertion_endpoints(
    assertion_id: str,
    semantic_family: str,
    source: Mapping[str, object],
    target: Mapping[str, object],
) -> None:
    """Keep semantic families from silently becoming generic planner rules."""
    source_is_entity = "entity" in source
    target_is_entity = "entity" in target
    if semantic_family in {"absorption_interaction_claim", "nutrient_balance_review_signal"} and (
        not source_is_entity or not target_is_entity
    ):
        raise OntologyInfrastructureError(
            f"Ontology assertion {assertion_id} {semantic_family} requires entity selectors on both endpoints"
        )
    if semantic_family == "nutritional_adequacy_advisory" and (
        not source_is_entity or target.get("category") != "context"
    ):
        raise OntologyInfrastructureError(
            f"Ontology assertion {assertion_id} nutritional_adequacy_advisory requires entity-to-context endpoints"
        )


def _normalize_governance(context: str, raw: Mapping[str, object]) -> dict[str, object]:
    if raw.get("legacy_preserved") is not True:
        raise OntologyInfrastructureError(f"{context} must declare legacy_preserved: true")
    if _required_string(raw, "status") != "review_pending":
        raise OntologyInfrastructureError(f"{context} must declare status: review_pending")
    evidence = raw.get("evidence")
    if not isinstance(evidence, list):
        raise OntologyInfrastructureError(f"{context} evidence must be a list")
    scope = _required_mapping(raw, "scope")
    planner_scope = _required_string(scope, "planner")
    return {
        "legacy_preserved": True,
        "status": "review_pending",
        "owner": _required_string(raw, "owner"),
        "review_by": _required_string(raw, "review_by"),
        "evidence": cast(list[object], evidence),
        "scope": {"planner": planner_scope},
    }


def _normalize_constraint_governance(context: str, raw: Mapping[str, object]) -> dict[str, object]:
    """Validate the explicit lifecycle/enforcement matrix for constraints."""
    status = _required_string(raw, "status")
    enforcement = _required_string(raw, "enforcement")
    valid = {
        ("proposed", "review"),
        ("review_pending", "review"),
        ("approved", "review"),
        ("approved", "advisory"),
        ("approved", "block"),
        ("retired", "review"),
    }
    if (status, enforcement) not in valid:
        raise OntologyInfrastructureError(
            f"{context} has invalid status/enforcement combination: {status}+{enforcement}"
        )
    if raw.get("legacy_preserved") is not True:
        raise OntologyInfrastructureError(f"{context} must declare legacy_preserved: true")
    evidence = raw.get("evidence")
    if not isinstance(evidence, list):
        raise OntologyInfrastructureError(f"{context} evidence must be a list")
    evidence_items = cast(list[object], evidence)
    for index, item in enumerate(evidence_items):
        if not isinstance(item, str):
            raise OntologyInfrastructureError(f"{context} evidence[{index}] must be a string HTTPS URL")
        parsed = urlparse(item)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username is not None or parsed.password is not None:
            raise OntologyInfrastructureError(f"{context} evidence[{index}] must be a string HTTPS URL")
    if status == "approved" and not evidence_items:
        raise OntologyInfrastructureError(f"{context} approved constraints require non-empty evidence")
    scope = _required_mapping(raw, "scope")
    return {
        "legacy_preserved": True,
        "status": status,
        "owner": _required_string(raw, "owner"),
        "review_by": _required_string(raw, "review_by"),
        "evidence": evidence_items,
        "scope": {"planner": _required_string(scope, "planner")},
    }


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


def _normalize_policy_effect(key: str, raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise OntologyInfrastructureError(f"Policy {key!r} effect must be a mapping")
    effect = cast(Mapping[str, object], raw)
    extras = sorted(set(effect) - {"match", "level", "block"})
    if extras:
        raise OntologyInfrastructureError(f"Policy {key!r} effect has unsupported fields: {', '.join(extras)}")
    normalized: dict[str, object] = {"match": _normalize_policy_match(key, effect.get("match"))}
    level = _normalize_policy_level(key, effect.get("level"))
    if level is not None:
        normalized["level"] = level
    block = _normalize_policy_block(key, effect.get("block"))
    if block is not None:
        normalized["block"] = block
    if len(normalized) == 1:
        raise OntologyInfrastructureError(f"Policy {key!r} effect must set level or block")
    return normalized


def _normalize_policy_match(key: str, raw: object) -> dict[str, object]:
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
        if near not in {"wake", "breakfast", "day_meal", "sleep", "workout_before", "workout_after"}:
            raise OntologyInfrastructureError(f"Policy {key!r} has invalid slot proximity {near!r}")
        normalized_match["near"] = near
    if "food" in match_map:
        food = match_map["food"]
        if not isinstance(food, bool):
            raise OntologyInfrastructureError(f"Policy {key!r} food match must be boolean")
        normalized_match["food"] = food
    return normalized_match


def _normalize_policy_level(key: str, level: object) -> str | None:
    if level is None:
        return None
    if level not in {"avoid_strong", "avoid", "prefer", "prefer_strong"}:
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


def _yaml_bytes(value: object) -> bytes:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=True).encode("utf-8")


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
