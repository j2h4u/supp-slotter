"""Single-substance relation match queries."""

from __future__ import annotations

from typing import cast

from planner.query_model.session import SurrealSession


def collect_substance_relation_matches(
    db: SurrealSession,
    substance_id: str,
    substance_name: str,
) -> list[tuple[dict[str, object], list[str]]]:
    rows = db.query(
        "SELECT id, type, assertion_kind, semantic_family, src_display, tgt_display, reason, action, "
        "src_substances, tgt_substances FROM ontology_assertion "
        "WHERE src_substances CONTAINS $sid OR tgt_substances CONTAINS $sid",
        {"sid": substance_id, "name": substance_name},
    )
    matches: list[tuple[dict[str, object], list[str]]] = []
    for row in rows:
        labels = _row_match_labels(row, substance_id)
        if labels:
            matches.append((row, labels))
    return matches


def _row_match_labels(row: dict[str, object], substance_id: str) -> list[str]:
    labels: list[str] = []
    for side, substances_field in (("source", "src_substances"), ("target", "tgt_substances")):
        substance_ids = cast("list[str]", row.get(substances_field) or [])
        if substance_id in substance_ids:
            labels.append(f"{side} selector")
    return labels
