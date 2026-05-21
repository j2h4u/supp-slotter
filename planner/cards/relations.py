"""Substance-to-substance relations: YAML loader, raw-data validator, and dataclass-side helpers.

Query/matching logic lives behind `planner.query_model`, which loads these
Relation dataclasses into an in-memory SurrealDB read model once per command.
The functions here stay Python because they operate on raw YAML before the read
model is constructed.
"""

from __future__ import annotations

import sys
from typing import Any, Literal, cast

from planner.cards.substance import substance_names
from planner.contracts import Relation, Severity, Substance, TraitDef
from planner.paths import Paths
from planner.schema_validation import schema_errors
from planner.yaml_io import load_yaml

RelationSide = Literal["source", "target"]


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
            f"warning: {relations_file}: expected mapping, got {type(data).__name__}; "
            "ignoring relation-based warnings",
            file=sys.stderr,
        )
        return []
    data_dict = cast(dict[str, Any], data)
    relations: list[Relation] = []
    for relation_type in ("balance", "supports", "competes", "review_with"):
        relation_items = data_dict.get(relation_type)
        if not isinstance(relation_items, list):
            continue
        relation_items_list = cast(list[Any], relation_items)
        for relation_raw in relation_items_list:
            if not isinstance(relation_raw, dict):
                continue
            relation = cast(dict[str, Any], relation_raw)
            relations.append(
                Relation(
                    type=relation_type,
                    reason=cast(str, relation.get("reason") or ""),
                    source_substance=cast(str | None, relation.get("source_substance")),
                    target_substance=cast(str | None, relation.get("target_substance")),
                    source_name=cast(str | None, relation.get("source_name")),
                    target_name=cast(str | None, relation.get("target_name")),
                    source_trait=cast(str | None, relation.get("source_trait")),
                    target_trait=cast(str | None, relation.get("target_trait")),
                    source_class=cast(str | None, relation.get("source_class")),
                    target_class=cast(str | None, relation.get("target_class")),
                    action=cast(str | None, relation.get("action")),
                    severity=cast(Severity | None, relation.get("severity")),
                )
            )
    return relations


def check_global_relations(
    relations_data: object,
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

    relations_dict = cast(dict[str, Any], relations_data)
    names = substance_names(substances)
    registered_classes = {
        td.short_name for td in trait_defs.values() if td.namespace == "is"
    }
    for relation_type in ("balance", "supports", "competes", "review_with"):
        relation_items: Any = relations_dict.get(relation_type) or []
        if not isinstance(relation_items, list):
            continue
        relation_items_list = cast(list[Any], relation_items)
        for index, relation_raw in enumerate(relation_items_list):
            if not isinstance(relation_raw, dict):
                continue
            relation = cast(dict[str, Any], relation_raw)
            path = f"{relations_file}: {relation_type}[{index}]"
            source_name = relation.get("source_name")
            target_name = relation.get("target_name")
            source_substance = relation.get("source_substance")
            target_substance = relation.get("target_substance")
            source_trait = relation.get("source_trait")
            target_trait = relation.get("target_trait")
            source_class = relation.get("source_class")
            target_class = relation.get("target_class")
            has_class_endpoint = source_class is not None or target_class is not None
            if has_class_endpoint and relation_type != "competes":
                errors.append(
                    f"{path}: source_class/target_class endpoints are only supported for competes relations"
                )
            if isinstance(source_name, str) and source_name not in names:
                errors.append(
                    f"{path}.source_name '{source_name}' has no matching substance name"
                )
            if isinstance(target_name, str) and target_name not in names:
                errors.append(
                    f"{path}.target_name '{target_name}' has no matching substance name"
                )
            if isinstance(source_substance, str) and source_substance not in substances:
                errors.append(
                    f"{path}.source_substance '{source_substance}' has no matching substance card"
                )
            if isinstance(target_substance, str) and target_substance not in substances:
                errors.append(
                    f"{path}.target_substance '{target_substance}' has no matching substance card"
                )
            if isinstance(source_trait, str) and source_trait not in trait_defs:
                errors.append(
                    f"{path}.source_trait '{source_trait}' is not a registered trait in data/traits/"
                )
            if isinstance(target_trait, str) and target_trait not in trait_defs:
                errors.append(
                    f"{path}.target_trait '{target_trait}' is not a registered trait in data/traits/"
                )
            if isinstance(source_class, str) and source_class not in registered_classes:
                errors.append(
                    f"{path}.source_class '{source_class}' is not a registered is: trait in data/traits/"
                )
            if isinstance(target_class, str) and target_class not in registered_classes:
                errors.append(
                    f"{path}.target_class '{target_class}' is not a registered is: trait in data/traits/"
                )
            source_key = (
                source_substance if isinstance(source_substance, str)
                else source_name if isinstance(source_name, str)
                else source_trait if isinstance(source_trait, str)
                else source_class if isinstance(source_class, str) else None
            )
            target_key = (
                target_substance if isinstance(target_substance, str)
                else target_name if isinstance(target_name, str)
                else target_trait if isinstance(target_trait, str)
                else target_class if isinstance(target_class, str) else None
            )
            if source_key is not None and source_key == target_key:
                errors.append(f"{path} references the same source and target")
    return errors
