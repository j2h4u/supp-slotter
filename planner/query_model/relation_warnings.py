"""Relation warning queries for the planner read model."""

from __future__ import annotations

from collections.abc import Mapping
from typing import NotRequired, TypedDict, cast

from planner.ontology.runtime_program import (
    RuntimeProgram,
    RuntimeRelationPresenceStatusPolicy,
    RuntimeRelationWarningRule,
)
from planner.query_model.session import SurrealSession

_RELATION_WARNING_PROJECTION = "src_key, tgt_key, src_display, tgt_display, reason, action, severity"


class RelationWarningRow(TypedDict):
    type: str
    source_substance: str
    source_name: str
    target_substance: str
    target_name: str
    reason: str
    action: str
    severity: NotRequired[str | int]


class RelationWarningQueryRow(TypedDict):
    src_key: str
    tgt_key: str
    src_display: str
    tgt_display: str
    reason: str
    action: str
    severity: str | int


def collect_relation_warnings(
    db: SurrealSession,
    active_substances: set[str],
    runtime: RuntimeProgram,
) -> list[RelationWarningRow]:
    """Collect every relation warning declared by the ontology runtime policy."""
    pairs = sorted({(row.relation_kind, row.warning_type) for row in runtime.relation_warning_rules})
    warnings: list[RelationWarningRow] = []
    for relation_type, warning_type in pairs:
        warnings.extend(_collect_relation_warning_rules(db, active_substances, runtime, relation_type, warning_type))
    return warnings


def _collect_relation_warning_rules(
    db: SurrealSession,
    active_substances: set[str],
    runtime: RuntimeProgram,
    relation_type: str,
    warning_type: str,
) -> list[RelationWarningRow]:
    rules = [
        row
        for row in runtime.relation_warning_rules
        if row.relation_kind == relation_type and row.warning_type == warning_type
    ]
    if not rules:
        raise ValueError(f"ontology relation_warning_rules does not declare {relation_type!r}/{warning_type!r}")
    return _collect_relation_warnings(
        db,
        relation_type=relation_type,
        warning_type=warning_type,
        queries=[
            _query_for_rule(rule, active_substances, runtime.relation_presence_statuses_by_active_side)
            for rule in rules
        ],
    )


def _query_for_rule(
    rule: RuntimeRelationWarningRule,
    active_substances: set[str],
    relation_presence_by_active_side: Mapping[str, RuntimeRelationPresenceStatusPolicy],
) -> tuple[str, dict[str, object]]:
    projection = _RELATION_WARNING_PROJECTION
    if rule.reverse_output:
        projection = (
            "tgt_key AS src_key, src_key AS tgt_key, "
            "tgt_display AS src_display, src_display AS tgt_display, reason, action, severity"
        )
    presence = _presence_policy_for(rule.active_side, relation_presence_by_active_side)
    source_match = _presence_operator(presence.source_active)
    target_match = _presence_operator(presence.target_active)
    sql = (
        f"SELECT {projection} FROM ontology_assertion "
        f"WHERE {rule.filter_field} = $filter_value "
        f"  AND src_substances {source_match} $active "
        f"  AND tgt_substances {target_match} $active"
    )
    return sql, {"active": list(active_substances), "filter_value": rule.filter_value}


def _presence_policy_for(
    active_side: str,
    relation_presence_by_active_side: Mapping[str, RuntimeRelationPresenceStatusPolicy],
) -> RuntimeRelationPresenceStatusPolicy:
    try:
        return relation_presence_by_active_side[active_side]
    except KeyError as error:
        raise ValueError(f"ontology relation_presence_statuses does not declare active_side {active_side!r}") from error


def _presence_operator(is_active: bool) -> str:
    return "ANYINSIDE" if is_active else "NONEINSIDE"


def _collect_relation_warnings(
    db: SurrealSession,
    *,
    relation_type: str,
    warning_type: str,
    queries: list[tuple[str, dict[str, object]]],
) -> list[RelationWarningRow]:
    rows: list[dict[str, object]] = []
    for sql, params in queries:
        rows.extend(db.query(sql, params))

    seen: set[tuple[str, str, str]] = set()
    warnings: list[RelationWarningRow] = []
    for row in rows:
        typed_row = cast(RelationWarningQueryRow, row)
        key = (typed_row["src_key"], relation_type, typed_row["tgt_key"])
        if key in seen:
            continue
        seen.add(key)
        warnings.append(_warning_from_row(typed_row, warning_type))
    return warnings


def _warning_from_row(row: RelationWarningQueryRow, warning_type: str) -> RelationWarningRow:
    out: RelationWarningRow = {
        "type": warning_type,
        "source_substance": row["src_key"],
        "source_name": row["src_display"],
        "target_substance": row["tgt_key"],
        "target_name": row["tgt_display"],
        "reason": row.get("reason") or "",
        "action": row.get("action") or "",
    }
    severity = row.get("severity")
    if severity is not None:
        out["severity"] = severity
    return out
