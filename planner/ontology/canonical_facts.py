"""Cross-card validation for the verified canonical fact catalog."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from planner.card_ids import composition_role_id
from planner.contracts import CardLoadError, Product, Substance
from planner.ontology.runtime_program import (
    RuntimeCanonicalFactCatalog,
    RuntimeCanonicalSchedulingFact,
    RuntimeCompositionRole,
)

_CATALOG_PATH = Path(__file__).resolve().parents[2] / "ontology" / "canonical-facts.yaml"


def composition_roles_for_products(products: Mapping[str, Product]) -> tuple[RuntimeCompositionRole, ...]:
    """Build the complete role index from authoritative product components."""
    roles: dict[str, RuntimeCompositionRole] = {}
    for product_id, product in sorted(products.items()):
        for component in product.components:
            role_id = component.id or composition_role_id(product_id, component.substance)
            role = RuntimeCompositionRole(role_id, product_id, component.substance)
            if role_id in roles:
                raise CardLoadError(Path("data/products"), f"duplicate composition role {role_id!r}")
            roles[role_id] = role
    return tuple(roles[role_id] for role_id in sorted(roles))


def _catalog_families(
    catalog: RuntimeCanonicalFactCatalog,
) -> tuple[tuple[str, Sequence[RuntimeCanonicalSchedulingFact]], ...]:
    return (
        ("food_effects", catalog.food_effects),
        ("acute_alertness_effects", catalog.acute_alertness_effects),
        ("acute_sleep_effects", catalog.acute_sleep_effects),
        ("pre_exercise_performance_effects", catalog.pre_exercise_performance_effects),
        ("post_exercise_recovery_effects", catalog.post_exercise_recovery_effects),
    )


def _applicability_errors(
    fact: RuntimeCanonicalSchedulingFact,
    label: str,
    roles: Mapping[str, RuntimeCompositionRole],
    substances: Mapping[str, Substance],
) -> list[str]:
    applicability = fact.applicability
    errors: list[str] = []
    if applicability.substance is not None:
        if applicability.substance not in substances:
            errors.append(f"{label} references unknown applicability substance {applicability.substance!r}")
        if fact.subject.substance != applicability.substance:
            errors.append(f"{label} substance subject must match applicability substance")
        return errors
    if applicability.composition_role not in roles:
        errors.append(f"{label} references unknown applicability composition role {applicability.composition_role!r}")
    if fact.subject.composition_role != applicability.composition_role:
        errors.append(f"{label} composition-role subject must match applicability composition role")
    return errors


def _subject_errors(
    fact: RuntimeCanonicalSchedulingFact,
    label: str,
    roles: Mapping[str, RuntimeCompositionRole],
    substances: Mapping[str, Substance],
) -> list[str]:
    subject = fact.subject
    if subject.substance is not None:
        return (
            []
            if subject.substance in substances
            else [f"{label} references unknown subject substance {subject.substance!r}"]
        )
    if subject.composition_role is None:
        return [f"{label} subject must select a substance or composition role"]
    return (
        []
        if subject.composition_role in roles
        else [f"{label} references unknown subject composition role {subject.composition_role!r}"]
    )


def _fact_reference_errors(
    fact: RuntimeCanonicalSchedulingFact,
    label: str,
    roles: Mapping[str, RuntimeCompositionRole],
    substances: Mapping[str, Substance],
    sources: set[str],
) -> list[str]:
    errors = _applicability_errors(fact, label, roles, substances)
    errors.extend(_subject_errors(fact, label, roles, substances))
    if fact.subject.substance is None and fact.subject.composition_role is None:
        return errors
    errors.extend(
        f"{label} references unknown evidence source {provenance.source!r}"
        for provenance in fact.provenance
        if provenance.source not in sources
    )
    return errors


def validate_canonical_fact_catalog(
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
    roles = {role.id: role for role in composition_roles_for_products(products)}
    sources = {source.id for source in catalog.evidence_sources}

    for family_name, facts in _catalog_families(catalog):
        for fact in facts:
            label = f"{family_name}.{fact.id}"
            errors.extend(_fact_reference_errors(fact, label, roles, substances, sources))

    if errors:
        raise CardLoadError(path, f"{path}: canonical fact catalog reference validation failed:\n" + "\n".join(errors))


__all__ = ["composition_roles_for_products", "validate_canonical_fact_catalog"]
