"""Canonical typed-selector relation loading and validation."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import NamedTuple, cast

from planner.cards.substance import substance_names
from planner.contracts import CardLoadError, Relation, RelationSelector, RelationType, Severity, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.paths import Paths
from planner.schema_validation import schema_errors
from planner.yaml_io import YamlValue, load_yaml


class _ValidationContext(NamedTuple):
    substances: Collection[str]
    names: Collection[str]
    known_terms: set[tuple[str, str]]
    relation_types: frozenset[str]


def load_global_relations(paths: Paths, bundle: OntologyBundle) -> list[Relation]:
    """Load authored ontology relations without endpoint aliases or fallback decoding."""
    data = load_yaml(paths.relations_file)
    if not isinstance(data, dict):
        return []
    result: list[Relation] = []
    entries = data.get("relations")
    if not isinstance(entries, list):
        return result
    relation_types = _ontology_relation_types(bundle, paths.relations_file)
    for index, raw_entry in enumerate(entries):
        if not isinstance(raw_entry, dict):
            continue
        entry = cast(dict[str, object], raw_entry)
        relation_type = entry.get("type")
        if not isinstance(relation_type, str) or relation_type not in relation_types:
            raise CardLoadError(
                paths.relations_file,
                f"{paths.relations_file}: relations[{index}].type {relation_type!r} is not in ontology relation_types",
            )
        result.append(_relation_from_mapping(cast(RelationType, relation_type), entry))
    return result


def _ontology_relation_types(bundle: OntologyBundle, path: Path) -> frozenset[str]:
    raw_relation_types = bundle.runtime_vocabulary.get("relation_types")
    if not isinstance(raw_relation_types, dict) or not raw_relation_types:
        raise CardLoadError(path, "canonical runtime vocabulary has no relation_types")
    relation_types = cast(dict[object, object], raw_relation_types)
    return frozenset(str(relation_type) for relation_type in relation_types)


def _relation_from_mapping(relation_type: RelationType, relation: dict[str, object]) -> Relation:
    source = _selector_from_mapping(relation.get("source_selector"))
    target = _selector_from_mapping(relation.get("target_selector"))
    return Relation(
        id=cast(str, relation.get("id", "")),
        type=relation_type,
        reason=cast(str, relation.get("reason", "")),
        source_selector=source,
        target_selector=target,
        action=_optional_str(relation.get("action")),
        severity=cast(Severity | None, relation.get("severity")),
        assertion_kind=_optional_str(relation.get("assertion_kind")),
        semantic_family=_optional_str(relation.get("semantic_family")),
    )


def _selector_from_mapping(raw: object) -> RelationSelector:
    selector = cast(dict[str, object], raw) if isinstance(raw, dict) else {}
    entity = selector.get("entity")
    if isinstance(entity, dict):
        entity_mapping = cast(dict[str, object], entity)
        return RelationSelector(
            entity_id=_optional_str(entity_mapping.get("id")), entity_name=_optional_str(entity_mapping.get("name"))
        )
    return RelationSelector(
        category=_optional_str(selector.get("category")),
        term=_optional_str(selector.get("term")),
    )


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def check_global_relations(
    relations_data: YamlValue, substances: dict[str, Substance], paths: Paths, bundle: OntologyBundle
) -> list[str]:
    """Validate selector shape and every entity/term reference against canonical vocabulary."""
    errors = schema_errors(relations_data, "relations", paths.relations_file, bundle)
    if errors or not isinstance(relations_data, dict):
        return errors
    vocabulary = bundle.runtime_vocabulary
    known_terms = {
        (str(term["semantic_category"]), str(term["slug"]))
        for raw in cast(list[object], vocabulary.get("terms", []))
        if isinstance(raw, dict)
        for term in [cast(dict[str, object], raw)]
    }
    names = substance_names(substances)
    relation_types = _ontology_relation_types(bundle, paths.relations_file)
    context = _ValidationContext(substances, names, known_terms, relation_types)
    entries = relations_data.get("relations")
    if not isinstance(entries, list):
        return errors
    for index, raw in enumerate(entries):
        if not isinstance(raw, dict):
            continue
        relation = cast(dict[str, object], raw)
        path = f"{paths.relations_file}: relations[{index}]"
        relation_type = relation.get("type")
        if not isinstance(relation_type, str) or relation_type not in context.relation_types:
            errors.append(f"{path}.type {relation_type!r} is not in ontology relation_types")
        for side in ("source", "target"):
            errors.extend(_selector_errors(relation.get(f"{side}_selector"), side, path, context))
    return errors


def _selector_errors(
    raw: object,
    side: str,
    path: str,
    context: _ValidationContext,
) -> list[str]:
    if not isinstance(raw, dict):
        return []
    selector = cast(dict[str, object], raw)
    entity = selector.get("entity")
    if isinstance(entity, dict):
        entity_mapping = cast(dict[str, object], entity)
        entity_id = entity_mapping.get("id")
        if isinstance(entity_id, str) and entity_id not in context.substances:
            return [f"{path}.{side}_selector.entity.id '{entity_id}' has no matching substance card"]
        entity_name = entity_mapping.get("name")
        if isinstance(entity_name, str) and entity_name not in context.names:
            return [f"{path}.{side}_selector.entity.name '{entity_name}' has no matching substance name"]
        return []
    category, term = selector.get("category"), selector.get("term")
    if isinstance(category, str) and isinstance(term, str) and (category, term) not in context.known_terms:
        return [f"{path}.{side}_selector term '{category}:{term}' is not in canonical ontology vocabulary"]
    return []
