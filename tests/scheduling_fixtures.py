"""Small dataclass factories shared by scheduling unit tests."""

from __future__ import annotations

from dataclasses import dataclass

from planner.contracts import (
    KnowledgeAssertion,
    Product,
    ScheduleAssertion,
    SchedulingPolicy,
    Slot,
    SlotObservation,
    Substance,
    TraitEffect,
)

NO_TRAIT_SOURCES: dict[str, list[str]] = {}


def make_slot(near: str = "breakfast", food: bool = True) -> Slot:
    return Slot(
        slot_id="test_slot",
        label="Test Slot",
        order=1,
        observations=(SlotObservation("near", near), SlotObservation("food", food)),
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
    schedule_assertions = tuple(
        ScheduleAssertion(axis, value)
        for axis, values in (
            ("intake", traits.intake),
            ("timing", traits.timing),
            ("activity", traits.activity),
        )
        for value in values
    )
    knowledge_assertions = tuple(
        KnowledgeAssertion(category, value)
        for category, values in (
            ("kind", traits.kind),
            ("effect", traits.effect),
            ("risk", traits.risk),
            ("pathway", traits.pathway),
        )
        for value in values
    )
    return Substance(
        id=sub_id,
        name=name,
        knowledge_assertions=knowledge_assertions,
        schedule_assertions=schedule_assertions,
    )


def make_product(prd_id: str, name: str, brand: str | None = None) -> Product:
    return Product(id=prd_id, name=name, components=(), brand=brand)
