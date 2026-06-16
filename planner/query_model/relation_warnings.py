"""Relation warning queries for the planner read model."""

from __future__ import annotations

from typing import Any

from planner.query_model.session import SurrealSession

_RELATION_WARNING_PROJECTION = "src_key, tgt_key, src_display, tgt_display, reason, action, severity"


def collect_review_with_relations(
    db: SurrealSession,
    active_substances: set[str],
) -> list[dict[str, Any]]:
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
                {"active": list(active_substances)},
            )
        ],
    )


def collect_missing_balance_relations(
    db: SurrealSession,
    active_substances: set[str],
) -> list[dict[str, Any]]:
    params = {"active": list(active_substances)}
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
) -> list[dict[str, Any]]:
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
                {"active": list(active_substances)},
            )
        ],
    )


def _collect_relation_warnings(
    db: SurrealSession,
    *,
    relation_type: str,
    warning_type: str,
    queries: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sql, params in queries:
        rows.extend(db.query(sql, params))

    seen: set[tuple[str, str, str]] = set()
    warnings: list[dict[str, Any]] = []
    for row in rows:
        key = (row["src_key"], relation_type, row["tgt_key"])
        if key in seen:
            continue
        seen.add(key)
        warnings.append(_warning_from_row(row, warning_type))
    return warnings


def _warning_from_row(row: dict[str, Any], warning_type: str) -> dict[str, Any]:
    out: dict[str, Any] = {
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
