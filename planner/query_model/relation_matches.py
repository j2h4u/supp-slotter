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
        "src_substances, tgt_substances, src_selector, tgt_selector FROM ontology_assertion",
    )
    matches: list[tuple[dict[str, object], list[str]]] = []
    for row in rows:
        labels = _row_match_labels(row, substance_id, substance_name)
        if labels:
            matches.append((row, labels))
    return matches


def _row_match_labels(row: dict[str, object], substance_id: str, substance_name: str = "") -> list[str]:
    """Include selector-declared entity names when no card resolves that endpoint."""
    labels: list[str] = []
    for side, substances_field, selector_field in (
        ("source", "src_substances", "src_selector"),
        ("target", "tgt_substances", "tgt_selector"),
    ):
        substance_ids = cast("list[str]", row.get(substances_field) or [])
        selector = row.get(selector_field)
        selector_name = selector.get("name") if isinstance(selector, dict) else None
        if substance_id in substance_ids or selector_name == substance_name:
            labels.append(f"{side} selector")
    return labels
