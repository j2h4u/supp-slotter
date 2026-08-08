"""Runtime tests for ontology-authored scheduling constraints."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest
from planner.contracts import CardLoadError, RelationSelector, SchedulingConstraint, Substance
from planner.engine._plan_blocking import blocking_constraint_diagnostics, slot_is_blocked
from planner.engine._plan_types import BlockingContext
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.policies import _constraint_selector, load_scheduling_constraints
from planner.ontology.substance_fields import validate_substance_schema_conformance
from planner.scheduling_constraint_execution import compile_scheduling_constraint_execution_plans

from tests.helpers import ontology_bundle


def test_generated_constraints_preserve_direct_runtime_fields() -> None:
    constraints = load_scheduling_constraints(ontology_bundle())

    assert len(constraints) == 4
    assert {constraint.operation for constraint in constraints} == {"separate_products_same_slot"}
    assert all(constraint.action for constraint in constraints)
    assert all(constraint.rationale for constraint in constraints)


@pytest.mark.parametrize("selector", [{"entity": {}}])
def test_malformed_selector_fails_fast(selector: object) -> None:
    with pytest.raises(CardLoadError):
        _constraint_selector(selector)


def test_execution_compiler_rejects_unsupported_operation_before_projection() -> None:
    bundle = ontology_bundle()
    constraint = replace(load_scheduling_constraints(bundle)[0], operation="unsupported_operation")

    with pytest.raises(OntologyInfrastructureError, match="unsupported operation"):
        compile_scheduling_constraint_execution_plans(
            (constraint,),
            {},
            bundle.runtime_program,
            allow_empty_selector_resolution=True,
            ontology_bundle=bundle,
        )


def test_execution_selector_uses_authored_category_predicates() -> None:
    bundle = ontology_bundle()
    constraint = replace(
        load_scheduling_constraints(bundle)[0],
        source_selector=RelationSelector(category="schedule_rule", term="food_preferred"),
        target_selector=RelationSelector(category="kind", term="mineral"),
    )
    source = Substance(id="sub_source", name="Source", intake=("food_preferred",))
    target = Substance(id="sub_target", name="Target", kind=("mineral",))

    plan = compile_scheduling_constraint_execution_plans(
        (constraint,),
        {source.id: source, target.id: target},
        bundle.runtime_program,
        ontology_bundle=bundle,
    )[0]

    assert plan.source_substance_ids == (source.id,)
    assert plan.target_substance_ids == (target.id,)
    assert plan.selector_resolution_outcome == "resolved"
    assert plan.executable and plan.blocks_slots


def test_unresolved_constraint_is_advisory_and_does_not_block() -> None:
    bundle = ontology_bundle()
    constraint = SchedulingConstraint(
        id="unresolved",
        source_selector=RelationSelector(entity_id="missing_source"),
        target_selector=RelationSelector(entity_id="missing_target"),
        operation="separate_products_same_slot",
    )
    plan = compile_scheduling_constraint_execution_plans(
        (constraint,),
        {},
        bundle.runtime_program,
        allow_empty_selector_resolution=True,
        ontology_bundle=bundle,
    )[0]

    assert plan.selector_resolution_outcome == "empty"
    assert not plan.executable and not plan.blocks_slots


def test_unknown_or_empty_slot_is_not_blocked_and_has_no_diagnostics() -> None:
    bundle = ontology_bundle()
    constraints = load_scheduling_constraints(bundle)
    substance = Substance(id="sub_m", name="Magnesium", kind=("mineral",))
    plans = compile_scheduling_constraint_execution_plans(
        constraints,
        {substance.id: substance},
        bundle.runtime_program,
        allow_empty_selector_resolution=True,
        ontology_bundle=bundle,
    )
    blocking = BlockingContext({"prd_m": [substance.id]}, {substance.id: substance}, plans)

    for slot_items in ({}, {"breakfast": []}):
        assert slot_is_blocked("prd_m", "breakfast", slot_items, blocking) is False
        assert blocking_constraint_diagnostics("prd_m", "breakfast", slot_items, blocking) == ()


def test_substance_schema_conformance_rejects_unmapped_authored_field() -> None:
    bundle = ontology_bundle()
    vocabulary = dict(bundle.runtime_vocabulary)
    categories = dict(cast(dict[str, object], vocabulary["categories"]))
    categories["future_category"] = {"allowed_predicates": ["knowledge.future_field"]}

    with pytest.raises(OntologyInfrastructureError, match="future_field"):
        validate_substance_schema_conformance(_bundle_with_vocabulary(bundle, {**vocabulary, "categories": categories}))


def _bundle_with_vocabulary(bundle: OntologyBundle, vocabulary: dict[str, object]) -> OntologyBundle:
    return replace(bundle, decoded={**bundle.decoded, "runtime-vocabulary.yaml": vocabulary})
