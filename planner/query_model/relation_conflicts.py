"""Scheduling-constraint conflict queries used by the planner read model."""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class _ConflictContext:
    warning_type: str
    item_id: str
    product_id: str
    message: str


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
    context = _ConflictContext(warning_type, item_id, product_id, warning_policy.default_message)
    for source_id, target_id in _component_pairs(component_ids):
        pair_key = frozenset((source_id, target_id))
        for matching_row in _matching_rows_for_pair(rows, source_id, target_id, runtime_program):
            conflict = _conflict_warning(
                matching_row,
                context=context,
                source_id=source_id,
                target_id=target_id,
            )
            identity = (conflict["constraint_id"], pair_key)
            if identity not in seen_pairs:
                seen_pairs.add(identity)
                conflicts.append(conflict)
    return sorted(conflicts, key=lambda row: (row["constraint_id"], row["source_substance"], row["target_substance"]))


def _component_pairs(component_ids: list[str]) -> list[tuple[str, str]]:
    return [
        (source_id, target_id)
        for index, source_id in enumerate(component_ids)
        for target_id in component_ids[index + 1 :]
        if source_id != target_id
    ]


def _conflict_warning(
    row: dict[str, object],
    *,
    context: _ConflictContext,
    source_id: str,
    target_id: str,
) -> RelationConflictWarningRow:
    raw_constraint_id = row.get("id")
    constraint_id = id_str(raw_constraint_id) if raw_constraint_id is not None else ""
    if not constraint_id.strip():
        raise OntologyInfrastructureError(
            f"scheduling constraint execution row has invalid id: {constraint_id!r}", code=MALFORMED
        )
    if not isinstance(row.get("operation"), str):
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: execution row has malformed operation", code=MALFORMED
        )
    action = row.get("action")
    if action is not None and not isinstance(action, str):
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: execution row has malformed action", code=MALFORMED
        )
    return {
        "constraint_id": constraint_id,
        "type": context.warning_type,
        "item": context.item_id,
        "product": context.product_id,
        "relation": "",
        "source_substance": source_id,
        "target_substance": target_id,
        "message": context.message,
        "action": action or "",
    }


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
    execution = _validated_execution_row(row)
    return interpret_execution_component_pair(
        execution,
        (source_id,),
        (target_id,),
        runtime_program,
    )


def _validated_execution_row(row: dict[str, object]) -> dict[str, object]:
    raw_constraint_id = row.get("id")
    constraint_id = id_str(raw_constraint_id) if raw_constraint_id is not None else ""
    if not constraint_id.strip():
        raise OntologyInfrastructureError(
            f"scheduling constraint execution row has invalid id: {constraint_id!r}", code=MALFORMED
        )
    operation = _required_execution_text(row, "operation", constraint_id)
    direction = _required_execution_text(row, "match_direction", constraint_id)
    aggregation = _required_execution_text(row, "aggregation", constraint_id)
    source_ids = _execution_substances(row.get("source_substances"), constraint_id, "source_substances")
    target_ids = _execution_substances(row.get("target_substances"), constraint_id, "target_substances")
    return {
        "id": constraint_id,
        "operation": operation,
        "match_direction": direction,
        "aggregation": aggregation,
        "source_substances": source_ids,
        "target_substances": target_ids,
    }


def _required_execution_text(row: dict[str, object], field: str, constraint_id: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: invalid {field}: {value!r}", code=MALFORMED
        )
    return value


def _execution_substances(value: object, constraint_id: str, field: str) -> list[str]:
    values = cast(list[object], value) if isinstance(value, list) else None
    if values is None or not all(isinstance(item, str) for item in values):
        raise OntologyInfrastructureError(f"scheduling constraint {constraint_id}: malformed {field}", code=MALFORMED)
    return cast(list[str], values)
