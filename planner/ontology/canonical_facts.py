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
    roles = {role.id: role for role in composition_roles_for_products(products)}
    sources = {source.id for source in catalog.evidence_sources}

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
            applicability = fact.applicability
            if applicability.substance is not None:
                if applicability.substance not in substances:
                    errors.append(f"{label} references unknown applicability substance {applicability.substance!r}")
                if fact.subject.substance != applicability.substance:
                    errors.append(f"{label} substance subject must match applicability substance")
            else:
                target_role = roles.get(applicability.composition_role or "")
                if target_role is None:
                    errors.append(
                        f"{label} references unknown applicability composition role {applicability.composition_role!r}"
                    )
                if fact.subject.composition_role != applicability.composition_role:
                    errors.append(f"{label} composition-role subject must match applicability composition role")
            subject = fact.subject
            if subject.substance is not None:
                if subject.substance not in substances:
                    errors.append(f"{label} references unknown subject substance {subject.substance!r}")
            else:
                if subject.composition_role is None:
                    errors.append(f"{label} subject must select a substance or composition role")
                    continue
                if subject.composition_role not in roles:
                    errors.append(f"{label} references unknown subject composition role {subject.composition_role!r}")
            errors.extend(
                f"{label} references unknown evidence source {provenance.source!r}"
                for provenance in fact.provenance
                if provenance.source not in sources
            )

    if errors:
        raise CardLoadError(path, f"{path}: canonical fact catalog reference validation failed:\n" + "\n".join(errors))


__all__ = ["composition_roles_for_products", "validate_canonical_fact_catalog"]
