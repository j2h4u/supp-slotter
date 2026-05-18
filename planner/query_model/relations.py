"""Relation classification queries for the planner read model."""

from __future__ import annotations

from typing import cast

from planner.query_model.session import SurrealSession

_RELATION_STATUS_PROJECTION = (
    "SELECT type, src_display AS source, tgt_display AS target, reason, "
    "  IF src_substances ANYINSIDE $active AND tgt_substances ANYINSIDE $active "
    "    THEN 'both_active' "
    "  ELSE IF src_substances ANYINSIDE $active "
    "    THEN 'missing_target' "
    "  ELSE IF tgt_substances ANYINSIDE $active "
    "    THEN 'missing_source' "
    "  ELSE 'neither_active' "
    "  END AS status "
    "FROM relation"
)


def classify_relations(
    db: SurrealSession,
    active_substances: set[str],
) -> dict[str, list[dict[str, str]]]:
    by_status: dict[str, list[dict[str, str]]] = {
        "both_active": [],
        "missing_source": [],
        "missing_target": [],
        "neither_active": [],
    }
    rows = db.query(_RELATION_STATUS_PROJECTION, {"active": list(active_substances)})
    for row in rows:
        status = cast(str, row["status"])
        by_status[status].append({
            "type": cast(str, row["type"]),
            "source": cast(str, row["source"]),
            "target": cast(str, row["target"]),
            "reason": cast(str, row.get("reason") or ""),
        })
    return by_status
