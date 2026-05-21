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

_REVIEW_STATUSES = (
    "actionable_now",
    "active_pair_present",
    "latent_one_side_present",
    "inactive",
)


def classify_relations(
    db: SurrealSession,
    active_substances: set[str],
) -> dict[str, list[dict[str, str]]]:
    by_status: dict[str, list[dict[str, str]]] = {status: [] for status in _REVIEW_STATUSES}
    rows = db.query(_RELATION_STATUS_PROJECTION, {"active": list(active_substances)})
    for row in rows:
        relation_type = cast(str, row["type"])
        presence_status = cast(str, row["status"])
        status = _semantic_review_status(relation_type, presence_status)
        by_status[status].append({
            "type": relation_type,
            "source": cast(str, row["source"]),
            "target": cast(str, row["target"]),
            "reason": cast(str, row.get("reason") or ""),
            "presence": _presence_description(presence_status),
        })
    return by_status


def _semantic_review_status(relation_type: str, presence_status: str) -> str:
    if presence_status == "neither_active":
        return "inactive"
    if presence_status == "both_active":
        if relation_type in {"competes", "review_with"}:
            return "actionable_now"
        return "active_pair_present"
    if relation_type == "balance":
        return "actionable_now"
    if relation_type == "supports" and presence_status == "missing_source":
        return "actionable_now"
    return "latent_one_side_present"


def _presence_description(presence_status: str) -> str:
    if presence_status == "both_active":
        return "both endpoints active"
    if presence_status == "missing_source":
        return "target active, source absent"
    if presence_status == "missing_target":
        return "source active, target absent"
    return "both endpoints absent"
