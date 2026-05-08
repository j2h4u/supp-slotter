"""Substance-to-substance relations: loading, matching, validation, conflict detection."""

from __future__ import annotations

from planner.io import RELATIONS_PATH, load_yaml, schema_errors
from planner.cards.substance import (
    collect_active_substance_names,
    format_substance_name,
    substance_names,
)


def load_global_relations() -> list[dict]:
    if not RELATIONS_PATH.exists():
        return []
    data = load_yaml(RELATIONS_PATH)
    if not isinstance(data, dict):
        return []
    relations: list[dict] = []
    for relation_type in ("balance", "supports", "competes", "antagonizes"):
        relation_items = data.get(relation_type)
        if not isinstance(relation_items, list):
            continue
        for relation in relation_items:
            if isinstance(relation, dict):
                relations.append({"type": relation_type, **relation})
    return relations

def global_relation_refs(
    substances: dict[str, dict],
    global_relations: list[dict],
) -> set[str]:
    refs = {
        value
        for relation in global_relations
        for key in ("source_substance", "target_substance")
        if isinstance((value := relation.get(key)), str)
    }
    names = {
        value
        for relation in global_relations
        for key in ("source_name", "target_name")
        if isinstance((value := relation.get(key)), str)
    }
    refs.update({
        substance_id
        for substance_id, substance in substances.items()
        if isinstance(substance.get("name"), str) and substance["name"] in names
    })
    return refs

def relation_endpoint_value(relation: dict, side: str) -> str | None:
    for suffix in ("substance", "name"):
        value = relation.get(f"{side}_{suffix}")
        if isinstance(value, str):
            return value
    return None

def substance_matches_relation_endpoint(
    substance_id: str,
    substance: dict,
    relation: dict,
    side: str,
) -> bool:
    exact_id = relation.get(f"{side}_substance")
    if isinstance(exact_id, str):
        return substance_id == exact_id
    expected_name = relation.get(f"{side}_name")
    return isinstance(expected_name, str) and substance.get("name") == expected_name

def relation_endpoint_is_active(
    relation: dict,
    side: str,
    substances: dict[str, dict],
    active_substances: set[str],
) -> bool:
    for substance_id in active_substances:
        substance = substances.get(substance_id)
        if isinstance(substance, dict) and substance_matches_relation_endpoint(
            substance_id,
            substance,
            relation,
            side,
        ):
            return True
    return False

def relation_endpoint_display(
    relation: dict,
    side: str,
    substances: dict[str, dict],
) -> tuple[str, str]:
    exact_id = relation.get(f"{side}_substance")
    if isinstance(exact_id, str):
        return exact_id, format_substance_name(substances.get(exact_id) or {"id": exact_id})
    name = relation.get(f"{side}_name")
    if isinstance(name, str):
        return name, name
    return "<unknown>", "<unknown>"

def relation_endpoint_match_label(
    relation: dict,
    side: str,
    substance_id: str | None,
    substance: dict,
) -> str | None:
    exact_id = relation.get(f"{side}_substance")
    if isinstance(exact_id, str) and substance_id == exact_id:
        return f"{side} exact id"
    expected_name = relation.get(f"{side}_name")
    if isinstance(expected_name, str) and substance.get("name") == expected_name:
        return f"{side} exact name"
    return None

def collect_substance_relation_matches(
    substance: dict,
    global_relations: list[dict],
) -> list[tuple[dict, list[str]]]:
    substance_id = substance.get("id")
    if not isinstance(substance_id, str):
        substance_id = None

    matches: list[tuple[dict, list[str]]] = []
    for relation in global_relations:
        matched_by = [
            label
            for side in ("source", "target")
            if (
                label := relation_endpoint_match_label(
                    relation,
                    side,
                    substance_id,
                    substance,
                )
            )
        ]
        if matched_by:
            matches.append((relation, matched_by))
    return matches

def print_central_relation_matches(
    substance: dict,
    substances: dict[str, dict],
) -> None:
    print("\nCentral relations from data/relations.yaml (read-only)")
    print("Edit these in data/relations.yaml, not in this substance card.")
    substance_id = substance.get("id")
    if isinstance(substance_id, str):
        print(f"Matches this substance by id: {substance_id}")
    name = substance.get("name")
    if isinstance(name, str):
        print(f"Matches this substance by exact name: {name}")

    matches = collect_substance_relation_matches(substance, load_global_relations())
    if not matches:
        print("  none matched; add links in data/relations.yaml if needed.")
        return

    print("Note: balance/competes are symmetric; supports/antagonizes are directional.")
    grouped: dict[str, list[tuple[dict, list[str]]]] = {}
    for relation, matched_by in matches:
        relation_type = str(relation.get("type") or "unknown")
        grouped.setdefault(relation_type, []).append((relation, matched_by))

    for relation_type in ("balance", "competes", "supports", "antagonizes"):
        relation_group = grouped.get(relation_type)
        if not relation_group:
            continue
        print(f"\n{relation_type}")
        for relation, matched_by in relation_group:
            _source_key, source_name = relation_endpoint_display(
                relation,
                "source",
                substances,
            )
            _target_key, target_name = relation_endpoint_display(
                relation,
                "target",
                substances,
            )
            print(f"  {source_name} -> {target_name}")
            print(f"    matched by: {', '.join(matched_by)}")
            reason = relation.get("reason")
            if isinstance(reason, str) and reason:
                print(f"    reason: {reason}")
            action = relation.get("action")
            if isinstance(action, str) and action:
                print(f"    action: {action}")

def check_global_relations(
    relations_data: object,
    substances: dict[str, dict],
) -> list[str]:
    errors: list[str] = []
    errors.extend(schema_errors(relations_data, "relations", RELATIONS_PATH))
    if errors or not isinstance(relations_data, dict):
        return errors

    names = substance_names(substances)
    relation_items = [
        (relation_type, index, relation)
        for relation_type in ("balance", "supports", "competes", "antagonizes")
        for index, relation in enumerate(relations_data.get(relation_type) or [])
    ]
    for relation_type, index, relation in relation_items:
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
        source = relation_endpoint_value(relation, "source")
        target = relation_endpoint_value(relation, "target")
        if source is not None and source == target:
            errors.append(f"{path} references the same source and target")
    return errors

def collect_missing_balance_relations(
    substances: dict[str, dict],
    active_substances: set[str],
    global_relations: list[dict] | None = None,
) -> list[dict]:
    warnings: list[dict] = []
    active_names = collect_active_substance_names(substances, active_substances)
    seen: set[tuple[str, str, str]] = set()
    for relation in global_relations or []:
        if relation.get("type") != "balance":
            continue
        pairs = (("source", "target"), ("target", "source"))
        for active_side, missing_side in pairs:
            if not relation_endpoint_is_active(
                relation,
                active_side,
                substances,
                active_substances,
            ) or relation_endpoint_is_active(
                relation,
                missing_side,
                substances,
                active_substances,
            ):
                continue
            source_key, source_name = relation_endpoint_display(
                relation,
                active_side,
                substances,
            )
            target_key, target_name = relation_endpoint_display(
                relation,
                missing_side,
                substances,
            )
            warning_key = (source_key, "balance", target_key)
            if warning_key in seen:
                continue
            seen.add(warning_key)
            reason = relation.get("reason")
            action = relation.get("action")
            warnings.append(
                {
                    "type": "missing_balance_substance",
                    "source_substance": source_key,
                    "source_name": source_name,
                    "target_substance": target_key,
                    "target_name": target_name,
                    "reason": reason if isinstance(reason, str) else "",
                    "action": action if isinstance(action, str) else "",
                }
            )
    return warnings

def collect_missing_support_relations(
    substances: dict[str, dict],
    active_substances: set[str],
    global_relations: list[dict] | None = None,
) -> list[dict]:
    warnings: list[dict] = []
    active_names = collect_active_substance_names(substances, active_substances)
    seen: set[tuple[str, str, str]] = set()
    for relation in global_relations or []:
        if relation.get("type") != "supports":
            continue
        if not relation_endpoint_is_active(
            relation,
            "target",
            substances,
            active_substances,
        ) or relation_endpoint_is_active(
            relation,
            "source",
            substances,
            active_substances,
        ):
            continue
        source_key, source_name = relation_endpoint_display(
            relation,
            "source",
            substances,
        )
        target_key, target_name = relation_endpoint_display(
            relation,
            "target",
            substances,
        )
        warning_key = (source_key, "supports", target_key)
        if warning_key in seen:
            continue
        seen.add(warning_key)
        reason = relation.get("reason")
        action = relation.get("action")
        warnings.append(
            {
                "type": "missing_support_substance",
                "source_substance": source_key,
                "source_name": source_name,
                "target_substance": target_key,
                "target_name": target_name,
                "reason": reason if isinstance(reason, str) else "",
                "action": action if isinstance(action, str) else "",
            }
        )
    return warnings

def global_relation_matches(
    left_id: str,
    right_id: str,
    substances: dict[str, dict],
    relation: dict,
    relation_type: str,
) -> bool:
    if relation.get("type") != relation_type:
        return False
    left = substances.get(left_id)
    right = substances.get(right_id)
    if not isinstance(left, dict) or not isinstance(right, dict):
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
        left_id,
        left,
        relation,
        "source",
    ) and substance_matches_relation_endpoint(right_id, right, relation, "target")

def components_have_global_relation(
    left_id: str,
    right_id: str,
    substances: dict[str, dict],
    relation_type: str,
    global_relations: list[dict] | None,
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
    substances: dict[str, dict],
    relation_type: str,
    global_relations: list[dict] | None = None,
) -> bool:
    for left_id in left_components:
        for right_id in right_components:
            if left_id == right_id:
                continue
            if components_have_global_relation(
                left_id,
                right_id,
                substances,
                relation_type,
                global_relations,
            ):
                return True
    return False

def collect_intra_product_relation_conflicts(
    *,
    item_id: str,
    product_id: str,
    component_ids: list[str],
    substances: dict[str, dict],
    relation_type: str,
    global_relations: list[dict] | None = None,
) -> list[dict]:
    conflicts: list[dict] = []
    component_set = set(component_ids)
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
                    if components_have_global_relation(
                        source_id,
                        target_id,
                        substances,
                        relation_type,
                        [candidate],
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
                    "action": relation.get("action", ""),
                }
            )
    return conflicts

def format_relation_warning(warning: dict) -> str:
    def endpoint(key: str, name: str) -> str:
        return name if key == name else f"{key} ({name})"

    reason = warning.get("reason")
    suffix = f": {reason}" if reason else ""
    return (
        f"{endpoint(warning['source_substance'], warning['source_name'])} -> "
        f"{endpoint(warning['target_substance'], warning['target_name'])}{suffix}"
    )

