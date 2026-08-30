"""Typed view of the executable scheduling and review ontology projection."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields
from types import MappingProxyType
from typing import cast

from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.glue_capabilities import (
    IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS,
    IMPLEMENTED_RELATION_ENDPOINT_SELECTOR_KINDS,
    IMPLEMENTED_RELATION_SELECTOR_FORMS,
)

IMPLEMENTED_TIE_BREAK = "stable_item_id_then_(slot.order,slot_id)"


def _error(label: str, message: str) -> OntologyInfrastructureError:
    return OntologyInfrastructureError(f"runtime program {label} {message}", code=MALFORMED)


def _map(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise _error(label, "must be a mapping with string keys")
    return cast(Mapping[str, object], value)


def _exact_map(value: object, label: str, expected: frozenset[str]) -> Mapping[str, object]:
    result = _map(value, label)
    actual = set(result)
    if actual != expected:
        missing = ", ".join(sorted(expected - actual))
        unknown = ", ".join(sorted(actual - expected))
        detail: list[str] = []
        if missing:
            detail.append(f"missing {missing}")
        if unknown:
            detail.append(f"unknown {unknown}")
        raise _error(label, "has an invalid closed shape (" + "; ".join(detail) + ")")
    return result


def _str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise _error(label, "must be a non-empty string")
    return value


def _bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise _error(label, "must be boolean")
    return value


def _int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _error(label, "must be an integer")
    return value


def _nonnegative_int(value: object, label: str) -> int:
    result = _int(value, label)
    if result < 0:
        raise _error(label, "must be a non-negative integer")
    return result


def _cardinality(value: object, label: str) -> int | None:
    if value is None:
        return None
    return _nonnegative_int(value, label)


def _rows(
    value: object,
    label: str,
    *,
    semantic_keys: tuple[tuple[str, ...], ...] = (),
    fields: frozenset[str] | None = None,
) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _error(label, "must be a list")
    sequence = cast(Sequence[object], value)
    result: list[Mapping[str, object]] = []
    ids: set[str] = set()
    seen_semantic: list[dict[tuple[object, ...], int]] = [{} for _ in semantic_keys]
    for index, item in enumerate(sequence):
        row = _map(item, f"{label}[{index}]")
        if fields is not None:
            _exact_map(row, f"{label}[{index}]", fields)
        identifier = _str(row.get("id"), f"{label}[{index}].id")
        if identifier in ids:
            raise _error(label, f"has duplicate id {identifier!r}")
        ids.add(identifier)
        for key_index, key_fields in enumerate(semantic_keys):
            values = tuple(row.get(field) for field in key_fields)
            if any(value is None for value in values):
                raise _error(
                    f"{label}[{index}]",
                    f"is missing semantic key fields {', '.join(key_fields)}",
                )
            previous = seen_semantic[key_index].get(values)
            if previous is not None:
                rendered = ":".join(repr(value) for value in values)
                raise _error(
                    label,
                    f"has duplicate semantic key ({', '.join(key_fields)})={rendered} at rows {previous} and {index}",
                )
            seen_semantic[key_index][values] = index
        result.append(row)
    return tuple(result)


def _strings(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _error(label, "must be a list of strings")
    sequence = cast(Sequence[object], value)
    result = tuple(_str(item, f"{label}[{index}]") for index, item in enumerate(sequence))
    if len(set(result)) != len(result):
        raise _error(label, "must not contain duplicate semantic values")
    return result


@dataclass(frozen=True, slots=True)
class RuntimeStackPartition:
    """Authored ownership and routing partition for stack membership."""

    id: str
    routable_stack_names: tuple[str, ...]
    excluded_stack_names: tuple[str, ...]
    tracked_unassigned_partition_name: str


@dataclass(frozen=True, slots=True)
class RuntimeGlueContract:
    id: str
    inactive_stack_name: str
    stack_partition: RuntimeStackPartition
    relation_endpoint_selector_kinds: tuple[str, ...]
    relation_selector_forms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeEngineSemantic:
    """One externally observable engine rule declared by the ontology."""

    id: str
    category: str
    rule: str
    source_of_truth: str


@dataclass(frozen=True, slots=True)
class RuntimeEngineContract:
    """Versioned protocol metadata for independent scheduler implementations."""

    id: str
    protocol_version: str
    result_mode: str
    pressure_identity: tuple[str, ...]
    domain_feasibility: str
    primary_objective: str
    secondary_objective: str
    tie_break: str
    publication_statuses: tuple[str, ...]
    semantics: tuple[RuntimeEngineSemantic, ...]


IMPLEMENTED_ENGINE_CONTRACT_PROTOCOL = "supp-slotter.engine-contract/v2"
IMPLEMENTED_ENGINE_RESULT_MODES = frozenset({"exact_assignment"})
IMPLEMENTED_PRESSURE_IDENTITY = ("item_id", "dimension", "value")
IMPLEMENTED_DOMAIN_FEASIBILITY = "unbounded_logical_domain"
IMPLEMENTED_PRIMARY_OBJECTIVE = "maximize_unique_pressure_satisfaction"
IMPLEMENTED_SECONDARY_OBJECTIVE = "minimize_integer_squared_load_per_domain"
IMPLEMENTED_ENGINE_TIE_BREAK = IMPLEMENTED_TIE_BREAK
IMPLEMENTED_PUBLICATION_STATUSES = ("Optimal", "Indeterminate")


@dataclass(frozen=True, slots=True)
class RuntimeSelectorFormCapability:
    id: str
    selector_form: str
    endpoint_kind: str
    show_match_details: bool


@dataclass(frozen=True, slots=True)
class RuntimeDashboardUsageStateDefinition:
    """One authored dashboard usage state and its presentation metadata."""

    id: str
    state: str
    label: str
    order: int


@dataclass(frozen=True, slots=True)
class RuntimeDashboardProductTrackingStateDefinition:
    """One authored product-tracking state and its presentation metadata."""

    id: str
    state: str
    label: str
    order: int


@dataclass(frozen=True, slots=True)
class RuntimeDashboardUsageTruthState:
    """One complete product/stack fact combination and its usage state."""

    id: str
    active_stack_membership: bool
    inactive_stack_membership: bool
    tracked_product_presence: bool
    state: str


@dataclass(frozen=True, slots=True)
class RuntimeDashboardProductTrackingTruthState:
    """One product-presence fact and its tracking state."""

    id: str
    tracked_product_presence: bool
    state: str


@dataclass(frozen=True, slots=True)
class RuntimeDashboardStateCatalog:
    """Decoded dashboard state vocabulary and exhaustive truth mappings."""

    usage_states: tuple[RuntimeDashboardUsageStateDefinition, ...]
    product_tracking_states: tuple[RuntimeDashboardProductTrackingStateDefinition, ...]
    usage_truth_table: tuple[RuntimeDashboardUsageTruthState, ...]
    product_tracking_truth_table: tuple[RuntimeDashboardProductTrackingTruthState, ...]

    @property
    def usage_states_by_state(self) -> Mapping[str, RuntimeDashboardUsageStateDefinition]:
        return MappingProxyType({row.state: row for row in self.usage_states})

    @property
    def product_tracking_states_by_state(self) -> Mapping[str, RuntimeDashboardProductTrackingStateDefinition]:
        return MappingProxyType({row.state: row for row in self.product_tracking_states})

    def usage_state_for(
        self,
        *,
        active_stack_membership: bool,
        inactive_stack_membership: bool,
        tracked_product_presence: bool,
    ) -> RuntimeDashboardUsageStateDefinition:
        key = (active_stack_membership, inactive_stack_membership, tracked_product_presence)
        for row in self.usage_truth_table:
            if (
                row.active_stack_membership,
                row.inactive_stack_membership,
                row.tracked_product_presence,
            ) == key:
                return self.usage_states_by_state[row.state]
        raise _error("dashboard_state_catalog.usage_truth_table", f"has no row for facts {key!r}")

    def product_tracking_state_for(
        self, *, tracked_product_presence: bool
    ) -> RuntimeDashboardProductTrackingStateDefinition:
        for row in self.product_tracking_truth_table:
            if row.tracked_product_presence == tracked_product_presence:
                return self.product_tracking_states_by_state[row.state]
        raise _error(
            "dashboard_state_catalog.product_tracking_truth_table",
            f"has no row for facts {tracked_product_presence!r}",
        )


@dataclass(frozen=True, slots=True)
class RuntimeCompositionRole:
    """Stable product/substance composition identity used by canonical facts."""

    id: str
    product: str
    substance: str


@dataclass(frozen=True, slots=True)
class RuntimeEvidenceSource:
    """Stable identity for an evidence source."""

    id: str


@dataclass(frozen=True, slots=True)
class RuntimeFactSubject:
    """Exactly one typed subject selector for a canonical fact."""

    substance: str | None
    composition_role: str | None


@dataclass(frozen=True, slots=True)
class RuntimeFactApplicability:
    """Exactly one declared target selector for a canonical fact."""

    substance: str | None
    composition_role: str | None

    @property
    def target_kind(self) -> str:
        return "substance" if self.substance is not None else "composition_role"

    @property
    def target_id(self) -> str:
        target = self.substance if self.substance is not None else self.composition_role
        if target is None:  # pragma: no cover - decoding establishes the XOR invariant.
            raise ValueError("fact applicability has no target")
        return target


@dataclass(frozen=True, slots=True)
class RuntimeEvidenceProvenance:
    source: str
    locator: str
    quotation: str | None


@dataclass(frozen=True, slots=True)
class RuntimeCanonicalSchedulingFact:
    id: str
    family: str
    subject: RuntimeFactSubject
    applicability: RuntimeFactApplicability
    provenance: tuple[RuntimeEvidenceProvenance, ...]
    value: str


@dataclass(frozen=True, slots=True)
class RuntimeCanonicalLaw:
    """One compiler-emitted, identity-free canonical inference law.

    Laws are indexed by ``(family, fact_value)`` by the inference executor.
    The law carries no item or evidence identity: those belong to the fact and
    the proof produced while traversing an applicability role.
    """

    id: str
    family: str
    fact_value: str
    dimension: str
    pressure_value: str


@dataclass(frozen=True, slots=True)
class RuntimePressureDimension:
    id: str
    pressure_values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeCanonicalFactFamily:
    id: str
    fact_values: tuple[str, ...]
    dimension: str


@dataclass(frozen=True, slots=True)
class RuntimeCanonicalScheduling:
    """Closed, data-derived scheduler evidence and universal laws."""

    dimensions: tuple[RuntimePressureDimension, ...]
    families: tuple[RuntimeCanonicalFactFamily, ...]
    evidence_sources: tuple[RuntimeEvidenceSource, ...]
    facts: tuple[RuntimeCanonicalSchedulingFact, ...]
    laws: tuple[RuntimeCanonicalLaw, ...]

    def __post_init__(self) -> None:
        _validate_runtime_canonical_scheduling(self)

    @property
    def dimensions_by_id(self) -> Mapping[str, RuntimePressureDimension]:
        return MappingProxyType({row.id: row for row in self.dimensions})

    @property
    def families_by_id(self) -> Mapping[str, RuntimeCanonicalFactFamily]:
        return MappingProxyType({row.id: row for row in self.families})

    @property
    def laws_by_key(self) -> Mapping[tuple[str, str], RuntimeCanonicalLaw]:
        return MappingProxyType({(row.family, row.fact_value): row for row in self.laws})

    @property
    def pressure_values_by_dimension(self) -> Mapping[str, frozenset[str]]:
        return MappingProxyType({row.id: frozenset(row.pressure_values) for row in self.dimensions})


def _validate_runtime_canonical_scheduling(catalog: RuntimeCanonicalScheduling) -> None:
    """Keep the compiled canonical graph internally complete at its owner."""
    if not all(isinstance(row, RuntimePressureDimension) for row in catalog.dimensions):
        raise _error("canonical_scheduling.dimensions", "must contain runtime pressure dimensions")
    if not all(isinstance(row, RuntimeCanonicalFactFamily) for row in catalog.families):
        raise _error("canonical_scheduling.families", "must contain runtime fact families")
    if not all(isinstance(row, RuntimeEvidenceSource) for row in catalog.evidence_sources):
        raise _error("canonical_scheduling.evidence_sources", "must contain runtime evidence sources")
    if not all(isinstance(row, RuntimeCanonicalSchedulingFact) for row in catalog.facts):
        raise _error("canonical_scheduling.facts", "must contain runtime canonical facts")
    if not all(isinstance(row, RuntimeCanonicalLaw) for row in catalog.laws):
        raise _error("canonical_scheduling.laws", "must contain runtime canonical laws")
    dimensions = {row.id: set(row.pressure_values) for row in catalog.dimensions}
    families = {row.id: row for row in catalog.families}
    sources = {row.id for row in catalog.evidence_sources}
    if len(dimensions) != len(catalog.dimensions) or len(families) != len(catalog.families):
        raise _error("canonical_scheduling", "has duplicate dimensions or families")
    if bool(dimensions) != bool(families):
        raise _error("canonical_scheduling", "must contain dimensions and families together")
    if any(
        not row.id or not row.pressure_values or len(set(row.pressure_values)) != len(row.pressure_values)
        for row in catalog.dimensions
    ):
        raise _error("canonical_scheduling.dimensions", "has empty or duplicate values")
    if any(
        not row.id
        or not row.fact_values
        or len(set(row.fact_values)) != len(row.fact_values)
        or row.dimension not in dimensions
        for row in catalog.families
    ):
        raise _error("canonical_scheduling.families", "has an incomplete dimension or fact-value graph")
    if any(not row.id for row in catalog.evidence_sources) or len(sources) != len(catalog.evidence_sources):
        raise _error("canonical_scheduling.evidence_sources", "has duplicate or empty identities")
    if any(
        fact.family not in families
        or fact.value not in families[fact.family].fact_values
        or any(provenance.source not in sources for provenance in fact.provenance)
        for fact in catalog.facts
    ):
        raise _error("canonical_scheduling.facts", "references an unknown family, value, or evidence source")
    expected = {(family.id, value) for family in catalog.families for value in family.fact_values}
    actual = {(law.family, law.fact_value) for law in catalog.laws}
    if (
        actual != expected
        or len(actual) != len(catalog.laws)
        or any(
            not law.id
            or law.dimension not in dimensions
            or law.family not in families
            or law.dimension != families[law.family].dimension
            or law.pressure_value not in dimensions[law.dimension]
            for law in catalog.laws
        )
    ):
        raise _error("canonical_scheduling.laws", "does not have exact admissible coverage")


@dataclass(frozen=True, slots=True)
class RuntimeProgram:
    format_version: str
    schema_version: str
    source_hash: str
    engine_contract: RuntimeEngineContract
    glue_contract: RuntimeGlueContract
    selector_form_capabilities: tuple[RuntimeSelectorFormCapability, ...]
    dashboard_state_catalog: RuntimeDashboardStateCatalog
    canonical_scheduling: RuntimeCanonicalScheduling

    @property
    def selector_form_capabilities_by_form(self) -> Mapping[str, RuntimeSelectorFormCapability]:
        return MappingProxyType({item.selector_form: item for item in self.selector_form_capabilities})


# This is technical dispatch metadata, not an authored domain vocabulary. The
# compiler uses it to validate the closed runtime record contract, while the
# decoder rejects silently ignored record fields. Deriving record fields from
# the DTOs keeps the two boundaries closed together when a retained runtime
# field is added or removed.
_RUNTIME_RECORDS: Mapping[str, type[object]] = {
    "engine_contract": RuntimeEngineContract,
    "engine_contract.semantics": RuntimeEngineSemantic,
    "glue_contract": RuntimeGlueContract,
    "glue_contract.stack_partition": RuntimeStackPartition,
    "selector_form_capabilities": RuntimeSelectorFormCapability,
    "dashboard_state_catalog": RuntimeDashboardStateCatalog,
    "dashboard_state_catalog.usage_states": RuntimeDashboardUsageStateDefinition,
    "dashboard_state_catalog.product_tracking_states": RuntimeDashboardProductTrackingStateDefinition,
    "dashboard_state_catalog.usage_truth_table": RuntimeDashboardUsageTruthState,
    "dashboard_state_catalog.product_tracking_truth_table": RuntimeDashboardProductTrackingTruthState,
    "canonical_scheduling": RuntimeCanonicalScheduling,
    "canonical_scheduling.dimensions": RuntimePressureDimension,
    "canonical_scheduling.families": RuntimeCanonicalFactFamily,
    "canonical_scheduling.evidence_sources": RuntimeEvidenceSource,
    "canonical_scheduling.facts": RuntimeCanonicalSchedulingFact,
    "canonical_scheduling.laws": RuntimeCanonicalLaw,
}
_MAPPING_RECORD_PATHS = frozenset({
    "engine_contract",
    "glue_contract",
    "glue_contract.stack_partition",
    "dashboard_state_catalog",
    "canonical_scheduling",
})
RUNTIME_PROGRAM_FIELDS: Mapping[str, frozenset[str]] = MappingProxyType({
    "": frozenset(
        field.name
        for field in fields(RuntimeProgram)
        if field.name not in {"format_version", "schema_version", "source_hash"}
    ),
    **{
        path: frozenset(field.name for field in fields(record))
        for path, record in _RUNTIME_RECORDS.items()
        if path in _MAPPING_RECORD_PATHS
    },
})
RUNTIME_PROGRAM_ROW_FIELDS: Mapping[str, frozenset[str]] = MappingProxyType({
    **{
        path: frozenset(field.name for field in fields(record))
        for path, record in _RUNTIME_RECORDS.items()
        if path not in _MAPPING_RECORD_PATHS
    },
})


def _typed_rows[T](
    value: object,
    label: str,
    factory: Callable[[Mapping[str, object], str], T],
    *,
    semantic_keys: tuple[tuple[str, ...], ...] = (),
    fields: frozenset[str] | None = None,
) -> tuple[T, ...]:
    result: list[object] = []
    for index, row in enumerate(_rows(value, label, semantic_keys=semantic_keys, fields=fields)):
        result.append(factory(row, f"{label}[{index}]"))
    return cast(tuple[T, ...], tuple(result))


def _engine_semantic(row: Mapping[str, object], label: str) -> RuntimeEngineSemantic:
    return RuntimeEngineSemantic(
        _str(row["id"], f"{label}.id"),
        _str(row["category"], f"{label}.category"),
        _str(row["rule"], f"{label}.rule"),
        _str(row["source_of_truth"], f"{label}.source_of_truth"),
    )


def _selector_form_capability(row: Mapping[str, object], label: str) -> RuntimeSelectorFormCapability:
    return RuntimeSelectorFormCapability(
        _str(row["id"], f"{label}.id"),
        _str(row["selector_form"], f"{label}.selector_form"),
        _str(row["endpoint_kind"], f"{label}.endpoint_kind"),
        _bool(row["show_match_details"], f"{label}.show_match_details"),
    )


def _dashboard_state_values(row: Mapping[str, object], label: str) -> tuple[str, str, str, int]:
    order = _int(row["order"], f"{label}.order")
    if order < 0:
        raise _error(f"{label}.order", "must be non-negative")
    return (
        _str(row["id"], f"{label}.id"),
        _str(row["state"], f"{label}.state"),
        _str(row["label"], f"{label}.label"),
        order,
    )


def _dashboard_usage_state(row: Mapping[str, object], label: str) -> RuntimeDashboardUsageStateDefinition:
    return RuntimeDashboardUsageStateDefinition(*_dashboard_state_values(row, label))


def _dashboard_product_tracking_state(
    row: Mapping[str, object], label: str
) -> RuntimeDashboardProductTrackingStateDefinition:
    return RuntimeDashboardProductTrackingStateDefinition(*_dashboard_state_values(row, label))


def _dashboard_usage_truth_state(row: Mapping[str, object], label: str) -> RuntimeDashboardUsageTruthState:
    return RuntimeDashboardUsageTruthState(
        _str(row["id"], f"{label}.id"),
        _bool(row["active_stack_membership"], f"{label}.active_stack_membership"),
        _bool(row["inactive_stack_membership"], f"{label}.inactive_stack_membership"),
        _bool(row["tracked_product_presence"], f"{label}.tracked_product_presence"),
        _str(row["state"], f"{label}.state"),
    )


def _dashboard_tracking_truth_state(row: Mapping[str, object], label: str) -> RuntimeDashboardProductTrackingTruthState:
    return RuntimeDashboardProductTrackingTruthState(
        _str(row["id"], f"{label}.id"),
        _bool(row["tracked_product_presence"], f"{label}.tracked_product_presence"),
        _str(row["state"], f"{label}.state"),
    )


def _closed_value(value: object, label: str, allowed: frozenset[str]) -> str:
    result = _str(value, label)
    if result not in allowed:
        raise _error(label, f"is not an admitted value: {result!r}")
    return result


def _composition_role(row: Mapping[str, object], label: str) -> RuntimeCompositionRole:
    return RuntimeCompositionRole(
        _str(row["id"], f"{label}.id"),
        _str(row["product"], f"{label}.product"),
        _str(row["substance"], f"{label}.substance"),
    )


def _evidence_source(row: Mapping[str, object], label: str) -> RuntimeEvidenceSource:
    return RuntimeEvidenceSource(_str(row["id"], f"{label}.id"))


def _fact_subject(value: object, label: str) -> RuntimeFactSubject:
    raw = _map(value, label)
    allowed = {"substance", "composition_role"}
    unknown = set(raw) - allowed
    if unknown:
        raise _error(label, "has an invalid closed shape (unknown " + ", ".join(sorted(unknown)) + ")")
    has_substance = "substance" in raw
    has_role = "composition_role" in raw
    if has_substance == has_role:
        raise _error(label, "must contain exactly one of substance or composition_role")
    substance = _str(raw["substance"], f"{label}.substance") if has_substance else None
    composition_role = _str(raw["composition_role"], f"{label}.composition_role") if has_role else None
    return RuntimeFactSubject(substance, composition_role)


def _fact_applicability(value: object, label: str) -> RuntimeFactApplicability:
    raw = _map(value, label)
    allowed = {"substance", "composition_role"}
    unknown = set(raw) - allowed
    if unknown:
        raise _error(label, "has an invalid closed shape (unknown " + ", ".join(sorted(unknown)) + ")")
    has_substance = "substance" in raw
    has_role = "composition_role" in raw
    if has_substance == has_role:
        raise _error(label, "must contain exactly one of substance or composition_role")
    substance = _str(raw["substance"], f"{label}.substance") if has_substance else None
    composition_role = _str(raw["composition_role"], f"{label}.composition_role") if has_role else None
    return RuntimeFactApplicability(substance, composition_role)


def _fact_provenance(value: object, label: str) -> tuple[RuntimeEvidenceProvenance, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _error(label, "must be a list")
    result: list[RuntimeEvidenceProvenance] = []
    for index, item in enumerate(cast(Sequence[object], value)):
        row = _map(item, f"{label}[{index}]")
        unknown = set(row) - {"source", "locator", "quotation"}
        if unknown:
            raise _error(
                f"{label}[{index}]",
                "has an invalid closed shape (unknown " + ", ".join(sorted(unknown)) + ")",
            )
        quotation = row.get("quotation")
        if quotation is not None and not isinstance(quotation, str):
            raise _error(f"{label}[{index}].quotation", "must be a string")
        locator = _str(row.get("locator"), f"{label}[{index}].locator")
        if not locator.strip():
            raise _error(f"{label}[{index}].locator", "must contain a non-whitespace character")
        result.append(
            RuntimeEvidenceProvenance(
                _str(row.get("source"), f"{label}[{index}].source"),
                locator,
                quotation,
            )
        )
    if not result:
        raise _error(label, "must contain at least one provenance witness")
    return tuple(result)


def _canonical_law(row: Mapping[str, object], label: str) -> RuntimeCanonicalLaw:
    """Decode one closed compiler law row."""
    expected = frozenset({"id", "family", "fact_value", "dimension", "pressure_value"})
    _exact_map(row, label, expected)
    return RuntimeCanonicalLaw(
        _str(row["id"], f"{label}.id"),
        _str(row["family"], f"{label}.family"),
        _str(row["fact_value"], f"{label}.fact_value"),
        _str(row["dimension"], f"{label}.dimension"),
        _str(row["pressure_value"], f"{label}.pressure_value"),
    )


def _pressure_dimension(row: Mapping[str, object], label: str) -> RuntimePressureDimension:
    _exact_map(row, label, RUNTIME_PROGRAM_ROW_FIELDS["canonical_scheduling.dimensions"])
    return RuntimePressureDimension(
        _str(row["id"], f"{label}.id"), _strings(row["pressure_values"], f"{label}.pressure_values")
    )


def _fact_family(row: Mapping[str, object], label: str) -> RuntimeCanonicalFactFamily:
    _exact_map(row, label, RUNTIME_PROGRAM_ROW_FIELDS["canonical_scheduling.families"])
    return RuntimeCanonicalFactFamily(
        _str(row["id"], f"{label}.id"),
        _strings(row["fact_values"], f"{label}.fact_values"),
        _str(row["dimension"], f"{label}.dimension"),
    )


def _canonical_fact(row: Mapping[str, object], label: str) -> RuntimeCanonicalSchedulingFact:
    _exact_map(row, label, RUNTIME_PROGRAM_ROW_FIELDS["canonical_scheduling.facts"])
    return RuntimeCanonicalSchedulingFact(
        _str(row["id"], f"{label}.id"),
        _str(row["family"], f"{label}.family"),
        _fact_subject(row["subject"], f"{label}.subject"),
        _fact_applicability(row["applicability"], f"{label}.applicability"),
        _fact_provenance(row["provenance"], f"{label}.provenance"),
        _str(row["value"], f"{label}.value"),
    )


def _canonical_scheduling(value: object) -> RuntimeCanonicalScheduling:
    raw = _exact_map(value, "canonical_scheduling", RUNTIME_PROGRAM_FIELDS["canonical_scheduling"])
    dimensions = _typed_rows(
        raw["dimensions"],
        "canonical_scheduling.dimensions",
        _pressure_dimension,
        semantic_keys=(("id",),),
        fields=RUNTIME_PROGRAM_ROW_FIELDS["canonical_scheduling.dimensions"],
    )
    families = _typed_rows(
        raw["families"],
        "canonical_scheduling.families",
        _fact_family,
        semantic_keys=(("id",),),
        fields=RUNTIME_PROGRAM_ROW_FIELDS["canonical_scheduling.families"],
    )
    sources = _typed_rows(
        raw["evidence_sources"],
        "canonical_scheduling.evidence_sources",
        _evidence_source,
        semantic_keys=(("id",),),
        fields=RUNTIME_PROGRAM_ROW_FIELDS["canonical_scheduling.evidence_sources"],
    )
    facts = _typed_rows(
        raw["facts"],
        "canonical_scheduling.facts",
        _canonical_fact,
        semantic_keys=(("id",),),
        fields=RUNTIME_PROGRAM_ROW_FIELDS["canonical_scheduling.facts"],
    )
    laws = _typed_rows(
        raw["laws"],
        "canonical_scheduling.laws",
        _canonical_law,
        semantic_keys=(("family", "fact_value"),),
        fields=RUNTIME_PROGRAM_ROW_FIELDS["canonical_scheduling.laws"],
    )
    dimensions_by_id = {row.id: set(row.pressure_values) for row in dimensions}
    families_by_id = {row.id: row for row in families}
    if not dimensions_by_id or len(dimensions_by_id) != len(dimensions) or len(families_by_id) != len(families):
        raise _error("canonical_scheduling", "has duplicate or empty dimensions/families")
    for family in families:
        if family.dimension not in dimensions_by_id:
            raise _error("canonical_scheduling.families", "references an unknown dimension")
    for fact in facts:
        family = families_by_id.get(fact.family)
        if family is None or fact.value not in family.fact_values:
            raise _error("canonical_scheduling.facts", "references an unknown family or unadmitted value")
    expected = {(family.id, value) for family in families for value in family.fact_values}
    actual = {(law.family, law.fact_value) for law in laws}
    if actual != expected or any(
        law.dimension not in dimensions_by_id
        or law.dimension != families_by_id[law.family].dimension
        or law.pressure_value not in dimensions_by_id.get(law.dimension, set())
        for law in laws
    ):
        raise _error("canonical_scheduling.laws", "does not have exact admissible coverage")
    return RuntimeCanonicalScheduling(
        cast(tuple[RuntimePressureDimension, ...], dimensions),
        cast(tuple[RuntimeCanonicalFactFamily, ...], families),
        cast(tuple[RuntimeEvidenceSource, ...], sources),
        cast(tuple[RuntimeCanonicalSchedulingFact, ...], facts),
        cast(tuple[RuntimeCanonicalLaw, ...], laws),
    )


def _validate_dashboard_state_catalog(catalog: RuntimeDashboardStateCatalog) -> None:
    _validate_dashboard_state_definitions("usage_states", catalog.usage_states)
    _validate_dashboard_state_definitions("product_tracking_states", catalog.product_tracking_states)
    _validate_usage_truth_table(catalog)
    _validate_tracking_truth_table(catalog)


def _validate_dashboard_state_definitions(
    label: str,
    definitions: Sequence[RuntimeDashboardUsageStateDefinition | RuntimeDashboardProductTrackingStateDefinition],
) -> None:
    if not definitions:
        raise _error(f"dashboard_state_catalog.{label}", "must be non-empty")
    if len({row.state for row in definitions}) != len(definitions):
        raise _error(f"dashboard_state_catalog.{label}", "must not duplicate state enums")
    if len({row.label for row in definitions}) != len(definitions):
        raise _error(f"dashboard_state_catalog.{label}", "must not duplicate state labels")
    orders = [row.order for row in definitions]
    if len(set(orders)) != len(orders) or set(orders) != set(range(len(orders))):
        raise _error(f"dashboard_state_catalog.{label}", "must have unique contiguous order values")


def _validate_usage_truth_table(catalog: RuntimeDashboardStateCatalog) -> None:
    usage_states = set(catalog.usage_states_by_state)
    usage_keys = {
        (row.active_stack_membership, row.inactive_stack_membership, row.tracked_product_presence)
        for row in catalog.usage_truth_table
    }
    expected_keys = {
        (active, inactive, tracked)
        for active in (False, True)
        for inactive in (False, True)
        for tracked in (False, True)
    }
    if usage_keys != expected_keys or len(catalog.usage_truth_table) != len(expected_keys):
        raise _error(
            "dashboard_state_catalog.usage_truth_table",
            "must have exact unique coverage of active, inactive, and tracked booleans",
        )
    states = {row.state for row in catalog.usage_truth_table}
    if any(state not in usage_states for state in states):
        raise _error("dashboard_state_catalog.usage_truth_table", "references an unknown usage state")
    if states != usage_states:
        raise _error("dashboard_state_catalog.usage_truth_table", "must cover every usage state")


def _validate_tracking_truth_table(catalog: RuntimeDashboardStateCatalog) -> None:
    tracking_states = set(catalog.product_tracking_states_by_state)
    tracking_keys = {row.tracked_product_presence for row in catalog.product_tracking_truth_table}
    if tracking_keys != {False, True} or len(catalog.product_tracking_truth_table) != 2:
        raise _error(
            "dashboard_state_catalog.product_tracking_truth_table",
            "must have exact unique false/true coverage",
        )
    states = {row.state for row in catalog.product_tracking_truth_table}
    if any(state not in tracking_states for state in states):
        raise _error(
            "dashboard_state_catalog.product_tracking_truth_table",
            "references an unknown product-tracking state",
        )
    if states != tracking_states:
        raise _error(
            "dashboard_state_catalog.product_tracking_truth_table",
            "must cover every product-tracking state",
        )


def _decode_program_payload(payload: Mapping[str, object]) -> tuple[str, str, str, Mapping[str, object]]:
    """Decode the closed envelope around the executable projection."""
    root = _map(payload, "")
    expected_root = {"format_version", "schema_version", "source_hash", "provenance", "projection"}
    if set(root) != expected_root:
        raise _error("", "has an invalid top-level shape")
    projection = _exact_map(root.get("projection"), "projection", RUNTIME_PROGRAM_FIELDS[""])
    return (
        _str(root["format_version"], "format_version"),
        _str(root["schema_version"], "schema_version"),
        _str(root["source_hash"], "source_hash"),
        projection,
    )


def _decode_engine_contract(projection: Mapping[str, object]) -> RuntimeEngineContract:
    """Decode and verify the closed exact-optimizer protocol section."""
    engine_raw = _exact_map(
        projection.get("engine_contract"),
        "engine_contract",
        RUNTIME_PROGRAM_FIELDS["engine_contract"],
    )
    engine_semantics = _typed_rows(
        engine_raw["semantics"],
        "engine_contract.semantics",
        _engine_semantic,
        semantic_keys=(("id",),),
        fields=RUNTIME_PROGRAM_ROW_FIELDS["engine_contract.semantics"],
    )
    if not engine_semantics:
        raise _error("engine_contract", "requires non-empty semantics")
    engine_contract = RuntimeEngineContract(
        _str(engine_raw["id"], "engine_contract.id"),
        _str(engine_raw["protocol_version"], "engine_contract.protocol_version"),
        _str(engine_raw["result_mode"], "engine_contract.result_mode"),
        _strings(engine_raw["pressure_identity"], "engine_contract.pressure_identity"),
        _str(engine_raw["domain_feasibility"], "engine_contract.domain_feasibility"),
        _str(engine_raw["primary_objective"], "engine_contract.primary_objective"),
        _str(engine_raw["secondary_objective"], "engine_contract.secondary_objective"),
        _str(engine_raw["tie_break"], "engine_contract.tie_break"),
        _strings(engine_raw["publication_statuses"], "engine_contract.publication_statuses"),
        cast(tuple[RuntimeEngineSemantic, ...], engine_semantics),
    )
    if engine_contract.protocol_version != IMPLEMENTED_ENGINE_CONTRACT_PROTOCOL:
        raise _error(
            "engine_contract.protocol_version",
            f"is not implemented: {engine_contract.protocol_version!r}",
        )
    if engine_contract.result_mode not in IMPLEMENTED_ENGINE_RESULT_MODES:
        raise _error(
            "engine_contract.result_mode",
            f"is not implemented: {engine_contract.result_mode!r}",
        )
    if engine_contract.pressure_identity != IMPLEMENTED_PRESSURE_IDENTITY:
        raise _error(
            "engine_contract.pressure_identity",
            "must be the unique (item_id, dimension, value) identity",
        )
    if engine_contract.domain_feasibility != IMPLEMENTED_DOMAIN_FEASIBILITY:
        raise _error("engine_contract.domain_feasibility", "must declare unbounded logical domains")
    if engine_contract.primary_objective != IMPLEMENTED_PRIMARY_OBJECTIVE:
        raise _error("engine_contract.primary_objective", "must maximize unique pressure satisfaction")
    if engine_contract.secondary_objective != IMPLEMENTED_SECONDARY_OBJECTIVE:
        raise _error("engine_contract.secondary_objective", "must minimize integer squared load per domain")
    if engine_contract.tie_break != IMPLEMENTED_ENGINE_TIE_BREAK:
        raise _error("engine_contract.tie_break", "must use stable item ID and slot order")
    if engine_contract.publication_statuses != IMPLEMENTED_PUBLICATION_STATUSES:
        raise _error(
            "engine_contract.publication_statuses",
            "must exactly be the closed Optimal/Indeterminate statuses",
        )
    return engine_contract


def _decode_glue_contract(projection: Mapping[str, object]) -> RuntimeGlueContract:
    """Decode the executable integration capability and partition section."""
    glue_raw = _exact_map(projection.get("glue_contract"), "glue_contract", RUNTIME_PROGRAM_FIELDS["glue_contract"])
    partition_raw = _exact_map(
        glue_raw["stack_partition"],
        "glue_contract.stack_partition",
        RUNTIME_PROGRAM_FIELDS["glue_contract.stack_partition"],
    )
    partition = RuntimeStackPartition(
        _str(partition_raw["id"], "glue_contract.stack_partition.id"),
        _strings(partition_raw["routable_stack_names"], "glue_contract.stack_partition.routable_stack_names"),
        _strings(partition_raw["excluded_stack_names"], "glue_contract.stack_partition.excluded_stack_names"),
        _str(
            partition_raw["tracked_unassigned_partition_name"],
            "glue_contract.stack_partition.tracked_unassigned_partition_name",
        ),
    )
    if not partition.routable_stack_names:
        raise _error("glue_contract.stack_partition.routable_stack_names", "must not be empty")
    if set(partition.routable_stack_names) & set(partition.excluded_stack_names):
        raise _error("glue_contract.stack_partition", "routable and excluded stack names must be disjoint")
    if partition.tracked_unassigned_partition_name in set(partition.routable_stack_names) | set(
        partition.excluded_stack_names
    ):
        raise _error("glue_contract.stack_partition", "tracked-unassigned partition must be distinct")
    if glue_raw["inactive_stack_name"] not in partition.excluded_stack_names:
        raise _error("glue_contract.inactive_stack_name", "must be an excluded stack partition")
    glue = RuntimeGlueContract(
        _str(glue_raw["id"], "glue_contract.id"),
        _str(glue_raw["inactive_stack_name"], "glue_contract.inactive_stack_name"),
        partition,
        _strings(glue_raw["relation_endpoint_selector_kinds"], "glue_contract.relation_endpoint_selector_kinds"),
        _strings(glue_raw["relation_selector_forms"], "glue_contract.relation_selector_forms"),
    )
    glue_capabilities: Mapping[str, tuple[str, ...]] = {
        "relation_endpoint_selector_kinds": glue.relation_endpoint_selector_kinds,
        "relation_selector_forms": glue.relation_selector_forms,
    }
    for field_name, expected in IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS.items():
        if field_name not in glue_capabilities:
            continue
        actual = glue_capabilities[field_name]
        if actual != expected:
            raise _error(f"glue_contract.{field_name}", "must exactly match executable capabilities")
    return glue


def _decode_relation_review_catalog(projection: Mapping[str, object]) -> tuple[RuntimeSelectorFormCapability, ...]:
    """Decode review vocabulary that is independent of canonical scheduling facts."""
    selector_form_capabilities = _typed_rows(
        projection["selector_form_capabilities"],
        "selector_form_capabilities",
        _selector_form_capability,
        semantic_keys=(("selector_form",),),
        fields=RUNTIME_PROGRAM_ROW_FIELDS["selector_form_capabilities"],
    )
    selector_forms = tuple(row.selector_form for row in selector_form_capabilities)
    if selector_forms != IMPLEMENTED_RELATION_SELECTOR_FORMS:
        raise _error(
            "selector_form_capabilities",
            "must declare exactly the executable selector forms",
        )
    endpoint_kinds = {row.endpoint_kind for row in selector_form_capabilities}
    if endpoint_kinds != set(IMPLEMENTED_RELATION_ENDPOINT_SELECTOR_KINDS):
        raise _error("selector_form_capabilities", "must declare exactly the executable endpoint kinds")
    return cast(tuple[RuntimeSelectorFormCapability, ...], selector_form_capabilities)


def _decode_dashboard_state_catalog(projection: Mapping[str, object]) -> RuntimeDashboardStateCatalog:
    """Decode the complete dashboard state vocabulary and truth tables."""
    dashboard_catalog = _exact_map(
        projection.get("dashboard_state_catalog"),
        "dashboard_state_catalog",
        RUNTIME_PROGRAM_FIELDS["dashboard_state_catalog"],
    )
    usage_states = _typed_rows(
        dashboard_catalog["usage_states"],
        "dashboard_state_catalog.usage_states",
        _dashboard_usage_state,
        semantic_keys=(("state",), ("order",)),
        fields=RUNTIME_PROGRAM_ROW_FIELDS["dashboard_state_catalog.usage_states"],
    )
    product_tracking_states = _typed_rows(
        dashboard_catalog["product_tracking_states"],
        "dashboard_state_catalog.product_tracking_states",
        _dashboard_product_tracking_state,
        semantic_keys=(("state",), ("order",)),
        fields=RUNTIME_PROGRAM_ROW_FIELDS["dashboard_state_catalog.product_tracking_states"],
    )
    usage_truth_table = _typed_rows(
        dashboard_catalog["usage_truth_table"],
        "dashboard_state_catalog.usage_truth_table",
        _dashboard_usage_truth_state,
        semantic_keys=(("active_stack_membership", "inactive_stack_membership", "tracked_product_presence"),),
        fields=RUNTIME_PROGRAM_ROW_FIELDS["dashboard_state_catalog.usage_truth_table"],
    )
    product_tracking_truth_table = _typed_rows(
        dashboard_catalog["product_tracking_truth_table"],
        "dashboard_state_catalog.product_tracking_truth_table",
        _dashboard_tracking_truth_state,
        semantic_keys=(("tracked_product_presence",),),
        fields=RUNTIME_PROGRAM_ROW_FIELDS["dashboard_state_catalog.product_tracking_truth_table"],
    )
    dashboard_state_catalog = RuntimeDashboardStateCatalog(
        usage_states=cast(tuple[RuntimeDashboardUsageStateDefinition, ...], usage_states),
        product_tracking_states=cast(
            tuple[RuntimeDashboardProductTrackingStateDefinition, ...], product_tracking_states
        ),
        usage_truth_table=cast(tuple[RuntimeDashboardUsageTruthState, ...], usage_truth_table),
        product_tracking_truth_table=cast(
            tuple[RuntimeDashboardProductTrackingTruthState, ...], product_tracking_truth_table
        ),
    )
    _validate_dashboard_state_catalog(dashboard_state_catalog)
    return dashboard_state_catalog


def decode_runtime_program(payload: Mapping[str, object]) -> RuntimeProgram:
    """Decode a compiler-verified runtime snapshot by its closed sections."""

    format_version, schema_version, source_hash, projection = _decode_program_payload(payload)
    if format_version != "ontology-runtime-program-v2":
        raise _error("format_version", "is unsupported")
    engine_contract = _decode_engine_contract(projection)
    glue_contract = _decode_glue_contract(projection)
    selector_form_capabilities = _decode_relation_review_catalog(projection)
    dashboard_state_catalog = _decode_dashboard_state_catalog(projection)
    canonical_scheduling = _canonical_scheduling(projection["canonical_scheduling"])
    return RuntimeProgram(
        format_version,
        schema_version,
        source_hash,
        engine_contract,
        glue_contract,
        selector_form_capabilities,
        dashboard_state_catalog,
        canonical_scheduling,
    )
