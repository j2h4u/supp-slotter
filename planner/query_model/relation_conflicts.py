"""Relation conflict queries used by scheduling."""

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


def collect_intra_product_relation_conflicts(
    db: SurrealSession,
    *,
    item_id: str,
    product_id: str,
    component_ids: list[str],
    relation_type: str,
) -> list[RelationConflictWarningRow]:
    rows = db.query(
        "SELECT src_substances, tgt_substances, action FROM relation "
        "WHERE type = $type "
        "  AND src_substances ANYINSIDE $components "
        "  AND tgt_substances ANYINSIDE $components",
        {"type": relation_type, "components": component_ids},
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
                    "action": action if isinstance(action, str) else "",
                }
            )
    return conflicts


def relation_substance_pairs(
    db: SurrealSession,
    relation_type: str,
) -> set[frozenset[str]]:
    pairs: set[frozenset[str]] = set()
    rows = db.query(
        "SELECT src_substances, tgt_substances FROM relation WHERE type = $t",
        {"t": relation_type},
    )
    for row in rows:
        src_ids = cast("list[str]", row.get("src_substances") or [])
        tgt_ids = cast("list[str]", row.get("tgt_substances") or [])
        for src in src_ids:
            for tgt in tgt_ids:
                if src != tgt:
                    pairs.add(frozenset({src, tgt}))
    return pairs


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
