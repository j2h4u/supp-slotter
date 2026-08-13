"""Scheduling-constraint conflict queries used by the planner read model."""

from __future__ import annotations

from typing import TypedDict, cast

from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.glue_capabilities import WARNING_EMITTER_INTRA_PRODUCT_CONSTRAINT_CONFLICT
from planner.ontology.runtime_program import RuntimeProgram
from planner.ontology.warning_policy import warning_policy_for_emitter
from planner.query_model.session import SurrealSession, id_str
from planner.scheduling_constraint_execution import interpret_execution_component_pair


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
    runtime_program: RuntimeProgram,
    *,
    item_id: str,
    product_id: str,
    component_ids: list[str],
) -> list[RelationConflictWarningRow]:
    warning_policy = warning_policy_for_emitter(runtime_program, WARNING_EMITTER_INTRA_PRODUCT_CONSTRAINT_CONFLICT)
    warning_type = warning_policy.warning_type
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
            for matching_row in _matching_rows_for_pair(rows, source_id, target_id, runtime_program):
                raw_constraint_id = matching_row.get("id")
                constraint_id = id_str(raw_constraint_id) if raw_constraint_id is not None else ""
                if not constraint_id.strip():
                    raise OntologyInfrastructureError(
                        f"scheduling constraint execution row has invalid id: {constraint_id!r}",
                        code=MALFORMED,
                    )
                identity = (constraint_id, pair_key)
                if identity in seen_pairs:
                    continue
                seen_pairs.add(identity)
                action = matching_row.get("action")
                operation = matching_row.get("operation")
                if not isinstance(operation, str):
                    raise OntologyInfrastructureError(
                        f"scheduling constraint {constraint_id}: execution row has malformed operation",
                        code=MALFORMED,
                    )
                if action is not None and not isinstance(action, str):
                    raise OntologyInfrastructureError(
                        f"scheduling constraint {constraint_id}: execution row has malformed action",
                        code=MALFORMED,
                    )
                conflicts.append({
                    "constraint_id": constraint_id,
                    "type": warning_type,
                    "item": item_id,
                    "product": product_id,
                    "relation": "",
                    "source_substance": source_id,
                    "target_substance": target_id,
                    "message": warning_policy.default_message,
                    "action": action or "",
                })
    return sorted(conflicts, key=lambda row: (row["constraint_id"], row["source_substance"], row["target_substance"]))


def _matching_rows_for_pair(
    rows: list[dict[str, object]],
    source_id: str,
    target_id: str,
    runtime_program: RuntimeProgram,
) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for row in sorted(rows, key=lambda item: str(item.get("id", ""))):
        raw_source_ids = row.get("source_substances")
        raw_target_ids = row.get("target_substances")
        if raw_source_ids == [] or raw_target_ids == []:
            continue
        if _constraint_matches_pair(row, source_id, target_id, runtime_program):
            matches.append(row)
    return matches


def _constraint_matches_pair(
    row: dict[str, object],
    source_id: str,
    target_id: str,
    runtime_program: RuntimeProgram,
) -> bool:
    """Delegate execution-grammar interpretation to the scheduler's one seam."""
    raw_constraint_id = row.get("id")
    constraint_id = id_str(raw_constraint_id) if raw_constraint_id is not None else ""
    operation = row.get("operation")
    direction = row.get("match_direction")
    aggregation = row.get("aggregation")
    source_ids = row.get("source_substances")
    target_ids = row.get("target_substances")
    if not constraint_id.strip():
        raise OntologyInfrastructureError(
            f"scheduling constraint execution row has invalid id: {constraint_id!r}",
            code=MALFORMED,
        )
    if not isinstance(operation, str) or not operation.strip():
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: execution row has invalid operation: {operation!r}",
            code=MALFORMED,
        )
    if not isinstance(direction, str) or not direction.strip():
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: execution row has invalid match_direction: {direction!r}",
            code=MALFORMED,
        )
    if not isinstance(aggregation, str) or not aggregation.strip():
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: execution row has invalid aggregation: {aggregation!r}",
            code=MALFORMED,
        )
    source_ids_list = cast(list[object], source_ids) if isinstance(source_ids, list) else None
    target_ids_list = cast(list[object], target_ids) if isinstance(target_ids, list) else None
    if source_ids_list is None or not all(isinstance(item, str) for item in source_ids_list):
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: execution row has malformed source_substances",
            code=MALFORMED,
        )
    if target_ids_list is None or not all(isinstance(item, str) for item in target_ids_list):
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: execution row has malformed target_substances",
            code=MALFORMED,
        )
    return interpret_execution_component_pair(
        {
            "id": constraint_id,
            "operation": operation,
            "match_direction": direction,
            "aggregation": aggregation,
            "source_substances": cast(list[str], source_ids_list),
            "target_substances": cast(list[str], target_ids_list),
        },
        (source_id,),
        (target_id,),
        runtime_program,
    )
