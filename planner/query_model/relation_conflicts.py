"""Scheduling-constraint conflict queries used by the planner read model."""

from __future__ import annotations

from typing import TypedDict, cast

from planner.query_model.session import SurrealSession


class RelationConflictWarningRow(TypedDict):
    type: str
    item: str
    product: str
    relation: str
    source_substance: str
    target_substance: str
    message: str
    action: str


def collect_intra_product_scheduling_constraint_conflicts(
    db: SurrealSession,
    *,
    item_id: str,
    product_id: str,
    component_ids: list[str],
) -> list[RelationConflictWarningRow]:
    rows = db.query(
        "SELECT src_substances, tgt_substances, action FROM scheduling_constraint "
        "WHERE effect = 'separate_slots' AND enforcement = 'block' "
        "  AND status = 'approved' AND array::len(evidence) > 0 "
        "  AND src_substances ANYINSIDE $components "
        "  AND tgt_substances ANYINSIDE $components",
        {"components": component_ids},
    )

    component_set = set(component_ids)
    conflicts: list[RelationConflictWarningRow] = []
    seen_pairs: set[frozenset[str]] = set()

    for index, source_id in enumerate(component_ids):
        for target_id in component_ids[index + 1 :]:
            if source_id == target_id:
                continue
            pair_key = frozenset([source_id, target_id])
            if pair_key in seen_pairs:
                continue
            matching_row = _find_matching_row_for_pair(rows, source_id, target_id, component_set)
            if matching_row is None:
                continue
            action = matching_row.get("action")
            seen_pairs.add(pair_key)
            conflicts.append({
                "type": "intra_product_scheduling_constraint_conflict",
                "item": item_id,
                "product": product_id,
                "relation": "separate_slots",
                "source_substance": source_id,
                "target_substance": target_id,
                "message": (
                    "Scheduling constraint applies inside one physical product; "
                    "scheduling keeps the product together and emits this warning"
                ),
                "action": action if isinstance(action, str) else "",
            })
    return conflicts


def _find_matching_row_for_pair(
    rows: list[dict[str, object]],
    source_id: str,
    target_id: str,
    component_set: set[str],
) -> dict[str, object] | None:
    for row in rows:
        src_ids: set[str] = set(cast("list[str]", row.get("src_substances") or []))
        tgt_ids: set[str] = set(cast("list[str]", row.get("tgt_substances") or []))
        if not src_ids or not tgt_ids:
            continue
        src_in_product = src_ids & component_set
        tgt_in_product = tgt_ids & component_set
        if (source_id in src_in_product and target_id in tgt_in_product) or (
            target_id in src_in_product and source_id in tgt_in_product
        ):
            return row
    return None
