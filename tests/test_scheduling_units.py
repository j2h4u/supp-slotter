from planner.contracts import Product, ProductComponent, SchedulingPolicy, Slot, Substance, TraitEffect, TraitEffectMatch
from planner.engine._scheduling import compute_slot_score, project_schedule_assignments, slot_matches

from tests.helpers import ontology_bundle


def _slot(*, food: bool = True, near: str = "breakfast") -> Slot:
    return Slot("slot", "Slot", 1, near, food, "daily", "Daily", "daily")


def test_slot_matches_declared_ontology_dimensions() -> None:
    slot = _slot(food=True, near="breakfast")
    program = ontology_bundle().runtime_program
    assert slot_matches(program, slot, TraitEffectMatch((("food", True),)))
    assert not slot_matches(program, slot, TraitEffectMatch((("food", False),)))


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
    substance = Substance("sub_a", "A", intake=("food_preferred",))
    product = Product("prd_a", "A", (ProductComponent("sub_a"),))
    projection = project_schedule_assignments(bundle.runtime_program, product, {"sub_a": substance}, {policy.id: policy})
    trace = compute_slot_score(bundle.runtime_program, projection, _slot(food=True), {policy.id: policy})
    assert trace.blocked is False
    assert trace.score > 0
    assert trace.effects[0].policy_id == policy.id


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
    substance = Substance("sub_pre", "Pre", activity=("pre_workout",))
    projection = project_schedule_assignments(bundle.runtime_program, product, {substance.id: substance}, {pre.id: pre, post.id: post})
    before = compute_slot_score(bundle.runtime_program, projection, _slot(near="workout_before"), {pre.id: pre, post.id: post})
    after = compute_slot_score(bundle.runtime_program, projection, _slot(near="workout_after"), {pre.id: pre, post.id: post})
    assert before.score > after.score


def test_empty_projection_is_neutral() -> None:
    trace = compute_slot_score(ontology_bundle().runtime_program, project_schedule_assignments(ontology_bundle().runtime_program, Product("p", "P", ()), {}, {}), _slot(), {})
    assert (trace.score, trace.blocked, trace.effects, trace.diagnostics) == (0, False, (), ())
