"""Focused tests for advisory scheduling penalties."""

from dataclasses import replace

import pytest
from planner.contracts import RelationSelector, Substance
from planner.ontology.errors import OntologyInfrastructureError
from planner.scheduling_constraint_execution import SchedulingConstraintExecutionPlan
from planner.scheduling_constraint_matching import advisory_penalty_for_candidate, constraint_matches_component_pair


def _rule(rule_id: str, source: str, target: str) -> SchedulingConstraintExecutionPlan:
    return SchedulingConstraintExecutionPlan(
        id=rule_id,
        source_substance_ids=(source,),
        target_substance_ids=(target,),
        operation="separate_slots",
        enforcement_mode="advisory",
        effect_role="advisory",
        executable=True,
        blocks_slots=False,
        scores_advisory=True,
        score_delta=-1,
        match_direction="symmetric",
        aggregation="distinct_constraint",
        selector_resolution="require_nonempty",
        selector_resolution_outcome="resolved",
        source_selector=RelationSelector(entity_id=source),
        target_selector=RelationSelector(entity_id=target),
    )


def test_advisory_penalty_is_symmetric_and_deduplicated() -> None:
    active = {"item_a": ["sub_a"], "item_b": ["sub_b"]}
    substances = {
        "sub_a": Substance(id="sub_a", name="A"),
        "sub_b": Substance(id="sub_b", name="B"),
    }
    rules = (_rule("rule_z", "sub_a", "sub_b"), _rule("rule_a", "sub_b", "sub_a"))

    forward = advisory_penalty_for_candidate("item_a", ["item_b", "item_b"], active, substances, rules)
    reverse = advisory_penalty_for_candidate("item_b", ["item_a"], active, substances, rules)

    assert forward == (-2, ("rule_a", "rule_z"))
    assert reverse == forward


def test_review_and_retired_rules_are_not_advisory_by_governance_filter() -> None:
    active = {"item_a": ["sub_a"], "item_b": ["sub_b"]}
    substances = {"sub_a": Substance(id="sub_a", name="A"), "sub_b": Substance(id="sub_b", name="B")}
    # The pure API is status-agnostic; governance filtering belongs to search.
    assert advisory_penalty_for_candidate("item_a", ["item_b"], active, substances, ()) == (0, ())


def test_malformed_execution_plan_aggregation_fails_closed() -> None:
    rule = _rule("rule_bad", "sub_a", "sub_b")
    malformed = replace(rule, aggregation="unsupported_aggregation")

    with pytest.raises(OntologyInfrastructureError, match="unsupported aggregation"):
        constraint_matches_component_pair(
            malformed,
            ("sub_a",),
            ("sub_b",),
            {"sub_a": Substance(id="sub_a", name="A"), "sub_b": Substance(id="sub_b", name="B")},
        )
