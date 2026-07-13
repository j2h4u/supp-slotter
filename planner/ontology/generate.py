"""Deterministic build of the committed executable ontology artifacts.

This module is generation-only: it imports LinkML to prove and inspect the
authored schema, while normal planner runtime paths only read the resulting
runtime-vocabulary YAML and RDF/SHACL artifacts.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import yaml
from linkml_runtime.utils.schemaview import SchemaView

from planner.ontology.errors import OntologyInfrastructureError

_BASE_IRI_KEY = "base_iri"
_MANIFEST_NAME = "manifest.yaml"
_GENERATED_DIR = "generated"
_RUNTIME_FORMAT = "supp-slotter.runtime-vocabulary/v1"
_POLICY_TERM_CATEGORIES = {"intake": "schedule_rule", "timing": "schedule_rule", "activity": "schedule_rule"}


def generate_ontology(ontology_root: Path, *, check: bool = False) -> None:
    """Generate or freshness-check all artifacts declared by the manifest."""
    manifest = _load_manifest(ontology_root)
    _validate_linkml_root(ontology_root, manifest)
    artifact_bytes = _render_artifacts(ontology_root, manifest)
    generated_dir = ontology_root / _GENERATED_DIR
    if check:
        _check_fresh(generated_dir, artifact_bytes)
        return
    generated_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, content in artifact_bytes.items():
        target = generated_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


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
        "policy_sources",
        "custom_shapes",
    }
    missing = sorted(required - loaded.keys())
    if missing:
        raise OntologyInfrastructureError(f"Ontology manifest is missing required keys: {', '.join(missing)}")
    if loaded[_BASE_IRI_KEY] != "https://j2h4u.github.io/supp-slotter/ontology/v1/":
        raise OntologyInfrastructureError("Ontology manifest has a non-canonical ss base IRI")
    return cast(dict[str, object], loaded)


def _validate_linkml_root(ontology_root: Path, manifest: Mapping[str, object]) -> None:
    root = ontology_root / _required_string(manifest, "linkml_root")
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


def _render_artifacts(ontology_root: Path, manifest: Mapping[str, object]) -> dict[Path, bytes]:
    source_hash = _source_hash(ontology_root, manifest)
    vocabulary = _load_yaml_mapping(ontology_root / "vocabulary.yaml")
    terms = _normalized_terms(vocabulary)
    categories = _required_mapping(vocabulary, "semantic_categories")
    scheduling_policies = _load_scheduling_policies(ontology_root, manifest, terms)
    base_iri = _required_string(manifest, _BASE_IRI_KEY)
    header = _header(manifest, source_hash)
    runtime_vocabulary: object = {
        "format": _RUNTIME_FORMAT,
        "schema_version": str(manifest["schema_version"]),
        "base_iri": base_iri,
        "source_hash": source_hash,
        "categories": categories,
        "terms": terms,
        "scheduling_policies": scheduling_policies,
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
            },
        },
    )
    return {
        Path("card.schema.json"): _json_bytes(card_schema, header),
        Path("ontology.ttl"): _ttl_bytes(header, base_iri, categories, terms),
        Path("shapes.ttl"): _shapes_bytes(header, base_iri, semantic_shapes),
        Path("runtime-vocabulary.yaml"): _yaml_bytes(runtime_vocabulary),
    }


def _source_hash(ontology_root: Path, manifest: Mapping[str, object]) -> str:
    paths = [_MANIFEST_NAME]
    paths.extend(_required_string_list(manifest, "linkml_modules"))
    paths.extend(_required_string_list(manifest, "policy_sources"))
    paths.extend(_required_string_list(manifest, "custom_shapes"))
    digest = hashlib.sha256()
    for relative_path in paths:
        path = ontology_root / relative_path
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
        normalized.append({
            "slug": slug,
            "label": _required_string(term, "label"),
            "description": _required_string(term, "description"),
            "semantic_category": category,
            "allowed_predicates": _required_string_list(category_metadata, "allowed_predicates"),
            "ontoclean_profile": _required_string(category_metadata, "ontoclean_profile"),
        })
    return sorted(normalized, key=lambda item: (str(item["semantic_category"]), str(item["slug"])))


def _load_scheduling_policies(
    ontology_root: Path, manifest: Mapping[str, object], terms: Sequence[Mapping[str, object]]
) -> dict[str, dict[str, object]]:
    """Load the planner policy contract from manifest-owned canonical sources.

    The deliberately broad name includes risk warnings: they are planner policy
    facts, even though they do not affect slot scoring.  Runtime consumers get a
    stable flat ``category:term`` key and never need to load ``data/traits``.
    """
    known_terms = {(str(term["semantic_category"]), str(term["slug"])): term for term in terms}
    policies: dict[str, dict[str, object]] = {}
    for relative_path in _required_string_list(manifest, "policy_sources"):
        source = _load_yaml_mapping(ontology_root / relative_path)
        raw_policies = _required_mapping(source, "scheduling_policies")
        for key, raw_policy in raw_policies.items():
            if not isinstance(key, str) or key.count(":") != 1:
                raise OntologyInfrastructureError(f"Policy key must be category:term in {relative_path}: {key!r}")
            category, term = key.split(":", maxsplit=1)
            term_metadata = known_terms.get((_POLICY_TERM_CATEGORIES.get(category, category), term))
            if term_metadata is None:
                raise OntologyInfrastructureError(f"Policy {key!r} has no controlled vocabulary term")
            if key in policies:
                raise OntologyInfrastructureError(f"Duplicate canonical scheduling policy {key!r}")
            if not isinstance(raw_policy, dict):
                raise OntologyInfrastructureError(f"Policy {key!r} must be a mapping")
            policies[key] = _normalize_scheduling_policy(key, cast(Mapping[str, object], raw_policy), term_metadata)
    return dict(sorted(policies.items()))


def _normalize_scheduling_policy(
    key: str, raw: Mapping[str, object], term_metadata: Mapping[str, object]
) -> dict[str, object]:
    allowed = {"applies_when", "effects", "warning", "action"}
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
    return normalized


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
    files: list[str] = _required_string_list(manifest, "custom_shapes")
    contents: list[str] = []
    for relative_path in files:
        path = ontology_root / relative_path
        source = path.read_text(encoding="utf-8")
        if base_iri not in source:
            raise OntologyInfrastructureError(f"Custom SHACL source has no canonical ss base IRI: {path}")
        contents.append(source.rstrip())
    return "\n\n".join(contents) + "\n"


def _ttl_bytes(
    header: str, base_iri: str, categories: Mapping[str, object], terms: Sequence[Mapping[str, object]]
) -> bytes:
    lines = [
        header.rstrip(),
        f"@prefix ss: <{base_iri}> .",
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "",
    ]
    lines.extend([f"<{base_iri}> a ss:Ontology .", ""])
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
            f"  ss:label {label} .",
            "",
        ])
    return ("\n".join(lines).rstrip() + "\n").encode("utf-8")


def _shapes_bytes(header: str, base_iri: str, semantic_shapes: str) -> bytes:
    return (header + f"@prefix ss: <{base_iri}> .\n\n" + semantic_shapes).encode("utf-8")


def _header(manifest: Mapping[str, object], source_hash: str) -> str:
    return (
        f"# generated-by: scripts/generate_ontology.py\n"
        f"# schema-version: {manifest['schema_version']}\n"
        f"# source-hash: {source_hash}\n"
    )


def _json_bytes(value: object, header: str) -> bytes:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return (header + payload).encode("utf-8")


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
