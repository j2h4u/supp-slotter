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
    IMPLEMENTED_RELATION_PRESENCE_TRUTH_TABLE,
    IMPLEMENTED_RELATION_SELECTOR_FORMS,
    relation_presence_active_side,
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


def _truth_table(value: object, label: str) -> tuple[tuple[bool, bool], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _error(label, "must be a list")
    sequence = cast(Sequence[object], value)
    states: list[tuple[bool, bool]] = []
    for index, item in enumerate(sequence):
        row = _exact_map(
            item,
            f"{label}[{index}]",
            RUNTIME_PROJECTION_ROW_FIELDS["glue_contract.relation_presence_truth_table"],
        )
        source_active = _bool(row.get("source_active"), f"{label}[{index}].source_active")
        target_active = _bool(row.get("target_active"), f"{label}[{index}].target_active")
        state = (source_active, target_active)
        if state in states:
            raise _error(label, f"has duplicate truth-table state {state!r}")
        states.append(state)
    expected = set(IMPLEMENTED_RELATION_PRESENCE_TRUTH_TABLE)
    if set(states) != expected:
        raise _error(label, "must have exact unique four-state coverage")
    return tuple(states)


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
    relation_warning_filter_fields: tuple[str, ...]
    relation_warning_active_sides: tuple[str, ...]
    relation_presence_active_sides: tuple[str, ...]
    relation_presence_truth_table: tuple[tuple[bool, bool], ...]
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
class RuntimeEngineConformanceScenario:
    """A stable fixture identity and expected protocol outcome."""

    id: str
    semantic: str
    fixture: str
    expected: str


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
    conformance_scenarios: tuple[RuntimeEngineConformanceScenario, ...]


IMPLEMENTED_ENGINE_CONTRACT_PROTOCOL = "supp-slotter.engine-contract/v2"
IMPLEMENTED_ENGINE_RESULT_MODES = frozenset({"exact_assignment"})
IMPLEMENTED_PRESSURE_IDENTITY = ("item_id", "dimension", "value")
IMPLEMENTED_DOMAIN_FEASIBILITY = "unbounded_logical_domain"
IMPLEMENTED_PRIMARY_OBJECTIVE = "maximize_unique_pressure_satisfaction"
IMPLEMENTED_SECONDARY_OBJECTIVE = "minimize_integer_squared_load_per_domain"
IMPLEMENTED_ENGINE_TIE_BREAK = IMPLEMENTED_TIE_BREAK
IMPLEMENTED_PUBLICATION_STATUSES = ("Optimal", "Indeterminate")


@dataclass(frozen=True, slots=True)
class RuntimeWarningTypePolicy:
    id: str
    warning_type: str
    label: str
    action_text: str


@dataclass(frozen=True, slots=True)
class RuntimeConcernCatalogEntry:
    id: str
    concern_kind: str
    warning_type: str


@dataclass(frozen=True, slots=True)
class RuntimeRelationWarningRule:
    id: str
    relation_kind: str
    filter_field: str
    filter_value: str
    active_side: str
    warning_type: str
    reverse_output: bool


@dataclass(frozen=True, slots=True)
class RuntimeRelationPresenceStatusPolicy:
    id: str
    status: str
    source_active: bool
    target_active: bool
    description: str

    @property
    def active_side(self) -> str:
        """Canonical label derived from the strict endpoint truth state."""
        return relation_presence_active_side(self.source_active, self.target_active)


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
    subject: RuntimeFactSubject
    applicability: RuntimeFactApplicability
    provenance: tuple[RuntimeEvidenceProvenance, ...]


@dataclass(frozen=True, slots=True)
class RuntimeFoodEffect(RuntimeCanonicalSchedulingFact):
    value: str


@dataclass(frozen=True, slots=True)
class RuntimeAcuteAlertnessEffect(RuntimeCanonicalSchedulingFact):
    value: str


@dataclass(frozen=True, slots=True)
class RuntimeAcuteSleepEffect(RuntimeCanonicalSchedulingFact):
    value: str


@dataclass(frozen=True, slots=True)
class RuntimePreExercisePerformanceEffect(RuntimeCanonicalSchedulingFact):
    value: str


@dataclass(frozen=True, slots=True)
class RuntimePostExerciseRecoveryEffect(RuntimeCanonicalSchedulingFact):
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
class RuntimeCanonicalFactCatalog:
    """Strict typed view of the authoritative canonical evidence catalog."""

    evidence_sources: tuple[RuntimeEvidenceSource, ...]
    food_effects: tuple[RuntimeFoodEffect, ...]
    acute_alertness_effects: tuple[RuntimeAcuteAlertnessEffect, ...]
    acute_sleep_effects: tuple[RuntimeAcuteSleepEffect, ...]
    pre_exercise_performance_effects: tuple[RuntimePreExercisePerformanceEffect, ...]
    post_exercise_recovery_effects: tuple[RuntimePostExerciseRecoveryEffect, ...]


@dataclass(frozen=True, slots=True)
class RuntimeProgram:
    format_version: str
    schema_version: str
    source_hash: str
    engine_contract: RuntimeEngineContract
    glue_contract: RuntimeGlueContract
    warning_types: tuple[RuntimeWarningTypePolicy, ...]
    concern_catalog: tuple[RuntimeConcernCatalogEntry, ...]
    relation_warning_rules: tuple[RuntimeRelationWarningRule, ...]
    relation_presence_statuses: tuple[RuntimeRelationPresenceStatusPolicy, ...]
    selector_form_capabilities: tuple[RuntimeSelectorFormCapability, ...]
    dashboard_state_catalog: RuntimeDashboardStateCatalog
    canonical_fact_catalog: RuntimeCanonicalFactCatalog
    canonical_laws: tuple[RuntimeCanonicalLaw, ...]

    @property
    def warning_types_by_type(self) -> Mapping[str, RuntimeWarningTypePolicy]:
        return MappingProxyType({item.warning_type: item for item in self.warning_types})

    @property
    def relation_presence_statuses_by_status(self) -> Mapping[str, RuntimeRelationPresenceStatusPolicy]:
        return MappingProxyType({item.status: item for item in self.relation_presence_statuses})

    @property
    def relation_presence_statuses_by_active_side(self) -> Mapping[str, RuntimeRelationPresenceStatusPolicy]:
        return MappingProxyType({item.active_side: item for item in self.relation_presence_statuses})

    @property
    def selector_form_capabilities_by_form(self) -> Mapping[str, RuntimeSelectorFormCapability]:
        return MappingProxyType({item.selector_form: item for item in self.selector_form_capabilities})

    @property
    def concern_warning_catalog_by_kind(self) -> Mapping[str, str]:
        return MappingProxyType({item.concern_kind: item.warning_type for item in self.concern_catalog})


# This is technical dispatch metadata, not an authored domain vocabulary.  The
# compiler imports it to validate the descriptor tree, while the decoder uses
# it to reject silently ignored projection branches and row fields.  Deriving
# record fields from the DTOs keeps the two boundaries closed together when a
# retained runtime field is added or removed.
_PROJECTION_RECORDS: Mapping[str, type[object]] = {
    "engine_contract": RuntimeEngineContract,
    "engine_contract.semantics": RuntimeEngineSemantic,
    "engine_contract.conformance_scenarios": RuntimeEngineConformanceScenario,
    "glue_contract": RuntimeGlueContract,
    "glue_contract.stack_partition": RuntimeStackPartition,
    "warning_types": RuntimeWarningTypePolicy,
    "concern_catalog": RuntimeConcernCatalogEntry,
    "relation_warning_rules": RuntimeRelationWarningRule,
    "relation_presence_statuses": RuntimeRelationPresenceStatusPolicy,
    "selector_form_capabilities": RuntimeSelectorFormCapability,
    "dashboard_state_catalog": RuntimeDashboardStateCatalog,
    "dashboard_state_catalog.usage_states": RuntimeDashboardUsageStateDefinition,
    "dashboard_state_catalog.product_tracking_states": RuntimeDashboardProductTrackingStateDefinition,
    "dashboard_state_catalog.usage_truth_table": RuntimeDashboardUsageTruthState,
    "dashboard_state_catalog.product_tracking_truth_table": RuntimeDashboardProductTrackingTruthState,
    "canonical_fact_catalog": RuntimeCanonicalFactCatalog,
    "canonical_fact_catalog.evidence_sources": RuntimeEvidenceSource,
    "canonical_fact_catalog.food_effects": RuntimeFoodEffect,
    "canonical_fact_catalog.acute_alertness_effects": RuntimeAcuteAlertnessEffect,
    "canonical_fact_catalog.acute_sleep_effects": RuntimeAcuteSleepEffect,
    "canonical_fact_catalog.pre_exercise_performance_effects": RuntimePreExercisePerformanceEffect,
    "canonical_fact_catalog.post_exercise_recovery_effects": RuntimePostExerciseRecoveryEffect,
    "canonical_laws": RuntimeCanonicalLaw,
}
_MAPPING_RECORD_PATHS = frozenset({
    "engine_contract",
    "glue_contract",
    "glue_contract.stack_partition",
    "dashboard_state_catalog",
    "canonical_fact_catalog",
})
RUNTIME_PROJECTION_FIELDS: Mapping[str, frozenset[str]] = MappingProxyType({
    "": frozenset(
        field.name
        for field in fields(RuntimeProgram)
        if field.name not in {"format_version", "schema_version", "source_hash"}
    ),
    **{
        path: frozenset(field.name for field in fields(record))
        for path, record in _PROJECTION_RECORDS.items()
        if path in _MAPPING_RECORD_PATHS
    },
})
RUNTIME_PROJECTION_ROW_FIELDS: Mapping[str, frozenset[str]] = MappingProxyType({
    **{
        path: frozenset(field.name for field in fields(record))
        for path, record in _PROJECTION_RECORDS.items()
        if path not in _MAPPING_RECORD_PATHS
    },
    "glue_contract.relation_presence_truth_table": frozenset({"source_active", "target_active"}),
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


def _engine_scenario(row: Mapping[str, object], label: str) -> RuntimeEngineConformanceScenario:
    return RuntimeEngineConformanceScenario(
        _str(row["id"], f"{label}.id"),
        _str(row["semantic"], f"{label}.semantic"),
        _str(row["fixture"], f"{label}.fixture"),
        _str(row["expected"], f"{label}.expected"),
    )


def _warning_type(row: Mapping[str, object], label: str) -> RuntimeWarningTypePolicy:
    return RuntimeWarningTypePolicy(
        _str(row["id"], f"{label}.id"),
        _str(row["warning_type"], f"{label}.warning_type"),
        _str(row["label"], f"{label}.label"),
        _str(row["action_text"], f"{label}.action_text"),
    )


def _concern_catalog(row: Mapping[str, object], label: str) -> RuntimeConcernCatalogEntry:
    return RuntimeConcernCatalogEntry(
        _str(row["id"], f"{label}.id"),
        _str(row["concern_kind"], f"{label}.concern_kind"),
        _str(row["warning_type"], f"{label}.warning_type"),
    )


def _relation_warning(row: Mapping[str, object], label: str) -> RuntimeRelationWarningRule:
    return RuntimeRelationWarningRule(
        _str(row["id"], f"{label}.id"),
        _str(row["relation_kind"], f"{label}.relation_kind"),
        _str(row["filter_field"], f"{label}.filter_field"),
        _str(row["filter_value"], f"{label}.filter_value"),
        _str(row["active_side"], f"{label}.active_side"),
        _str(row["warning_type"], f"{label}.warning_type"),
        _bool(row["reverse_output"], f"{label}.reverse_output"),
    )


def _presence(row: Mapping[str, object], label: str) -> RuntimeRelationPresenceStatusPolicy:
    return RuntimeRelationPresenceStatusPolicy(
        _str(row["id"], f"{label}.id"),
        _str(row["status"], f"{label}.status"),
        _bool(row["source_active"], f"{label}.source_active"),
        _bool(row["target_active"], f"{label}.target_active"),
        _str(row["description"], f"{label}.description"),
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


_FOOD_EFFECT_VALUES = frozenset({
    "bioavailability_increases",
    "bioavailability_decreases",
    "tolerability_improves",
    "tolerability_worsens",
})
_ACUTE_ALERTNESS_EFFECT_VALUES = frozenset({"acute_alertness_increases"})
_ACUTE_SLEEP_EFFECT_VALUES = frozenset({"onset_latency_decreases", "continuity_improves"})
_PRE_EXERCISE_PERFORMANCE_EFFECT_VALUES = frozenset({"performance_improves"})
_POST_EXERCISE_RECOVERY_EFFECT_VALUES = frozenset({"recovery_improves"})


def _canonical_fact(
    row: Mapping[str, object],
    label: str,
    factory: Callable[
        [str, RuntimeFactSubject, RuntimeFactApplicability, tuple[RuntimeEvidenceProvenance, ...], str], object
    ],
    values: frozenset[str],
) -> object:
    return factory(
        _str(row["id"], f"{label}.id"),
        _fact_subject(row["subject"], f"{label}.subject"),
        _fact_applicability(row["applicability"], f"{label}.applicability"),
        _fact_provenance(row["provenance"], f"{label}.provenance"),
        _closed_value(row["value"], f"{label}.value", values),
    )


def _food_effect(row: Mapping[str, object], label: str) -> RuntimeFoodEffect:
    return cast(RuntimeFoodEffect, _canonical_fact(row, label, RuntimeFoodEffect, _FOOD_EFFECT_VALUES))


def _acute_alertness_effect(row: Mapping[str, object], label: str) -> RuntimeAcuteAlertnessEffect:
    return cast(
        RuntimeAcuteAlertnessEffect,
        _canonical_fact(row, label, RuntimeAcuteAlertnessEffect, _ACUTE_ALERTNESS_EFFECT_VALUES),
    )


def _acute_sleep_effect(row: Mapping[str, object], label: str) -> RuntimeAcuteSleepEffect:
    return cast(
        RuntimeAcuteSleepEffect, _canonical_fact(row, label, RuntimeAcuteSleepEffect, _ACUTE_SLEEP_EFFECT_VALUES)
    )


def _pre_exercise_performance_effect(row: Mapping[str, object], label: str) -> RuntimePreExercisePerformanceEffect:
    return cast(
        RuntimePreExercisePerformanceEffect,
        _canonical_fact(row, label, RuntimePreExercisePerformanceEffect, _PRE_EXERCISE_PERFORMANCE_EFFECT_VALUES),
    )


def _post_exercise_recovery_effect(row: Mapping[str, object], label: str) -> RuntimePostExerciseRecoveryEffect:
    return cast(
        RuntimePostExerciseRecoveryEffect,
        _canonical_fact(row, label, RuntimePostExerciseRecoveryEffect, _POST_EXERCISE_RECOVERY_EFFECT_VALUES),
    )


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


def _canonical_laws(value: object, label: str = "canonical_laws") -> tuple[RuntimeCanonicalLaw, ...]:
    rows = _rows(value, label)
    result = tuple(_canonical_law(row, f"{label}[{index}]") for index, row in enumerate(rows))
    if len(result) != 9:
        raise _error(label, "must contain exactly nine laws")
    keys = [(law.family, law.fact_value) for law in result]
    if len(keys) != len(set(keys)):
        raise _error(label, "has duplicate semantic keys (family, fact_value)")
    expected_keys = frozenset({
        ("FoodEffect", "bioavailability_increases"),
        ("FoodEffect", "bioavailability_decreases"),
        ("FoodEffect", "tolerability_improves"),
        ("FoodEffect", "tolerability_worsens"),
        ("AcuteAlertnessEffect", "acute_alertness_increases"),
        ("AcuteSleepEffect", "onset_latency_decreases"),
        ("AcuteSleepEffect", "continuity_improves"),
        ("PreExercisePerformanceEffect", "performance_improves"),
        ("PostExerciseRecoveryEffect", "recovery_improves"),
    })
    if frozenset(keys) != expected_keys:
        raise _error(label, "does not cover the exact nine admitted family/value laws")
    return result


def _canonical_fact_catalog(value: object, label: str = "canonical_fact_catalog") -> RuntimeCanonicalFactCatalog:
    catalog = _exact_map(value, label, RUNTIME_PROJECTION_FIELDS[label])
    evidence_sources = _typed_rows(
        catalog["evidence_sources"],
        f"{label}.evidence_sources",
        _evidence_source,
        semantic_keys=(("id",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS[f"{label}.evidence_sources"],
    )
    food_effects = _typed_rows(
        catalog["food_effects"],
        f"{label}.food_effects",
        _food_effect,
        semantic_keys=(("id",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS[f"{label}.food_effects"],
    )
    acute_alertness_effects = _typed_rows(
        catalog["acute_alertness_effects"],
        f"{label}.acute_alertness_effects",
        _acute_alertness_effect,
        semantic_keys=(("id",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS[f"{label}.acute_alertness_effects"],
    )
    acute_sleep_effects = _typed_rows(
        catalog["acute_sleep_effects"],
        f"{label}.acute_sleep_effects",
        _acute_sleep_effect,
        semantic_keys=(("id",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS[f"{label}.acute_sleep_effects"],
    )
    pre_exercise_performance_effects = _typed_rows(
        catalog["pre_exercise_performance_effects"],
        f"{label}.pre_exercise_performance_effects",
        _pre_exercise_performance_effect,
        semantic_keys=(("id",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS[f"{label}.pre_exercise_performance_effects"],
    )
    post_exercise_recovery_effects = _typed_rows(
        catalog["post_exercise_recovery_effects"],
        f"{label}.post_exercise_recovery_effects",
        _post_exercise_recovery_effect,
        semantic_keys=(("id",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS[f"{label}.post_exercise_recovery_effects"],
    )
    families = (
        food_effects,
        acute_alertness_effects,
        acute_sleep_effects,
        pre_exercise_performance_effects,
        post_exercise_recovery_effects,
    )
    fact_ids = [fact.id for family in families for fact in family]
    if len(fact_ids) != len(set(fact_ids)):
        raise _error(label, "has duplicate fact IDs across effect families")
    return RuntimeCanonicalFactCatalog(
        cast(tuple[RuntimeEvidenceSource, ...], evidence_sources),
        cast(tuple[RuntimeFoodEffect, ...], food_effects),
        cast(tuple[RuntimeAcuteAlertnessEffect, ...], acute_alertness_effects),
        cast(tuple[RuntimeAcuteSleepEffect, ...], acute_sleep_effects),
        cast(tuple[RuntimePreExercisePerformanceEffect, ...], pre_exercise_performance_effects),
        cast(tuple[RuntimePostExerciseRecoveryEffect, ...], post_exercise_recovery_effects),
    )


def _validate_relation_presence_statuses(
    truth: tuple[tuple[bool, bool], ...], statuses: Sequence[RuntimeRelationPresenceStatusPolicy]
) -> None:
    actual = {(row.source_active, row.target_active) for row in statuses}
    if actual != set(truth):
        raise _error(
            "relation_presence_statuses",
            "must have exact unique coverage matching glue_contract.relation_presence_truth_table",
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
    projection = _exact_map(root.get("projection"), "projection", RUNTIME_PROJECTION_FIELDS[""])
    return (
        _str(root["format_version"], "format_version"),
        _str(root["schema_version"], "schema_version"),
        _str(root["source_hash"], "source_hash"),
        projection,
    )


def _validate_engine_scenario_coverage(
    semantic_ids: set[str], scenarios: Sequence[RuntimeEngineConformanceScenario]
) -> None:
    scenario_semantics = {row.semantic for row in scenarios}
    missing_scenario_semantics = sorted(semantic_ids - scenario_semantics)
    if missing_scenario_semantics:
        raise _error(
            "engine_contract.conformance_scenarios",
            "missing semantic coverage: " + ", ".join(missing_scenario_semantics),
        )


def _decode_engine_contract(projection: Mapping[str, object]) -> RuntimeEngineContract:
    """Decode and verify the closed exact-optimizer protocol section."""
    engine_raw = _exact_map(
        projection.get("engine_contract"),
        "engine_contract",
        RUNTIME_PROJECTION_FIELDS["engine_contract"],
    )
    engine_semantics = _typed_rows(
        engine_raw["semantics"],
        "engine_contract.semantics",
        _engine_semantic,
        semantic_keys=(("id",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["engine_contract.semantics"],
    )
    engine_scenarios = _typed_rows(
        engine_raw["conformance_scenarios"],
        "engine_contract.conformance_scenarios",
        _engine_scenario,
        semantic_keys=(("id",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["engine_contract.conformance_scenarios"],
    )
    if not engine_semantics or not engine_scenarios:
        raise _error("engine_contract", "requires non-empty semantics and conformance_scenarios")
    semantic_ids = {row.id for row in engine_semantics}
    unknown_scenario_semantics = sorted({row.semantic for row in engine_scenarios} - semantic_ids)
    if unknown_scenario_semantics:
        raise _error(
            "engine_contract.conformance_scenarios",
            "references unknown semantics: " + ", ".join(unknown_scenario_semantics),
        )
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
        cast(tuple[RuntimeEngineConformanceScenario, ...], engine_scenarios),
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
    _validate_engine_scenario_coverage(semantic_ids, engine_scenarios)
    return engine_contract


def _decode_glue_contract(
    projection: Mapping[str, object],
) -> tuple[RuntimeGlueContract, tuple[tuple[bool, bool], ...]]:
    """Decode the executable integration capability and partition section."""
    glue_raw = _exact_map(projection.get("glue_contract"), "glue_contract", RUNTIME_PROJECTION_FIELDS["glue_contract"])
    truth = _truth_table(
        glue_raw.get("relation_presence_truth_table"),
        "glue_contract.relation_presence_truth_table",
    )
    partition_raw = _exact_map(
        glue_raw["stack_partition"],
        "glue_contract.stack_partition",
        RUNTIME_PROJECTION_FIELDS["glue_contract.stack_partition"],
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
        _strings(glue_raw["relation_warning_filter_fields"], "glue_contract.relation_warning_filter_fields"),
        _strings(glue_raw["relation_warning_active_sides"], "glue_contract.relation_warning_active_sides"),
        _strings(glue_raw["relation_presence_active_sides"], "glue_contract.relation_presence_active_sides"),
        truth,
        _strings(glue_raw["relation_endpoint_selector_kinds"], "glue_contract.relation_endpoint_selector_kinds"),
        _strings(glue_raw["relation_selector_forms"], "glue_contract.relation_selector_forms"),
    )
    glue_capabilities: Mapping[str, tuple[str, ...]] = {
        "relation_warning_filter_fields": glue.relation_warning_filter_fields,
        "relation_warning_active_sides": glue.relation_warning_active_sides,
        "relation_presence_active_sides": glue.relation_presence_active_sides,
        "relation_endpoint_selector_kinds": glue.relation_endpoint_selector_kinds,
        "relation_selector_forms": glue.relation_selector_forms,
    }
    for field_name, expected in IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS.items():
        if field_name not in glue_capabilities:
            continue
        actual = glue_capabilities[field_name]
        if actual != expected:
            raise _error(f"glue_contract.{field_name}", "must exactly match executable capabilities")
    return glue, truth


def _decode_relation_review_catalog(
    projection: Mapping[str, object], truth: tuple[tuple[bool, bool], ...]
) -> tuple[
    tuple[RuntimeWarningTypePolicy, ...],
    tuple[RuntimeConcernCatalogEntry, ...],
    tuple[RuntimeRelationWarningRule, ...],
    tuple[RuntimeRelationPresenceStatusPolicy, ...],
    tuple[RuntimeSelectorFormCapability, ...],
]:
    """Decode review vocabulary that is independent of canonical scheduling facts."""
    warning_types = _typed_rows(
        projection["warning_types"],
        "warning_types",
        _warning_type,
        semantic_keys=(("warning_type",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["warning_types"],
    )
    concern_catalog = _typed_rows(
        projection["concern_catalog"],
        "concern_catalog",
        _concern_catalog,
        semantic_keys=(("concern_kind",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["concern_catalog"],
    )
    relation_warning_rules = _typed_rows(
        projection["relation_warning_rules"],
        "relation_warning_rules",
        _relation_warning,
        semantic_keys=(("relation_kind", "filter_field", "filter_value", "active_side", "reverse_output"),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["relation_warning_rules"],
    )
    relation_presence_statuses = _typed_rows(
        projection["relation_presence_statuses"],
        "relation_presence_statuses",
        _presence,
        semantic_keys=(("status",), ("source_active", "target_active")),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["relation_presence_statuses"],
    )
    _validate_relation_presence_statuses(truth, relation_presence_statuses)
    selector_form_capabilities = _typed_rows(
        projection["selector_form_capabilities"],
        "selector_form_capabilities",
        _selector_form_capability,
        semantic_keys=(("selector_form",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["selector_form_capabilities"],
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
    return (
        cast(tuple[RuntimeWarningTypePolicy, ...], warning_types),
        cast(tuple[RuntimeConcernCatalogEntry, ...], concern_catalog),
        cast(tuple[RuntimeRelationWarningRule, ...], relation_warning_rules),
        cast(tuple[RuntimeRelationPresenceStatusPolicy, ...], relation_presence_statuses),
        cast(tuple[RuntimeSelectorFormCapability, ...], selector_form_capabilities),
    )


def _decode_dashboard_state_catalog(projection: Mapping[str, object]) -> RuntimeDashboardStateCatalog:
    """Decode the complete dashboard state vocabulary and truth tables."""
    dashboard_catalog = _exact_map(
        projection.get("dashboard_state_catalog"),
        "dashboard_state_catalog",
        RUNTIME_PROJECTION_FIELDS["dashboard_state_catalog"],
    )
    usage_states = _typed_rows(
        dashboard_catalog["usage_states"],
        "dashboard_state_catalog.usage_states",
        _dashboard_usage_state,
        semantic_keys=(("state",), ("order",)),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["dashboard_state_catalog.usage_states"],
    )
    product_tracking_states = _typed_rows(
        dashboard_catalog["product_tracking_states"],
        "dashboard_state_catalog.product_tracking_states",
        _dashboard_product_tracking_state,
        semantic_keys=(("state",), ("order",)),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["dashboard_state_catalog.product_tracking_states"],
    )
    usage_truth_table = _typed_rows(
        dashboard_catalog["usage_truth_table"],
        "dashboard_state_catalog.usage_truth_table",
        _dashboard_usage_truth_state,
        semantic_keys=(("active_stack_membership", "inactive_stack_membership", "tracked_product_presence"),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["dashboard_state_catalog.usage_truth_table"],
    )
    product_tracking_truth_table = _typed_rows(
        dashboard_catalog["product_tracking_truth_table"],
        "dashboard_state_catalog.product_tracking_truth_table",
        _dashboard_tracking_truth_state,
        semantic_keys=(("tracked_product_presence",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["dashboard_state_catalog.product_tracking_truth_table"],
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
    engine_contract = _decode_engine_contract(projection)
    glue_contract, presence_truth_table = _decode_glue_contract(projection)
    (
        warning_types,
        concern_catalog,
        relation_warning_rules,
        relation_presence_statuses,
        selector_form_capabilities,
    ) = _decode_relation_review_catalog(projection, presence_truth_table)
    dashboard_state_catalog = _decode_dashboard_state_catalog(projection)
    canonical_fact_catalog = _canonical_fact_catalog(projection["canonical_fact_catalog"])
    canonical_laws = _canonical_laws(projection["canonical_laws"])
    return RuntimeProgram(
        format_version,
        schema_version,
        source_hash,
        engine_contract,
        glue_contract,
        warning_types,
        concern_catalog,
        relation_warning_rules,
        relation_presence_statuses,
        selector_form_capabilities,
        dashboard_state_catalog,
        canonical_fact_catalog,
        canonical_laws,
    )


def relation_presence_policy_for_active_side(
    active_side: str,
    relation_presence_by_active_side: Mapping[str, RuntimeRelationPresenceStatusPolicy],
) -> RuntimeRelationPresenceStatusPolicy:
    try:
        return relation_presence_by_active_side[active_side]
    except KeyError as error:
        raise ValueError(f"unknown relation active side {active_side!r}") from error
