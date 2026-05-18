"""Small dataclass factories shared by scheduling unit tests."""

from __future__ import annotations

from planner.contracts import Product, Slot, Substance, TraitDef, TraitEffect

NO_TRAIT_SOURCES: dict[str, list[str]] = {}


def make_slot(near: str = "breakfast", food: bool = True) -> Slot:
    return Slot(
        slot_id="test_slot",
        label="Test Slot",
        order=1,
        near=near,  # type: ignore[arg-type]
        food=food,
        pillbox="daily",
        pillbox_label="Daily",
        stack="daily",
    )


def make_trait_def(
    trait_id: str,
    *,
    effects: tuple[TraitEffect, ...] = (),
) -> TraitDef:
    return TraitDef(
        id=trait_id,
        namespace="intake",
        short_name=trait_id,
        label=trait_id,
        description="",
        applies_when="always",
        effects=effects,
    )


def make_substance(
    sub_id: str,
    name: str = "Substance",
    *,
    intake: tuple[str, ...] = (),
    timing: tuple[str, ...] = (),
    activity: tuple[str, ...] = (),
    is_: tuple[str, ...] = (),
    effect: tuple[str, ...] = (),
    risk: tuple[str, ...] = (),
    pathway: tuple[str, ...] = (),
) -> Substance:
    return Substance(
        id=sub_id,
        name=name,
        intake=intake,
        timing=timing,
        activity=activity,
        is_=is_,
        effect=effect,
        risk=risk,
        pathway=pathway,
    )


def make_product(prd_id: str, name: str, brand: str | None = None) -> Product:
    return Product(id=prd_id, name=name, components=(), brand=brand)
