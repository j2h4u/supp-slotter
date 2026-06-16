"""Relation warning queries for the planner read model."""

from __future__ import annotations

from typing import NotRequired, TypedDict, cast

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


def collect_review_with_relations(
    db: SurrealSession,
    active_substances: set[str],
) -> list[RelationWarningRow]:
    active_param: dict[str, object] = {"active": list(active_substances)}
    return _collect_relation_warnings(
        db,
        relation_type="review_with",
        warning_type="review_with_substance_present",
        queries=[
            (
                f"SELECT {_RELATION_WARNING_PROJECTION} FROM relation "
                "WHERE type = 'review_with' "
                "  AND src_substances ANYINSIDE $active "
                "  AND tgt_substances ANYINSIDE $active",
                active_param,
            )
        ],
    )


def collect_missing_balance_relations(
    db: SurrealSession,
    active_substances: set[str],
) -> list[RelationWarningRow]:
    params: dict[str, object] = {"active": list(active_substances)}
    return _collect_relation_warnings(
        db,
        relation_type="balance",
        warning_type="missing_balance_substance",
        queries=[
            (
                f"SELECT {_RELATION_WARNING_PROJECTION} FROM relation "
                "WHERE type = 'balance' "
                "  AND src_substances ANYINSIDE $active "
                "  AND tgt_substances NONEINSIDE $active",
                params,
            ),
            (
                "SELECT tgt_key AS src_key, src_key AS tgt_key, "
                "       tgt_display AS src_display, src_display AS tgt_display, "
                "       reason, action, severity "
                "FROM relation "
                "WHERE type = 'balance' "
                "  AND tgt_substances ANYINSIDE $active "
                "  AND src_substances NONEINSIDE $active",
                params,
            ),
        ],
    )


def collect_missing_support_relations(
    db: SurrealSession,
    active_substances: set[str],
) -> list[RelationWarningRow]:
    active_param: dict[str, object] = {"active": list(active_substances)}
    return _collect_relation_warnings(
        db,
        relation_type="supports",
        warning_type="missing_support_substance",
        queries=[
            (
                f"SELECT {_RELATION_WARNING_PROJECTION} FROM relation "
                "WHERE type = 'supports' "
                "  AND tgt_substances ANYINSIDE $active "
                "  AND src_substances NONEINSIDE $active",
                active_param,
            )
        ],
    )


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
