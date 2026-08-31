"""Small dataclass factories shared by scheduling unit tests."""

from __future__ import annotations

from dataclasses import dataclass

from planner.contracts import KnowledgeAssertion, Product, Substance


@dataclass(frozen=True, slots=True)
class SubstanceTraitOverrides:
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
    )


def make_product(prd_id: str, name: str, brand: str | None = None) -> Product:
    return Product(id=prd_id, name=name, components=(), brand=brand)
