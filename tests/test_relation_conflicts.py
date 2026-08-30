"""Scheduling-constraint query contract tests."""

import pytest
from planner.ontology.errors import OntologyInfrastructureError
from planner.query_model.relation_conflicts import (
    _constraint_matches_pair,
    collect_intra_product_scheduling_constraint_conflicts,
)
from planner.scheduling_constraint_execution import SchedulingConstraintExecutionPlan

from tests.helpers import ontology_bundle


def test_intra_product_conflict_requires_executable_blocking_plan() -> None:
    assert (
        collect_intra_product_scheduling_constraint_conflicts(
            (),
            ontology_bundle().runtime_program,
            item_id="item",
            product_id="product",
            component_ids=["sub_a", "sub_b"],
        )
        == []
    )


def test_intra_product_conflict_query_interprets_symmetric_pairs_and_deduplicates_reversed_components() -> None:
    plan = SchedulingConstraintExecutionPlan(
        id="constraint_1",
        operation="separate_products_same_slot",
        match_direction="symmetric",
        aggregation="distinct_constraint",
        source_substance_ids=("sub_a",),
        target_substance_ids=("sub_b",),
        executable=True,
        blocks_slots=True,
        scores_advisory=False,
        score_delta=0,
        selector_resolution="allow_empty",
        selector_resolution_outcome="resolved",
        action="separate",
    )
    conflicts = collect_intra_product_scheduling_constraint_conflicts(
        (plan,),
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
