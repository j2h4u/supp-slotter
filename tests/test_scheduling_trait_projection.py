from planner.contracts import (
    EnforcementCap,
    GovernanceStatus,
    PlannerCapability,
    Product,
    ProductComponent,
    ScheduleGovernance,
    SchedulingPolicy,
    SlotPolicyEvidence,
    Substance,
)
from planner.engine._scheduling import project_governed_assignments


def gov(
    *,
    status: GovernanceStatus = "approved",
    cap: EnforcementCap = "preference",
    scope: tuple[tuple[str, str], ...] = (("planner", "slot_policy"),),
) -> ScheduleGovernance:
    return ScheduleGovernance(status, cap, scope, (SlotPolicyEvidence("test", "test", "test"),), "owner", "2026-10-13")


def policy(
    pid: str,
    *,
    status: GovernanceStatus = "approved",
    enforcement: EnforcementCap = "preference",
    scope: tuple[tuple[str, str], ...] = (),
) -> SchedulingPolicy:
    axis, slug = pid.split(":")
    return SchedulingPolicy(pid, axis, slug, pid, "", "", status=status, enforcement=enforcement, scope=scope)


def capability(product_id: str = "prd_test") -> PlannerCapability:
    return PlannerCapability("slot_policy", "binary", frozenset({"binary"}), product_id, ())


def test_projection_preserves_typed_assignment_governance() -> None:
    g = gov()
    sub = Substance("sub_a", "A", intake=("food_preferred",), schedule_governance={"intake:food_preferred": g})
    product = Product("prd_test", "P", (ProductComponent("sub_a"),))
    projection = project_governed_assignments(
        product, {sub.id: sub}, {"intake:food_preferred": policy("intake:food_preferred")}, capability()
    )
    row = projection.assignments[0]
    assert row.assignment_id == "substance:sub_a:intake:food_preferred"
    assert row.governance is g
    assert row.authority == "component_primary"
    assert projection.groups[0].controlling_assignment_ids == (row.assignment_id,)


def test_scope_mismatch_suppresses_without_creating_group() -> None:
    g = gov(scope=(("food_model", "not_binary"), ("slot_model", "missing")))
    sub = Substance("sub_a", "A", intake=("food_preferred",), schedule_governance={"intake:food_preferred": g})
    product = Product("prd_test", "P", (ProductComponent("sub_a"),))
    projection = project_governed_assignments(
        product, {sub.id: sub}, {"intake:food_preferred": policy("intake:food_preferred")}, capability()
    )
    row = projection.assignments[0]
    assert row.assignment_scope.outcome == "mismatch"
    assert row.assignment_scope.reason_code == "ASSIGNMENT_SCOPE_MISMATCH:food_model,slot_model"
    assert row.reason_code == "ASSIGNMENT_SCOPE_MISMATCH"
    assert row.action == "suppressed"
    assert row.effective_cap == "none"
    assert projection.groups == ()
