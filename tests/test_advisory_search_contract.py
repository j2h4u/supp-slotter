"""Focused tests for advisory scheduling penalties."""

from dataclasses import replace

import pytest
from planner.contracts import RelationSelector
from planner.ontology.errors import OntologyInfrastructureError
from planner.scheduling_constraint_execution import (
    SchedulingConstraintExecutionPlan,
    interpret_constraint_component_pair,
)
from planner.scheduling_constraint_matching import advisory_penalty_for_candidate

from tests.helpers import ontology_bundle


def _rule(rule_id: str, source: str, target: str) -> SchedulingConstraintExecutionPlan:
    policy = ontology_bundle().runtime_program.constraint_execution_policy_for("separate_products_same_slot")
    assert policy is not None
    return SchedulingConstraintExecutionPlan(
        id=rule_id,
        source_substance_ids=(source,),
        target_substance_ids=(target,),
        operation=policy.operation,
        effect_role="advisory",
        executable=True,
        blocks_slots=False,
        scores_advisory=True,
        score_delta=-1,
        match_direction=policy.match_direction,
        aggregation=policy.aggregation,
        selector_resolution="require_nonempty",
        selector_resolution_outcome="resolved",
        source_selector=RelationSelector(entity_id=source),
        target_selector=RelationSelector(entity_id=target),
    )


def test_empty_constraint_projection_has_no_advisory_penalty() -> None:
    active = {"item_a": ["sub_a"], "item_b": ["sub_b"]}
    assert advisory_penalty_for_candidate("item_a", ["item_b"], active, (), ontology_bundle().runtime_program) == (
        0,
        (),
    )


def test_malformed_execution_plan_aggregation_fails_closed() -> None:
    rule = _rule("rule_bad", "sub_a", "sub_b")
    malformed = replace(rule, aggregation="unsupported_aggregation")

    with pytest.raises(OntologyInfrastructureError, match="unsupported aggregation"):
        interpret_constraint_component_pair(
            malformed,
            ("sub_a",),
            ("sub_b",),
            ontology_bundle().runtime_program,
        )


def test_execution_plan_uses_compiled_aggregation_policy() -> None:
    bundle = ontology_bundle()
    policy = bundle.runtime_program.constraint_execution_policy_for("separate_products_same_slot")
    assert policy is not None
    runtime_program = replace(
        bundle.runtime_program,
        constraint_execution_policies=(replace(policy, aggregation="compiled_aggregation"),),
    )
    rule = replace(_rule("rule_compiled", "sub_a", "sub_b"), aggregation="compiled_aggregation")

    assert interpret_constraint_component_pair(rule, ("sub_a",), ("sub_b",), runtime_program)
