from planner.contracts import (
    EnforcementCap,
    GovernanceStatus,
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
from planner.engine._scheduling import compute_slot_score, project_governed_assignments


def gov(
    cap: EnforcementCap = "preference",
    *,
    status: GovernanceStatus = "approved",
    scope: tuple[tuple[str, str], ...] = (("planner", "slot_policy"),),
) -> ScheduleGovernance:
    return ScheduleGovernance(
        status,
        cap,
        scope,
        (SlotPolicyEvidence("test", "test", "test"),),
        "owner",
        "2026-10-13",
    )


def policy(
    pid: str,
    enforcement: EnforcementCap = "preference",
    *,
    status: GovernanceStatus = "approved",
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
        effects=(TraitEffect(TraitEffectMatch(food=False), block=True),),
    )


CAP = PlannerCapability("slot_policy", "binary", frozenset({"binary"}), "prd", ())


def test_same_policy_primary_shadows_secondary() -> None:
    pid = "intake:food_preferred"
    primary = Substance("sub_primary", "Primary", intake=("food_preferred",), schedule_governance={pid: gov()})
    secondary = Substance(
        "sub_secondary", "Secondary", intake=("food_preferred",), schedule_governance={pid: gov("block")}
    )
    product = Product("prd", "P", (ProductComponent(primary.id, primary=True), ProductComponent(secondary.id)))
    projection = project_governed_assignments(
        product, {primary.id: primary, secondary.id: secondary}, {pid: policy(pid, "block")}, CAP
    )
    group = projection.groups[0]
    assert group.controlling_assignment_ids == ("substance:sub_primary:intake:food_preferred",)
    assert group.effective_cap == "preference"


def test_secondary_only_group_is_capped_and_weighted() -> None:
    pid = "intake:food_preferred"
    primary = Substance("sub_primary", "Primary")
    secondary = Substance(
        "sub_secondary", "Secondary", intake=("food_preferred",), schedule_governance={pid: gov("block")}
    )
    product = Product("prd", "P", (ProductComponent(primary.id, primary=True), ProductComponent(secondary.id)))
    projection = project_governed_assignments(
        product, {primary.id: primary, secondary.id: secondary}, {pid: policy(pid, "block")}, CAP
    )
    group = projection.groups[0]
    assert group.effective_cap == "preference"
    assert group.score_weight == 0.25
    secondary_row = next(row for row in projection.assignments if row.source_card_id == secondary.id)
    assert secondary_row.reason_code == "SECONDARY_CAPPED"
    assert "SECONDARY_CAPPED" in {
        diagnostic.code
        for diagnostic in projection.diagnostics
        if diagnostic.assignment_id == secondary_row.assignment_id
    }


def test_review_pending_secondary_does_not_emit_redundant_secondary_capped() -> None:
    pid = "intake:food_preferred"
    primary = Substance("sub_primary", "Primary")
    secondary = Substance(
        "sub_secondary",
        "Secondary",
        intake=("food_preferred",),
        schedule_governance={pid: gov("block", status="review_pending")},
    )
    product = Product("prd", "P", (ProductComponent(primary.id, primary=True), ProductComponent(secondary.id)))
    projection = project_governed_assignments(
        product, {primary.id: primary, secondary.id: secondary}, {pid: policy(pid, "block")}, CAP
    )
    row = next(row for row in projection.assignments if row.source_card_id == secondary.id)
    codes = {diagnostic.code for diagnostic in projection.diagnostics if diagnostic.assignment_id == row.assignment_id}
    assert row.effective_cap == "preference"
    assert row.reason_code == "ACTIVE"
    assert "SECONDARY_CAPPED" not in codes
    trace = compute_slot_score(
        projection,
        Slot("empty", "Empty", 1, "wake", False, "daily", "Daily", "daily"),
        {pid: policy(pid, "block")},
    )
    assert "PENDING_BLOCK_SUPPRESSED" in {
        diagnostic.code for diagnostic in trace.diagnostics if diagnostic.assignment_id == row.assignment_id
    }


def test_scope_mismatched_secondary_does_not_emit_redundant_secondary_capped() -> None:
    pid = "intake:food_preferred"
    primary = Substance("sub_primary", "Primary")
    secondary = Substance(
        "sub_secondary",
        "Secondary",
        intake=("food_preferred",),
        schedule_governance={pid: gov("block", scope=(("food_model", "not_binary"),))},
    )
    product = Product("prd", "P", (ProductComponent(primary.id, primary=True), ProductComponent(secondary.id)))
    projection = project_governed_assignments(
        product, {primary.id: primary, secondary.id: secondary}, {pid: policy(pid, "block")}, CAP
    )
    row = next(row for row in projection.assignments if row.source_card_id == secondary.id)
    codes = {diagnostic.code for diagnostic in projection.diagnostics if diagnostic.assignment_id == row.assignment_id}
    assert (row.effective_cap, row.action, row.reason_code) == ("none", "suppressed", "ASSIGNMENT_SCOPE_MISMATCH")
    assert codes == {"ASSIGNMENT_SCOPE_MISMATCH"}


def test_no_explicit_primary_uses_all_components_as_primary() -> None:
    p1, p2 = "intake:food_preferred", "intake:empty_preferred"
    a = Substance("sub_a", "A", intake=("food_preferred",), schedule_governance={p1: gov()})
    b = Substance("sub_b", "B", intake=("empty_preferred",), schedule_governance={p2: gov()})
    product = Product("prd", "P", (ProductComponent(a.id), ProductComponent(b.id)))
    projection = project_governed_assignments(product, {a.id: a, b.id: b}, {p1: policy(p1), p2: policy(p2)}, CAP)
    assert {r.authority for r in projection.assignments} == {"component_primary"}
    assert {g.policy_id for g in projection.groups} == {p1, p2}
