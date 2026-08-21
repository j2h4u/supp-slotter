"""Scheduling-constraint query contract tests."""

import pytest
from planner.ontology.errors import OntologyInfrastructureError
from planner.query_model.relation_conflicts import (
    _constraint_matches_pair,
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


def test_intra_product_conflict_query_requires_executable_blocking_plan() -> None:
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


def test_intra_product_conflict_query_interprets_symmetric_pairs_and_deduplicates_reversed_components() -> None:
    row = {
        "id": "constraint_1",
        "operation": "separate_products_same_slot",
        "match_direction": "symmetric",
        "aggregation": "distinct_constraint",
        "source_substances": ["sub_a"],
        "target_substances": ["sub_b"],
        "action": "separate",
    }

    class _Rows(_QueryCapture):
        def query(self, sql: str, params: dict[str, object] | None = None, /) -> list[dict[str, object]]:
            self.sql = sql
            return [row]

    conflicts = collect_intra_product_scheduling_constraint_conflicts(
        _Rows(),
        ontology_bundle().runtime_program,
        item_id="item",
        product_id="product",
        component_ids=["sub_a", "sub_b", "sub_a"],
    )

    assert len(conflicts) == 1
    assert conflicts[0]["source_substance"] == "sub_a"
    assert conflicts[0]["target_substance"] == "sub_b"
    assert conflicts[0]["action"] == "separate"


@pytest.mark.parametrize("field", ("id", "operation", "match_direction", "aggregation", "source_substances"))
def test_constraint_matching_rejects_malformed_execution_rows(field: str) -> None:
    row: dict[str, object] = {
        "id": "constraint_1",
        "operation": "separate_products_same_slot",
        "match_direction": "symmetric",
        "aggregation": "distinct_constraint",
        "source_substances": ["sub_a"],
        "target_substances": ["sub_b"],
    }
    row[field] = "" if field == "id" else ([] if field != "source_substances" else ["sub_a", 3])

    with pytest.raises(OntologyInfrastructureError):
        _constraint_matches_pair(row, "sub_a", "sub_b", ontology_bundle().runtime_program)
