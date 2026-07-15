"""Small dataclass factories shared by scheduling unit tests."""

from __future__ import annotations

from dataclasses import dataclass

from planner.contracts import (
    Product,
    ScheduleGovernance,
    SchedulingPolicy,
    Slot,
    SlotNear,
    SlotPolicyEvidence,
    Substance,
    TraitEffect,
)

NO_TRAIT_SOURCES: dict[str, list[str]] = {}

FIXTURE_GOVERNANCE = ScheduleGovernance(
    status="approved",
    enforcement_cap="preference",
    scope=(("planner", "slot_policy"),),
    evidence=(
        SlotPolicyEvidence(
            source="operational.policy_contract",
            supports="Synthetic fixture assignment for planner tests.",
            limitations="Not a substance or product instruction.",
        ),
    ),
    owner="supp-slotter-maintainers",
    review_by="2026-10-13",
)


def fixture_governance(traits: SubstanceTraitOverrides) -> dict[str, ScheduleGovernance]:
    assignments: dict[str, tuple[str, ...]] = {
        "intake": traits.intake,
        "timing": traits.timing,
        "activity": traits.activity,
    }
    result: dict[str, ScheduleGovernance] = {}
    for axis, policies in assignments.items():
        for policy in policies:
            result[f"{axis}:{policy}"] = FIXTURE_GOVERNANCE
    return result


def make_slot(near: SlotNear = "breakfast", food: bool = True) -> Slot:
    return Slot(
        slot_id="test_slot",
        label="Test Slot",
        order=1,
        near=near,
        food=food,
        pillbox="daily",
        pillbox_label="Daily",
        stack="daily",
    )


def make_trait_def(
    trait_id: str,
    *,
    effects: tuple[TraitEffect, ...] = (),
) -> SchedulingPolicy:
    return SchedulingPolicy(
        id=trait_id,
        namespace="intake",
        short_name=trait_id,
        label=trait_id,
        description="",
        applies_when="always",
        effects=effects,
    )


@dataclass(frozen=True, slots=True)
class SubstanceTraitOverrides:
    intake: tuple[str, ...] = ()
    timing: tuple[str, ...] = ()
    activity: tuple[str, ...] = ()
    kind: tuple[str, ...] = ()
    effect: tuple[str, ...] = ()
    risk: tuple[str, ...] = ()
    pathway: tuple[str, ...] = ()


NO_SUBSTANCE_TRAIT_OVERRIDES = SubstanceTraitOverrides()


def make_substance(
    sub_id: str,
    name: str = "Substance",
    *,
    traits: SubstanceTraitOverrides = NO_SUBSTANCE_TRAIT_OVERRIDES,
) -> Substance:
    return Substance(
        id=sub_id,
        name=name,
        intake=traits.intake,
        timing=traits.timing,
        activity=traits.activity,
        kind=traits.kind,
        effect=traits.effect,
        risk=traits.risk,
        pathway=traits.pathway,
        schedule_governance=fixture_governance(traits),
    )


def make_product(prd_id: str, name: str, brand: str | None = None) -> Product:
    return Product(id=prd_id, name=name, components=(), brand=brand)
