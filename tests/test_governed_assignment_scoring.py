import pytest
from planner.contracts import (
    EnforcementCap,
    GovernanceStatus,
    GovernedScheduleProjection,
    PlannerCapability,
    Product,
    ProductComponent,
    ScheduleGovernance,
    SchedulingPolicy,
    Slot,
    SlotPolicyEvidence,
    Substance,
    TraitEffect,
    TraitEffectMatch,
)
from planner.engine._plan_feasibility import build_feasibility_index
from planner.engine._plan_types import ActiveIndex
from planner.engine._scheduling import _evaluate_scope, compute_slot_score, project_governed_assignments


def gov(
    status: GovernanceStatus = "approved",
    cap: EnforcementCap = "block",
    scope: tuple[tuple[str, str], ...] = (("planner", "slot_policy"),),
) -> ScheduleGovernance:
    return ScheduleGovernance(status, cap, scope, (SlotPolicyEvidence("test", "test", "test"),), "owner", "2026-10-13")


def policy(
    pid: str = "intake:food_required",
    status: GovernanceStatus = "approved",
    enforcement: EnforcementCap = "block",
    scope: tuple[tuple[str, str], ...] = (),
) -> SchedulingPolicy:
    axis, slug = pid.split(":")
    return SchedulingPolicy(
        pid,
        axis,
        slug,
        pid,
        "",
        "",
        status=status,
        enforcement=enforcement,
        scope=scope,
        effects=(
            TraitEffect(TraitEffectMatch(food=False), level="avoid_strong", block=True),
            TraitEffect(TraitEffectMatch(food=True), level="prefer_strong"),
        ),
    )


def slot(food: bool) -> Slot:
    return Slot("s", "S", 1, "breakfast", food, "daily", "Daily", "daily")


def projection(
    g: ScheduleGovernance,
    p: SchedulingPolicy | None = None,
    *,
    product_direct: bool = False,
) -> tuple[GovernedScheduleProjection, dict[str, SchedulingPolicy]]:
    p = p or policy()
    if product_direct:
        product = Product("prd", "P", (), intake=("food_required",), schedule_governance={p.id: g})
        substances = {}
    else:
        sub = Substance("sub", "S", intake=("food_required",), schedule_governance={p.id: g})
        product = Product("prd", "P", (ProductComponent("sub"),))
        substances = {"sub": sub}
    cap = PlannerCapability("slot_policy", "binary", frozenset({"binary"}), "prd", ())
    return project_governed_assignments(product, substances, {p.id: p}, cap), {p.id: p}


@pytest.mark.parametrize(
    "declared,expected", [("none", "none"), ("advisory", "advisory"), ("preference", "preference"), ("block", "block")]
)
def test_cap_lattice_does_not_iterate_cap_characters(declared: EnforcementCap, expected: EnforcementCap) -> None:
    proj, _ = projection(gov(cap=declared), policy(enforcement="block"), product_direct=True)
    assert proj.assignments[0].effective_cap == expected


@pytest.mark.parametrize(
    "key,value,expected",
    [
        ("planner", "wrong", "mismatch"),
        ("food_model", "not_binary", "mismatch"),
        ("slot_model", "wake_day_sleep", "mismatch"),
        ("product", "other", "mismatch"),
        ("formulation", "unknown", "limited"),
        ("formulation", "tablet", "mismatch"),
        ("intended_use", "digestive", "limited"),
    ],
)
def test_scope_evaluation_covers_supported_restrictions(key: str, value: str, expected: str) -> None:
    source = Substance("sub", "S", form="capsule")
    capability = PlannerCapability("slot_policy", "binary", frozenset({"binary"}), "prd", ())
    result = _evaluate_scope("POLICY", ((key, value),), capability, False, source)
    assert result.outcome == expected


def test_scope_evaluation_rejects_unknown_keys() -> None:
    capability = PlannerCapability("slot_policy", "binary", frozenset({"binary"}), "prd", ())
    with pytest.raises(ValueError, match="unknown schedule scope key"):
        _evaluate_scope("POLICY", (("unknown", "value"),), capability, False, Substance("sub", "S"))


def test_pending_assignment_suppresses_block_and_downgrades_strong_effect() -> None:
    proj, policies = projection(gov(status="review_pending", cap="block"))
    trace = compute_slot_score(proj, slot(False), policies)
    assert trace.blocked is False
    assert "PENDING_BLOCK_SUPPRESSED" in {row.code for row in trace.diagnostics}
    assert "STRONG_EFFECT_DOWNGRADED" in {row.code for row in trace.diagnostics}


def test_advisory_assignment_has_no_score_or_block() -> None:
    proj, policies = projection(gov(cap="advisory"))
    trace = compute_slot_score(proj, slot(False), policies)
    assert (trace.score, trace.blocked) == (0, False)
    assert trace.effects[0].action_codes == ("ADVISORY_NO_SCORE",)
    assert "ADVISORY_NO_SCORE" in {row.code for row in trace.diagnostics}


def test_limited_scope_retains_authored_preference() -> None:
    proj, _ = projection(gov(cap="preference", scope=(("intended_use", "digestive"),)))
    row = proj.assignments[0]
    assert row.assignment_scope.outcome == "limited"
    assert row.reason_code == "ASSIGNMENT_SCOPE_LIMITED"
    assert row.effective_cap == "preference"


def test_product_direct_assignment_overrides_component_axis() -> None:
    component_pid = "intake:empty_preferred"
    direct_pid = "intake:food_required"
    sub = Substance("sub", "S", intake=("empty_preferred",), schedule_governance={component_pid: gov(cap="preference")})
    product = Product(
        "prd",
        "P",
        (ProductComponent("sub"),),
        intake=("food_required",),
        schedule_governance={direct_pid: gov(scope=(("product", "prd"),))},
    )
    policies = {direct_pid: policy(direct_pid), component_pid: policy(component_pid, enforcement="preference")}
    cap = PlannerCapability("slot_policy", "binary", frozenset({"binary"}), "prd", ())
    proj = project_governed_assignments(product, {"sub": sub}, policies, cap)
    assert [g.policy_id for g in proj.groups] == [direct_pid]
    assert next(row for row in proj.assignments if row.source_kind == "product").reason_code == "ACTIVE"
    component = next(row for row in proj.assignments if row.source_kind == "substance")
    assert (component.action, component.effective_cap, component.reason_code) == (
        "shadowed",
        "none",
        "PRODUCT_AXIS_OVERRIDE",
    )


def test_policy_and_assignment_scope_are_independent_and_mismatch_suppresses_block() -> None:
    p = policy(scope=(("food_model", "not_binary"),))
    proj, policies = projection(gov(scope=(("planner", "slot_policy"),)), p)
    row = proj.assignments[0]
    assert row.policy_scope.reason_code == "POLICY_SCOPE_MISMATCH:food_model"
    assert row.assignment_scope.reason_code == "ASSIGNMENT_SCOPE_MATCHED"
    assert (row.effective_cap, row.action, row.reason_code) == ("none", "suppressed", "POLICY_SCOPE_MISMATCH")
    assert compute_slot_score(proj, slot(False), policies).blocked is False


def test_distinct_live_policies_on_same_axis_emit_structured_multi_policy_rows() -> None:
    food, empty = "intake:food_required", "intake:empty_preferred"
    a = Substance("sub_a", "A", intake=("food_required",), schedule_governance={food: gov()})
    b = Substance("sub_b", "B", intake=("empty_preferred",), schedule_governance={empty: gov(cap="preference")})
    product = Product("prd", "P", (ProductComponent(a.id), ProductComponent(b.id)))
    policies = {food: policy(food), empty: policy(empty, enforcement="preference")}
    proj = project_governed_assignments(
        product,
        {a.id: a, b.id: b},
        policies,
        PlannerCapability("slot_policy", "binary", frozenset({"binary"}), "prd", ()),
    )
    diagnostics = [row for row in proj.diagnostics if row.code == "MULTI_POLICY_AXIS"]
    assert len(diagnostics) == 2
    assert {row.related_policy_ids for row in diagnostics} == {(empty, food)}
    assert {row.source_card_id for row in diagnostics} == {a.id, b.id}


def test_all_slot_failure_retains_rejected_traces_and_exact_contributors() -> None:
    wake, sleep = "timing:wake_block", "timing:sleep_block"
    a = Substance("sub_a", "A", timing=("wake_block",), schedule_governance={wake: gov()})
    b = Substance("sub_b", "B", timing=("sleep_block",), schedule_governance={sleep: gov()})
    product = Product("prd", "P", (ProductComponent(a.id), ProductComponent(b.id)))
    policies = {
        wake: SchedulingPolicy(
            wake,
            "timing",
            "wake_block",
            wake,
            "",
            "",
            enforcement="block",
            effects=(TraitEffect(TraitEffectMatch(near="wake"), block=True),),
        ),
        sleep: SchedulingPolicy(
            sleep,
            "timing",
            "sleep_block",
            sleep,
            "",
            "",
            enforcement="block",
            effects=(TraitEffect(TraitEffectMatch(near="sleep"), block=True),),
        ),
    }
    projection = project_governed_assignments(
        product,
        {a.id: a, b.id: b},
        policies,
        PlannerCapability("slot_policy", "binary", frozenset({"binary", "wake_day_sleep"}), "prd", ()),
    )
    active = ActiveIndex(
        item_products={"item": product.id},
        active_components={"item": [a.id, b.id]},
        intra_product_relation_conflicts_by_item={},
        item_stacks={"item": "daily"},
        governed_projection_by_item={"item": projection},
        active_policy_ids_by_item={"item": {wake, sleep}},
    )
    slots = {
        "wake": Slot("wake", "Wake", 1, "wake", False, "daily", "Daily", "daily"),
        "sleep": Slot("sleep", "Sleep", 2, "sleep", False, "daily", "Daily", "daily"),
    }
    errors: list[str] = []
    assert build_feasibility_index(slots, active, policies, errors) is None
    assert errors == [
        "plan: stack item 'item' is blocked from every slot. [BLOCKED_ALL_SLOTS: "
        "timing:sleep_block|substance:sub_b:timing:sleep_block|sub_b;"
        "timing:wake_block|substance:sub_a:timing:wake_block|sub_a]"
    ]
