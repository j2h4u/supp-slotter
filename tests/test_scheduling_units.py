from dataclasses import replace
from typing import cast

import pytest
from planner.contracts import (
    Concern,
    Product,
    ProductComponent,
    ScheduleAssertion,
    SchedulingAssessment,
    SchedulingPolicy,
    Slot,
    SlotObservation,
    Substance,
    TraitEffect,
    TraitEffectMatch,
)
from planner.engine._plan_output import _neutral_components
from planner.engine._scheduling import (
    compute_slot_score,
    project_schedule_assignments,
    render_slot_effects,
    slot_matches,
)
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.presentation import load_review_presentation

from tests.helpers import ontology_bundle


def _slot(*, food: bool = True, near: str = "breakfast") -> Slot:
    return Slot(
        "slot",
        "Slot",
        1,
        (SlotObservation("near", near), SlotObservation("food", food)),
        "daily",
        "Daily",
        "daily",
    )


def test_schedule_assignment_scores_are_direct_ontology_effects() -> None:
    bundle = ontology_bundle()
    policy = SchedulingPolicy(
        id="intake:food_preferred",
        namespace="intake",
        short_name="food_preferred",
        label="Food preferred",
        description="",
        applies_when="fixture",
        effects=(TraitEffect(TraitEffectMatch((("food", True),)), level="prefer"),),
    )
    substance = Substance("sub_a", "A", schedule_assertions=(ScheduleAssertion("intake", "food_preferred"),))
    product = Product("prd_a", "A", (ProductComponent("sub_a"),))
    projection = project_schedule_assignments(
        bundle.runtime_program, product, {"sub_a": substance}, {policy.id: policy}
    )
    slot = _slot(food=True)
    assert slot_matches(bundle.runtime_program, slot, TraitEffectMatch((("food", True),)))
    assert not slot_matches(bundle.runtime_program, slot, TraitEffectMatch((("food", False),)))
    trace = compute_slot_score(bundle.runtime_program, projection, slot, {policy.id: policy})
    assert trace.blocked is False
    assert trace.score > 0
    assert trace.effects[0].policy_id == policy.id


def test_unique_component_votes_accumulate_and_preserve_opposing_strengths() -> None:
    bundle = ontology_bundle()
    food_policy = SchedulingPolicy(
        id="intake:food_preferred",
        namespace="intake",
        short_name="food_preferred",
        label="Food preferred",
        description="",
        applies_when="fixture",
        effects=(TraitEffect(TraitEffectMatch((("food", True),)), level="prefer"),),
    )
    empty_policy = SchedulingPolicy(
        id="intake:empty_preferred",
        namespace="intake",
        short_name="empty_preferred",
        label="Empty preferred",
        description="",
        applies_when="fixture",
        effects=(
            TraitEffect(TraitEffectMatch((("food", False),)), level="prefer"),
            TraitEffect(TraitEffectMatch((("food", True),)), level="avoid"),
        ),
    )
    substances = {
        **{
            f"sub_{index:010d}": Substance(
                f"sub_{index:010d}",
                f"Food {index}",
                schedule_assertions=(ScheduleAssertion("intake", "food_preferred"),),
            )
            for index in range(5)
        },
        **{
            f"sub_{index:010d}": Substance(
                f"sub_{index:010d}",
                f"Empty {index}",
                schedule_assertions=(ScheduleAssertion("intake", "empty_preferred"),),
            )
            for index in range(5, 7)
        },
    }
    product = Product("prd_votes", "Votes", tuple(ProductComponent(substance_id) for substance_id in substances))
    policies = {food_policy.id: food_policy, empty_policy.id: empty_policy}
    projection = project_schedule_assignments(bundle.runtime_program, product, substances, policies)

    food_trace = compute_slot_score(bundle.runtime_program, projection, _slot(food=True), policies)
    empty_trace = compute_slot_score(bundle.runtime_program, projection, _slot(food=False), policies)

    assert food_trace.score == 6  # 5 * +2, plus 2 * -2 opposing votes.
    assert empty_trace.score == 4  # 2 * +2; food votes have no matching effect.
    assert [(effect.policy_id, effect.vote_count, effect.delta) for effect in food_trace.effects] == [
        ("intake:empty_preferred", 2, -4),
        ("intake:food_preferred", 5, 10),
    ]


def test_duplicate_typed_component_reference_fails_closed() -> None:
    bundle = ontology_bundle()
    substance = Substance("sub_duplicate", "Duplicate", schedule_assertions=())
    product = Product(
        "prd_duplicate",
        "Duplicate",
        (ProductComponent(substance.id), ProductComponent(substance.id)),
    )

    with pytest.raises(OntologyInfrastructureError, match="duplicate component substance"):
        project_schedule_assignments(bundle.runtime_program, product, {substance.id: substance}, {})


def test_no_scheduling_fact_component_is_score_neutral() -> None:
    bundle = ontology_bundle()
    scheduled = Substance(
        "sub_scheduled",
        "Scheduled",
        schedule_assertions=(ScheduleAssertion("intake", "food_preferred"),),
    )
    neutral = Substance("sub_neutral", "Neutral")
    policy = SchedulingPolicy(
        id="intake:food_preferred",
        namespace="intake",
        short_name="food_preferred",
        label="Food preferred",
        description="",
        applies_when="fixture",
        effects=(TraitEffect(TraitEffectMatch((("food", True),)), level="prefer"),),
    )
    projection = project_schedule_assignments(
        bundle.runtime_program,
        Product("prd_neutral", "Neutral", (ProductComponent(scheduled.id), ProductComponent(neutral.id))),
        {scheduled.id: scheduled, neutral.id: neutral},
        {policy.id: policy},
    )

    trace = compute_slot_score(bundle.runtime_program, projection, _slot(food=True), {policy.id: policy})

    assert trace.score == 2
    assert [effect.vote_count for effect in trace.effects] == [1]
    assert _neutral_components([neutral.id], {neutral.id: neutral}) == [
        {
            "substance_id": neutral.id,
            "substance": "Neutral",
            "status": "no-scheduling-fact",
            "reason": "no-scheduling-fact",
        }
    ]


def test_neutral_journal_distinguishes_unassessed_and_researched_insufficient() -> None:
    bundle = ontology_bundle()
    researched = Substance(
        "sub_researched",
        "Researched",
        scheduling_assessments=(SchedulingAssessment("intake", "insufficient", None, ("source",), "insufficient"),),
    )
    unassessed = Substance("sub_unassessed", "Unassessed")

    rows = _neutral_components(
        [researched.id, unassessed.id],
        {researched.id: researched, unassessed.id: unassessed},
        bundle,
    )
    by_id = {row["substance_id"]: row for row in rows}
    assert by_id[researched.id]["assessment_states"] == {
        "intake": "insufficient",
        "timing": "unassessed",
        "activity": "unassessed",
    }
    assert by_id[unassessed.id]["assessment_states"] == {
        "intake": "unassessed",
        "timing": "unassessed",
        "activity": "unassessed",
    }


def test_assessment_metadata_does_not_change_slot_score() -> None:
    bundle = ontology_bundle()
    policy = SchedulingPolicy(
        id="intake:food_preferred",
        namespace="intake",
        short_name="food_preferred",
        label="Food preferred",
        description="",
        applies_when="fixture",
        effects=(TraitEffect(TraitEffectMatch((("food", True),)), level="prefer"),),
    )
    without = Substance(
        "sub_score_probe",
        "Score probe",
        schedule_assertions=(ScheduleAssertion("intake", "food_preferred"),),
    )
    with_metadata = replace(
        without,
        scheduling_assessments=(
            SchedulingAssessment("intake", "supports_preference", "food_preferred", ("source",), "supports"),
        ),
    )
    product = Product("prd_scoreprobe", "Score probe", (ProductComponent(without.id),))
    plain_projection = project_schedule_assignments(
        bundle.runtime_program, product, {without.id: without}, {policy.id: policy}
    )
    metadata_projection = project_schedule_assignments(
        bundle.runtime_program,
        product,
        {with_metadata.id: with_metadata},
        {policy.id: policy},
    )
    assert (
        compute_slot_score(bundle.runtime_program, plain_projection, _slot(), {policy.id: policy}).score
        == compute_slot_score(
            bundle.runtime_program,
            metadata_projection,
            _slot(),
            {policy.id: policy},
        ).score
    )


def test_pre_and_post_workout_policies_score_different_slots() -> None:
    bundle = ontology_bundle()
    pre = SchedulingPolicy(
        id="activity:pre_workout",
        namespace="activity",
        short_name="pre_workout",
        label="Pre-workout",
        description="",
        applies_when="fixture",
        effects=(TraitEffect(TraitEffectMatch((("near", "workout_before"),)), level="prefer"),),
    )
    post = SchedulingPolicy(
        id="activity:post_workout",
        namespace="activity",
        short_name="post_workout",
        label="Post-workout",
        description="",
        applies_when="fixture",
        effects=(TraitEffect(TraitEffectMatch((("near", "workout_after"),)), level="prefer"),),
    )
    product = Product("training", "Training", (ProductComponent("sub_pre"),))
    substance = Substance("sub_pre", "Pre", schedule_assertions=(ScheduleAssertion("activity", "pre_workout"),))
    projection = project_schedule_assignments(
        bundle.runtime_program, product, {substance.id: substance}, {pre.id: pre, post.id: post}
    )
    before = compute_slot_score(
        bundle.runtime_program, projection, _slot(near="workout_before"), {pre.id: pre, post.id: post}
    )
    after = compute_slot_score(
        bundle.runtime_program, projection, _slot(near="workout_after"), {pre.id: pre, post.id: post}
    )
    assert before.score > after.score


def test_empty_projection_is_neutral() -> None:
    bundle = ontology_bundle()
    trace = compute_slot_score(
        bundle.runtime_program,
        project_schedule_assignments(bundle.runtime_program, Product("p", "P", ()), {}, {}),
        _slot(),
        {},
    )
    assert (trace.score, trace.blocked, trace.effects, trace.diagnostics) == (0, False, (), ())
    assert render_slot_effects(trace, bundle) == [load_review_presentation(bundle).zero_effect_template]


def test_nonzero_effect_rendering_does_not_use_zero_effect_template() -> None:
    bundle = ontology_bundle()
    policy = SchedulingPolicy(
        id="intake:food_preferred",
        namespace="intake",
        short_name="food_preferred",
        label="Food preferred",
        description="",
        applies_when="fixture",
        effects=(TraitEffect(TraitEffectMatch((("food", True),)), level="prefer"),),
    )
    substance = Substance("sub_a", "A", schedule_assertions=(ScheduleAssertion("intake", "food_preferred"),))
    projection = project_schedule_assignments(
        bundle.runtime_program,
        Product("prd_a", "A", (ProductComponent("sub_a"),)),
        {"sub_a": substance},
        {policy.id: policy},
    )
    trace = compute_slot_score(bundle.runtime_program, projection, _slot(food=True), {policy.id: policy})
    rendered = render_slot_effects(trace, bundle)
    assert rendered and rendered != [load_review_presentation(bundle).zero_effect_template]
    assert policy.id in rendered[0]


def test_authored_zero_effect_template_mutation_changes_runtime_output() -> None:
    source = ontology_bundle()
    decoded = cast(dict[str, object], _thaw(cast(dict[str, object], source.decoded)))
    vocabulary = cast(dict[str, object], decoded["runtime-vocabulary.yaml"])
    presentation = cast(dict[str, object], vocabulary["schedule_presentation"])
    zero_effect = cast(dict[str, object], presentation["zero_effect"])
    zero_effect["template"] = "Authored neutral placement explanation."
    bundle = replace(source, decoded=decoded)
    trace = compute_slot_score(
        bundle.runtime_program,
        project_schedule_assignments(bundle.runtime_program, Product("p", "P", ()), {}, {}),
        _slot(),
        {},
    )
    assert render_slot_effects(trace, bundle) == ["Authored neutral placement explanation."]


def test_zero_effect_presentation_metadata_fails_closed() -> None:
    source = ontology_bundle()
    decoded = cast(dict[str, object], _thaw(cast(dict[str, object], source.decoded)))
    vocabulary = cast(dict[str, object], decoded["runtime-vocabulary.yaml"])
    presentation = cast(dict[str, object], vocabulary["schedule_presentation"])
    presentation.pop("zero_effect")
    with pytest.raises(OntologyInfrastructureError) as raised:
        load_review_presentation(replace(source, decoded=decoded))
    assert raised.value.code == MALFORMED


def test_concerns_do_not_change_schedule_placement() -> None:
    bundle = ontology_bundle()
    policy = SchedulingPolicy(
        id="intake:food_preferred",
        namespace="intake",
        short_name="food_preferred",
        label="Food preferred",
        description="",
        applies_when="fixture",
        effects=(TraitEffect(TraitEffectMatch((("food", True),)), level="prefer"),),
    )
    substance = Substance("sub_a", "A", schedule_assertions=(ScheduleAssertion("intake", "food_preferred"),))
    plain = Product("prd_a", "A", (ProductComponent("sub_a"),))
    annotated = Product(
        "prd_a",
        "A",
        (ProductComponent("sub_a"),),
        concerns=(Concern("safety", "Authored annotation only."),),
    )
    slots = (_slot(food=True), _slot(food=False))

    def placement(product: Product) -> tuple[int, ...]:
        projection = project_schedule_assignments(
            bundle.runtime_program, product, {substance.id: substance}, {policy.id: policy}
        )
        return tuple(
            compute_slot_score(bundle.runtime_program, projection, slot, {policy.id: policy}).score for slot in slots
        )

    assert placement(annotated) == placement(plain)


def _thaw(value: object) -> object:
    if isinstance(value, dict):
        mapping = cast(dict[str, object], value)
        return {key: _thaw(item) for key, item in mapping.items()}
    if isinstance(value, list):
        return [_thaw(item) for item in cast(list[object], value)]
    if isinstance(value, tuple):
        return tuple(_thaw(item) for item in cast(tuple[object, ...], value))
    return value
