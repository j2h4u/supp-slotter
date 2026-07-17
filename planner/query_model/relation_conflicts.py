"""Scheduling-constraint conflict queries used by the planner read model."""

from __future__ import annotations

from typing import TypedDict, cast

from planner.query_model.session import SurrealSession


class RelationConflictWarningRow(TypedDict):
    constraint_id: str
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
        "SELECT id, operation, match_direction, aggregation, source_substances, target_substances, action "
        "FROM scheduling_constraint_execution_plan "
        "WHERE executable = true AND blocks_slots = true "
        "  AND source_substances ANYINSIDE $components "
        "  AND target_substances ANYINSIDE $components",
        {"components": component_ids},
    )

    conflicts: list[RelationConflictWarningRow] = []
    seen_pairs: set[tuple[str, frozenset[str]]] = set()

    for index, source_id in enumerate(component_ids):
        for target_id in component_ids[index + 1 :]:
            if source_id == target_id:
                continue
            pair_key = frozenset([source_id, target_id])
            for matching_row in _matching_rows_for_pair(rows, source_id, target_id):
                constraint_id = matching_row.get("id")
                if not isinstance(constraint_id, str):
                    continue
                identity = (constraint_id, pair_key)
                if identity in seen_pairs:
                    continue
                seen_pairs.add(identity)
                action = matching_row.get("action")
                operation = matching_row.get("operation")
                conflicts.append({
                    "constraint_id": constraint_id,
                    "type": "intra_product_scheduling_constraint_conflict",
                    "item": item_id,
                    "product": product_id,
                    "relation": operation if isinstance(operation, str) else "",
                    "source_substance": source_id,
                    "target_substance": target_id,
                    "message": (
                        "Scheduling constraint applies inside one physical product; "
                        "scheduling keeps the product together and emits this warning"
                    ),
                    "action": action if isinstance(action, str) else "",
                })
    return sorted(conflicts, key=lambda row: (row["constraint_id"], row["source_substance"], row["target_substance"]))


def _matching_rows_for_pair(
    rows: list[dict[str, object]],
    source_id: str,
    target_id: str,
)-> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for row in sorted(rows, key=lambda item: str(item.get("id", ""))):
        src_ids: set[str] = set(cast("list[str]", row.get("source_substances") or []))
        tgt_ids: set[str] = set(cast("list[str]", row.get("target_substances") or []))
        if not src_ids or not tgt_ids:
            continue
        # Keep parity with the planner matcher and fail closed for a malformed
        # execution-plan row that bypassed runtime ontology validation.
        if row.get("aggregation") != "distinct_constraint":
            continue
        direction = row.get("match_direction")
        forward = source_id in src_ids and target_id in tgt_ids
        reverse = target_id in src_ids and source_id in tgt_ids
        if direction == "directed" and forward:
            matches.append(row)
        elif direction == "symmetric" and (forward or reverse):
            matches.append(row)
    return matches
