"""Closed canonical-fact laws and pressure normalization.

This module deliberately has no scheduling or optimization concerns.  It
traverses the explicit composition/applicability role on a fact, applies the
compiler-emitted law for the exact ``(family, fact_value)`` pair, and returns
set-normalized pressure proofs or a same-dimension conflict.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import (
    IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY,
    RuntimeCanonicalLaw,
    RuntimeCanonicalScheduling,
    RuntimeCanonicalSchedulingFact,
    RuntimeCompositionRole,
    RuntimeEvidenceProvenance,
    RuntimeFactSubject,
)


@dataclass(frozen=True, slots=True)
class UnaryPressureIdentity:
    """The only identity used for pressure counting."""

    item_id: str
    dimension: str
    value: str


@dataclass(frozen=True, slots=True)
class CompositionApplicabilityPath:
    """The explicit role traversal used to reach a selected product item."""

    target_kind: str
    target_id: str
    resolved_role: str
    product: str
    substance: str

    @property
    def role_id(self) -> str:
        return self.resolved_role


@dataclass(frozen=True, slots=True)
class PressureDerivation:
    """One provenance-rich proof for a normalized pressure identity."""

    law: RuntimeCanonicalLaw
    family: str
    fact: RuntimeCanonicalSchedulingFact
    value: str
    subject: RuntimeFactSubject
    path: CompositionApplicabilityPath
    provenance: tuple[RuntimeEvidenceProvenance, ...]

    @property
    def law_id(self) -> str:
        return self.law.id

    @property
    def fact_id(self) -> str:
        return self.fact.id


@dataclass(frozen=True, slots=True)
class NormalizedUnaryPressure:
    """One pressure identity with all unique derivations attached."""

    identity: UnaryPressureIdentity
    derivations: tuple[PressureDerivation, ...]

    @property
    def item_id(self) -> str:
        return self.identity.item_id

    @property
    def dimension(self) -> str:
        return self.identity.dimension

    @property
    def value(self) -> str:
        return self.identity.value


@dataclass(frozen=True, slots=True)
class SameDimensionPressureConflict:
    """Conflicting values for one item and one independent dimension."""

    item_id: str
    dimension: str
    values: tuple[str, ...]
    derivations: tuple[PressureDerivation, ...]


@dataclass(frozen=True, slots=True)
class Success:
    """Conflict-free normalized pressures."""

    pressures: tuple[NormalizedUnaryPressure, ...]


@dataclass(frozen=True, slots=True)
class Conflict:
    """Layout-free result when one item has opposing values on one axis."""

    conflicts: tuple[SameDimensionPressureConflict, ...]


InferenceResult = Success | Conflict


def _selected_items(selected_items: Iterable[object] | Mapping[object, object]) -> dict[str, str]:
    """Return the closed string item-to-product selection boundary."""
    if isinstance(selected_items, Mapping):
        result: dict[str, str] = {}
        for item_id, product_id in selected_items.items():
            if not isinstance(item_id, str) or not item_id or not isinstance(product_id, str) or not product_id:
                raise OntologyInfrastructureError(
                    "canonical inference selected item mapping must contain non-empty strings"
                )
            result[item_id] = product_id
        return result
    if isinstance(selected_items, (str, bytes)):
        raise OntologyInfrastructureError("canonical inference selected items must be an iterable of non-empty strings")
    result = {}
    for item_id in selected_items:
        if not isinstance(item_id, str) or not item_id:
            raise OntologyInfrastructureError("canonical inference selected items must contain non-empty strings")
        result[item_id] = item_id
    return result


def _unique_provenance(rows: Sequence[RuntimeEvidenceProvenance]) -> tuple[RuntimeEvidenceProvenance, ...]:
    unique = {(row.source, row.locator, row.quotation): row for row in rows}
    return tuple(
        unique[key]
        for key in sorted(
            unique,
            key=lambda row: (row[0], row[1], row[2] is not None, row[2] or ""),
        )
    )


def _path(fact: RuntimeCanonicalSchedulingFact, role: RuntimeCompositionRole) -> CompositionApplicabilityPath:
    return CompositionApplicabilityPath(
        fact.applicability.target_kind,
        fact.applicability.target_id,
        role.id,
        role.product,
        role.substance,
    )


def _law_for(
    laws: Mapping[tuple[str, str], RuntimeCanonicalLaw], family: str, value: str
) -> RuntimeCanonicalLaw | None:
    # Exact lookup is intentional: there is no open-ended family/value
    # fallback and no item-name-specific inference.
    return laws.get((family, value))


def _roles_for_fact(
    fact: RuntimeCanonicalSchedulingFact,
    roles: Mapping[str, RuntimeCompositionRole],
    applicability_expansion_strategy: str,
) -> tuple[RuntimeCompositionRole, ...]:
    if applicability_expansion_strategy != IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY:
        raise OntologyInfrastructureError("canonical inference has an unsupported applicability expansion strategy")
    target = fact.applicability
    if target.product is not None:
        return () if fact.subject.product != target.product else ()
    if target.substance is not None:
        if fact.subject.substance != target.substance:
            return ()
        return tuple(role for role in roles.values() if role.substance == target.substance)
    if fact.subject.composition_role != target.composition_role:
        return ()
    role = roles.get(target.composition_role or "")
    return () if role is None else (role,)


def _derivations_for_fact(
    fact: RuntimeCanonicalSchedulingFact,
    law_index: Mapping[tuple[str, str], RuntimeCanonicalLaw],
    roles: Mapping[str, RuntimeCompositionRole],
    selected_by_product: Mapping[str, tuple[str, ...]],
    applicability_expansion_strategy: str,
) -> tuple[tuple[UnaryPressureIdentity, PressureDerivation], ...]:
    family = fact.family
    fact_value = fact.value
    law = _law_for(law_index, family, fact_value)
    if law is None:
        raise OntologyInfrastructureError(f"canonical law missing for family={family!r}, fact_value={fact_value!r}")
    derivations: list[tuple[UnaryPressureIdentity, PressureDerivation]] = []
    if fact.applicability.product is not None:
        # Product-scoped instructions target the intake item directly.  There
        # is deliberately no role traversal here: the product's components
        # must never inherit a product instruction.
        if fact.subject.product != fact.applicability.product:
            return ()
        product_id = fact.applicability.product
        for item_id in selected_by_product.get(product_id, ()):
            identity = UnaryPressureIdentity(item_id, law.dimension, law.pressure_value)
            derivations.append((
                identity,
                PressureDerivation(
                    law=law,
                    family=family,
                    fact=fact,
                    value=fact_value,
                    subject=fact.subject,
                    path=CompositionApplicabilityPath(
                        target_kind="product",
                        target_id=product_id,
                        resolved_role=product_id,
                        product=product_id,
                        substance="",
                    ),
                    provenance=_unique_provenance(fact.provenance),
                ),
            ))
        return tuple(derivations)
    for role in _roles_for_fact(fact, roles, applicability_expansion_strategy):
        for item_id in selected_by_product.get(role.product, ()):
            identity = UnaryPressureIdentity(item_id, law.dimension, law.pressure_value)
            derivations.append((
                identity,
                PressureDerivation(
                    law=law,
                    family=family,
                    fact=fact,
                    value=fact_value,
                    subject=fact.subject,
                    path=_path(fact, role),
                    provenance=_unique_provenance(fact.provenance),
                ),
            ))
    return tuple(derivations)


def _collect_derivations(
    catalog: RuntimeCanonicalScheduling,
    laws: Mapping[tuple[str, str], RuntimeCanonicalLaw],
    roles: Mapping[str, RuntimeCompositionRole],
    selected: Mapping[str, str],
    applicability_expansion_strategy: str,
) -> dict[UnaryPressureIdentity, list[PressureDerivation]]:
    selected_by_product: dict[str, tuple[str, ...]] = {}
    for product_id in set(selected.values()):
        selected_by_product[product_id] = tuple(
            sorted(item_id for item_id, product in selected.items() if product == product_id)
        )
    by_identity: dict[UnaryPressureIdentity, list[PressureDerivation]] = {}
    for fact in catalog.facts:
        for identity, derivation in _derivations_for_fact(
            fact,
            laws,
            roles,
            selected_by_product,
            applicability_expansion_strategy,
        ):
            by_identity.setdefault(identity, []).append(derivation)
    return by_identity


def _normalized_pressures(
    by_identity: Mapping[UnaryPressureIdentity, Sequence[PressureDerivation]],
) -> tuple[NormalizedUnaryPressure, ...]:
    normalized: list[NormalizedUnaryPressure] = []
    for identity in sorted(by_identity, key=lambda row: (row.item_id, row.dimension, row.value)):
        unique_derivations = {
            (
                derivation.law.id,
                derivation.family,
                derivation.fact.id,
                derivation.value,
                derivation.subject,
                derivation.path,
                derivation.provenance,
            ): derivation
            for derivation in by_identity[identity]
        }
        derivations = tuple(
            unique_derivations[key]
            for key in sorted(
                unique_derivations,
                key=lambda row: (row[0], row[1], row[2], row[3], repr(row[4]), repr(row[5]), repr(row[6])),
            )
        )
        normalized.append(NormalizedUnaryPressure(identity, derivations))
    return tuple(normalized)


def _same_dimension_conflicts(
    pressures: Sequence[NormalizedUnaryPressure],
) -> tuple[SameDimensionPressureConflict, ...]:
    grouped: dict[tuple[str, str], list[NormalizedUnaryPressure]] = {}
    for pressure in pressures:
        grouped.setdefault((pressure.item_id, pressure.dimension), []).append(pressure)
    conflicts: list[SameDimensionPressureConflict] = []
    for (item_id, dimension), same_dimension in sorted(grouped.items()):
        values = tuple(sorted({pressure.value for pressure in same_dimension}))
        if len(values) > 1:
            derivations = tuple(
                derivation
                for pressure in sorted(same_dimension, key=lambda row: row.value)
                for derivation in pressure.derivations
            )
            conflicts.append(SameDimensionPressureConflict(item_id, dimension, values, derivations))
    return tuple(conflicts)


def execute_canonical_inference(
    catalog: RuntimeCanonicalScheduling,
    selected_items: Iterable[object] | Mapping[object, object],
    *,
    applicability_expansion_strategy: str,
    composition_roles: Iterable[RuntimeCompositionRole] = (),
    known_products: Iterable[str] = (),
) -> InferenceResult:
    """Apply compiled laws to selected items and normalize their proofs.

    Facts whose explicit applicability role is unknown, whose subject does not
    match that role, or whose role product is not selected are ignored.  Such
    rows cannot produce a pressure.  A malformed catalog is validated by the
    catalog boundary; this executor remains total for boundary-adjacent rows.
    """
    if not isinstance(catalog, RuntimeCanonicalScheduling):
        raise TypeError("canonical inference requires RuntimeCanonicalScheduling")
    if applicability_expansion_strategy != IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY:
        raise OntologyInfrastructureError("canonical inference has an unsupported applicability expansion strategy")
    selected = _selected_items(selected_items)
    roles: dict[str, RuntimeCompositionRole] = {}
    for role in composition_roles:
        if not isinstance(role, RuntimeCompositionRole) or not role.id or not role.product or not role.substance:
            raise OntologyInfrastructureError("canonical inference composition roles must be complete runtime roles")
        if role.id in roles:
            raise OntologyInfrastructureError(f"canonical inference has duplicate composition role {role.id!r}")
        roles[role.id] = role
    admitted_products = set(known_products) | {role.product for role in roles.values()}
    if any(not isinstance(product, str) or not product for product in admitted_products):
        raise OntologyInfrastructureError("canonical inference known products must be non-empty strings")
    unknown = set(selected.values()) - admitted_products
    if unknown:
        raise OntologyInfrastructureError(
            f"canonical inference selected unknown products: {', '.join(sorted(unknown))}"
        )
    normalized = _normalized_pressures(
        _collect_derivations(
            catalog,
            catalog.laws_by_key,
            roles,
            selected,
            applicability_expansion_strategy,
        )
    )
    conflicts = _same_dimension_conflicts(normalized)
    if conflicts:
        return Conflict(conflicts)
    return Success(normalized)


__all__ = [
    "CompositionApplicabilityPath",
    "Conflict",
    "InferenceResult",
    "NormalizedUnaryPressure",
    "PressureDerivation",
    "SameDimensionPressureConflict",
    "Success",
    "UnaryPressureIdentity",
    "execute_canonical_inference",
]
