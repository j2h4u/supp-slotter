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

IMPLEMENTED_OBJECTIVE_FUNCTION = "slot_score_plus_prefer_with_minus_quadratic_balance_penalty"
IMPLEMENTED_BALANCE_PENALTY_EXPRESSION = "balance_weight * sum(slot_count^2)"
IMPLEMENTED_TIE_BREAK = "stable_slot_order"
IMPLEMENTED_AGGREGATION_MODE = "sum_unique_component_assignments"
SUPPORTED_GROOMING_ELIGIBILITY = "active_reachable_substance_without_semantic_enrichment_attempt"
SUPPORTED_GROOMING_METRICS = frozenset({"active_unique_product_count", "total_unique_product_count"})


def _error(label: str, message: str) -> OntologyInfrastructureError:
    return OntologyInfrastructureError(f"runtime program {label} {message}", code=MALFORMED)


def _validate_effect_scoring_interlock(effect_scoring: RuntimeEffectScoring) -> None:
    """Fail while decoding when the compiled ontology requests unsupported search math."""
    if (
        effect_scoring.aggregation_mode != IMPLEMENTED_AGGREGATION_MODE
        or effect_scoring.objective_function != IMPLEMENTED_OBJECTIVE_FUNCTION
        or effect_scoring.balance_penalty_expression != IMPLEMENTED_BALANCE_PENALTY_EXPRESSION
        or effect_scoring.tie_break != IMPLEMENTED_TIE_BREAK
    ):
        raise _error(
            "effect_scoring",
            "declares an objective not implemented by planner search: "
            f"objective_function={effect_scoring.objective_function!r}, "
            f"aggregation_mode={effect_scoring.aggregation_mode!r}, "
            f"balance_penalty_expression={effect_scoring.balance_penalty_expression!r}, "
            f"tie_break={effect_scoring.tie_break!r}",
        )


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


def _number(value: object, label: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error(label, "must be a number")
    return value


def _nonnegative_number(value: object, label: str) -> float | int:
    result = _number(value, label)
    if result < 0:
        raise _error(label, "must be a non-negative number")
    return result


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
class RuntimeGlueContract:
    id: str
    inactive_stack_name: str
    source_kinds: tuple[str, ...]
    source_kind_roles: tuple[str, ...]
    relation_warning_filter_fields: tuple[str, ...]
    relation_warning_active_sides: tuple[str, ...]
    relation_presence_active_sides: tuple[str, ...]
    relation_presence_truth_table: tuple[tuple[bool, bool], ...]
    relation_endpoint_selector_kinds: tuple[str, ...]
    relation_selector_forms: tuple[str, ...]
    warning_emitter_ids: tuple[str, ...]
    prefer_with_source_fields: tuple[str, ...]
    prefer_with_target_resolutions: tuple[str, ...]
    prefer_with_pair_modes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeSourceKindValuePolicy:
    id: str
    source_kind: str
    applies_to: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeEffectMatchDimension:
    id: str
    key: str
    slot_field: str
    value_type: str


@dataclass(frozen=True, slots=True)
class RuntimeAssignmentAxis:
    id: str
    axis: str
    order: int
    assignment_source: str
    assignment_field: str
    minimum_cardinality: int
    maximum_cardinality: int | None


@dataclass(frozen=True, slots=True)
class RuntimeEffectScore:
    id: str
    level: str
    score: float | int


@dataclass(frozen=True, slots=True)
class RuntimeEffectScoring:
    id: str
    aggregation_mode: str
    scores: tuple[RuntimeEffectScore, ...]
    objective_function: str
    balance_penalty_expression: str
    tie_break: str
    balance_weight: float | int
    prefer_with_bonus: int

    @property
    def scores_by_level(self) -> Mapping[str, RuntimeEffectScore]:
        return MappingProxyType({row.level: row for row in self.scores})


@dataclass(frozen=True, slots=True)
class RuntimePreferWithPolicy:
    id: str
    source_field: str
    target_resolution: str
    pair_mode: str


@dataclass(frozen=True, slots=True)
class RuntimeSemanticEnrichmentGroomingPolicy:
    id: str
    eligibility: str
    roi_order_desc: tuple[str, ...]
    default_batch_size: int


@dataclass(frozen=True, slots=True)
class RuntimeConstraintExecutionPolicy:
    id: str
    operation: str
    match_direction: str
    aggregation: str
    selector_resolution: str
    blocks_slots: bool
    scores_advisory: bool
    score_delta: int


@dataclass(frozen=True, slots=True)
class RuntimeWarningTypePolicy:
    id: str
    warning_type: str
    label: str
    action_text: str


@dataclass(frozen=True, slots=True)
class RuntimeWarningEmitterPolicy:
    id: str
    emitter: str
    warning_type: str
    default_message: str


@dataclass(frozen=True, slots=True)
class RuntimeWarningTraitAction:
    id: str
    trait_id: str
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
class RuntimeProgram:
    format_version: str
    schema_version: str
    source_hash: str
    glue_contract: RuntimeGlueContract
    source_kind_values: tuple[RuntimeSourceKindValuePolicy, ...]
    assignment_axes: tuple[RuntimeAssignmentAxis, ...]
    slot_near_values: tuple[str, ...]
    effect_match_dimensions: tuple[RuntimeEffectMatchDimension, ...]
    effect_scoring: RuntimeEffectScoring
    prefer_with_policy: RuntimePreferWithPolicy
    constraint_execution_policies: tuple[RuntimeConstraintExecutionPolicy, ...]
    warning_types: tuple[RuntimeWarningTypePolicy, ...]
    warning_emitters: tuple[RuntimeWarningEmitterPolicy, ...]
    warning_trait_actions: tuple[RuntimeWarningTraitAction, ...]
    concern_catalog: tuple[RuntimeConcernCatalogEntry, ...]
    relation_warning_rules: tuple[RuntimeRelationWarningRule, ...]
    relation_presence_statuses: tuple[RuntimeRelationPresenceStatusPolicy, ...]
    selector_form_capabilities: tuple[RuntimeSelectorFormCapability, ...]
    dashboard_state_catalog: RuntimeDashboardStateCatalog
    semantic_enrichment_grooming: RuntimeSemanticEnrichmentGroomingPolicy

    @property
    def effect_score_levels(self) -> frozenset[str]:
        return frozenset(item.level for item in self.effect_scoring.scores)

    @property
    def effect_match_dimensions_by_key(self) -> Mapping[str, RuntimeEffectMatchDimension]:
        return MappingProxyType({item.key: item for item in self.effect_match_dimensions})

    @property
    def warning_types_by_type(self) -> Mapping[str, RuntimeWarningTypePolicy]:
        return MappingProxyType({item.warning_type: item for item in self.warning_types})

    @property
    def warning_emitters_by_emitter(self) -> Mapping[str, RuntimeWarningEmitterPolicy]:
        return MappingProxyType({item.emitter: item for item in self.warning_emitters})

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
    def warning_trait_actions_by_trait(self) -> Mapping[str, RuntimeWarningTraitAction]:
        return MappingProxyType({item.trait_id: item for item in self.warning_trait_actions})

    @property
    def concern_warning_catalog_by_kind(self) -> Mapping[str, str]:
        return MappingProxyType({item.concern_kind: item.warning_type for item in self.concern_catalog})

    def constraint_execution_policy_for(self, operation: str) -> RuntimeConstraintExecutionPolicy | None:
        return next((item for item in self.constraint_execution_policies if item.operation == operation), None)


# This is technical dispatch metadata, not an authored domain vocabulary.  The
# compiler imports it to validate the descriptor tree, while the decoder uses
# it to reject silently ignored projection branches and row fields.  Deriving
# record fields from the DTOs keeps the two boundaries closed together when a
# retained runtime field is added or removed.
_PROJECTION_RECORDS: Mapping[str, type[object]] = {
    "glue_contract": RuntimeGlueContract,
    "effect_scoring": RuntimeEffectScoring,
    "prefer_with_policy": RuntimePreferWithPolicy,
    "semantic_enrichment_grooming": RuntimeSemanticEnrichmentGroomingPolicy,
    "source_kind_values": RuntimeSourceKindValuePolicy,
    "assignment_axes": RuntimeAssignmentAxis,
    "effect_match_dimensions": RuntimeEffectMatchDimension,
    "effect_scoring.scores": RuntimeEffectScore,
    "constraint_execution_policies": RuntimeConstraintExecutionPolicy,
    "warning_types": RuntimeWarningTypePolicy,
    "warning_emitters": RuntimeWarningEmitterPolicy,
    "warning_trait_actions": RuntimeWarningTraitAction,
    "concern_catalog": RuntimeConcernCatalogEntry,
    "relation_warning_rules": RuntimeRelationWarningRule,
    "relation_presence_statuses": RuntimeRelationPresenceStatusPolicy,
    "selector_form_capabilities": RuntimeSelectorFormCapability,
    "dashboard_state_catalog": RuntimeDashboardStateCatalog,
    "dashboard_state_catalog.usage_states": RuntimeDashboardUsageStateDefinition,
    "dashboard_state_catalog.product_tracking_states": RuntimeDashboardProductTrackingStateDefinition,
    "dashboard_state_catalog.usage_truth_table": RuntimeDashboardUsageTruthState,
    "dashboard_state_catalog.product_tracking_truth_table": RuntimeDashboardProductTrackingTruthState,
}
_MAPPING_RECORD_PATHS = frozenset(
    {"glue_contract", "effect_scoring", "prefer_with_policy", "semantic_enrichment_grooming", "dashboard_state_catalog"}
)
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


def _source_kind(row: Mapping[str, object], label: str) -> RuntimeSourceKindValuePolicy:
    return RuntimeSourceKindValuePolicy(
        _str(row["id"], f"{label}.id"),
        _str(row["source_kind"], f"{label}.source_kind"),
        _strings(row["applies_to"], f"{label}.applies_to"),
    )


def _axis(row: Mapping[str, object], label: str) -> RuntimeAssignmentAxis:
    minimum = _cardinality(row.get("minimum_cardinality", 0), f"{label}.minimum_cardinality")
    maximum = _cardinality(row.get("maximum_cardinality", 1), f"{label}.maximum_cardinality")
    if minimum is None:
        minimum = 0
    if maximum is not None and minimum > maximum:
        raise _error(label, "minimum_cardinality exceeds maximum_cardinality")
    return RuntimeAssignmentAxis(
        _str(row["id"], f"{label}.id"),
        _str(row["axis"], f"{label}.axis"),
        _int(row["order"], f"{label}.order"),
        _str(row["assignment_source"], f"{label}.assignment_source"),
        _str(row["assignment_field"], f"{label}.assignment_field"),
        minimum,
        maximum,
    )


def axis_cardinality_violation(axis: RuntimeAssignmentAxis, count: int) -> str | None:
    """Return a diagnostic when an assertion count violates one axis."""
    if count < axis.minimum_cardinality:
        return f"requires at least {axis.minimum_cardinality} value(s), got {count}"
    if axis.maximum_cardinality is not None and count > axis.maximum_cardinality:
        return f"allows at most {axis.maximum_cardinality} value(s), got {count}"
    return None


def _dimension(row: Mapping[str, object], label: str) -> RuntimeEffectMatchDimension:
    return RuntimeEffectMatchDimension(
        _str(row["id"], f"{label}.id"),
        _str(row["key"], f"{label}.key"),
        _str(row["slot_field"], f"{label}.slot_field"),
        _str(row["value_type"], f"{label}.value_type"),
    )


def _semantic_enrichment_grooming(
    row: Mapping[str, object], label: str
) -> RuntimeSemanticEnrichmentGroomingPolicy:
    eligibility = _str(row["eligibility"], f"{label}.eligibility")
    if eligibility != SUPPORTED_GROOMING_ELIGIBILITY:
        raise _error(f"{label}.eligibility", f"unsupported eligibility {eligibility!r}")
    metrics = _strings(row["roi_order_desc"], f"{label}.roi_order_desc")
    if not metrics:
        raise _error(f"{label}.roi_order_desc", "must be non-empty")
    if any(metric not in SUPPORTED_GROOMING_METRICS for metric in metrics):
        raise _error(f"{label}.roi_order_desc", "contains an unsupported metric")
    batch_size = _int(row["default_batch_size"], f"{label}.default_batch_size")
    if batch_size <= 0:
        raise _error(f"{label}.default_batch_size", "must be positive")
    return RuntimeSemanticEnrichmentGroomingPolicy(
        _str(row["id"], f"{label}.id"), eligibility, metrics, batch_size
    )


def _policy(row: Mapping[str, object], label: str) -> RuntimeConstraintExecutionPolicy:
    return RuntimeConstraintExecutionPolicy(
        _str(row["id"], f"{label}.id"),
        _str(row["operation"], f"{label}.operation"),
        _str(row["match_direction"], f"{label}.match_direction"),
        _str(row["aggregation"], f"{label}.aggregation"),
        _str(row["selector_resolution"], f"{label}.selector_resolution"),
        _bool(row["blocks_slots"], f"{label}.blocks_slots"),
        _bool(row["scores_advisory"], f"{label}.scores_advisory"),
        _int(row["score_delta"], f"{label}.score_delta"),
    )


def _score(row: Mapping[str, object], label: str) -> RuntimeEffectScore:
    return RuntimeEffectScore(
        _str(row["id"], f"{label}.id"), _str(row["level"], f"{label}.level"), _number(row["score"], f"{label}.score")
    )


def _warning_type(row: Mapping[str, object], label: str) -> RuntimeWarningTypePolicy:
    return RuntimeWarningTypePolicy(
        _str(row["id"], f"{label}.id"),
        _str(row["warning_type"], f"{label}.warning_type"),
        _str(row["label"], f"{label}.label"),
        _str(row["action_text"], f"{label}.action_text"),
    )


def _warning_emitter(row: Mapping[str, object], label: str) -> RuntimeWarningEmitterPolicy:
    return RuntimeWarningEmitterPolicy(
        _str(row["id"], f"{label}.id"),
        _str(row["emitter"], f"{label}.emitter"),
        _str(row["warning_type"], f"{label}.warning_type"),
        _str(row["default_message"], f"{label}.default_message"),
    )


def _warning_trait(row: Mapping[str, object], label: str) -> RuntimeWarningTraitAction:
    return RuntimeWarningTraitAction(
        _str(row["id"], f"{label}.id"),
        _str(row["trait_id"], f"{label}.trait_id"),
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
    for label, definitions in (
        ("usage_states", catalog.usage_states),
        ("product_tracking_states", catalog.product_tracking_states),
    ):
        if not definitions:
            raise _error(f"dashboard_state_catalog.{label}", "must be non-empty")
        if len({row.state for row in definitions}) != len(definitions):
            raise _error(f"dashboard_state_catalog.{label}", "must not duplicate state enums")
        if len({row.label for row in definitions}) != len(definitions):
            raise _error(f"dashboard_state_catalog.{label}", "must not duplicate state labels")
        orders = [row.order for row in definitions]
        if len(set(orders)) != len(orders) or set(orders) != set(range(len(orders))):
            raise _error(f"dashboard_state_catalog.{label}", "must have unique contiguous order values")
    usage_states = set(catalog.usage_states_by_state)
    usage_keys = {
        (row.active_stack_membership, row.inactive_stack_membership, row.tracked_product_presence)
        for row in catalog.usage_truth_table
    }
    expected_usage_keys = {
        (active, inactive, tracked)
        for active in (False, True)
        for inactive in (False, True)
        for tracked in (False, True)
    }
    if usage_keys != expected_usage_keys or len(catalog.usage_truth_table) != len(expected_usage_keys):
        raise _error(
            "dashboard_state_catalog.usage_truth_table",
            "must have exact unique coverage of active, inactive, and tracked booleans",
        )
    if any(row.state not in usage_states for row in catalog.usage_truth_table):
        raise _error("dashboard_state_catalog.usage_truth_table", "references an unknown usage state")
    if {row.state for row in catalog.usage_truth_table} != usage_states:
        raise _error("dashboard_state_catalog.usage_truth_table", "must cover every usage state")
    tracking_states = set(catalog.product_tracking_states_by_state)
    tracking_keys = {row.tracked_product_presence for row in catalog.product_tracking_truth_table}
    if tracking_keys != {False, True} or len(catalog.product_tracking_truth_table) != 2:
        raise _error(
            "dashboard_state_catalog.product_tracking_truth_table",
            "must have exact unique false/true coverage",
        )
    if any(row.state not in tracking_states for row in catalog.product_tracking_truth_table):
        raise _error(
            "dashboard_state_catalog.product_tracking_truth_table",
            "references an unknown product-tracking state",
        )
    if {row.state for row in catalog.product_tracking_truth_table} != tracking_states:
        raise _error(
            "dashboard_state_catalog.product_tracking_truth_table",
            "must cover every product-tracking state",
        )


def decode_runtime_program(payload: Mapping[str, object]) -> RuntimeProgram:
    """Decode a compiler-verified runtime snapshot."""
    root = _map(payload, "")
    expected_root = {"format_version", "schema_version", "source_hash", "provenance", "projection"}
    if set(root) != expected_root:
        raise _error("", "has an invalid top-level shape")
    projection = _exact_map(root.get("projection"), "projection", RUNTIME_PROJECTION_FIELDS[""])
    glue_raw = _exact_map(projection.get("glue_contract"), "glue_contract", RUNTIME_PROJECTION_FIELDS["glue_contract"])
    truth = _truth_table(
        glue_raw.get("relation_presence_truth_table"),
        "glue_contract.relation_presence_truth_table",
    )
    glue = RuntimeGlueContract(
        _str(glue_raw["id"], "glue_contract.id"),
        _str(glue_raw["inactive_stack_name"], "glue_contract.inactive_stack_name"),
        _strings(glue_raw["source_kinds"], "glue_contract.source_kinds"),
        _strings(glue_raw["source_kind_roles"], "glue_contract.source_kind_roles"),
        _strings(glue_raw["relation_warning_filter_fields"], "glue_contract.relation_warning_filter_fields"),
        _strings(glue_raw["relation_warning_active_sides"], "glue_contract.relation_warning_active_sides"),
        _strings(glue_raw["relation_presence_active_sides"], "glue_contract.relation_presence_active_sides"),
        truth,
        _strings(glue_raw["relation_endpoint_selector_kinds"], "glue_contract.relation_endpoint_selector_kinds"),
        _strings(glue_raw["relation_selector_forms"], "glue_contract.relation_selector_forms"),
        _strings(glue_raw["warning_emitter_ids"], "glue_contract.warning_emitter_ids"),
        _strings(glue_raw["prefer_with_source_fields"], "glue_contract.prefer_with_source_fields"),
        _strings(glue_raw["prefer_with_target_resolutions"], "glue_contract.prefer_with_target_resolutions"),
        _strings(glue_raw["prefer_with_pair_modes"], "glue_contract.prefer_with_pair_modes"),
    )
    glue_capabilities: Mapping[str, tuple[str, ...]] = {
        "source_kind_roles": glue.source_kind_roles,
        "relation_warning_filter_fields": glue.relation_warning_filter_fields,
        "relation_warning_active_sides": glue.relation_warning_active_sides,
        "relation_presence_active_sides": glue.relation_presence_active_sides,
        "relation_endpoint_selector_kinds": glue.relation_endpoint_selector_kinds,
        "relation_selector_forms": glue.relation_selector_forms,
        "warning_emitter_ids": glue.warning_emitter_ids,
        "prefer_with_source_fields": glue.prefer_with_source_fields,
        "prefer_with_target_resolutions": glue.prefer_with_target_resolutions,
        "prefer_with_pair_modes": glue.prefer_with_pair_modes,
    }
    for field_name, expected in IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS.items():
        actual = glue_capabilities[field_name]
        if actual != expected:
            raise _error(f"glue_contract.{field_name}", "must exactly match executable capabilities")
    scoring = _exact_map(
        projection.get("effect_scoring"), "effect_scoring", RUNTIME_PROJECTION_FIELDS["effect_scoring"]
    )
    scoring_obj = RuntimeEffectScoring(
        _str(scoring["id"], "effect_scoring.id"),
        _str(scoring["aggregation_mode"], "effect_scoring.aggregation_mode"),
        cast(
            tuple[RuntimeEffectScore, ...],
            _typed_rows(
                scoring["scores"],
                "effect_scoring.scores",
                _score,
                semantic_keys=(("level",),),
                fields=RUNTIME_PROJECTION_ROW_FIELDS["effect_scoring.scores"],
            ),
        ),
        _str(scoring["objective_function"], "effect_scoring.objective_function"),
        _str(scoring["balance_penalty_expression"], "effect_scoring.balance_penalty_expression"),
        _str(scoring["tie_break"], "effect_scoring.tie_break"),
        _nonnegative_number(scoring["balance_weight"], "effect_scoring.balance_weight"),
        _nonnegative_int(scoring["prefer_with_bonus"], "effect_scoring.prefer_with_bonus"),
    )
    _validate_effect_scoring_interlock(scoring_obj)
    prefer = _exact_map(
        projection.get("prefer_with_policy"),
        "prefer_with_policy",
        RUNTIME_PROJECTION_FIELDS["prefer_with_policy"],
    )
    prefer_obj = RuntimePreferWithPolicy(
        _str(prefer["id"], "prefer_with_policy.id"),
        _str(prefer["source_field"], "prefer_with_policy.source_field"),
        _str(prefer["target_resolution"], "prefer_with_policy.target_resolution"),
        _str(prefer["pair_mode"], "prefer_with_policy.pair_mode"),
    )
    grooming = _exact_map(
        projection.get("semantic_enrichment_grooming"),
        "semantic_enrichment_grooming",
        RUNTIME_PROJECTION_FIELDS["semantic_enrichment_grooming"],
    )
    grooming_obj = _semantic_enrichment_grooming(grooming, "semantic_enrichment_grooming")
    source_kind_values = _typed_rows(
        projection["source_kind_values"],
        "source_kind_values",
        _source_kind,
        semantic_keys=(("source_kind",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["source_kind_values"],
    )
    assignment_axes = _typed_rows(
        projection["assignment_axes"],
        "assignment_axes",
        _axis,
        semantic_keys=(("axis",), ("order",)),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["assignment_axes"],
    )
    slot_near_values = _strings(projection["slot_near_values"], "slot_near_values")
    if not slot_near_values:
        raise _error("slot_near_values", "must be non-empty")
    if len(set(slot_near_values)) != len(slot_near_values):
        raise _error("slot_near_values", "must not contain duplicates")
    effect_match_dimensions = _typed_rows(
        projection["effect_match_dimensions"],
        "effect_match_dimensions",
        _dimension,
        semantic_keys=(("key",), ("slot_field",)),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["effect_match_dimensions"],
    )
    constraint_execution_policies = _typed_rows(
        projection["constraint_execution_policies"],
        "constraint_execution_policies",
        _policy,
        semantic_keys=(("operation",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["constraint_execution_policies"],
    )
    warning_types = _typed_rows(
        projection["warning_types"],
        "warning_types",
        _warning_type,
        semantic_keys=(("warning_type",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["warning_types"],
    )
    warning_emitters = _typed_rows(
        projection["warning_emitters"],
        "warning_emitters",
        _warning_emitter,
        semantic_keys=(("emitter",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["warning_emitters"],
    )
    emitter_ids = tuple(item.emitter for item in warning_emitters)
    expected_emitter_ids = IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS["warning_emitter_ids"]
    if set(emitter_ids) != set(expected_emitter_ids) or len(emitter_ids) != len(expected_emitter_ids):
        raise _error("warning_emitters", "must exactly match executable emitter IDs")
    warning_trait_actions = _typed_rows(
        projection["warning_trait_actions"],
        "warning_trait_actions",
        _warning_trait,
        semantic_keys=(("trait_id",),),
        fields=RUNTIME_PROJECTION_ROW_FIELDS["warning_trait_actions"],
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
    return RuntimeProgram(
        _str(root["format_version"], "format_version"),
        _str(root["schema_version"], "schema_version"),
        _str(root["source_hash"], "source_hash"),
        glue,
        source_kind_values,
        assignment_axes,
        slot_near_values,
        effect_match_dimensions,
        scoring_obj,
        prefer_obj,
        constraint_execution_policies,
        warning_types,
        warning_emitters,
        warning_trait_actions,
        concern_catalog,
        relation_warning_rules,
        relation_presence_statuses,
        selector_form_capabilities,
        dashboard_state_catalog,
        grooming_obj,
    )


def relation_presence_policy_for_active_side(
    active_side: str,
    relation_presence_by_active_side: Mapping[str, RuntimeRelationPresenceStatusPolicy],
) -> RuntimeRelationPresenceStatusPolicy:
    try:
        return relation_presence_by_active_side[active_side]
    except KeyError as error:
        raise ValueError(f"unknown relation active side {active_side!r}") from error
