from planner.contracts import (
    EffectiveAssignmentProjection,
    EffectivePolicyGroup,
    GovernedScheduleProjection,
    ScheduleGovernance,
    SchedulingPolicy,
    ScopeEvaluation,
    Slot,
    TraitEffect,
    TraitEffectMatch,
)
from planner.engine._scheduling import compute_slot_score, slot_matches


def _slot(*, food: bool = True, near: str = "breakfast") -> Slot:
    return Slot("slot", "Slot", 1, near, food, "daily", "Daily", "daily")  # type: ignore[arg-type]


def _policy(pid: str, effect: TraitEffect, enforcement: str = "block") -> SchedulingPolicy:
    axis, slug = pid.split(":")
    return SchedulingPolicy(pid, axis, slug, pid, "", "", enforcement=enforcement, effects=(effect,))  # type: ignore[arg-type]


def _projection(pid: str, cap: str = "block", weight: float = 1.0) -> GovernedScheduleProjection:
    group = EffectivePolicyGroup(pid.split(":")[0], pid, ("a",), ("a",), cap, weight)  # type: ignore[arg-type]
    matched_policy = ScopeEvaluation("matched", (), (), "POLICY_SCOPE_MATCHED")
    matched_assignment = ScopeEvaluation("matched", (), (), "ASSIGNMENT_SCOPE_MATCHED")
    governance = ScheduleGovernance("approved", cap, (), (), "owner", "2026-10-13")  # type: ignore[arg-type]
    assignment = EffectiveAssignmentProjection(
        "a",
        "intake",
        pid,
        "substance",
        "sub",
        "sub",
        "component_primary",
        governance,
        matched_policy,
        matched_assignment,
        cap,  # type: ignore[arg-type]
        "active",
        "ACTIVE",
    )
    return GovernedScheduleProjection((assignment,), (group,), ())


def test_slot_matches_near_and_food_conjunction() -> None:
    slot = _slot(food=True, near="breakfast")
    assert slot_matches(slot, TraitEffectMatch(food=True))
    assert not slot_matches(slot, TraitEffectMatch(food=False))
    assert not slot_matches(slot, TraitEffectMatch(near="sleep"))


def test_compute_slot_score_retains_block_cap_effect() -> None:
    pid = "intake:required"
    policies = {pid: _policy(pid, TraitEffect(TraitEffectMatch(food=False), block=True))}
    trace = compute_slot_score(_projection(pid), _slot(food=False), policies)
    assert trace.blocked is True
    assert trace.score == 0
    assert trace.effects[0].assignment_ids == ("a",)


def test_compute_slot_score_applies_secondary_weight_once() -> None:
    pid = "intake:preferred"
    policies = {pid: _policy(pid, TraitEffect(TraitEffectMatch(food=True), level="prefer_strong"))}
    trace = compute_slot_score(_projection(pid, weight=0.25), _slot(food=True), policies)
    assert trace.score == 1
    assert trace.effects[0].weight == 0.25


def test_empty_projection_is_neutral() -> None:
    trace = compute_slot_score(GovernedScheduleProjection((), (), ()), _slot(), {})
    assert (trace.score, trace.blocked, trace.effects, trace.diagnostics) == (0, False, (), ())
