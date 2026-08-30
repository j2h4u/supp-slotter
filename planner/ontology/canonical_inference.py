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

    applicability_role: str
    product: str
    substance: str

    @property
    def role_id(self) -> str:
        return self.applicability_role

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


def _path(role: RuntimeCompositionRole) -> CompositionApplicabilityPath:
    return CompositionApplicabilityPath(role.id, role.product, role.substance)


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


def execute_canonical_inference(  # noqa: C901, PLR0912, PLR0914
    catalog: RuntimeCanonicalFactCatalog | object,
    selected_items: Iterable[object] | Mapping[object, object],
    laws: Iterable[RuntimeCanonicalLaw] | Mapping[tuple[str, str], RuntimeCanonicalLaw] | None = None,
) -> InferenceResult:
    """Apply compiled laws to selected items and normalize their proofs.

    Facts whose explicit applicability role is unknown, whose subject does not
    match that role, or whose role product is not selected are ignored.  Such
    rows cannot produce a pressure.  A malformed catalog is validated by the
    catalog boundary; this executor remains total for boundary-adjacent rows.
    """
    # Accepting a RuntimeProgram here keeps the execution boundary convenient
    # without coupling the inference module to planner command inputs.
    runtime = catalog
    if not isinstance(catalog, RuntimeCanonicalFactCatalog):
        runtime_catalog = getattr(runtime, "canonical_fact_catalog", None)
        if not isinstance(runtime_catalog, RuntimeCanonicalFactCatalog):
            raise TypeError("canonical inference requires RuntimeCanonicalFactCatalog or RuntimeProgram")
        catalog = runtime_catalog
        if laws is None:
            laws = getattr(runtime, "canonical_laws", None)
    if laws is None:
        raise OntologyInfrastructureError("canonical inference requires compiler-emitted canonical laws")
    law_index = (
        dict(cast(Mapping[tuple[str, str], RuntimeCanonicalLaw], laws))
        if isinstance(laws, Mapping)
        else _law_index(laws)
    )
    selected = _selected_items(selected_items)
    roles = {role.id: role for role in catalog.composition_roles}
    by_identity: dict[UnaryPressureIdentity, list[PressureDerivation]] = {}

    families: tuple[Sequence[RuntimeCanonicalSchedulingFact], ...] = (
        catalog.food_effects,
        catalog.acute_alertness_effects,
        catalog.acute_sleep_effects,
        catalog.pre_exercise_performance_effects,
        catalog.post_exercise_recovery_effects,
    )
    for family_facts in families:
        for fact in family_facts:
            family = _fact_family(fact)
            if family is None:
                continue
            fact_value = getattr(fact, "value", None)
            if not isinstance(fact_value, str):
                continue
            law = _law_for(law_index, family, fact_value)
            if law is None:
                raise OntologyInfrastructureError(
                    f"canonical law missing for family={family!r}, fact_value={fact_value!r}"
                )
            role = roles.get(fact.applicability)
            if role is None:
                continue
            if fact.subject.substance is not None:
                if fact.subject.substance != role.substance:
                    continue
            elif fact.subject.composition_role != role.id:
                continue
            item_ids = sorted(item_id for item_id, product_id in selected.items() if product_id == role.product)
            for item_id in item_ids:
                identity = UnaryPressureIdentity(item_id, law.dimension, law.pressure_value)
                derivation = PressureDerivation(
                    law=law,
                    family=family,
                    fact=fact,
                    value=fact_value,
                    subject=fact.subject,
                    path=_path(role),
                    provenance=_unique_provenance(fact.provenance),
                )
                by_identity.setdefault(identity, []).append(derivation)

    normalized: dict[UnaryPressureIdentity, NormalizedUnaryPressure] = {}
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
        normalized[identity] = NormalizedUnaryPressure(identity, derivations)

    grouped: dict[tuple[str, str], list[NormalizedUnaryPressure]] = {}
    for pressure in normalized.values():
        grouped.setdefault((pressure.item_id, pressure.dimension), []).append(pressure)
    conflicts: list[SameDimensionPressureConflict] = []
    for (item_id, dimension), pressures in sorted(grouped.items()):
        values = tuple(sorted({pressure.value for pressure in pressures}))
        if len(values) > 1:
            derivations = tuple(
                derivation
                for pressure in sorted(pressures, key=lambda row: row.value)
                for derivation in pressure.derivations
            )
            conflicts.append(SameDimensionPressureConflict(item_id, dimension, values, derivations))
    if conflicts:
        return Conflict(tuple(conflicts))
    return Success(tuple(normalized.values()))


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
