"""Cross-card validation for the verified canonical fact catalog."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from planner.cards.product import composition_role_id
from planner.contracts import CardLoadError, Product, Substance
from planner.ontology.runtime_program import RuntimeCanonicalFactCatalog, RuntimeCanonicalSchedulingFact

_CATALOG_PATH = Path(__file__).resolve().parents[2] / "ontology" / "canonical-facts.yaml"


def validate_canonical_fact_catalog(  # noqa: C901, PLR0912
    catalog: RuntimeCanonicalFactCatalog,
    substances: Mapping[str, Substance],
    products: Mapping[str, Product],
    *,
    path: Path = _CATALOG_PATH,
) -> None:
    """Fail closed when canonical facts reference cards outside the catalog.

    Runtime decoding proves the shape and closed values.  This boundary proves
    identities that only exist in repository cards: product/substance roles,
    fact subjects, applicability roles, and evidence source references.
    """
    errors: list[str] = []
    roles = {role.id: role for role in catalog.composition_roles}
    sources = {source.id for source in catalog.evidence_sources}

    for role in catalog.composition_roles:
        expected_role_id = composition_role_id(role.product, role.substance)
        if role.id != expected_role_id:
            errors.append(
                f"composition role {role.id!r} must equal authored identity "
                f"{expected_role_id!r} for product/substance pair"
            )
        if role.product not in products:
            errors.append(f"composition role {role.id!r} references unknown product {role.product!r}")
        if role.substance not in substances:
            errors.append(f"composition role {role.id!r} references unknown substance {role.substance!r}")
        product = products.get(role.product)
        if product is not None:
            matching_components = [
                component for component in product.components if component.substance == role.substance
            ]
            if not matching_components:
                errors.append(
                    f"composition role {role.id!r} substance {role.substance!r} is not a component of product {role.product!r}"
                )
            elif not any(component.id == role.id for component in matching_components):
                errors.append(
                    f"composition role {role.id!r} does not match the authored component ID "
                    f"for product {role.product!r} and substance {role.substance!r}"
                )

    families: Sequence[tuple[str, Sequence[RuntimeCanonicalSchedulingFact]]] = (
        ("food_effects", catalog.food_effects),
        ("acute_alertness_effects", catalog.acute_alertness_effects),
        ("acute_sleep_effects", catalog.acute_sleep_effects),
        ("pre_exercise_performance_effects", catalog.pre_exercise_performance_effects),
        ("post_exercise_recovery_effects", catalog.post_exercise_recovery_effects),
    )
    for family_name, facts in families:
        for fact in facts:
            label = f"{family_name}.{fact.id}"
            applicability = roles.get(fact.applicability)
            if applicability is None:
                errors.append(f"{label} references unknown applicability role {fact.applicability!r}")
            subject = fact.subject
            if subject.substance is not None:
                if subject.substance not in substances:
                    errors.append(f"{label} references unknown subject substance {subject.substance!r}")
                if applicability is not None and subject.substance != applicability.substance:
                    errors.append(f"{label} subject substance does not match applicability role substance")
            else:
                if subject.composition_role is None:
                    errors.append(f"{label} subject must select a substance or composition role")
                    continue
                if subject.composition_role not in roles:
                    errors.append(f"{label} references unknown subject composition role {subject.composition_role!r}")
                if subject.composition_role != fact.applicability:
                    errors.append(f"{label} subject composition role does not match applicability role")
            errors.extend(
                f"{label} references unknown evidence source {provenance.source!r}"
                for provenance in fact.provenance
                if provenance.source not in sources
            )

    if errors:
        raise CardLoadError(path, f"{path}: canonical fact catalog reference validation failed:\n" + "\n".join(errors))
