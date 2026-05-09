"""Substance-to-substance relations: loading, matching, validation, conflict detection."""

from __future__ import annotations

from typing import Any, cast

from planner.cards.substance import (
    collect_active_substance_names,  # noqa: F401  re-exported for engine plan use
    format_substance_name,
    substance_names,
)
from planner.contracts import Relation, RelationType, Substance
from planner.io import RELATIONS_PATH, load_yaml, schema_errors


def load_global_relations() -> list[Relation]:
    """Load all substance-to-substance relations into typed Relation objects."""
    if not RELATIONS_PATH.exists():
        return []
    data = load_yaml(RELATIONS_PATH)
    if not isinstance(data, dict):
        return []
    relations: list[Relation] = []
    for relation_type in ("balance", "supports", "competes", "antagonizes"):
        relation_items = data.get(relation_type)
        if not isinstance(relation_items, list):
            continue
        for relation in relation_items:
            if not isinstance(relation, dict):
                continue
            relations.append(
                Relation(
                    type=cast(RelationType, relation_type),
                    reason=relation.get("reason") or "",
                    source_substance=relation.get("source_substance"),
                    target_substance=relation.get("target_substance"),
                    source_name=relation.get("source_name"),
                    target_name=relation.get("target_name"),
                    action=relation.get("action"),
                )
            )
    return relations


def global_relation_refs(
    substances: dict[str, Substance],
    global_relations: list[Relation],
) -> set[str]:
    refs: set[str] = set()
    names: set[str] = set()
    for relation in global_relations:
        if relation.source_substance is not None:
            refs.add(relation.source_substance)
        if relation.target_substance is not None:
            refs.add(relation.target_substance)
        if relation.source_name is not None:
            names.add(relation.source_name)
        if relation.target_name is not None:
            names.add(relation.target_name)
    refs.update(
        substance_id
        for substance_id, substance in substances.items()
        if substance.name in names
    )
    return refs


def relation_endpoint_value(relation: Relation, side: str) -> str | None:
    if side == "source":
        return relation.source_substance or relation.source_name
    if side == "target":
        return relation.target_substance or relation.target_name
    return None


def substance_matches_relation_endpoint(
    substance_id: str,
    substance: Substance,
    relation: Relation,
    side: str,
) -> bool:
    if side == "source":
        if relation.source_substance is not None:
            return substance_id == relation.source_substance
        return relation.source_name is not None and substance.name == relation.source_name
    if side == "target":
        if relation.target_substance is not None:
            return substance_id == relation.target_substance
        return relation.target_name is not None and substance.name == relation.target_name
    return False


def relation_endpoint_is_active(
    relation: Relation,
    side: str,
    substances: dict[str, Substance],
    active_substances: set[str],
) -> bool:
    for substance_id in active_substances:
        substance = substances.get(substance_id)
        if substance is not None and substance_matches_relation_endpoint(
            substance_id, substance, relation, side
        ):
            return True
    return False


def relation_endpoint_display(
    relation: Relation,
    side: str,
    substances: dict[str, Substance],
) -> tuple[str, str]:
    exact_id = relation.source_substance if side == "source" else relation.target_substance
    if exact_id is not None:
        substance = substances.get(exact_id)
        if substance is not None:
            return exact_id, format_substance_name(substance)
        return exact_id, exact_id
    name = relation.source_name if side == "source" else relation.target_name
    if name is not None:
        return name, name
    return "<unknown>", "<unknown>"


def relation_endpoint_match_label(
    relation: Relation,
    side: str,
    substance_id: str | None,
    substance: Substance,
) -> str | None:
    exact_id = relation.source_substance if side == "source" else relation.target_substance
    if exact_id is not None and substance_id == exact_id:
        return f"{side} exact id"
    expected_name = relation.source_name if side == "source" else relation.target_name
    if expected_name is not None and substance.name == expected_name:
        return f"{side} exact name"
    return None


def collect_substance_relation_matches(
    substance: Substance,
    global_relations: list[Relation],
) -> list[tuple[Relation, list[str]]]:
    matches: list[tuple[Relation, list[str]]] = []
    for relation in global_relations:
        matched_by = [
            label
            for side in ("source", "target")
            if (
                label := relation_endpoint_match_label(
                    relation, side, substance.id, substance
                )
            )
        ]
        if matched_by:
            matches.append((relation, matched_by))
    return matches


def print_central_relation_matches(
    substance: Substance,
    substances: dict[str, Substance],
) -> None:
    print("\nCentral relations from data/relations.yaml (read-only)")
    print("Edit these in data/relations.yaml, not in this substance card.")
    if substance.id:
        print(f"Matches this substance by id: {substance.id}")
    if substance.name:
        print(f"Matches this substance by exact name: {substance.name}")

    matches = collect_substance_relation_matches(substance, load_global_relations())
    if not matches:
        print("  none matched; add links in data/relations.yaml if needed.")
        return

    print("Note: balance/competes are symmetric; supports/antagonizes are directional.")
    grouped: dict[str, list[tuple[Relation, list[str]]]] = {}
    for relation, matched_by in matches:
        grouped.setdefault(relation.type, []).append((relation, matched_by))

    for relation_type in ("balance", "competes", "supports", "antagonizes"):
        relation_group = grouped.get(relation_type)
        if not relation_group:
            continue
        print(f"\n{relation_type}")
        for relation, matched_by in relation_group:
            _source_key, source_name = relation_endpoint_display(relation, "source", substances)
            _target_key, target_name = relation_endpoint_display(relation, "target", substances)
            print(f"  {source_name} -> {target_name}")
            print(f"    matched by: {', '.join(matched_by)}")
            if relation.reason:
                print(f"    reason: {relation.reason}")
            if relation.action:
                print(f"    action: {relation.action}")


def check_global_relations(
    relations_data: object,
    substances: dict[str, Substance],
) -> list[str]:
    errors: list[str] = []
    errors.extend(schema_errors(relations_data, "relations", RELATIONS_PATH))
    if errors or not isinstance(relations_data, dict):
        return errors

    names = substance_names(substances)
    for relation_type in ("balance", "supports", "competes", "antagonizes"):
        relation_items = relations_data.get(relation_type) or []
        if not isinstance(relation_items, list):
            continue
        for index, relation in enumerate(relation_items):
            if not isinstance(relation, dict):
                continue
            path = f"{RELATIONS_PATH}: {relation_type}[{index}]"
            source_name = relation.get("source_name")
            target_name = relation.get("target_name")
            source_substance = relation.get("source_substance")
            target_substance = relation.get("target_substance")
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
            source_key = (
                source_substance if isinstance(source_substance, str)
                else source_name if isinstance(source_name, str) else None
            )
            target_key = (
                target_substance if isinstance(target_substance, str)
                else target_name if isinstance(target_name, str) else None
            )
            if source_key is not None and source_key == target_key:
                errors.append(f"{path} references the same source and target")
    return errors


def collect_missing_balance_relations(
    substances: dict[str, Substance],
    active_substances: set[str],
    global_relations: list[Relation] | None = None,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for relation in global_relations or []:
        if relation.type != "balance":
            continue
        for active_side, missing_side in (("source", "target"), ("target", "source")):
            if not relation_endpoint_is_active(
                relation, active_side, substances, active_substances,
            ) or relation_endpoint_is_active(
                relation, missing_side, substances, active_substances,
            ):
                continue
            source_key, source_name = relation_endpoint_display(relation, active_side, substances)
            target_key, target_name = relation_endpoint_display(relation, missing_side, substances)
            warning_key = (source_key, "balance", target_key)
            if warning_key in seen:
                continue
            seen.add(warning_key)
            warnings.append(
                {
                    "type": "missing_balance_substance",
                    "source_substance": source_key,
                    "source_name": source_name,
                    "target_substance": target_key,
                    "target_name": target_name,
                    "reason": relation.reason,
                    "action": relation.action or "",
                }
            )
    return warnings


def collect_missing_support_relations(
    substances: dict[str, Substance],
    active_substances: set[str],
    global_relations: list[Relation] | None = None,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for relation in global_relations or []:
        if relation.type != "supports":
            continue
        if not relation_endpoint_is_active(
            relation, "target", substances, active_substances,
        ) or relation_endpoint_is_active(
            relation, "source", substances, active_substances,
        ):
            continue
        source_key, source_name = relation_endpoint_display(relation, "source", substances)
        target_key, target_name = relation_endpoint_display(relation, "target", substances)
        warning_key = (source_key, "supports", target_key)
        if warning_key in seen:
            continue
        seen.add(warning_key)
        warnings.append(
            {
                "type": "missing_support_substance",
                "source_substance": source_key,
                "source_name": source_name,
                "target_substance": target_key,
                "target_name": target_name,
                "reason": relation.reason,
                "action": relation.action or "",
            }
        )
    return warnings


def global_relation_matches(
    left_id: str,
    right_id: str,
    substances: dict[str, Substance],
    relation: Relation,
    relation_type: str,
) -> bool:
    if relation.type != relation_type:
        return False
    left = substances.get(left_id)
    right = substances.get(right_id)
    if left is None or right is None:
        return False
    if relation_type in {"balance", "competes"}:
        return (
            substance_matches_relation_endpoint(left_id, left, relation, "source")
            and substance_matches_relation_endpoint(right_id, right, relation, "target")
        ) or (
            substance_matches_relation_endpoint(left_id, left, relation, "target")
            and substance_matches_relation_endpoint(right_id, right, relation, "source")
        )
    return substance_matches_relation_endpoint(
        left_id, left, relation, "source"
    ) and substance_matches_relation_endpoint(right_id, right, relation, "target")


def components_have_global_relation(
    left_id: str,
    right_id: str,
    substances: dict[str, Substance],
    relation_type: str,
    global_relations: list[Relation] | None,
) -> bool:
    for relation in global_relations or []:
        if global_relation_matches(left_id, right_id, substances, relation, relation_type):
            return True
        if global_relation_matches(right_id, left_id, substances, relation, relation_type):
            return True
    return False


def component_sets_have_relation(
    left_components: list[str],
    right_components: list[str],
    substances: dict[str, Substance],
    relation_type: str,
    global_relations: list[Relation] | None = None,
) -> bool:
    for left_id in left_components:
        for right_id in right_components:
            if left_id == right_id:
                continue
            if components_have_global_relation(
                left_id, right_id, substances, relation_type, global_relations,
            ):
                return True
    return False


def collect_intra_product_relation_conflicts(
    *,
    item_id: str,
    product_id: str,
    component_ids: list[str],
    substances: dict[str, Substance],
    relation_type: str,
    global_relations: list[Relation] | None = None,
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    seen_pairs: set[frozenset[str]] = set()
    for index, source_id in enumerate(component_ids):
        for target_id in component_ids[index + 1 :]:
            if source_id == target_id:
                continue
            pair_key = frozenset([source_id, target_id])
            if pair_key in seen_pairs:
                continue
            relation = next(
                (
                    candidate
                    for candidate in global_relations or []
                    if global_relation_matches(
                        source_id, target_id, substances, candidate, relation_type
                    )
                    or global_relation_matches(
                        target_id, source_id, substances, candidate, relation_type
                    )
                ),
                None,
            )
            if relation is None:
                continue
            seen_pairs.add(pair_key)
            conflicts.append(
                {
                    "type": "intra_product_relation_conflict",
                    "item": item_id,
                    "product": product_id,
                    "relation": relation_type,
                    "source_substance": source_id,
                    "target_substance": target_id,
                    "message": (
                        "Component relation conflicts inside one physical product; "
                        "scheduling keeps the product together and emits this warning"
                    ),
                    "action": relation.action or "",
                }
            )
    return conflicts


def format_relation_warning(warning: dict[str, Any]) -> str:
    def endpoint(key: str, name: str) -> str:
        return name if key == name else f"{key} ({name})"

    reason = warning.get("reason")
    suffix = f": {reason}" if reason else ""
    return (
        f"{endpoint(warning['source_substance'], warning['source_name'])} -> "
        f"{endpoint(warning['target_substance'], warning['target_name'])}{suffix}"
    )
