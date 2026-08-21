"""Small read-model query for authored research-state metadata."""

from __future__ import annotations

from collections.abc import Mapping

from planner.query_model.session import SurrealSession, id_str, string_list


def collect_research_state_assertions(
    db: SurrealSession, active_substances: set[str], research_state: str
) -> list[dict[str, object]]:
    """Return matching knowledge/relation assertions touching active substances.

    This is deliberately a categorical filter, not a ranking or confidence
    score.  Active reachability is established from stack-derived substance
    IDs before relation endpoints are considered.
    """
    rows: list[dict[str, object]] = []
    for substance in db.query("SELECT id, name, knowledge_assertions FROM substance"):
        substance_id = id_str(substance.get("id", ""))
        if substance_id not in active_substances:
            continue
        name = substance.get("name", substance_id)
        for assertion in substance.get("knowledge_assertions", []):
            if not isinstance(assertion, Mapping):
                continue
            if assertion.get("research_state", "unassessed") != research_state:
                continue
            rows.append({
                "kind": "knowledge",
                "id": substance_id,
                "name": name,
                "category": assertion.get("knowledge_category", ""),
                "value": assertion.get("knowledge_value", ""),
                "research_state": research_state,
                "sources": string_list(assertion.get("sources")),
            })
    for relation in db.query(
        "SELECT id, type, src_substances, tgt_substances, src_display, tgt_display, reason, "
        "research_state, sources FROM ontology_assertion"
    ):
        if relation.get("research_state", "unassessed") != research_state:
            continue
        endpoints = set(string_list(relation.get("src_substances"))) | set(string_list(relation.get("tgt_substances")))
        if not endpoints & active_substances:
            continue
        rows.append({
            "kind": "relation",
            "id": id_str(relation.get("id", "")),
            "type": relation.get("type", ""),
            "source": relation.get("src_display", ""),
            "target": relation.get("tgt_display", ""),
            "reason": relation.get("reason", ""),
            "research_state": research_state,
            "sources": string_list(relation.get("sources")),
        })
    return sorted(rows, key=lambda row: (str(row["kind"]), str(row["id"]), str(row.get("value", ""))))
