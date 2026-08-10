"""Runtime tests for ontology-authored scheduling constraints."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest
from planner.contracts import (
    CardLoadError,
    KnowledgeAssertion,
    RelationSelector,
    ScheduleAssertion,
    SchedulingConstraint,
    Substance,
)
from planner.engine._plan_blocking import blocking_constraint_diagnostics, slot_is_blocked
from planner.engine._plan_types import BlockingContext
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.policies import _constraint_selector, load_scheduling_constraints
from planner.scheduling_constraint_execution import compile_scheduling_constraint_execution_plans
from planner.scheduling_constraint_matching import advisory_penalty_for_slot

from tests.helpers import ontology_bundle


def test_generated_constraints_preserve_direct_runtime_fields() -> None:
    constraints = load_scheduling_constraints(ontology_bundle())

    assert len(constraints) == 4
    assert {constraint.operation for constraint in constraints} == {"separate_products_same_slot"}
    assert all(constraint.action for constraint in constraints)
    assert all(constraint.rationale for constraint in constraints)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("action", None),
        ("action", 7),
        ("action", "   "),
        ("rationale", None),
        ("rationale", 7),
        ("rationale", "   "),
    ],
)
def test_constraint_loader_rejects_missing_wrong_or_empty_required_metadata(field: str, value: object) -> None:
    source = ontology_bundle()
    decoded = cast(dict[str, object], _thaw(cast(dict[str, object], source.decoded)))
    vocabulary = cast(dict[str, object], decoded["runtime-vocabulary.yaml"])
    constraints = cast(dict[str, object], vocabulary["scheduling_constraints"])
    first = cast(dict[str, object], next(iter(constraints.values())))
    if value is None:
        first.pop(field, None)
    else:
        first[field] = value

    with pytest.raises(OntologyInfrastructureError, match=rf"invalid {field}") as raised:
        load_scheduling_constraints(replace(source, decoded=decoded))
    assert raised.value.code == MALFORMED
    assert raised.value.path == source.root / "generated" / "runtime-vocabulary.yaml"


def test_generated_constraints_do_not_expose_decorative_assertion_type() -> None:
    constraints = load_scheduling_constraints(ontology_bundle())
    assert all(not hasattr(constraint, "assertion_type") for constraint in constraints)


def _thaw(value: object) -> object:
    if isinstance(value, dict):
        mapping = cast(dict[str, object], value)
        return {key: _thaw(item) for key, item in mapping.items()}
    if isinstance(value, list):
        return [_thaw(item) for item in cast(list[object], value)]
    if isinstance(value, tuple):
        return tuple(_thaw(item) for item in cast(tuple[object, ...], value))
    return value


@pytest.mark.parametrize("selector", [{"entity": {}}, {"entity": {"name": "unstable name"}}])
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
            ontology_bundle=bundle,
        )


def test_execution_selector_uses_authored_category_predicates() -> None:
    bundle = ontology_bundle()
    constraint = replace(
        next(item for item in load_scheduling_constraints(bundle) if item.id == "sc_zinc_copper_separate_slots"),
        source_selector=RelationSelector(category="intake", term="food_preferred"),
        target_selector=RelationSelector(category="kind", term="mineral"),
    )
    source = Substance(
        id="sub_source",
        name="Source",
        schedule_assertions=(ScheduleAssertion("intake", "food_preferred"),),
    )
    target = Substance(
        id="sub_target",
        name="Target",
        knowledge_assertions=(KnowledgeAssertion("kind", "mineral"),),
    )

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


def test_calcium_iron_is_advisory_and_allows_co_location_with_authored_penalty() -> None:
    bundle = ontology_bundle()
    calcium = "sub_vvmld46dbz"
    iron = "sub_ses5czfzi1"
    constraint = next(
        item for item in load_scheduling_constraints(bundle) if item.id == "sc_calcium_iron_separate_slots"
    )
    plan = compile_scheduling_constraint_execution_plans(
        (constraint,),
        {
            calcium: Substance(id=calcium, name="Calcium"),
            iron: Substance(id=iron, name="Iron"),
        },
        bundle.runtime_program,
        ontology_bundle=bundle,
    )[0]

    assert plan.executable
    assert not plan.blocks_slots
    assert plan.scores_advisory
    assert plan.score_delta == -1
    assert advisory_penalty_for_slot(
        ("calcium_item", "iron_item"),
        {"calcium_item": [calcium], "iron_item": [iron]},
        (plan,),
    ) == (-1, (plan.id,))


def test_unresolved_constraint_is_rejected_when_nonempty_resolution_is_authored() -> None:
    bundle = ontology_bundle()
    constraint = SchedulingConstraint(
        id="unresolved",
        source_selector=RelationSelector(entity_id="missing_source"),
        target_selector=RelationSelector(entity_id="missing_target"),
        operation="separate_products_same_slot",
    )
    with pytest.raises(OntologyInfrastructureError, match="unsupported_selector"):
        compile_scheduling_constraint_execution_plans(
            (constraint,),
            {},
            bundle.runtime_program,
            ontology_bundle=bundle,
        )


def test_unknown_or_empty_slot_is_not_blocked_and_has_no_diagnostics() -> None:
    substance = Substance(
        id="sub_m",
        name="Magnesium",
        knowledge_assertions=(KnowledgeAssertion("kind", "mineral"),),
    )
    blocking = BlockingContext({"prd_m": [substance.id]}, {substance.id: substance}, ())

    for slot_items in ({}, {"breakfast": []}):
        typed_slot_items = cast(dict[str, list[str]], slot_items)
        assert slot_is_blocked("prd_m", "breakfast", typed_slot_items, blocking) is False
        assert blocking_constraint_diagnostics("prd_m", "breakfast", typed_slot_items, blocking) == ()
