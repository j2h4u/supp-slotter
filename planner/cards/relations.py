"""Substance-to-substance relations: YAML loader, raw-data validator, and dataclass-side helpers.

Query/matching logic lives behind `planner.query_model`, which loads these
Relation dataclasses into an in-memory SurrealDB read model once per command.
The functions here stay Python because they operate on raw YAML before the read
model is constructed.
"""

from __future__ import annotations

import sys
from collections.abc import Collection
from pathlib import Path
from typing import Literal, NamedTuple, cast

from planner.cards.substance import substance_names
from planner.contracts import Relation, RelationType, Severity, Substance, TraitDef
from planner.paths import Paths
from planner.schema_validation import schema_errors
from planner.yaml_io import YamlValue, load_yaml

RelationSide = Literal["source", "target"]


class _RelationValidationContext(NamedTuple):
    relations_file: Path
    names: set[str]
    substances: dict[str, Substance]
    trait_defs: dict[str, TraitDef]
    registered_classes: set[str]


def load_global_relations(paths: Paths) -> list[Relation]:
    """Read data/relations.yaml and return the flat list of Relation dataclasses.

    Silently returns [] when the file is absent or has a non-mapping top level
    (with a stderr warning in the latter case); schema-level validation belongs
    in `check_global_relations`, which runs before any caller relies on this.
    """
    relations_file = paths.relations_file
    if not relations_file.exists():
        return []
    data = load_yaml(relations_file)
    if not isinstance(data, dict):
        print(
            f"warning: {relations_file}: expected mapping, got {type(data).__name__}; ignoring relation-based warnings",
            file=sys.stderr,
        )
        return []
    data_dict = cast(dict[str, object], data)
    relations: list[Relation] = []
    for relation_type in ("balance", "supports", "competes", "review_with"):
        relation_items = data_dict.get(relation_type)
        if not isinstance(relation_items, list):
            continue
        relation_items_list = cast(list[object], relation_items)
        for relation_raw in relation_items_list:
            if not isinstance(relation_raw, dict):
                continue
            relation = cast(dict[str, object], relation_raw)
            relations.append(_relation_from_mapping(relation_type, relation))
    return relations


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _relation_from_mapping(relation_type: RelationType, relation: dict[str, object]) -> Relation:
    reason = relation.get("reason")
    return Relation(
        type=relation_type,
        reason=reason if isinstance(reason, str) else "",
        source_substance=_optional_str(relation.get("source_substance")),
        target_substance=_optional_str(relation.get("target_substance")),
        source_name=_optional_str(relation.get("source_name")),
        target_name=_optional_str(relation.get("target_name")),
        source_trait=_optional_str(relation.get("source_trait")),
        target_trait=_optional_str(relation.get("target_trait")),
        source_class=_optional_str(relation.get("source_class")),
        target_class=_optional_str(relation.get("target_class")),
        action=_optional_str(relation.get("action")),
        severity=cast(Severity | None, relation.get("severity")),
    )


def check_global_relations(
    relations_data: YamlValue,
    substances: dict[str, Substance],
    trait_defs: dict[str, TraitDef],
    paths: Paths,
) -> list[str]:
    """Validate relations.yaml against schema and reference integrity.

    Runs before read-model construction — operates on raw YAML data so that
    schema-broken files can be reported before any downstream loader fires.

    Class endpoints (`source_class` / `target_class`) are checked against the
    registered `is:` namespace in the trait registry. A misspelled class slug would
    otherwise pass JSON Schema (it's any lowercase identifier) but never match
    in `slot_is_blocked` — silent failure.
    """
    relations_file = paths.relations_file
    errors: list[str] = []
    errors.extend(schema_errors(relations_data, "relations", relations_file))
    if errors or not isinstance(relations_data, dict):
        return errors

    relations_dict = cast(dict[str, object], relations_data)
    context = _RelationValidationContext(
        relations_file=relations_file,
        names=substance_names(substances),
        substances=substances,
        trait_defs=trait_defs,
        registered_classes={td.short_name for td in trait_defs.values() if td.namespace == "is"},
    )
    return [*errors, *_relation_reference_errors(relations_dict, context)]


def _relation_reference_errors(
    relations_dict: dict[str, object],
    context: _RelationValidationContext,
) -> list[str]:
    errors: list[str] = []
    for relation_type in ("balance", "supports", "competes", "review_with"):
        relation_items = relations_dict.get(relation_type) or []
        if not isinstance(relation_items, list):
            continue
        relation_items_list = cast(list[object], relation_items)
        for index, relation_raw in enumerate(relation_items_list):
            if not isinstance(relation_raw, dict):
                continue
            errors.extend(_relation_item_errors(cast(dict[str, object], relation_raw), relation_type, index, context))
    return errors


def _relation_item_errors(
    relation: dict[str, object],
    relation_type: str,
    index: int,
    context: _RelationValidationContext,
) -> list[str]:
    path = f"{context.relations_file}: {relation_type}[{index}]"
    errors = _endpoint_reference_errors(relation, path, context)
    has_class_endpoint = relation.get("source_class") is not None or relation.get("target_class") is not None
    if has_class_endpoint and relation_type != "competes":
        errors.append(f"{path}: source_class/target_class endpoints are only supported for competes relations")

    source_key = _endpoint_key(relation, "source")
    target_key = _endpoint_key(relation, "target")
    if source_key is not None and source_key == target_key:
        errors.append(f"{path} references the same source and target")
    return errors


def _endpoint_reference_errors(
    relation: dict[str, object],
    path: str,
    context: _RelationValidationContext,
) -> list[str]:
    errors: list[str] = []
    _append_missing_reference_error(
        errors,
        relation.get("source_name"),
        context.names,
        f"{path}.source_name",
        "has no matching substance name",
    )
    _append_missing_reference_error(
        errors,
        relation.get("target_name"),
        context.names,
        f"{path}.target_name",
        "has no matching substance name",
    )
    _append_missing_reference_error(
        errors,
        relation.get("source_substance"),
        context.substances,
        f"{path}.source_substance",
        "has no matching substance card",
    )
    _append_missing_reference_error(
        errors,
        relation.get("target_substance"),
        context.substances,
        f"{path}.target_substance",
        "has no matching substance card",
    )
    _append_missing_reference_error(
        errors,
        relation.get("source_trait"),
        context.trait_defs,
        f"{path}.source_trait",
        "is not a registered trait in data/traits/",
    )
    _append_missing_reference_error(
        errors,
        relation.get("target_trait"),
        context.trait_defs,
        f"{path}.target_trait",
        "is not a registered trait in data/traits/",
    )
    _append_missing_reference_error(
        errors,
        relation.get("source_class"),
        context.registered_classes,
        f"{path}.source_class",
        "is not a registered is: trait in data/traits/",
    )
    _append_missing_reference_error(
        errors,
        relation.get("target_class"),
        context.registered_classes,
        f"{path}.target_class",
        "is not a registered is: trait in data/traits/",
    )
    return errors


def _append_missing_reference_error(
    errors: list[str],
    value: object,
    known_values: Collection[str],
    label: str,
    missing_text: str,
) -> None:
    if isinstance(value, str) and value not in known_values:
        errors.append(f"{label} '{value}' {missing_text}")


def _endpoint_key(relation: dict[str, object], side: RelationSide) -> str | None:
    for suffix in ("substance", "name", "trait", "class"):
        value = relation.get(f"{side}_{suffix}")
        if isinstance(value, str):
            return value
    return None
