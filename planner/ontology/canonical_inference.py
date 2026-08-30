"""Closed canonical-fact laws and pressure normalization.

This module deliberately has no scheduling or optimization concerns.  It
traverses the explicit composition/applicability role on a fact, applies the
compiler-emitted law for the exact ``(family, fact_value)`` pair, and returns
set-normalized pressure proofs or a same-dimension conflict.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import (
    RuntimeAcuteAlertnessEffect,
    RuntimeAcuteSleepEffect,
    RuntimeCanonicalFactCatalog,
    RuntimeCanonicalLaw,
    RuntimeCanonicalSchedulingFact,
    RuntimeCompositionRole,
    RuntimeEvidenceProvenance,
    RuntimeFactSubject,
    RuntimeFoodEffect,
    RuntimePostExerciseRecoveryEffect,
    RuntimePreExercisePerformanceEffect,
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

    @property
    def applicability_role(self) -> str:
        """Compatibility alias for the resolved role in an emitted proof."""
        return self.resolved_role

    @property
    def product_id(self) -> str:
        return self.product

    @property
    def substance_id(self) -> str:
        return self.substance


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

    @property
    def fact_value(self) -> str:
        return self.value


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

    @property
    def identities(self) -> tuple[UnaryPressureIdentity, ...]:
        return tuple(UnaryPressureIdentity(self.item_id, self.dimension, value) for value in self.values)

    @property
    def pressure_identities(self) -> tuple[UnaryPressureIdentity, ...]:
        return self.identities


@dataclass(frozen=True, slots=True)
class Success:
    """Conflict-free normalized pressures."""

    pressures: tuple[NormalizedUnaryPressure, ...]

    @property
    def normalized_pressures(self) -> tuple[NormalizedUnaryPressure, ...]:
        return self.pressures


@dataclass(frozen=True, slots=True)
class Conflict:
    """Layout-free result when one item has opposing values on one axis."""

    conflicts: tuple[SameDimensionPressureConflict, ...]

    @property
    def diagnostics(self) -> tuple[SameDimensionPressureConflict, ...]:
        return self.conflicts

    @property
    def pressure_conflicts(self) -> tuple[SameDimensionPressureConflict, ...]:
        return self.conflicts


InferenceResult = Success | Conflict


_FACT_TYPES: tuple[tuple[type[RuntimeCanonicalSchedulingFact], str], ...] = (
    (RuntimeFoodEffect, "FoodEffect"),
    (RuntimeAcuteAlertnessEffect, "AcuteAlertnessEffect"),
    (RuntimeAcuteSleepEffect, "AcuteSleepEffect"),
    (RuntimePreExercisePerformanceEffect, "PreExercisePerformanceEffect"),
    (RuntimePostExerciseRecoveryEffect, "PostExerciseRecoveryEffect"),
)


def _fact_family(fact: RuntimeCanonicalSchedulingFact) -> str | None:
    for fact_type, family in _FACT_TYPES:
        if isinstance(fact, fact_type):
            return family
    return None


def _stable_id(value: object) -> str | None:
    if isinstance(value, str):
        return value
    candidate = getattr(value, "id", None)
    return candidate if isinstance(candidate, str) else None


def _selected_items(selected_items: Iterable[object] | Mapping[object, object]) -> dict[str, str]:
    """Return stable item IDs to product IDs from common plan input forms.

    The normal form is an iterable of product IDs.  A mapping is also accepted
    for callers whose scenario item ID differs from its product ID; its key is
    the item ID and its string value is the product ID.
    """
    if isinstance(selected_items, Mapping):
        result: dict[str, str] = {}
        mapping = cast(Mapping[object, object], selected_items)
        for raw_item, raw_product in mapping.items():
            item_id = _stable_id(raw_item)
            product_id = _stable_id(raw_product)
            if item_id is not None and product_id is not None:
                result[item_id] = product_id
        return result
    result = {}
    for raw_item in selected_items:
        item_id = _stable_id(raw_item)
        if item_id is not None:
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


def _law_index(laws: Iterable[RuntimeCanonicalLaw]) -> dict[tuple[str, str], RuntimeCanonicalLaw]:
    index: dict[tuple[str, str], RuntimeCanonicalLaw] = {}
    for law in laws:
        key = (law.family, law.fact_value)
        if key in index:
            raise OntologyInfrastructureError(f"duplicate canonical law key {key!r}")
        index[key] = law
    return index


def _law_for(
    laws: Mapping[tuple[str, str], RuntimeCanonicalLaw], family: str, value: str
) -> RuntimeCanonicalLaw | None:
    # Exact lookup is intentional: there is no open-ended family/value
    # fallback and no item-name-specific inference.
    return laws.get((family, value))


def _catalog_and_laws(
    catalog: RuntimeCanonicalFactCatalog | object,
    laws: Iterable[RuntimeCanonicalLaw] | Mapping[tuple[str, str], RuntimeCanonicalLaw] | None,
) -> tuple[
    RuntimeCanonicalFactCatalog,
    Iterable[RuntimeCanonicalLaw] | Mapping[tuple[str, str], RuntimeCanonicalLaw],
]:
    if isinstance(catalog, RuntimeCanonicalFactCatalog):
        if laws is None:
            raise OntologyInfrastructureError("canonical inference requires compiler-emitted canonical laws")
        return catalog, laws
    runtime_catalog = getattr(catalog, "canonical_fact_catalog", None)
    if not isinstance(runtime_catalog, RuntimeCanonicalFactCatalog):
        raise TypeError("canonical inference requires RuntimeCanonicalFactCatalog or RuntimeProgram")
    runtime_laws = laws if laws is not None else getattr(catalog, "canonical_laws", None)
    if runtime_laws is None:
        raise OntologyInfrastructureError("canonical inference requires compiler-emitted canonical laws")
    return runtime_catalog, runtime_laws


def _indexed_laws(
    laws: Iterable[RuntimeCanonicalLaw] | Mapping[tuple[str, str], RuntimeCanonicalLaw],
) -> dict[tuple[str, str], RuntimeCanonicalLaw]:
    return (
        dict(cast(Mapping[tuple[str, str], RuntimeCanonicalLaw], laws))
        if isinstance(laws, Mapping)
        else _law_index(laws)
    )


def _facts_with_families(
    catalog: RuntimeCanonicalFactCatalog,
) -> tuple[Sequence[RuntimeCanonicalSchedulingFact], ...]:
    return (
        catalog.food_effects,
        catalog.acute_alertness_effects,
        catalog.acute_sleep_effects,
        catalog.pre_exercise_performance_effects,
        catalog.post_exercise_recovery_effects,
    )


def _roles_for_fact(
    fact: RuntimeCanonicalSchedulingFact,
    roles: Mapping[str, RuntimeCompositionRole],
) -> tuple[RuntimeCompositionRole, ...]:
    target = fact.applicability
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
) -> tuple[tuple[UnaryPressureIdentity, PressureDerivation], ...]:
    family = _fact_family(fact)
    fact_value = getattr(fact, "value", None)
    if family is None or not isinstance(fact_value, str):
        return ()
    law = _law_for(law_index, family, fact_value)
    if law is None:
        raise OntologyInfrastructureError(f"canonical law missing for family={family!r}, fact_value={fact_value!r}")
    derivations: list[tuple[UnaryPressureIdentity, PressureDerivation]] = []
    for role in _roles_for_fact(fact, roles):
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
    catalog: RuntimeCanonicalFactCatalog,
    laws: Mapping[tuple[str, str], RuntimeCanonicalLaw],
    roles: Mapping[str, RuntimeCompositionRole],
    selected: Mapping[str, str],
) -> dict[UnaryPressureIdentity, list[PressureDerivation]]:
    selected_by_product: dict[str, tuple[str, ...]] = {}
    for product_id in set(selected.values()):
        selected_by_product[product_id] = tuple(
            sorted(item_id for item_id, product in selected.items() if product == product_id)
        )
    by_identity: dict[UnaryPressureIdentity, list[PressureDerivation]] = {}
    for facts in _facts_with_families(catalog):
        for fact in facts:
            for identity, derivation in _derivations_for_fact(fact, laws, roles, selected_by_product):
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
    catalog: RuntimeCanonicalFactCatalog | object,
    selected_items: Iterable[object] | Mapping[object, object],
    laws: Iterable[RuntimeCanonicalLaw] | Mapping[tuple[str, str], RuntimeCanonicalLaw] | None = None,
    *,
    composition_roles: Iterable[RuntimeCompositionRole] = (),
) -> InferenceResult:
    """Apply compiled laws to selected items and normalize their proofs.

    Facts whose explicit applicability role is unknown, whose subject does not
    match that role, or whose role product is not selected are ignored.  Such
    rows cannot produce a pressure.  A malformed catalog is validated by the
    catalog boundary; this executor remains total for boundary-adjacent rows.
    """
    catalog, resolved_laws = _catalog_and_laws(catalog, laws)
    law_index = _indexed_laws(resolved_laws)
    selected = _selected_items(selected_items)
    roles = {role.id: role for role in composition_roles}
    normalized = _normalized_pressures(_collect_derivations(catalog, law_index, roles, selected))
    conflicts = _same_dimension_conflicts(normalized)
    if conflicts:
        return Conflict(conflicts)
    return Success(normalized)


def infer_canonical_pressures(
    catalog: RuntimeCanonicalFactCatalog | object,
    selected_items: Iterable[object] | Mapping[object, object],
    laws: Iterable[RuntimeCanonicalLaw] | Mapping[tuple[str, str], RuntimeCanonicalLaw] | None = None,
) -> InferenceResult:
    """Descriptive alias for :func:`execute_canonical_inference`."""
    return execute_canonical_inference(catalog, selected_items, laws)


infer_pressures = infer_canonical_pressures


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
    "infer_canonical_pressures",
    "infer_pressures",
]
