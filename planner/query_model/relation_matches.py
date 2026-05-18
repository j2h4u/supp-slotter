"""Single-substance relation match queries."""

from __future__ import annotations

from typing import Any

from planner.query_model.session import SurrealSession


def collect_substance_relation_matches(
    db: SurrealSession,
    substance_id: str,
    substance_name: str,
) -> list[tuple[dict[str, Any], list[str]]]:
    rows = db.query(
        "SELECT * FROM relation "
        "WHERE src_substances CONTAINS $sid OR tgt_substances CONTAINS $sid "
        "   OR src_name_raw = $name OR tgt_name_raw = $name",
        {"sid": substance_id, "name": substance_name},
    )
    matches: list[tuple[dict[str, Any], list[str]]] = []
    for row in rows:
        labels = _row_match_labels(row, substance_id, substance_name)
        if labels:
            matches.append((row, labels))
    return matches


def _row_match_labels(
    row: dict[str, Any], substance_id: str, substance_name: str
) -> list[str]:
    labels: list[str] = []
    for side, id_field, name_field in (
        ("source", "src_substance_raw", "src_name_raw"),
        ("target", "tgt_substance_raw", "tgt_name_raw"),
    ):
        exact_id = row.get(id_field)
        expected_name = row.get(name_field)
        if isinstance(exact_id, str) and substance_id == exact_id:
            labels.append(f"{side} exact id")
        elif isinstance(expected_name, str) and substance_name == expected_name:
            labels.append(f"{side} exact name")
    return labels
