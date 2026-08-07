"""Scheduling-constraint query governance tests."""

from typing import cast

import pytest
from planner.ontology.errors import OntologyInfrastructureError
from planner.query_model.relation_conflicts import (
    _matching_rows_for_pair,
    collect_intra_product_scheduling_constraint_conflicts,
)

from tests.helpers import ontology_bundle


class _QueryCapture:
    sql: str = ""

    def use(self, namespace: str, _database: str, /) -> object:
        return None

    def create(self, _table: str, data: dict[str, object], /) -> object:
        return data

    def query(self, sql: str, params: dict[str, object] | None = None, /) -> list[dict[str, object]]:
        self.sql = sql
        return []


def test_intra_product_conflict_query_requires_approved_block_with_evidence() -> None:
    db = _QueryCapture()

    assert (
        collect_intra_product_scheduling_constraint_conflicts(
            db,
            ontology_bundle().runtime_program,
            item_id="item",
            product_id="product",
            component_ids=["sub_a", "sub_b"],
        )
        == []
    )
    assert "FROM scheduling_constraint_execution_plan" in db.sql
    assert "executable = true" in db.sql
    assert "blocks_slots = true" in db.sql


def test_find_matching_row_skips_empty_rows_and_matches_forward_pair() -> None:
    matching = {
        "id": "sc",
        "source_substances": ["a"],
        "target_substances": ["b"],
        "aggregation": "distinct_constraint",
        "match_direction": "symmetric",
        "action": "separate",
    }
    assert _matching_rows_for_pair([{}, {"source_substances": ["a"], "target_substances": []}, matching], "a", "b") == [
        matching
    ]


def test_find_matching_row_matches_reverse_orientation_and_limits_to_product() -> None:
    matching = {
        "id": "sc",
        "source_substances": ["outside", "b"],
        "target_substances": ["a"],
        "aggregation": "distinct_constraint",
        "match_direction": "symmetric",
    }
    assert _matching_rows_for_pair(cast(list[dict[str, object]], [matching]), "a", "b") == [matching]


def test_find_matching_row_returns_none_for_non_matching_or_unknown_pairs() -> None:
    rows: list[dict[str, object]] = [
        {
            "source_substances": ["a"],
            "target_substances": ["c"],
            "aggregation": "distinct_constraint",
            "match_direction": "symmetric",
        },
        {
            "source_substances": ["outside"],
            "target_substances": ["b"],
            "aggregation": "distinct_constraint",
            "match_direction": "symmetric",
        },
    ]
    assert _matching_rows_for_pair(rows, "a", "b") == []


def test_find_matching_row_fails_closed_for_unsupported_execution_shape() -> None:
    base = {
        "id": "sc",
        "source_substances": ["a"],
        "target_substances": ["b"],
        "aggregation": "distinct_constraint",
        "match_direction": "symmetric",
    }
    with pytest.raises(OntologyInfrastructureError, match="unsupported aggregation"):
        _matching_rows_for_pair([{**base, "aggregation": "unknown"}], "a", "b")
    with pytest.raises(OntologyInfrastructureError, match="unsupported match direction"):
        _matching_rows_for_pair([{**base, "match_direction": "unknown"}], "a", "b")
