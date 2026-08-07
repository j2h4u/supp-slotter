"""Strict, immutable, typed view of the verified executable ontology projection."""

# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownLambdaType=false, reportReturnType=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportArgumentType=false

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from math import isfinite
from numbers import Real
from types import MappingProxyType
from typing import cast
from urllib.parse import urlparse

from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.glue_capabilities import (
    EFFECT_BLOCK_BEHAVIOR_PRESERVE,
    EFFECT_BLOCK_BEHAVIOR_SUPPRESS,
    IMPLEMENTED_EFFECT_BLOCK_BEHAVIORS,
    IMPLEMENTED_EFFECT_ROLES,
    IMPLEMENTED_GLUE_CONTRACT_AUTHORED_SEQUENCE_FIELDS,
    IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS,
    IMPLEMENTED_GLUE_CONTRACT_FIELD_NAMES,
    IMPLEMENTED_GLUE_CONTRACT_SCALAR_FIELDS,
    IMPLEMENTED_GLUE_CONTRACT_STRUCTURED_FIELDS,
    IMPLEMENTED_RELATION_PRESENCE_TRUTH_TABLE,
)

_FORMAT = "ontology-runtime-program-v1"
_TOP_KEYS = frozenset({
    "format_version",
    "schema_version",
    "source_hash",
    "provenance",
    "protocol",
    "projection",
    "rules",
    "tables",
})
_PROJECTION_KEYS = frozenset({
    "glue_contract",
    "fact_fields",
    "source_kind_values",
    "assignment_governance",
    "assignment_actions",
    "assignment_axes",
    "capability_rules",
    "constraint_governance",
    "constraint_precedence",
    "effect_match_dimensions",
    "effect_scoring",
    "prefer_with_policy",
    "enforcement",
    "execution_gates",
    "lifecycle",
    "scope",
    "scope_outcomes",
    "scope_dimensions",
    "scope_rules",
    "authorities",
    "component_authority",
    "competition_rules",
    "enforcement_projection",
    "effect_remaps",
    "effect_remap_profiles",
    "warning_types",
    "warning_emitters",
    "warning_trait_actions",
    "concern_warning_rules",
    "non_warning_concern_kinds",
    "concern_review_statuses",
    "relation_warning_rules",
    "relation_review_statuses",
    "relation_presence_statuses",
    "relation_endpoint_policies",
})
_CONDITION_OPERATORS = frozenset({
    "equals",
    "equals_field",
    "member_of_field",
    "contains",
    "is_true",
    "is_false",
    "all",
    "any",
    "not",
})
_CONDITION_VALUE_TYPES = frozenset({"string", "strings", "boolean"})


def _error(label: str, message: str) -> OntologyInfrastructureError:
    return OntologyInfrastructureError(f"runtime program {label} {message}", code=MALFORMED)


def _map(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(k, str) for k in value):
        raise _error(label, "must be a mapping with string keys")
    return cast(Mapping[str, object], value)


def _exact_map(value: object, label: str, keys: frozenset[str]) -> Mapping[str, object]:
    mapping = _map(value, label)
    actual = frozenset(mapping)
    if actual != keys:
        raise _error(label, f"has invalid keys (missing={sorted(keys - actual)}, unknown={sorted(actual - keys)})")
    return mapping


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
        raise _error(label, "must be an integer (boolean is not accepted)")
    return value


def _number(value: object, label: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise _error(label, "must be a number (boolean is not accepted)")
    if not isfinite(float(value)):
        raise _error(label, "must be finite")
    return value


def _strings(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _error(label, "must be a list of non-empty strings")
    result = tuple(_str(item, f"{label}[{index}]") for index, item in enumerate(value))
    if not result:
        raise _error(label, "must not be empty")
    return result


def _rows(value: object, label: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise _error(label, "must be a non-empty list")
    rows: list[Mapping[str, object]] = []
    ids: set[str] = set()
    for index, item in enumerate(value):
        row = _map(item, f"{label}[{index}]")
        identifier = _str(row.get("id"), f"{label}[{index}].id")
        if identifier in ids:
            raise _error(label, f"has duplicate id {identifier!r}")
        ids.add(identifier)
        rows.append(row)
    return tuple(rows)


def _sequence_rows(value: object, label: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise _error(label, "must be a non-empty list")
    return tuple(_map(item, f"{label}[{index}]") for index, item in enumerate(value))


def _require_fields(row: Mapping[str, object], label: str, fields: frozenset[str]) -> None:
    actual = frozenset(row)
    if actual != fields:
        raise _error(
            label, f"has invalid fields (missing={sorted(fields - actual)}, unknown={sorted(actual - fields)})"
        )


@dataclass(frozen=True, slots=True)
class RuntimeProvenance:
    source: str
    source_sha256: str
    manifest_schema_version: str
    compiler_sha256: str


@dataclass(frozen=True, slots=True)
class RuntimeProtocol:
    condition_classes: tuple[str, ...]
    action_classes: tuple[str, ...]
    gate_classes: tuple[str, ...]
    policy_class: str


@dataclass(frozen=True, slots=True)
class RuntimeRelationPresenceTruthState:
    source_active: bool
    target_active: bool


@dataclass(frozen=True, slots=True)
class RuntimeGlueContract:
    id: str
    inactive_stack_name: str
    source_kinds: tuple[str, ...]
    source_kind_roles: tuple[str, ...]
    scope_fact_adapters: tuple[str, ...]
    component_authority_outcomes: tuple[str, ...]
    component_authority_primary_values: tuple[str, ...]
    relation_warning_filter_fields: tuple[str, ...]
    relation_warning_active_sides: tuple[str, ...]
    relation_presence_active_sides: tuple[str, ...]
    relation_presence_truth_table: tuple[RuntimeRelationPresenceTruthState, ...]
    relation_review_status_ids: tuple[str, ...]
    relation_endpoint_selector_kinds: tuple[str, ...]
    concern_membership_roles: tuple[str, ...]
    active_concern_role: str
    inactive_concern_role: str
    product_concern_fallback_role: str
    substance_concern_fallback_role: str
    warning_emitter_ids: tuple[str, ...]
    prefer_with_source_fields: tuple[str, ...]
    prefer_with_target_resolutions: tuple[str, ...]
    prefer_with_pair_modes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeFactField:
    id: str
    field: str
    value_type: str


@dataclass(frozen=True, slots=True)
class RuntimeSourceKindValuePolicy:
    id: str
    source_kind: str
    applies_to: tuple[str, ...]
    description: str


@dataclass(frozen=True, slots=True)
class RuntimeLifecycleDecision:
    id: str
    state: str
    rank: int
    executable: bool


@dataclass(frozen=True, slots=True)
class RuntimeDegradationRule:
    id: str
    lifecycle_state: str
    incoming_mode: str
    effective_mode: str


@dataclass(frozen=True, slots=True)
class RuntimeEnforcementDecision:
    id: str
    mode: str
    rank: int
    executable: bool
    effect_role: str


@dataclass(frozen=True, slots=True)
class RuntimeExecutionGate:
    id: str
    lifecycle_state: str
    evidence_requirement: str
    executable: bool


@dataclass(frozen=True, slots=True)
class RuntimeScopeOutcome:
    id: str
    outcome: str
    rank: int
    scope_action: str
    direct_product: str
    formulation: str
    enforcement_cap: str


@dataclass(frozen=True, slots=True)
class RuntimeScopeDimension:
    id: str
    key: str
    values: tuple[str, ...]
    rule_ids: tuple[str, ...]
    default_outcome: str
    fact_adapter: str
    capability_field: str
    allows_block_enforcement: bool

    @property
    def accepts_external_identity_values(self) -> bool:
        """Whether scope values may come from an external entity identity."""
        return self.fact_adapter == "product_identity"


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


@dataclass(frozen=True, slots=True)
class RuntimeAssignmentAction:
    id: str
    action: str
    executable: bool
    shadowed: bool


@dataclass(frozen=True, slots=True)
class RuntimeScopeRule:
    id: str
    priority: int
    conditions: RuntimeValue
    outcome: str


@dataclass(frozen=True, slots=True)
class RuntimeAuthority:
    id: str
    priority: int
    conditions: RuntimeValue
    authority: str
    enforcement_cap: str
    score_weight: float | int
    control_rank: int
    action_code: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class RuntimeComponentAuthorityRule:
    id: str
    priority: int
    conditions: RuntimeValue
    outcome: str


@dataclass(frozen=True, slots=True)
class RuntimeCompetitionRule:
    id: str
    priority: int
    conditions: RuntimeValue
    action_code: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class RuntimeEnforcementProjection:
    id: str
    mode: str
    effect_role: str


@dataclass(frozen=True, slots=True)
class RuntimeEffectRemap:
    id: str
    mode: str
    level: str | None
    projected_level: str | None
    score_enabled: bool
    block_behavior: str
    level_code: str
    block_code: str
    default_code: str


@dataclass(frozen=True, slots=True)
class RuntimeEffectRemapProfile:
    id: str
    modes: tuple[str, ...]
    score_enabled: bool
    block_behavior: str


@dataclass(frozen=True, slots=True)
class RuntimeNearModel:
    id: str
    near: str
    model: str


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
class RuntimeConcernWarningRule:
    id: str
    concern_kind: str
    warning_type: str


@dataclass(frozen=True, slots=True)
class RuntimeNonWarningConcernKindPolicy:
    id: str
    concern_kind: str
    review_surface: str
    description: str


@dataclass(frozen=True, slots=True)
class RuntimeConcernReviewStatusPolicy:
    id: str
    status: str
    rank: int
    membership_role: str
    description: str


@dataclass(frozen=True, slots=True)
class RuntimeRelationWarningRule:
    id: str
    relation_kind: str
    warning_type: str
    review_status: str
    filter_field: str
    filter_value: str
    active_side: str
    reverse_output: bool


@dataclass(frozen=True, slots=True)
class RuntimeRelationReviewStatusPolicy:
    id: str
    status: str
    rank: int
    description: str


@dataclass(frozen=True, slots=True)
class RuntimeRelationPresenceStatusPolicy:
    id: str
    status: str
    source_active: bool
    target_active: bool
    active_side: str
    default_review_status: str
    description: str


@dataclass(frozen=True, slots=True)
class RuntimeRelationEndpointPolicy:
    id: str
    selector_kind: str
    broad_endpoint: bool
    show_match_details: bool
    audit_member_limit: int
    label: str


@dataclass(frozen=True, slots=True)
class RuntimeCapabilityRule:
    id: str
    planner: str
    food_model: str
    base_slot_models: tuple[str, ...]
    slot_models: tuple[str, ...]
    product_scope: tuple[str, ...]
    formulations: tuple[str, ...]
    near_to_model: tuple[RuntimeNearModel, ...]


@dataclass(frozen=True, slots=True)
class RuntimeAssignmentGovernance:
    id: str
    required: bool
    required_fields: tuple[str, ...]
    secondary_enforcement_cap: str


@dataclass(frozen=True, slots=True)
class RuntimeEffectScore:
    id: str
    level: str
    score: float | int


@dataclass(frozen=True, slots=True)
class RuntimeEffectScoring:
    id: str
    scores: tuple[RuntimeEffectScore, ...]
    balance_weight: float | int
    prefer_with_bonus: int
    advisory_constraint_score_delta: int
    advisory_match_direction: str

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
class RuntimePrecedenceDecision:
    id: str
    key: str
    rank: int


@dataclass(frozen=True, slots=True)
class RuntimeEvidenceFormat:
    scheme: str
    require_host: bool
    forbid_userinfo: bool

    def accepts(self, value: str) -> bool:
        try:
            parsed = urlparse(value)
        except ValueError:
            return False
        has_userinfo = parsed.username is not None or parsed.password is not None
        return (
            parsed.scheme == self.scheme
            and (not self.require_host or parsed.hostname is not None)
            and (not self.forbid_userinfo or not has_userinfo)
        )


@dataclass(frozen=True, slots=True)
class RuntimeConstraintGovernance:
    evidence_format: RuntimeEvidenceFormat
    lifecycle_states: tuple[RuntimeLifecycleDecision, ...]
    enforcement_modes: tuple[RuntimeEnforcementDecision, ...]
    execution_gates: tuple[RuntimeExecutionGate, ...]
    allowed_pairs: frozenset[tuple[str, str]]
    execution_policies: tuple[RuntimeConstraintExecutionPolicy, ...]


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


type RuntimeValue = (
    str | bool | int | float | None | tuple["RuntimeValue", ...] | tuple[tuple[str, "RuntimeValue"], ...]
)


@dataclass(frozen=True, slots=True)
class RuntimeRule:
    id: str
    kind: str
    fields: tuple[tuple[str, RuntimeValue], ...]


@dataclass(frozen=True, slots=True)
class RuntimeTable:
    id: str
    rows: tuple[tuple[tuple[str, RuntimeValue], ...], ...]


@dataclass(frozen=True, slots=True)
class RuntimeProjection:
    glue_contract: RuntimeGlueContract
    fact_fields: tuple[RuntimeFactField, ...]
    source_kind_values: tuple[RuntimeSourceKindValuePolicy, ...]
    assignment_governance: RuntimeAssignmentGovernance
    assignment_actions: tuple[RuntimeAssignmentAction, ...]
    capability_rules: tuple[RuntimeCapabilityRule, ...]
    constraint_governance: RuntimeConstraintGovernance
    constraint_precedence: tuple[RuntimePrecedenceDecision, ...]
    effect_scoring: RuntimeEffectScoring
    prefer_with_policy: RuntimePreferWithPolicy
    enforcement: tuple[RuntimeEnforcementDecision, ...]
    execution_gates: tuple[RuntimeExecutionGate, ...]
    lifecycle: tuple[RuntimeLifecycleDecision, ...]
    degradation: tuple[RuntimeDegradationRule, ...]
    scope_dimensions: tuple[RuntimeScopeDimension, ...]
    scope_outcomes: tuple[RuntimeScopeOutcome, ...]
    effect_match_dimensions: tuple[RuntimeEffectMatchDimension, ...]
    assignment_axes: tuple[RuntimeAssignmentAxis, ...]
    scope_rules: tuple[RuntimeScopeRule, ...]
    authorities: tuple[RuntimeAuthority, ...]
    component_authority: tuple[RuntimeComponentAuthorityRule, ...]
    competition_rules: tuple[RuntimeCompetitionRule, ...]
    enforcement_projection: tuple[RuntimeEnforcementProjection, ...]
    effect_remaps: tuple[RuntimeEffectRemap, ...]
    effect_remap_profiles: tuple[RuntimeEffectRemapProfile, ...]
    warning_types: tuple[RuntimeWarningTypePolicy, ...]
    warning_emitters: tuple[RuntimeWarningEmitterPolicy, ...]
    warning_trait_actions: tuple[RuntimeWarningTraitAction, ...]
    concern_warning_rules: tuple[RuntimeConcernWarningRule, ...]
    non_warning_concern_kinds: tuple[RuntimeNonWarningConcernKindPolicy, ...]
    concern_review_statuses: tuple[RuntimeConcernReviewStatusPolicy, ...]
    relation_warning_rules: tuple[RuntimeRelationWarningRule, ...]
    relation_review_statuses: tuple[RuntimeRelationReviewStatusPolicy, ...]
    relation_presence_statuses: tuple[RuntimeRelationPresenceStatusPolicy, ...]
    relation_endpoint_policies: tuple[RuntimeRelationEndpointPolicy, ...]


@dataclass(frozen=True, slots=True)
class RuntimeProgram:
    format_version: str
    schema_version: str
    source_hash: str
    provenance: RuntimeProvenance
    protocol: RuntimeProtocol
    projection: RuntimeProjection
    glue_contract: RuntimeGlueContract
    fact_fields: tuple[RuntimeFactField, ...]
    source_kind_values: tuple[RuntimeSourceKindValuePolicy, ...]
    lifecycle: tuple[RuntimeLifecycleDecision, ...]
    enforcement: tuple[RuntimeEnforcementDecision, ...]
    execution_gates: tuple[RuntimeExecutionGate, ...]
    constraint_governance: RuntimeConstraintGovernance
    scope_outcomes: tuple[RuntimeScopeOutcome, ...]
    scope_dimensions: tuple[RuntimeScopeDimension, ...]
    assignment_governance: RuntimeAssignmentGovernance
    assignment_actions: tuple[RuntimeAssignmentAction, ...]
    effect_scoring: RuntimeEffectScoring
    prefer_with_policy: RuntimePreferWithPolicy
    constraint_precedence: tuple[RuntimePrecedenceDecision, ...]
    capability_rules: tuple[RuntimeCapabilityRule, ...]
    effect_match_dimensions: tuple[RuntimeEffectMatchDimension, ...]
    assignment_axes: tuple[RuntimeAssignmentAxis, ...]
    scope_rules: tuple[RuntimeScopeRule, ...]
    authorities: tuple[RuntimeAuthority, ...]
    component_authority: tuple[RuntimeComponentAuthorityRule, ...]
    competition_rules: tuple[RuntimeCompetitionRule, ...]
    enforcement_projection: tuple[RuntimeEnforcementProjection, ...]
    effect_remaps: tuple[RuntimeEffectRemap, ...]
    effect_remap_profiles: tuple[RuntimeEffectRemapProfile, ...]
    warning_types: tuple[RuntimeWarningTypePolicy, ...]
    warning_emitters: tuple[RuntimeWarningEmitterPolicy, ...]
    warning_trait_actions: tuple[RuntimeWarningTraitAction, ...]
    concern_warning_rules: tuple[RuntimeConcernWarningRule, ...]
    non_warning_concern_kinds: tuple[RuntimeNonWarningConcernKindPolicy, ...]
    concern_review_statuses: tuple[RuntimeConcernReviewStatusPolicy, ...]
    relation_warning_rules: tuple[RuntimeRelationWarningRule, ...]
    relation_review_statuses: tuple[RuntimeRelationReviewStatusPolicy, ...]
    relation_presence_statuses: tuple[RuntimeRelationPresenceStatusPolicy, ...]
    relation_endpoint_policies: tuple[RuntimeRelationEndpointPolicy, ...]
    rules: tuple[RuntimeRule, ...]
    tables: tuple[RuntimeTable, ...]

    @property
    def lifecycle_by_state(self) -> Mapping[str, RuntimeLifecycleDecision]:
        return MappingProxyType({row.state: row for row in self.lifecycle})

    @property
    def enforcement_by_mode(self) -> Mapping[str, RuntimeEnforcementDecision]:
        return MappingProxyType({row.mode: row for row in self.enforcement})

    @property
    def assignment_actions_by_state(self) -> Mapping[tuple[bool, bool], RuntimeAssignmentAction]:
        return MappingProxyType({(row.executable, row.shadowed): row for row in self.assignment_actions})

    def assignment_action_for(self, *, executable: bool, shadowed: bool) -> str:
        row = self.assignment_actions_by_state.get((executable, shadowed))
        if row is None:
            raise _error(
                "assignment_actions",
                f"has no action for executable={executable!r}, shadowed={shadowed!r}",
            )
        return row.action

    def assignment_action_is_eligible(self, action: str) -> bool:
        rows = tuple(row for row in self.assignment_actions if row.action == action)
        if len(rows) != 1:
            raise _error("assignment_actions", f"action {action!r} is missing or ambiguous")
        return rows[0].executable and not rows[0].shadowed

    @property
    def scope_by_key(self) -> Mapping[str, RuntimeScopeDimension]:
        return MappingProxyType({row.key: row for row in self.scope_dimensions})

    @property
    def identity_scope_dimension(self) -> RuntimeScopeDimension:
        """Return the unique scope dimension backed by an external identity."""
        dimensions = tuple(row for row in self.scope_dimensions if row.accepts_external_identity_values)
        if len(dimensions) != 1:
            raise _error(
                "scope.dimensions",
                "must declare exactly one dimension accepting external identity values",
            )
        return dimensions[0]

    @property
    def identity_scope_key(self) -> str:
        """Return the authored key for the external-identity scope dimension."""
        return self.identity_scope_dimension.key

    @property
    def effect_match_dimensions_by_key(self) -> Mapping[str, RuntimeEffectMatchDimension]:
        return MappingProxyType({row.key: row for row in self.effect_match_dimensions})

    @property
    def source_kind_values_by_kind(self) -> Mapping[str, RuntimeSourceKindValuePolicy]:
        return MappingProxyType({row.source_kind: row for row in self.source_kind_values})

    def source_kind_for_role(self, role: str, *, excluding_roles: Sequence[str] = ()) -> str:
        """Return the unique source kind assigned to a role after exclusions."""
        declared_roles = set(self.glue_contract.source_kind_roles)
        if role not in declared_roles:
            raise _error("source_kind_values", f"source kind role {role!r} is not declared")
        if role in excluding_roles or not set(excluding_roles) <= declared_roles:
            raise _error("source_kind_values", f"source kind role exclusions for {role!r} are invalid")
        candidates = tuple(
            row.source_kind
            for row in self.source_kind_values
            if role in row.applies_to and not set(excluding_roles).intersection(row.applies_to)
        )
        if len(candidates) != 1:
            raise _error(
                "source_kind_values",
                f"source kind role {role!r} must resolve to exactly one kind, found {len(candidates)}",
            )
        return candidates[0]

    @property
    def identity_scope_value(self) -> str:
        """Return the unique authored value for the external-identity scope."""
        values = self.identity_scope_dimension.values
        if len(values) != 1:
            raise _error("scope.dimensions", "external-identity dimension must declare exactly one value")
        return values[0]

    @property
    def slot_near_values(self) -> frozenset[str]:
        return frozenset(mapping.near for capability in self.capability_rules for mapping in capability.near_to_model)

    @property
    def effect_score_levels(self) -> frozenset[str]:
        return frozenset(row.level for row in self.effect_scoring.scores)

    @property
    def warning_types_by_type(self) -> Mapping[str, RuntimeWarningTypePolicy]:
        return MappingProxyType({row.warning_type: row for row in self.warning_types})

    @property
    def warning_emitters_by_emitter(self) -> Mapping[str, RuntimeWarningEmitterPolicy]:
        return MappingProxyType({row.emitter: row for row in self.warning_emitters})

    @property
    def relation_review_statuses_by_status(self) -> Mapping[str, RuntimeRelationReviewStatusPolicy]:
        return MappingProxyType({row.status: row for row in self.relation_review_statuses})

    @property
    def relation_review_status_order(self) -> tuple[str, ...]:
        return tuple(row.status for row in sorted(self.relation_review_statuses, key=lambda row: (row.rank, row.id)))

    @property
    def relation_presence_statuses_by_status(self) -> Mapping[str, RuntimeRelationPresenceStatusPolicy]:
        return MappingProxyType({row.status: row for row in self.relation_presence_statuses})

    @property
    def relation_presence_statuses_by_active_side(self) -> Mapping[str, RuntimeRelationPresenceStatusPolicy]:
        return MappingProxyType({row.active_side: row for row in self.relation_presence_statuses})

    @property
    def relation_endpoint_policies_by_selector_kind(self) -> Mapping[str, RuntimeRelationEndpointPolicy]:
        return MappingProxyType({row.selector_kind: row for row in self.relation_endpoint_policies})

    def relation_endpoint_selector_kind_for(self, *, broad_endpoint: bool) -> str:
        """Return the unique authored selector kind for an endpoint breadth."""
        policy_kinds = tuple(row.selector_kind for row in self.relation_endpoint_policies)
        declared_kinds = tuple(self.glue_contract.relation_endpoint_selector_kinds)
        if (
            len(policy_kinds) != len(set(policy_kinds))
            or len(declared_kinds) != len(set(declared_kinds))
            or set(policy_kinds) != set(declared_kinds)
        ):
            raise _error(
                "relation_endpoint_policies",
                "must uniquely cover glue_contract relation endpoint selector kinds",
            )
        candidates = tuple(
            row.selector_kind for row in self.relation_endpoint_policies if row.broad_endpoint is broad_endpoint
        )
        if len(candidates) != 1:
            breadth = "broad" if broad_endpoint else "concrete"
            raise _error(
                "relation_endpoint_policies",
                f"{breadth} endpoint must resolve to exactly one selector kind, found {len(candidates)}",
            )
        return candidates[0]

    @property
    def concrete_relation_endpoint_selector_kind(self) -> str:
        """Return the authored selector kind for concrete relation endpoints."""
        return self.relation_endpoint_selector_kind_for(broad_endpoint=False)

    @property
    def term_relation_endpoint_selector_kind(self) -> str:
        """Return the authored selector kind for term/category relation endpoints."""
        return self.relation_endpoint_selector_kind_for(broad_endpoint=True)

    @property
    def warning_trait_actions_by_trait(self) -> Mapping[str, RuntimeWarningTraitAction]:
        return MappingProxyType({row.trait_id: row for row in self.warning_trait_actions})

    @property
    def warning_type_by_concern_kind(self) -> Mapping[str, str]:
        return MappingProxyType({row.concern_kind: row.warning_type for row in self.concern_warning_rules})

    @property
    def non_warning_concern_kinds_by_kind(self) -> Mapping[str, RuntimeNonWarningConcernKindPolicy]:
        return MappingProxyType({row.concern_kind: row for row in self.non_warning_concern_kinds})

    @property
    def concern_review_statuses_by_membership_role(self) -> Mapping[str, RuntimeConcernReviewStatusPolicy]:
        return MappingProxyType({row.membership_role: row for row in self.concern_review_statuses})

    @property
    def concern_review_status_order(self) -> tuple[str, ...]:
        return tuple(row.status for row in sorted(self.concern_review_statuses, key=lambda row: (row.rank, row.id)))

    @property
    def rules_by_kind(self) -> Mapping[str, tuple[RuntimeRule, ...]]:
        grouped: dict[str, list[RuntimeRule]] = {}
        for row in self.rules:
            grouped.setdefault(row.kind, []).append(row)
        return MappingProxyType({kind: tuple(rows) for kind, rows in grouped.items()})

    @property
    def tables_by_id(self) -> Mapping[str, RuntimeTable]:
        return MappingProxyType({table.id: table for table in self.tables})

    def rules_of_kind(self, kind: str) -> tuple[RuntimeRule, ...]:
        return self.rules_by_kind.get(kind, ())

    def rule(self, kind: str, identifier: str) -> RuntimeRule | None:
        return next((row for row in self.rules if row.kind == kind and row.id == identifier), None)

    def table(self, identifier: str) -> RuntimeTable | None:
        return self.tables_by_id.get(identifier)

    def ordered_rows(self, table_id: str) -> tuple[tuple[tuple[str, RuntimeValue], ...], ...]:
        table = self.table(table_id)
        return () if table is None else table.rows

    @property
    def constraint_allowed_pairs(self) -> frozenset[tuple[str, str]]:
        return self.constraint_governance.allowed_pairs

    def constraint_execution_policy_for(self, operation: str) -> RuntimeConstraintExecutionPolicy | None:
        return next((row for row in self.constraint_governance.execution_policies if row.operation == operation), None)

    def lifecycle_decision(self, state: str) -> RuntimeLifecycleDecision | None:
        return self.lifecycle_by_state.get(state)

    def enforcement_decision(self, mode: str) -> RuntimeEnforcementDecision | None:
        return self.enforcement_by_mode.get(mode)

    def execution_gate_for(self, state: str) -> RuntimeExecutionGate | None:
        return next((gate for gate in self.execution_gates if gate.lifecycle_state == state), None)

    def constraint_execution_gate_for(self, state: str) -> RuntimeExecutionGate | None:
        return next(
            (gate for gate in self.constraint_governance.execution_gates if gate.lifecycle_state == state), None
        )

    def enforcement_rank(self, mode: str) -> int | None:
        decision = self.enforcement_decision(mode)
        return decision.rank if decision is not None else None


def _row_map(row: Mapping[str, object]) -> tuple[tuple[str, RuntimeValue], ...]:
    return tuple((key, cast(RuntimeValue, _runtime_value(value))) for key, value in sorted(row.items()))


def _runtime_value(value: object) -> RuntimeValue:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, Mapping):
        return tuple(
            (str(key), _runtime_value(item)) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(_runtime_value(item) for item in value)
    raise _error("value", "contains an unsupported scalar")


def _typed_rows(value: object, label: str, fields: frozenset[str], factory: object) -> tuple[object, ...]:
    rows = _rows(value, label)
    result: list[object] = []
    for index, row in enumerate(rows):
        _require_fields(row, f"{label}[{index}]", fields)
        result.append(cast(object, factory(row, f"{label}[{index}]")))
    return tuple(result)


def _ensure_unique(values: Sequence[str], label: str, field: str) -> None:
    if len(set(values)) != len(values):
        raise _error(label, f"has duplicate {field}")


def relation_presence_policy_for_active_side(
    active_side: str,
    relation_presence_by_active_side: Mapping[str, RuntimeRelationPresenceStatusPolicy],
) -> RuntimeRelationPresenceStatusPolicy:
    """Return the ontology-authored relation presence policy for an active-side selector."""

    try:
        return relation_presence_by_active_side[active_side]
    except KeyError as error:
        raise ValueError(f"ontology relation_presence_statuses does not declare active_side {active_side!r}") from error


def _lifecycle(row: Mapping[str, object], label: str) -> RuntimeLifecycleDecision:
    return RuntimeLifecycleDecision(
        _str(row["id"], f"{label}.id"),
        _str(row["state"], f"{label}.state"),
        _int(row["rank"], f"{label}.rank"),
        _bool(row["executable"], f"{label}.executable"),
    )


def _fact_field(row: Mapping[str, object], label: str) -> RuntimeFactField:
    return RuntimeFactField(*(_str(row[key], f"{label}.{key}") for key in ("id", "field", "value_type")))


def _source_kind_value(row: Mapping[str, object], label: str) -> RuntimeSourceKindValuePolicy:
    return RuntimeSourceKindValuePolicy(
        _str(row["id"], f"{label}.id"),
        _str(row["source_kind"], f"{label}.source_kind"),
        _strings(row["applies_to"], f"{label}.applies_to"),
        _str(row["description"], f"{label}.description"),
    )


def _degradation(row: Mapping[str, object], label: str) -> RuntimeDegradationRule:
    return RuntimeDegradationRule(
        *(_str(row[key], f"{label}.{key}") for key in ("id", "lifecycle_state", "incoming_mode", "effective_mode"))
    )


def _enforcement(row: Mapping[str, object], label: str) -> RuntimeEnforcementDecision:
    return RuntimeEnforcementDecision(
        _str(row["id"], f"{label}.id"),
        _str(row["mode"], f"{label}.mode"),
        _int(row["rank"], f"{label}.rank"),
        _bool(row["executable"], f"{label}.executable"),
        _str(row["effect_role"], f"{label}.effect_role"),
    )


def _gate(row: Mapping[str, object], label: str) -> RuntimeExecutionGate:
    return RuntimeExecutionGate(
        _str(row["id"], f"{label}.id"),
        _str(row["lifecycle_state"], f"{label}.lifecycle_state"),
        _str(row["evidence_requirement"], f"{label}.evidence_requirement"),
        _bool(row["executable"], f"{label}.executable"),
    )


def _scope_outcome(row: Mapping[str, object], label: str) -> RuntimeScopeOutcome:
    return RuntimeScopeOutcome(
        _str(row["id"], f"{label}.id"),
        _str(row["outcome"], f"{label}.outcome"),
        _int(row["rank"], f"{label}.rank"),
        _str(row["scope_action"], f"{label}.scope_action"),
        _str(row["direct_product"], f"{label}.direct_product"),
        _str(row["formulation"], f"{label}.formulation"),
        _str(row["enforcement_cap"], f"{label}.enforcement_cap"),
    )


def _scope_dimension(row: Mapping[str, object], label: str) -> RuntimeScopeDimension:
    return RuntimeScopeDimension(
        _str(row["id"], f"{label}.id"),
        _str(row["key"], f"{label}.key"),
        _strings(row["values"], f"{label}.values"),
        _strings(row["rule_ids"], f"{label}.rule_ids"),
        _str(row["default_outcome"], f"{label}.default_outcome"),
        _str(row["fact_adapter"], f"{label}.fact_adapter"),
        _str(row["capability_field"], f"{label}.capability_field"),
        _bool(row["allows_block_enforcement"], f"{label}.allows_block_enforcement"),
    )


def _effect_match_dimension(row: Mapping[str, object], label: str) -> RuntimeEffectMatchDimension:
    return RuntimeEffectMatchDimension(
        _str(row["id"], f"{label}.id"),
        _str(row["key"], f"{label}.key"),
        _str(row["slot_field"], f"{label}.slot_field"),
        _str(row["value_type"], f"{label}.value_type"),
    )


def _assignment_axis(row: Mapping[str, object], label: str) -> RuntimeAssignmentAxis:
    return RuntimeAssignmentAxis(
        _str(row["id"], f"{label}.id"),
        _str(row["axis"], f"{label}.axis"),
        _int(row["order"], f"{label}.order"),
        _str(row["assignment_source"], f"{label}.assignment_source"),
        _str(row["assignment_field"], f"{label}.assignment_field"),
    )


def _assignment_action(row: Mapping[str, object], label: str) -> RuntimeAssignmentAction:
    return RuntimeAssignmentAction(
        _str(row["id"], f"{label}.id"),
        _str(row["assignment_action"], f"{label}.assignment_action"),
        _bool(row["executable"], f"{label}.executable"),
        _bool(row["shadowed"], f"{label}.shadowed"),
    )


def _condition_rows(
    value: object, label: str, condition_path_types: Mapping[str, str], *, allow_empty: bool = False
) -> RuntimeValue:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or (not value and not allow_empty):
        requirement = "a list" if allow_empty else "a non-empty list"
        raise _error(label, f"must be {requirement}")
    for index, item in enumerate(value):
        _condition(value_item=item, label=f"{label}[{index}]", condition_path_types=condition_path_types)
    return cast(RuntimeValue, _runtime_value(value))


def _condition(value_item: object, label: str, condition_path_types: Mapping[str, str]) -> None:
    row = _map(value_item, label)
    operator = _str(row.get("operator"), f"{label}.operator")
    if operator not in _CONDITION_OPERATORS:
        raise _error(f"{label}.operator", f"unknown operator {operator!r}")
    if operator in {"equals", "equals_field", "member_of_field", "contains", "is_true", "is_false"}:
        expected = (
            frozenset({"operator", "field", "value"})
            if operator in {"equals", "equals_field", "member_of_field", "contains"}
            else frozenset({"operator", "field"})
        )
        _require_fields(row, label, expected)
        field = _str(row["field"], f"{label}.field")
        field_type = condition_path_types.get(field)
        if field_type is None:
            raise _error(f"{label}.field", "references an unknown condition path")
        if operator in {"is_true", "is_false"}:
            if field_type != "boolean":
                raise _error(label, "boolean operator requires a boolean path")
            return
        operand = row["value"]
        if operator in {"equals_field", "member_of_field"}:
            other = _str(operand, f"{label}.value")
            other_type = condition_path_types.get(other)
            compatible = (
                field_type == other_type
                if operator == "equals_field"
                else field_type == "string" and other_type == "strings"
            )
            if not compatible:
                raise _error(label, "cross-field operands are incompatible")
        elif operator == "contains":
            if field_type != "string":
                raise _error(label, "contains requires a string path")
            _str(operand, f"{label}.value")
        elif field_type == "string":
            _str(operand, f"{label}.value")
        elif field_type == "boolean" and not isinstance(operand, bool):
            raise _error(f"{label}.value", "requires a boolean operand")
        return
    _require_fields(row, label, frozenset({"operator", "conditions"}))
    children = row["conditions"]
    if not isinstance(children, Sequence) or isinstance(children, (str, bytes)) or not children:
        raise _error(f"{label}.conditions", "must be a non-empty list")
    if operator == "not" and len(children) != 1:
        raise _error(f"{label}.conditions", "not requires exactly one child condition")
    for index, child in enumerate(children):
        _condition(child, f"{label}.conditions[{index}]", condition_path_types)


def _scope_rule(row: Mapping[str, object], label: str, condition_path_types: Mapping[str, str]) -> RuntimeScopeRule:
    return RuntimeScopeRule(
        _str(row["id"], f"{label}.id"),
        _int(row["priority"], f"{label}.priority"),
        _condition_rows(row["conditions"], f"{label}.conditions", condition_path_types),
        _str(row["outcome"], f"{label}.outcome"),
    )


def _authority(row: Mapping[str, object], label: str, condition_path_types: Mapping[str, str]) -> RuntimeAuthority:
    return RuntimeAuthority(
        _str(row["id"], f"{label}.id"),
        _int(row["priority"], f"{label}.priority"),
        _condition_rows(row["conditions"], f"{label}.conditions", condition_path_types),
        _str(row["authority"], f"{label}.authority"),
        _str(row["enforcement_cap"], f"{label}.enforcement_cap"),
        _number(row["score_weight"], f"{label}.score_weight"),
        _int(row["control_rank"], f"{label}.control_rank"),
        _str(row["action_code"], f"{label}.action_code"),
        _str(row["reason_code"], f"{label}.reason_code"),
    )


def _component_authority(
    row: Mapping[str, object], label: str, condition_path_types: Mapping[str, str]
) -> RuntimeComponentAuthorityRule:
    return RuntimeComponentAuthorityRule(
        _str(row["id"], f"{label}.id"),
        _int(row["priority"], f"{label}.priority"),
        _condition_rows(row["conditions"], f"{label}.conditions", condition_path_types),
        _str(row["outcome"], f"{label}.outcome"),
    )


def _competition_rule(
    row: Mapping[str, object], label: str, condition_path_types: Mapping[str, str]
) -> RuntimeCompetitionRule:
    return RuntimeCompetitionRule(
        _str(row["id"], f"{label}.id"),
        _int(row["priority"], f"{label}.priority"),
        _condition_rows(row["conditions"], f"{label}.conditions", condition_path_types, allow_empty=True),
        _str(row["action_code"], f"{label}.action_code"),
        _str(row["reason_code"], f"{label}.reason_code"),
    )


def _enforcement_projection(row: Mapping[str, object], label: str) -> RuntimeEnforcementProjection:
    return RuntimeEnforcementProjection(
        _str(row["id"], f"{label}.id"),
        _str(row["mode"], f"{label}.mode"),
        _str(row["effect_role"], f"{label}.effect_role"),
    )


def _effect_remap(row: Mapping[str, object], label: str) -> RuntimeEffectRemap:
    level = row["level"]
    if level is not None:
        level = _str(level, f"{label}.level")
    projected = row["projected_level"]
    if projected is not None:
        projected = _str(projected, f"{label}.projected_level")
    return RuntimeEffectRemap(
        _str(row["id"], f"{label}.id"),
        _str(row["mode"], f"{label}.mode"),
        cast(str | None, level),
        cast(str | None, projected),
        _bool(row["score_enabled"], f"{label}.score_enabled"),
        _str(row["block_behavior"], f"{label}.block_behavior"),
        _str(row["level_code"], f"{label}.level_code"),
        _str(row["block_code"], f"{label}.block_code"),
        _str(row["default_code"], f"{label}.default_code"),
    )


def _effect_remap_profile(row: Mapping[str, object], label: str) -> RuntimeEffectRemapProfile:
    return RuntimeEffectRemapProfile(
        _str(row["id"], f"{label}.id"),
        _strings(row["modes"], f"{label}.modes"),
        _bool(row["score_enabled"], f"{label}.score_enabled"),
        _str(row["block_behavior"], f"{label}.block_behavior"),
    )


def _capability(row: Mapping[str, object], label: str) -> RuntimeCapabilityRule:
    near_rows = _rows(row["near_to_model"], f"{label}.near_to_model")
    near: list[RuntimeNearModel] = []
    for index, item in enumerate(near_rows):
        _require_fields(item, f"{label}.near_to_model[{index}]", frozenset({"id", "near", "model"}))
        near.append(
            RuntimeNearModel(
                _str(item["id"], "near.id"), _str(item["near"], "near.near"), _str(item["model"], "near.model")
            )
        )
    return RuntimeCapabilityRule(
        _str(row["id"], f"{label}.id"),
        _str(row["planner"], f"{label}.planner"),
        _str(row["food_model"], f"{label}.food_model"),
        _strings(row["base_slot_models"], f"{label}.base_slot_models"),
        _strings(row["slot_models"], f"{label}.slot_models"),
        _strings(row["product_scope"], f"{label}.product_scope"),
        _strings(row["formulations"], f"{label}.formulations"),
        tuple(near),
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


def _warning_trait_action(row: Mapping[str, object], label: str) -> RuntimeWarningTraitAction:
    return RuntimeWarningTraitAction(
        _str(row["id"], f"{label}.id"),
        _str(row["trait_id"], f"{label}.trait_id"),
        _str(row["action_text"], f"{label}.action_text"),
    )


def _concern_warning_rule(row: Mapping[str, object], label: str) -> RuntimeConcernWarningRule:
    return RuntimeConcernWarningRule(
        _str(row["id"], f"{label}.id"),
        _str(row["concern_kind"], f"{label}.concern_kind"),
        _str(row["warning_type"], f"{label}.warning_type"),
    )


def _non_warning_concern_kind(row: Mapping[str, object], label: str) -> RuntimeNonWarningConcernKindPolicy:
    return RuntimeNonWarningConcernKindPolicy(
        _str(row["id"], f"{label}.id"),
        _str(row["concern_kind"], f"{label}.concern_kind"),
        _str(row["review_surface"], f"{label}.review_surface"),
        _str(row["description"], f"{label}.description"),
    )


def _concern_review_status(row: Mapping[str, object], label: str) -> RuntimeConcernReviewStatusPolicy:
    return RuntimeConcernReviewStatusPolicy(
        _str(row["id"], f"{label}.id"),
        _str(row["status"], f"{label}.status"),
        _int(row["rank"], f"{label}.rank"),
        _str(row["membership_role"], f"{label}.membership_role"),
        _str(row["description"], f"{label}.description"),
    )


def _glue_contract(value: object, label: str) -> RuntimeGlueContract:
    fields = frozenset({
        "id",
        "inactive_stack_name",
        "source_kinds",
        "source_kind_roles",
        "scope_fact_adapters",
        "component_authority_outcomes",
        "component_authority_primary_values",
        "relation_warning_filter_fields",
        "relation_warning_active_sides",
        "relation_presence_active_sides",
        "relation_presence_truth_table",
        "relation_review_status_ids",
        "relation_endpoint_selector_kinds",
        "concern_membership_roles",
        "active_concern_role",
        "inactive_concern_role",
        "product_concern_fallback_role",
        "substance_concern_fallback_role",
        "warning_emitter_ids",
        "prefer_with_source_fields",
        "prefer_with_target_resolutions",
        "prefer_with_pair_modes",
    })
    raw = _exact_map(value, label, fields)
    return RuntimeGlueContract(
        _str(raw["id"], f"{label}.id"),
        _str(raw["inactive_stack_name"], f"{label}.inactive_stack_name"),
        _strings(raw["source_kinds"], f"{label}.source_kinds"),
        _strings(raw["source_kind_roles"], f"{label}.source_kind_roles"),
        _strings(raw["scope_fact_adapters"], f"{label}.scope_fact_adapters"),
        _strings(raw["component_authority_outcomes"], f"{label}.component_authority_outcomes"),
        _strings(raw["component_authority_primary_values"], f"{label}.component_authority_primary_values"),
        _strings(raw["relation_warning_filter_fields"], f"{label}.relation_warning_filter_fields"),
        _strings(raw["relation_warning_active_sides"], f"{label}.relation_warning_active_sides"),
        _strings(raw["relation_presence_active_sides"], f"{label}.relation_presence_active_sides"),
        _relation_presence_truth_states(raw["relation_presence_truth_table"], f"{label}.relation_presence_truth_table"),
        _strings(raw["relation_review_status_ids"], f"{label}.relation_review_status_ids"),
        _strings(raw["relation_endpoint_selector_kinds"], f"{label}.relation_endpoint_selector_kinds"),
        _strings(raw["concern_membership_roles"], f"{label}.concern_membership_roles"),
        _str(raw["active_concern_role"], f"{label}.active_concern_role"),
        _str(raw["inactive_concern_role"], f"{label}.inactive_concern_role"),
        _str(raw["product_concern_fallback_role"], f"{label}.product_concern_fallback_role"),
        _str(raw["substance_concern_fallback_role"], f"{label}.substance_concern_fallback_role"),
        _strings(raw["warning_emitter_ids"], f"{label}.warning_emitter_ids"),
        _strings(raw["prefer_with_source_fields"], f"{label}.prefer_with_source_fields"),
        _strings(raw["prefer_with_target_resolutions"], f"{label}.prefer_with_target_resolutions"),
        _strings(raw["prefer_with_pair_modes"], f"{label}.prefer_with_pair_modes"),
    )


def _relation_presence_truth_states(value: object, label: str) -> tuple[RuntimeRelationPresenceTruthState, ...]:
    rows = _sequence_rows(value, label)
    states: list[RuntimeRelationPresenceTruthState] = []
    for index, row in enumerate(rows):
        row_label = f"{label}[{index}]"
        raw = _exact_map(row, row_label, frozenset({"source_active", "target_active"}))
        source_active = raw["source_active"]
        target_active = raw["target_active"]
        if not isinstance(source_active, bool) or not isinstance(target_active, bool):
            raise _error(row_label, "must declare boolean source_active and target_active")
        states.append(RuntimeRelationPresenceTruthState(source_active, target_active))
    return tuple(states)


def _relation_warning_rule(row: Mapping[str, object], label: str) -> RuntimeRelationWarningRule:
    reverse = row.get("reverse_output", False)
    if not isinstance(reverse, bool):
        raise _error(label, "reverse_output must be boolean")
    return RuntimeRelationWarningRule(
        _str(row["id"], f"{label}.id"),
        _str(row["relation_kind"], f"{label}.relation_kind"),
        _str(row["warning_type"], f"{label}.warning_type"),
        _str(row["review_status"], f"{label}.review_status"),
        _str(row["filter_field"], f"{label}.filter_field"),
        _str(row["filter_value"], f"{label}.filter_value"),
        _str(row["active_side"], f"{label}.active_side"),
        reverse,
    )


def _relation_review_status(row: Mapping[str, object], label: str) -> RuntimeRelationReviewStatusPolicy:
    return RuntimeRelationReviewStatusPolicy(
        _str(row["id"], f"{label}.id"),
        _str(row["status"], f"{label}.status"),
        _int(row["rank"], f"{label}.rank"),
        _str(row["description"], f"{label}.description"),
    )


def _relation_presence_status(row: Mapping[str, object], label: str) -> RuntimeRelationPresenceStatusPolicy:
    return RuntimeRelationPresenceStatusPolicy(
        _str(row["id"], f"{label}.id"),
        _str(row["status"], f"{label}.status"),
        _bool(row["source_active"], f"{label}.source_active"),
        _bool(row["target_active"], f"{label}.target_active"),
        _str(row["active_side"], f"{label}.active_side"),
        _str(row["default_review_status"], f"{label}.default_review_status"),
        _str(row["description"], f"{label}.description"),
    )


def _relation_endpoint_policy(row: Mapping[str, object], label: str) -> RuntimeRelationEndpointPolicy:
    return RuntimeRelationEndpointPolicy(
        _str(row["id"], f"{label}.id"),
        _str(row["selector_kind"], f"{label}.selector_kind"),
        _bool(row["broad_endpoint"], f"{label}.broad_endpoint"),
        _bool(row["show_match_details"], f"{label}.show_match_details"),
        _int(row["audit_member_limit"], f"{label}.audit_member_limit"),
        _str(row["label"], f"{label}.label"),
    )


def _assignment(row: Mapping[str, object], label: str) -> RuntimeAssignmentGovernance:
    return RuntimeAssignmentGovernance(
        _str(row["id"], f"{label}.id"),
        _bool(row["required"], f"{label}.required"),
        _strings(row["required_fields"], f"{label}.required_fields"),
        _str(row["secondary_enforcement_cap"], f"{label}.secondary_enforcement_cap"),
    )


def _effect_score(row: Mapping[str, object], label: str) -> RuntimeEffectScore:
    return RuntimeEffectScore(
        _str(row["id"], f"{label}.id"), _str(row["level"], f"{label}.level"), _number(row["score"], f"{label}.score")
    )


def _precedence(row: Mapping[str, object], label: str) -> RuntimePrecedenceDecision:
    return RuntimePrecedenceDecision(
        _str(row["id"], f"{label}.id"), _str(row["key"], f"{label}.key"), _int(row["rank"], f"{label}.rank")
    )


def _constraint_execution_policy(row: Mapping[str, object], label: str) -> RuntimeConstraintExecutionPolicy:
    direction = _str(row["match_direction"], f"{label}.match_direction")
    aggregation = _str(row["aggregation"], f"{label}.aggregation")
    selector_resolution = _str(row["selector_resolution"], f"{label}.selector_resolution")
    if direction not in {"symmetric", "directed"}:
        raise _error(label, "match_direction must be symmetric or directed")
    if aggregation != "distinct_constraint":
        raise _error(label, "aggregation must be distinct_constraint")
    if selector_resolution != "require_nonempty":
        raise _error(label, "selector_resolution must be require_nonempty")
    blocks_slots = _bool(row["blocks_slots"], f"{label}.blocks_slots")
    scores_advisory = _bool(row["scores_advisory"], f"{label}.scores_advisory")
    score_delta = _int(row["score_delta"], f"{label}.score_delta")
    if scores_advisory and score_delta > 0:
        raise _error(label, "advisory score_delta must be non-positive")
    return RuntimeConstraintExecutionPolicy(
        _str(row["id"], f"{label}.id"),
        _str(row["operation"], f"{label}.operation"),
        direction,
        aggregation,
        selector_resolution,
        blocks_slots,
        scores_advisory,
        score_delta,
    )


def _governance(value: object, label: str) -> RuntimeConstraintGovernance:
    raw = _exact_map(
        value,
        label,
        frozenset({
            "id",
            "evidence_format",
            "lifecycle_states",
            "enforcement_modes",
            "execution_gates",
            "allowed_pairs",
            "execution_policies",
        }),
    )
    evidence = _exact_map(
        raw["evidence_format"],
        f"{label}.evidence_format",
        frozenset({"id", "scheme", "require_host", "forbid_userinfo"}),
    )
    evidence_format = RuntimeEvidenceFormat(
        _str(evidence["scheme"], "evidence.scheme"),
        _bool(evidence["require_host"], "evidence.require_host"),
        _bool(evidence["forbid_userinfo"], "evidence.forbid_userinfo"),
    )
    lifecycle = cast(
        tuple[RuntimeLifecycleDecision, ...],
        _typed_rows(
            raw["lifecycle_states"],
            f"{label}.lifecycle_states",
            frozenset({"id", "state", "rank", "executable"}),
            _lifecycle,
        ),
    )
    enforcement = cast(
        tuple[RuntimeEnforcementDecision, ...],
        _typed_rows(
            raw["enforcement_modes"],
            f"{label}.enforcement_modes",
            frozenset({"id", "mode", "rank", "executable", "effect_role"}),
            lambda row, name: RuntimeEnforcementDecision(
                _str(row["id"], f"{name}.id"),
                _str(row["mode"], f"{name}.mode"),
                _int(row["rank"], f"{name}.rank"),
                _bool(row["executable"], f"{name}.executable"),
                _str(row["effect_role"], f"{name}.effect_role"),
            ),
        ),
    )
    gates = cast(
        tuple[RuntimeExecutionGate, ...],
        _typed_rows(
            raw["execution_gates"],
            f"{label}.execution_gates",
            frozenset({"id", "lifecycle_state", "evidence_requirement", "executable"}),
            _gate,
        ),
    )
    _ensure_unique(tuple(row.state for row in lifecycle), f"{label}.lifecycle_states", "state")
    _ensure_unique(tuple(row.mode for row in enforcement), f"{label}.enforcement_modes", "mode")
    _ensure_unique(tuple(row.lifecycle_state for row in gates), f"{label}.execution_gates", "lifecycle_state")
    pairs = _rows(raw["allowed_pairs"], f"{label}.allowed_pairs")
    allowed = frozenset(
        (_str(row["lifecycle_state"], "pair.lifecycle_state"), _str(row["enforcement_mode"], "pair.enforcement_mode"))
        for row in pairs
        if frozenset(row) == frozenset({"id", "lifecycle_state", "enforcement_mode"})
    )
    if len(allowed) != len(pairs):
        raise _error(f"{label}.allowed_pairs", "contains malformed records")
    policies = cast(
        tuple[RuntimeConstraintExecutionPolicy, ...],
        _typed_rows(
            raw["execution_policies"],
            f"{label}.execution_policies",
            frozenset({
                "aggregation",
                "blocks_slots",
                "id",
                "match_direction",
                "operation",
                "score_delta",
                "scores_advisory",
                "selector_resolution",
            }),
            _constraint_execution_policy,
        ),
    )
    _ensure_unique(tuple(row.id for row in policies), f"{label}.execution_policies", "id")
    _ensure_unique(tuple(row.operation for row in policies), f"{label}.execution_policies", "operation")
    return RuntimeConstraintGovernance(
        evidence_format, tuple(lifecycle), tuple(enforcement), tuple(gates), allowed, policies
    )


def _effect_scoring(value: object, label: str) -> RuntimeEffectScoring:
    raw = _exact_map(
        value,
        label,
        frozenset({
            "id",
            "scores",
            "balance_weight",
            "prefer_with_bonus",
            "advisory_constraint_score_delta",
            "advisory_match_direction",
        }),
    )
    scores = cast(
        tuple[RuntimeEffectScore, ...],
        _typed_rows(raw["scores"], f"{label}.scores", frozenset({"id", "level", "score"}), _effect_score),
    )
    _ensure_unique(tuple(row.level for row in scores), f"{label}.scores", "level")
    return RuntimeEffectScoring(
        _str(raw["id"], f"{label}.id"),
        scores,
        _number(raw["balance_weight"], f"{label}.balance_weight"),
        _int(raw["prefer_with_bonus"], f"{label}.prefer_with_bonus"),
        _int(raw["advisory_constraint_score_delta"], f"{label}.advisory_constraint_score_delta"),
        _str(raw["advisory_match_direction"], f"{label}.advisory_match_direction"),
    )


def _prefer_with_policy(value: object, label: str) -> RuntimePreferWithPolicy:
    raw = _exact_map(
        value,
        label,
        frozenset({"id", "pair_mode", "source_field", "target_resolution"}),
    )
    return RuntimePreferWithPolicy(
        _str(raw["id"], f"{label}.id"),
        _str(raw["source_field"], f"{label}.source_field"),
        _str(raw["target_resolution"], f"{label}.target_resolution"),
        _str(raw["pair_mode"], f"{label}.pair_mode"),
    )


def _rule_rows(value: object, label: str) -> tuple[RuntimeRule, ...]:
    result: list[RuntimeRule] = []
    seen: set[tuple[str, str]] = set()
    fields_by_kind: dict[str, frozenset[str]] = {}
    for index, row in enumerate(_sequence_rows(value, label)):
        kind = _str(row.get("kind"), f"{label}[{index}].kind")
        fields = frozenset(row)
        if "id" not in fields or "kind" not in fields:
            raise _error(f"{label}[{index}]", "requires id and kind")
        previous_fields = fields_by_kind.setdefault(kind, fields)
        if fields != previous_fields:
            raise _error(f"{label}[{index}]", f"diverges from rule kind {kind!r} field contract")
        identifier = _str(row["id"], f"{label}[{index}].id")
        key = (kind, identifier)
        if key in seen:
            raise _error(label, f"has duplicate kind/id {kind}:{identifier}")
        seen.add(key)
        _validate_runtime_value(row, f"{label}[{index}]")
        result.append(RuntimeRule(identifier, kind, _row_map(row)))
    return tuple(result)


def _validate_runtime_value(value: object, label: str) -> None:
    if (
        value is None
        or isinstance(value, (str, bool))
        or (isinstance(value, int) and not isinstance(value, bool))
        or isinstance(value, float)
    ):
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise _error(label, "contains a non-string key")
            _validate_runtime_value(item, f"{label}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            _validate_runtime_value(item, f"{label}[{index}]")
        return
    raise _error(label, "contains unsupported value")


def _tables(value: object) -> tuple[RuntimeTable, ...]:
    result: list[RuntimeTable] = []
    seen: set[str] = set()
    for index, table_value in enumerate(_sequence_rows(value, "tables")):
        table = _exact_map(table_value, f"tables[{index}]", frozenset({"id", "rows"}))
        table_id = _str(table["id"], f"tables[{index}].id")
        if table_id in seen:
            raise _error("tables", f"has duplicate id {table_id!r}")
        seen.add(table_id)
        rows: list[tuple[tuple[str, RuntimeValue], ...]] = []
        row_ids: set[str] = set()
        ordering: set[object] = set()
        raw_rows = _sequence_rows(table["rows"], f"tables[{index}].rows")
        fields = frozenset(raw_rows[0])
        if "id" not in fields:
            raise _error(f"tables[{index}].rows", "requires id")
        for row_index, row in enumerate(raw_rows):
            _require_fields(row, f"tables[{index}].rows[{row_index}]", fields)
            _validate_runtime_value(row, f"tables[{index}].rows[{row_index}]")
            row_id = _str(row["id"], f"tables[{index}].rows[{row_index}].id")
            if row_id in row_ids:
                raise _error(f"tables[{index}].rows", f"has duplicate id {row_id!r}")
            row_ids.add(row_id)
            for field in () if table_id == "scope_rules" else ("rank", "priority"):
                if field in row:
                    value = row[field]
                    if value in ordering:
                        raise _error(f"tables[{index}].rows", f"has duplicate ordering identifier {field}={value!r}")
                    ordering.add(value)
            rows.append(_row_map(row))
        result.append(RuntimeTable(table_id, tuple(rows)))
    table_by_id = {table.id: table for table in result}
    dimensions = table_by_id.get("scope_dimensions_table")
    scope_rules = table_by_id.get("scope_rules")
    if dimensions is not None and scope_rules is not None:
        priorities = {cast(str, dict(row).get("id")): cast(int, dict(row).get("priority")) for row in scope_rules.rows}
        for row in dimensions.rows:
            values = dict(row)
            refs = values.get("rule_ids")
            if isinstance(refs, tuple):
                seen_priorities: set[int] = set()
                for ref in refs:
                    if not isinstance(ref, str) or ref not in priorities:
                        raise _error("tables.scope_dimensions_table", "references unknown scope rule")
                    priority = priorities[ref]
                    if priority in seen_priorities:
                        raise _error("tables.scope_dimensions_table", f"has ambiguous priority {priority}")
                    seen_priorities.add(priority)
    return tuple(result)


def _normalized_rows(value: object, label: str) -> tuple[tuple[tuple[str, RuntimeValue], ...], ...]:
    return tuple(_row_map(row) for row in _rows(value, label))


def _validate_projection_duplicates(
    projection: Mapping[str, object],
    rules: Sequence[RuntimeRule],
    tables: Sequence[RuntimeTable],
) -> None:
    lifecycle = _map(projection["lifecycle"], "projection.lifecycle")
    enforcement = _map(projection["enforcement"], "projection.enforcement")
    governance = _map(projection["constraint_governance"], "projection.constraint_governance")
    scoring = _map(projection["effect_scoring"], "projection.effect_scoring")
    scope = _map(projection["scope"], "projection.scope")

    if _normalized_rows(projection["scope_dimensions"], "projection.scope_dimensions") != _normalized_rows(
        scope["dimensions"], "projection.scope.dimensions"
    ):
        raise _error("projection.scope_dimensions", "diverges from projection.scope.dimensions")

    table_sources: Mapping[str, object] = {
        "effect_match_dimensions": projection["effect_match_dimensions"],
        "source_kind_values": projection["source_kind_values"],
        "assignment_axes": projection["assignment_axes"],
        "assignment_actions": projection["assignment_actions"],
        "scope_dimensions_table": projection["scope_dimensions"],
        "scope_rules": projection["scope_rules"],
        "authorities": projection["authorities"],
        "component_authority": projection["component_authority"],
        "competition_rules": projection["competition_rules"],
        "enforcement_projection_table": projection["enforcement_projection"],
        "effect_remaps": projection["effect_remaps"],
        "effect_remap_profiles": projection["effect_remap_profiles"],
        "lifecycle": lifecycle["states"],
        "degradation": lifecycle["degradation"],
        "enforcement": enforcement["modes"],
        "execution_gates": projection["execution_gates"],
        "constraint_lifecycle": governance["lifecycle_states"],
        "constraint_enforcement": governance["enforcement_modes"],
        "constraint_execution_gates": governance["execution_gates"],
        "constraint_allowed_pairs": governance["allowed_pairs"],
        "constraint_execution_policies": governance["execution_policies"],
        "scope_outcomes": projection["scope_outcomes"],
        "effect_scores": scoring["scores"],
        "constraint_precedence": projection["constraint_precedence"],
        "warning_types": projection["warning_types"],
        "warning_emitters": projection["warning_emitters"],
        "warning_trait_actions": projection["warning_trait_actions"],
        "concern_warning_rules": projection["concern_warning_rules"],
        "non_warning_concern_kinds": projection["non_warning_concern_kinds"],
        "concern_review_statuses": projection["concern_review_statuses"],
        "relation_warning_rules": projection["relation_warning_rules"],
        "relation_review_statuses": projection["relation_review_statuses"],
        "relation_presence_statuses": projection["relation_presence_statuses"],
        "relation_endpoint_policies": projection["relation_endpoint_policies"],
    }
    table_by_id = {table.id: table for table in tables}
    if set(table_by_id) != set(table_sources):
        raise _error("tables", "does not exactly match projected table sources")
    for table_id, source in table_sources.items():
        if table_by_id[table_id].rows != _normalized_rows(source, f"projection table source {table_id}"):
            raise _error(f"tables.{table_id}", "diverges from its projection source")

    rule_sources: Mapping[str, object] = {
        "lifecycle": lifecycle["states"],
        "degradation": lifecycle["degradation"],
        "enforcement": enforcement["modes"],
        "execution_gate": projection["execution_gates"],
        "constraint_lifecycle": governance["lifecycle_states"],
        "constraint_enforcement": governance["enforcement_modes"],
        "constraint_execution_gate": governance["execution_gates"],
        "constraint_allowed_pair": governance["allowed_pairs"],
        "constraint_execution_policy": governance["execution_policies"],
        "scope_outcome": projection["scope_outcomes"],
        "effect_score": scoring["scores"],
        "precedence": projection["constraint_precedence"],
        "capability": projection["capability_rules"],
        "effect_match_dimension": projection["effect_match_dimensions"],
        "source_kind_value": projection["source_kind_values"],
        "assignment_action": projection["assignment_actions"],
        "warning_type": projection["warning_types"],
        "warning_emitter": projection["warning_emitters"],
        "warning_trait_action": projection["warning_trait_actions"],
        "concern_warning_rule": projection["concern_warning_rules"],
        "non_warning_concern_kind": projection["non_warning_concern_kinds"],
        "concern_review_status": projection["concern_review_statuses"],
        "relation_warning_rule": projection["relation_warning_rules"],
        "relation_review_status": projection["relation_review_statuses"],
        "relation_presence_status": projection["relation_presence_statuses"],
        "relation_endpoint_policy": projection["relation_endpoint_policies"],
    }
    actual_kinds = {rule.kind for rule in rules}
    if actual_kinds != set(rule_sources):
        raise _error("rules", "does not exactly match projected rule sources")
    for kind, source in rule_sources.items():
        expected = tuple(
            _row_map({"kind": kind, **dict(row)}) for row in _rows(source, f"projection rule source {kind}")
        )
        actual = tuple(rule.fields for rule in rules if rule.kind == kind)
        if actual != expected:
            raise _error(f"rules.{kind}", "diverges from its projection source")


def _validate_scope_priority_ambiguity(
    dimensions: Sequence[RuntimeScopeDimension], rules: Sequence[RuntimeScopeRule], label: str
) -> None:
    rules_by_id = {rule.id: rule for rule in rules}
    for dimension in dimensions:
        priorities: set[int] = set()
        for rule_id in dimension.rule_ids:
            rule = rules_by_id.get(rule_id)
            if rule is None:
                raise _error(label, f"dimension {dimension.id!r} references unknown rule {rule_id!r}")
            if rule.priority in priorities:
                raise _error(label, f"dimension {dimension.id!r} has ambiguous priority {rule.priority}")
            priorities.add(rule.priority)


def _condition_object(value: RuntimeValue) -> object:
    if isinstance(value, tuple):
        if all(isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) for item in value):
            return {cast(str, key): _condition_object(cast(RuntimeValue, item)) for key, item in value}
        return tuple(_condition_object(cast(RuntimeValue, item)) for item in value)
    return value


def _component_authority_case(
    value: RuntimeValue,
    label: str,
    component_primary_values: frozenset[str],
) -> tuple[bool, str]:
    decoded = _condition_object(value)
    if not isinstance(decoded, tuple) or len(decoded) != 2:
        raise _error(label, "must contain exactly one clause for each authority dimension")
    explicit: bool | None = None
    primary: str | None = None
    for index, clause in enumerate(decoded):
        if not isinstance(clause, Mapping):
            raise _error(f"{label}[{index}]", "must be a mapping")
        field = clause.get("field")
        if field == "any_explicit_primary":
            if set(clause) != {"operator", "field"} or clause.get("operator") not in {"is_true", "is_false"}:
                raise _error(f"{label}[{index}]", "must be an is_true/is_false clause for any_explicit_primary")
            if explicit is not None:
                raise _error(label, "contains duplicate any_explicit_primary clauses")
            explicit = clause["operator"] == "is_true"
        elif field == "component_primary":
            if set(clause) != {"operator", "field", "value"} or clause.get("operator") != "equals":
                raise _error(f"{label}[{index}]", "must be an equals clause for component_primary")
            value = clause.get("value")
            if not isinstance(value, str) or value not in component_primary_values:
                raise _error(f"{label}[{index}]", "component_primary is not declared by glue_contract")
            if primary is not None:
                raise _error(label, "contains duplicate component_primary clauses")
            primary = cast(str, value)
        else:
            raise _error(f"{label}[{index}]", "references an unknown component authority dimension")
    if explicit is None or primary is None:
        raise _error(label, "must cover any_explicit_primary and component_primary exactly once")
    return explicit, primary


def _validate_component_authority(
    rules: Sequence[RuntimeComponentAuthorityRule], glue_contract: RuntimeGlueContract, label: str
) -> None:
    if not rules:
        raise _error(label, "component authority table must not be empty")
    if len({row.priority for row in rules}) != len(rules):
        raise _error(label, "component authority rules must have unique priorities")
    outcomes = frozenset(glue_contract.component_authority_outcomes)
    if any(row.outcome not in outcomes for row in rules):
        raise _error(label, "component authority rules have invalid outcomes")
    primary_values = frozenset(glue_contract.component_authority_primary_values)
    expected = {(explicit, primary) for explicit in (False, True) for primary in primary_values}
    seen: dict[tuple[bool, str], str] = {}
    for row in rules:
        case = _component_authority_case(row.conditions, f"{label}.{row.id}.conditions", primary_values)
        if case in seen:
            raise _error(label, f"has duplicate component state {case!r} in {seen[case]!r} and {row.id!r}")
        seen[case] = row.id
    if set(seen) != expected:
        raise _error(
            label,
            f"must contain exactly the six canonical component states (missing={sorted(expected - set(seen))}, extra={sorted(set(seen) - expected)})",
        )


def _mirror_condition_value(value: RuntimeValue) -> RuntimeValue:
    if not isinstance(value, tuple):
        return value
    is_mapping = all(isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) for item in value)
    if not is_mapping:
        return tuple(_mirror_condition_value(cast(RuntimeValue, item)) for item in value)
    mirrored: list[tuple[str, RuntimeValue]] = []
    for key, item in cast(tuple[tuple[str, RuntimeValue], ...], value):
        if key in {"field", "value"} and isinstance(item, str):
            if item.startswith("left_"):
                item = f"right_{item[5:]}"
            elif item.startswith("right_"):
                item = f"left_{item[6:]}"
        mirrored.append((key, _mirror_condition_value(item)))
    return tuple(mirrored)


def _validate_glue_contract_capabilities(glue_contract: RuntimeGlueContract) -> None:
    runtime_fields = tuple(field.name for field in fields(RuntimeGlueContract))
    if runtime_fields != IMPLEMENTED_GLUE_CONTRACT_FIELD_NAMES:
        raise _error("glue_contract", "RuntimeGlueContract fields must be exhaustively classified")
    classified = (
        set(IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS)
        | set(IMPLEMENTED_GLUE_CONTRACT_AUTHORED_SEQUENCE_FIELDS)
        | set(IMPLEMENTED_GLUE_CONTRACT_SCALAR_FIELDS)
        | set(IMPLEMENTED_GLUE_CONTRACT_STRUCTURED_FIELDS)
    )
    if classified != set(IMPLEMENTED_GLUE_CONTRACT_FIELD_NAMES):
        raise _error("glue_contract", "implemented planner glue capability classifications are incomplete")
    for field_name, implemented in IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS.items():
        authored = cast(tuple[str, ...], getattr(glue_contract, field_name))
        if set(authored) != set(implemented) or len(set(authored)) != len(authored):
            raise _error("glue_contract", f"{field_name} must match implemented planner glue capabilities")
    truth_table = tuple((row.source_active, row.target_active) for row in glue_contract.relation_presence_truth_table)
    if set(truth_table) != set(IMPLEMENTED_RELATION_PRESENCE_TRUTH_TABLE) or len(set(truth_table)) != len(truth_table):
        raise _error("glue_contract", "relation_presence_truth_table must match implemented planner glue capabilities")


def _validate_runtime_semantics(
    glue_contract: RuntimeGlueContract,
    fact_fields: Sequence[RuntimeFactField],
    source_kind_values: Sequence[RuntimeSourceKindValuePolicy],
    lifecycle: Sequence[RuntimeLifecycleDecision],
    degradation: Sequence[RuntimeDegradationRule],
    enforcement: Sequence[RuntimeEnforcementDecision],
    governance: RuntimeConstraintGovernance,
    assignment_axes: Sequence[RuntimeAssignmentAxis],
    assignment_actions: Sequence[RuntimeAssignmentAction],
    authorities: Sequence[RuntimeAuthority],
    component_authority: Sequence[RuntimeComponentAuthorityRule],
    competition_rules: Sequence[RuntimeCompetitionRule],
    enforcement_projection: Sequence[RuntimeEnforcementProjection],
    effect_remaps: Sequence[RuntimeEffectRemap],
    effect_remap_profiles: Sequence[RuntimeEffectRemapProfile],
    scoring: RuntimeEffectScoring,
    capabilities: Sequence[RuntimeCapabilityRule],
    scope_outcomes: Sequence[RuntimeScopeOutcome],
    scope_dimensions: Sequence[RuntimeScopeDimension],
    scope_rules: Sequence[RuntimeScopeRule],
    effect_match_dimensions: Sequence[RuntimeEffectMatchDimension],
    warning_types: Sequence[RuntimeWarningTypePolicy],
    concern_warning_rules: Sequence[RuntimeConcernWarningRule],
    non_warning_concern_kinds: Sequence[RuntimeNonWarningConcernKindPolicy],
    relation_warning_rules: Sequence[RuntimeRelationWarningRule],
    label: str,
) -> None:
    from planner.contracts import Slot

    _validate_glue_contract_capabilities(glue_contract)
    declared_fact_fields = {row.field: row.value_type for row in fact_fields}
    if len(declared_fact_fields) != len(fact_fields) or not declared_fact_fields:
        raise _error(label, "fact fields must declare unique condition paths")
    if any(row.value_type not in _CONDITION_VALUE_TYPES for row in fact_fields):
        raise _error(label, "fact fields contain an unknown value type")
    source_kind_roles = set(glue_contract.source_kind_roles)
    if {row.source_kind for row in source_kind_values} != set(glue_contract.source_kinds):
        raise _error(label, "source kind taxonomy must match glue_contract")
    for row in source_kind_values:
        if len(set(row.applies_to)) != len(row.applies_to) or not set(row.applies_to) <= source_kind_roles:
            raise _error(label, f"source kind value {row.id!r} has invalid roles")
        if not row.description.strip():
            raise _error(label, f"source kind value {row.id!r} has no description")
    modes = {row.mode for row in enforcement}
    states = {row.state for row in lifecycle}
    main_roles = {row.effect_role for row in enforcement}
    if not main_roles <= set(IMPLEMENTED_EFFECT_ROLES):
        raise _error(
            label,
            "enforcement modes must match implemented planner effect-role capabilities",
        )
    if len(main_roles) != len(enforcement):
        raise _error(label, "enforcement modes have duplicate effect_role")
    for row in governance.enforcement_modes:
        if row.effect_role not in main_roles:
            raise _error(label, f"constraint enforcement role {row.effect_role!r} is not declared by main enforcement")
    projection_modes: set[str] = set()
    for row in enforcement_projection:
        if row.mode in projection_modes or row.mode not in modes:
            raise _error(label, f"enforcement projection mode {row.mode!r} is invalid or duplicated")
        if row.effect_role not in main_roles:
            raise _error(label, f"enforcement projection role {row.effect_role!r} is not declared by main enforcement")
        projection_modes.add(row.mode)
    if projection_modes != modes:
        raise _error(label, "enforcement projection must cover every enforcement mode exactly once")

    degradation_pairs = {(row.lifecycle_state, row.incoming_mode) for row in degradation}
    expected_degradation_pairs = {(state, mode) for state in states for mode in modes}
    if len(degradation_pairs) != len(degradation) or degradation_pairs != expected_degradation_pairs:
        raise _error(label, "degradation must cover every lifecycle-state/incoming-mode pair exactly once")
    for row in degradation:
        if row.effective_mode not in modes:
            raise _error(label, f"degradation {row.id!r} references an unknown enforcement mode")
    for row in scope_outcomes:
        if row.enforcement_cap not in modes:
            raise _error(label, f"scope outcome {row.id!r} references an unknown enforcement mode")
    outcome_refs = {row.id for row in scope_outcomes}
    rule_ids = {row.id for row in scope_rules}
    for row in scope_rules:
        if row.outcome not in outcome_refs:
            raise _error(label, f"scope rule {row.id!r} references an unknown outcome")
    for row in scope_dimensions:
        if row.default_outcome not in outcome_refs or not set(row.rule_ids) <= rule_ids:
            raise _error(label, f"scope dimension {row.id!r} has an unknown rule or outcome reference")
        if len(set(row.values)) != len(row.values):
            raise _error(label, f"scope dimension {row.id!r} has duplicate values")
        if row.fact_adapter not in set(glue_contract.scope_fact_adapters):
            raise _error(label, f"scope dimension {row.id!r} has unsupported fact_adapter")
        if row.fact_adapter == "dimension_singleton" and len(row.values) != 1:
            raise _error(label, f"scope dimension {row.id!r} singleton adapter requires one authored value")

    slot_fields = {row.name for row in fields(Slot)}
    for row in effect_match_dimensions:
        if row.slot_field not in slot_fields:
            raise _error(label, f"effect match dimension {row.id!r} references unknown Slot field")
        if row.value_type not in {"slot_near", "boolean"}:
            raise _error(label, f"effect match dimension {row.id!r} has unsupported value type")

    warning_type_ids = {row.warning_type for row in warning_types}
    concern_kind_refs: set[str] = set()
    for row in concern_warning_rules:
        if row.warning_type not in warning_type_ids or row.concern_kind in concern_kind_refs:
            raise _error(label, f"concern warning rule {row.id!r} is invalid")
        concern_kind_refs.add(row.concern_kind)
    non_warning_concern_kind_refs: set[str] = set()
    for row in non_warning_concern_kinds:
        if (
            row.concern_kind in non_warning_concern_kind_refs
            or row.concern_kind in concern_kind_refs
            or row.review_surface != "review"
            or not row.description.strip()
        ):
            raise _error(label, f"non-warning concern kind {row.id!r} is invalid")
        non_warning_concern_kind_refs.add(row.concern_kind)
    for row in relation_warning_rules:
        if row.warning_type not in warning_type_ids:
            raise _error(label, f"relation warning rule {row.id!r} references unknown warning type")
        if row.filter_field not in set(glue_contract.relation_warning_filter_fields):
            raise _error(label, f"relation warning rule {row.id!r} references unsupported filter_field")
        if row.active_side not in set(glue_contract.relation_warning_active_sides):
            raise _error(label, f"relation warning rule {row.id!r} references unsupported active_side")

    axis_names = tuple(row.axis for row in assignment_axes)
    axis_orders = tuple(row.order for row in assignment_axes)
    _ensure_unique(axis_names, label, "assignment axis")
    if len(set(axis_orders)) != len(axis_orders) or set(axis_orders) != set(range(len(axis_orders))):
        raise _error(label, "assignment axis order must be unique and contiguous from zero")
    if any(row.assignment_field != row.axis for row in assignment_axes):
        raise _error(label, "assignment fields must identify their declared axis")

    action_names = tuple(row.action for row in assignment_actions)
    if not action_names or len(set(action_names)) != len(action_names):
        raise _error(label, "assignment actions must declare unique action names")
    action_states = {(row.executable, row.shadowed) for row in assignment_actions}
    if len(action_states) != len(assignment_actions) or action_states != {(True, False), (False, False), (False, True)}:
        raise _error(label, "assignment actions must cover executable, suppressed, and shadowed states")

    _ensure_unique(tuple(row.authority for row in authorities), label, "authority")
    if len({row.priority for row in authorities}) != len(authorities) or len({
        row.control_rank for row in authorities
    }) != len(authorities):
        raise _error(label, "authorities must have unique priorities and control ranks")
    for row in authorities:
        if row.enforcement_cap not in modes or row.score_weight <= 0 or row.score_weight > 1:
            raise _error(label, f"authority {row.id!r} has an invalid cap or score weight")
    _validate_component_authority(component_authority, glue_contract, label)

    if len({row.priority for row in competition_rules}) != len(competition_rules):
        raise _error(label, "competition rules must have unique priorities")
    fallbacks = tuple(row for row in competition_rules if row.conditions == ())
    if (
        len(fallbacks) != 1
        or fallbacks[0].priority != min(row.priority for row in competition_rules)
        or fallbacks[0].action_code != "no_action"
    ):
        raise _error(label, "competition rules require one lowest-priority empty no-action fallback")
    semantic_competition = tuple(row for row in competition_rules if row.conditions != ())
    for row in semantic_competition:
        if row.action_code not in {"left_wins", "right_wins"}:
            raise _error(label, f"competition rule {row.id!r} must declare an oriented winner")
        mirrored_action = "right_wins" if row.action_code == "left_wins" else "left_wins"
        mirrored_conditions = _mirror_condition_value(row.conditions)
        if not any(
            candidate.action_code == mirrored_action
            and candidate.reason_code == row.reason_code
            and candidate.conditions == mirrored_conditions
            for candidate in semantic_competition
            if candidate is not row
        ):
            raise _error(label, f"competition rule {row.id!r} has no explicit mirrored orientation")

    if scoring.balance_weight < 0:
        raise _error(label, "balance weight must be non-negative")
    if scoring.prefer_with_bonus < 0:
        raise _error(label, "prefer-with bonus must be non-negative")
    if scoring.advisory_constraint_score_delta > 0:
        raise _error(label, "advisory constraint score delta must be non-positive")
    if scoring.advisory_match_direction not in {"symmetric", "directed"}:
        raise _error(label, "advisory match direction must be symmetric or directed")
    score_levels = tuple(row.level for row in scoring.scores)
    score_values = {row.level: float(row.score) for row in scoring.scores}
    maximum_score_magnitude = max(abs(value) for value in score_values.values())
    expected = {(row.mode, level) for row in enforcement for level in (*score_levels, None)}
    pairs: set[tuple[str, str | None]] = set()
    profiles: dict[str, set[tuple[bool, str]]] = {row.mode: set() for row in enforcement}
    for row in effect_remaps:
        pair = (row.mode, row.level)
        if pair in pairs:
            raise _error(label, f"effect remap pair {pair!r} is duplicated")
        if pair not in expected:
            raise _error(label, f"effect remap pair {pair!r} is outside the declared coverage")
        if row.score_enabled != (row.projected_level is not None):
            raise _error(label, f"effect remap {row.id!r} has inconsistent score projection")
        if row.projected_level is not None and row.projected_level not in score_levels:
            raise _error(label, f"effect remap {row.id!r} references an unknown score level")
        if row.block_behavior not in IMPLEMENTED_EFFECT_BLOCK_BEHAVIORS:
            raise _error(label, f"effect remap {row.id!r} has an unknown block behavior")
        if row.block_behavior == EFFECT_BLOCK_BEHAVIOR_PRESERVE and row.projected_level != row.level:
            raise _error(label, f"effect remap {row.id!r} may preserve blocking only for identity projection")
        if row.level is None and row.projected_level is not None:
            raise _error(label, f"block-only effect remap {row.id!r} may not invent a score level")
        if (
            row.level is not None
            and row.score_enabled
            and row.block_behavior == EFFECT_BLOCK_BEHAVIOR_SUPPRESS
            and abs(score_values[row.level]) == maximum_score_magnitude
        ) and abs(score_values[cast(str, row.projected_level)]) >= maximum_score_magnitude:
            raise _error(label, f"effect remap {row.id!r} must downgrade a strongest level")
        pairs.add(pair)
        if row.level is not None:
            profiles[row.mode].add((row.score_enabled, row.block_behavior))
    if pairs != expected:
        raise _error(
            label,
            "effect remaps must cover every enforcement-mode/effect-level pair, including block-only effects, exactly once",
        )
    if any(len(profile) != 1 for profile in profiles.values()):
        raise _error(label, "effect remap mechanics must be consistent within each enforcement mode")
    profile_by_mode: dict[str, RuntimeEffectRemapProfile] = {}
    for profile in effect_remap_profiles:
        if not profile.modes:
            raise _error(label, f"effect remap profile {profile.id!r} must declare modes")
        if len(set(profile.modes)) != len(profile.modes):
            raise _error(label, f"effect remap profile {profile.id!r} has duplicate modes")
        if profile.block_behavior not in IMPLEMENTED_EFFECT_BLOCK_BEHAVIORS:
            raise _error(label, f"effect remap profile {profile.id!r} has an unknown block behavior")
        for mode in profile.modes:
            if mode not in modes:
                raise _error(label, f"effect remap profile {profile.id!r} references unknown mode {mode!r}")
            if mode in profile_by_mode:
                raise _error(label, f"effect remap mode {mode!r} belongs to multiple profiles")
            profile_by_mode[mode] = profile
    if set(profile_by_mode) != modes:
        raise _error(label, "effect remap profiles must cover every enforcement mode exactly once")
    for mode, actual_profile in profiles.items():
        authored_profile = profile_by_mode[mode]
        if frozenset(actual_profile) != frozenset({(authored_profile.score_enabled, authored_profile.block_behavior)}):
            raise _error(label, f"effect remap profile for enforcement mode {mode!r} disagrees with remaps")

    capability_keys: set[tuple[str, str]] = set()
    for row in capabilities:
        key = (row.planner, row.food_model)
        if key in capability_keys:
            raise _error(label, f"capability planner/food-model pair {key!r} is duplicated")
        capability_keys.add(key)
        if not set(row.base_slot_models) <= set(row.slot_models) or row.food_model not in row.base_slot_models:
            raise _error(label, f"capability {row.id!r} has invalid base slot models")
        near_keys = tuple(item.near for item in row.near_to_model)
        if len(set(near_keys)) != len(near_keys) or any(
            item.model not in row.slot_models for item in row.near_to_model
        ):
            raise _error(label, f"capability {row.id!r} has invalid near-model mappings")


def decode_runtime_program(payload: Mapping[str, object]) -> RuntimeProgram:
    """Decode one compiler- and manifest-verified JSON snapshot, fail closed."""
    root = _exact_map(payload, "", _TOP_KEYS)
    fmt = _str(root["format_version"], "format_version")
    if fmt != _FORMAT:
        raise _error("format_version", f"must equal {_FORMAT!r}")
    schema = _str(root["schema_version"], "schema_version")
    source_hash = _str(root["source_hash"], "source_hash")
    provenance_raw = _exact_map(
        root["provenance"],
        "provenance",
        frozenset({"source", "source_sha256", "manifest_schema_version", "compiler_sha256"}),
    )
    provenance = RuntimeProvenance(
        *(
            _str(provenance_raw[key], f"provenance.{key}")
            for key in ("source", "source_sha256", "manifest_schema_version", "compiler_sha256")
        )
    )
    protocol_raw = _exact_map(
        root["protocol"], "protocol", frozenset({"condition_classes", "action_classes", "gate_classes", "policy_class"})
    )
    protocol = RuntimeProtocol(
        _strings(protocol_raw["condition_classes"], "protocol.condition_classes"),
        _strings(protocol_raw["action_classes"], "protocol.action_classes"),
        _strings(protocol_raw["gate_classes"], "protocol.gate_classes"),
        _str(protocol_raw["policy_class"], "protocol.policy_class"),
    )
    projection_raw = _exact_map(root["projection"], "projection", _PROJECTION_KEYS)
    glue_contract = _glue_contract(projection_raw["glue_contract"], "glue_contract")
    fact_fields = cast(
        tuple[RuntimeFactField, ...],
        _typed_rows(
            projection_raw["fact_fields"], "fact_fields", frozenset({"id", "field", "value_type"}), _fact_field
        ),
    )
    condition_path_types = {row.field: row.value_type for row in fact_fields}
    source_kind_values = cast(
        tuple[RuntimeSourceKindValuePolicy, ...],
        _typed_rows(
            projection_raw["source_kind_values"],
            "source_kind_values",
            frozenset({"id", "source_kind", "applies_to", "description"}),
            _source_kind_value,
        ),
    )
    lifecycle_raw = _exact_map(
        projection_raw["lifecycle"], "projection.lifecycle", frozenset({"states", "degradation"})
    )
    lifecycle = cast(
        tuple[RuntimeLifecycleDecision, ...],
        _typed_rows(
            lifecycle_raw["states"], "lifecycle.states", frozenset({"id", "state", "rank", "executable"}), _lifecycle
        ),
    )
    degradation = cast(
        tuple[RuntimeDegradationRule, ...],
        _typed_rows(
            lifecycle_raw["degradation"],
            "lifecycle.degradation",
            frozenset({"id", "lifecycle_state", "incoming_mode", "effective_mode"}),
            _degradation,
        ),
    )
    enforcement_raw = _exact_map(projection_raw["enforcement"], "projection.enforcement", frozenset({"modes"}))
    enforcement = cast(
        tuple[RuntimeEnforcementDecision, ...],
        _typed_rows(
            enforcement_raw["modes"],
            "enforcement.modes",
            frozenset({"id", "mode", "rank", "executable", "effect_role"}),
            _enforcement,
        ),
    )
    governance = _governance(projection_raw["constraint_governance"], "constraint_governance")
    gates = cast(
        tuple[RuntimeExecutionGate, ...],
        _typed_rows(
            projection_raw["execution_gates"],
            "execution_gates",
            frozenset({"id", "lifecycle_state", "evidence_requirement", "executable"}),
            _gate,
        ),
    )
    outcomes = cast(
        tuple[RuntimeScopeOutcome, ...],
        _typed_rows(
            projection_raw["scope_outcomes"],
            "scope_outcomes",
            frozenset({"direct_product", "enforcement_cap", "formulation", "id", "outcome", "rank", "scope_action"}),
            _scope_outcome,
        ),
    )
    scope_raw = _exact_map(projection_raw["scope"], "projection.scope", frozenset({"dimensions"}))
    dimensions = cast(
        tuple[RuntimeScopeDimension, ...],
        _typed_rows(
            scope_raw["dimensions"],
            "scope.dimensions",
            frozenset({
                "allows_block_enforcement",
                "capability_field",
                "default_outcome",
                "fact_adapter",
                "id",
                "key",
                "rule_ids",
                "values",
            }),
            _scope_dimension,
        ),
    )
    effect_match_dimensions = cast(
        tuple[RuntimeEffectMatchDimension, ...],
        _typed_rows(
            projection_raw["effect_match_dimensions"],
            "effect_match_dimensions",
            frozenset({"id", "key", "slot_field", "value_type"}),
            _effect_match_dimension,
        ),
    )
    assignment_axes = cast(
        tuple[RuntimeAssignmentAxis, ...],
        _typed_rows(
            projection_raw["assignment_axes"],
            "assignment_axes",
            frozenset({"assignment_field", "assignment_source", "axis", "id", "order"}),
            _assignment_axis,
        ),
    )
    assignment_actions = cast(
        tuple[RuntimeAssignmentAction, ...],
        _typed_rows(
            projection_raw["assignment_actions"],
            "assignment_actions",
            frozenset({"assignment_action", "executable", "id", "shadowed"}),
            _assignment_action,
        ),
    )
    scope_rules = cast(
        tuple[RuntimeScopeRule, ...],
        _typed_rows(
            projection_raw["scope_rules"],
            "scope_rules",
            frozenset({"conditions", "id", "outcome", "priority"}),
            lambda row, label: _scope_rule(row, label, condition_path_types),
        ),
    )
    authorities = cast(
        tuple[RuntimeAuthority, ...],
        _typed_rows(
            projection_raw["authorities"],
            "authorities",
            frozenset({
                "action_code",
                "authority",
                "conditions",
                "control_rank",
                "enforcement_cap",
                "id",
                "priority",
                "reason_code",
                "score_weight",
            }),
            lambda row, label: _authority(row, label, condition_path_types),
        ),
    )
    component_authority = cast(
        tuple[RuntimeComponentAuthorityRule, ...],
        _typed_rows(
            projection_raw["component_authority"],
            "component_authority",
            frozenset({"conditions", "id", "outcome", "priority"}),
            lambda row, label: _component_authority(row, label, condition_path_types),
        ),
    )
    competition_rules = cast(
        tuple[RuntimeCompetitionRule, ...],
        _typed_rows(
            projection_raw["competition_rules"],
            "competition_rules",
            frozenset({"action_code", "conditions", "id", "priority", "reason_code"}),
            lambda row, label: _competition_rule(row, label, condition_path_types),
        ),
    )
    enforcement_projection = cast(
        tuple[RuntimeEnforcementProjection, ...],
        _typed_rows(
            projection_raw["enforcement_projection"],
            "enforcement_projection",
            frozenset({"effect_role", "id", "mode"}),
            _enforcement_projection,
        ),
    )
    effect_remaps = cast(
        tuple[RuntimeEffectRemap, ...],
        _typed_rows(
            projection_raw["effect_remaps"],
            "effect_remaps",
            frozenset({
                "block_behavior",
                "block_code",
                "default_code",
                "id",
                "level",
                "level_code",
                "mode",
                "projected_level",
                "score_enabled",
            }),
            _effect_remap,
        ),
    )
    effect_remap_profiles = cast(
        tuple[RuntimeEffectRemapProfile, ...],
        _typed_rows(
            projection_raw["effect_remap_profiles"],
            "effect_remap_profiles",
            frozenset({"block_behavior", "id", "modes", "score_enabled"}),
            _effect_remap_profile,
        ),
    )
    precedence = cast(
        tuple[RuntimePrecedenceDecision, ...],
        _typed_rows(
            projection_raw["constraint_precedence"],
            "constraint_precedence",
            frozenset({"id", "key", "rank"}),
            _precedence,
        ),
    )
    capabilities = cast(
        tuple[RuntimeCapabilityRule, ...],
        _typed_rows(
            projection_raw["capability_rules"],
            "capability_rules",
            frozenset({
                "id",
                "planner",
                "food_model",
                "base_slot_models",
                "slot_models",
                "product_scope",
                "formulations",
                "near_to_model",
            }),
            _capability,
        ),
    )
    _ensure_unique(tuple(row.state for row in lifecycle), "lifecycle.states", "state")
    warning_types = cast(
        tuple[RuntimeWarningTypePolicy, ...],
        _typed_rows(
            projection_raw["warning_types"],
            "warning_types",
            frozenset({"id", "warning_type", "label", "action_text"}),
            _warning_type,
        ),
    )
    warning_emitters = cast(
        tuple[RuntimeWarningEmitterPolicy, ...],
        _typed_rows(
            projection_raw["warning_emitters"],
            "warning_emitters",
            frozenset({"default_message", "emitter", "id", "warning_type"}),
            _warning_emitter,
        ),
    )
    warning_trait_actions = cast(
        tuple[RuntimeWarningTraitAction, ...],
        _typed_rows(
            projection_raw["warning_trait_actions"],
            "warning_trait_actions",
            frozenset({"id", "trait_id", "action_text"}),
            _warning_trait_action,
        ),
    )
    concern_warning_rules = cast(
        tuple[RuntimeConcernWarningRule, ...],
        _typed_rows(
            projection_raw["concern_warning_rules"],
            "concern_warning_rules",
            frozenset({"id", "concern_kind", "warning_type"}),
            _concern_warning_rule,
        ),
    )
    non_warning_concern_kinds = cast(
        tuple[RuntimeNonWarningConcernKindPolicy, ...],
        _typed_rows(
            projection_raw["non_warning_concern_kinds"],
            "non_warning_concern_kinds",
            frozenset({"id", "concern_kind", "review_surface", "description"}),
            _non_warning_concern_kind,
        ),
    )
    concern_review_statuses = cast(
        tuple[RuntimeConcernReviewStatusPolicy, ...],
        _typed_rows(
            projection_raw["concern_review_statuses"],
            "concern_review_statuses",
            frozenset({"description", "id", "membership_role", "rank", "status"}),
            _concern_review_status,
        ),
    )
    relation_warning_rules = cast(
        tuple[RuntimeRelationWarningRule, ...],
        _typed_rows(
            projection_raw["relation_warning_rules"],
            "relation_warning_rules",
            frozenset({
                "active_side",
                "filter_field",
                "filter_value",
                "id",
                "relation_kind",
                "review_status",
                "reverse_output",
                "warning_type",
            }),
            _relation_warning_rule,
        ),
    )
    relation_review_statuses = cast(
        tuple[RuntimeRelationReviewStatusPolicy, ...],
        _typed_rows(
            projection_raw["relation_review_statuses"],
            "relation_review_statuses",
            frozenset({"id", "status", "rank", "description"}),
            _relation_review_status,
        ),
    )
    relation_presence_statuses = cast(
        tuple[RuntimeRelationPresenceStatusPolicy, ...],
        _typed_rows(
            projection_raw["relation_presence_statuses"],
            "relation_presence_statuses",
            frozenset({
                "active_side",
                "default_review_status",
                "description",
                "id",
                "source_active",
                "status",
                "target_active",
            }),
            _relation_presence_status,
        ),
    )
    relation_endpoint_policies = cast(
        tuple[RuntimeRelationEndpointPolicy, ...],
        _typed_rows(
            projection_raw["relation_endpoint_policies"],
            "relation_endpoint_policies",
            frozenset({
                "audit_member_limit",
                "broad_endpoint",
                "id",
                "label",
                "selector_kind",
                "show_match_details",
            }),
            _relation_endpoint_policy,
        ),
    )
    _ensure_unique(tuple(row.key for row in effect_match_dimensions), "effect_match_dimensions", "key")
    _ensure_unique(tuple(row.warning_type for row in warning_types), "warning_types", "warning_type")
    _ensure_unique(tuple(row.trait_id for row in warning_trait_actions), "warning_trait_actions", "trait_id")
    _ensure_unique(tuple(row.concern_kind for row in concern_warning_rules), "concern_warning_rules", "concern_kind")
    _ensure_unique(tuple(row.status for row in concern_review_statuses), "concern_review_statuses", "status")
    _ensure_unique(
        tuple(row.membership_role for row in concern_review_statuses),
        "concern_review_statuses",
        "membership_role",
    )
    _ensure_unique(tuple(row.status for row in relation_review_statuses), "relation_review_statuses", "status")
    _ensure_unique(tuple(str(row.rank) for row in relation_review_statuses), "relation_review_statuses", "rank")
    _ensure_unique(tuple(row.status for row in relation_presence_statuses), "relation_presence_statuses", "status")
    _ensure_unique(
        tuple(row.active_side for row in relation_presence_statuses), "relation_presence_statuses", "active_side"
    )
    _ensure_unique(
        tuple(row.selector_kind for row in relation_endpoint_policies),
        "relation_endpoint_policies",
        "selector_kind",
    )
    if {row.status for row in relation_review_statuses} != set(glue_contract.relation_review_status_ids) or {
        row.rank for row in relation_review_statuses
    } != set(range(len(relation_review_statuses))):
        raise _error(
            "relation_review_statuses",
            "must declare glue_contract relation review statuses with contiguous ranks",
        )
    if {row.review_status for row in relation_warning_rules} - {row.status for row in relation_review_statuses}:
        raise _error("relation_warning_rules", "must reference authored relation review statuses")
    expected_presence_truth_table = {
        (row.source_active, row.target_active) for row in glue_contract.relation_presence_truth_table
    }
    if (
        {(row.source_active, row.target_active) for row in relation_presence_statuses} != expected_presence_truth_table
        or {row.active_side for row in relation_presence_statuses} != set(glue_contract.relation_presence_active_sides)
        or {row.default_review_status for row in relation_presence_statuses}
        - {row.status for row in relation_review_statuses}
    ):
        raise _error(
            "relation_presence_statuses",
            "must cover glue_contract endpoint-active states and reference authored review statuses",
        )
    if {row.selector_kind for row in relation_endpoint_policies} != set(
        glue_contract.relation_endpoint_selector_kinds
    ) or any(row.audit_member_limit < 0 for row in relation_endpoint_policies):
        raise _error(
            "relation_endpoint_policies",
            "must cover glue_contract selector kinds with non-negative audit limits",
        )
    if {row.membership_role for row in concern_review_statuses} != set(glue_contract.concern_membership_roles) or {
        row.rank for row in concern_review_statuses
    } != set(range(len(concern_review_statuses))):
        raise _error("concern_review_statuses", "must declare every concern membership role with contiguous ranks")
    if {
        glue_contract.product_concern_fallback_role,
        glue_contract.substance_concern_fallback_role,
        glue_contract.active_concern_role,
        glue_contract.inactive_concern_role,
    } - set(glue_contract.concern_membership_roles):
        raise _error("glue_contract", "concern fallback roles must be declared concern membership roles")
    assignment_raw = _exact_map(
        projection_raw["assignment_governance"],
        "assignment_governance",
        frozenset({"id", "required", "required_fields", "secondary_enforcement_cap"}),
    )
    assignment = _assignment(assignment_raw, "assignment_governance")
    scoring = _effect_scoring(projection_raw["effect_scoring"], "effect_scoring")
    prefer_with_policy = _prefer_with_policy(projection_raw["prefer_with_policy"], "prefer_with_policy")
    _ensure_unique(tuple(row.mode for row in enforcement), "enforcement.modes", "mode")
    _ensure_unique(tuple(row.lifecycle_state for row in gates), "execution_gates", "lifecycle_state")
    _ensure_unique(tuple(row.outcome for row in outcomes), "scope_outcomes", "outcome")
    _ensure_unique(tuple(row.rank for row in outcomes), "scope_outcomes", "rank")
    _ensure_unique(tuple(row.key for row in dimensions), "scope.dimensions", "key")
    _ensure_unique(tuple(row.key for row in precedence), "constraint_precedence", "key")
    _ensure_unique(tuple(row.source_kind for row in source_kind_values), "source_kind_values", "source_kind")
    _ensure_unique(tuple(row.emitter for row in warning_emitters), "warning_emitters", "emitter")
    _ensure_unique(tuple(row.id for row in non_warning_concern_kinds), "non_warning_concern_kinds", "id")
    _ensure_unique(tuple(row.concern_kind for row in non_warning_concern_kinds), "non_warning_concern_kinds", "kind")
    if (
        {row.emitter for row in warning_emitters} != set(glue_contract.warning_emitter_ids)
        or {row.warning_type for row in warning_emitters} - {row.warning_type for row in warning_types}
        or any(not row.default_message.strip() for row in warning_emitters)
    ):
        raise _error("warning_emitters", "must declare supported Python glue warning emitters")
    if (
        prefer_with_policy.source_field not in set(glue_contract.prefer_with_source_fields)
        or prefer_with_policy.target_resolution not in set(glue_contract.prefer_with_target_resolutions)
        or prefer_with_policy.pair_mode not in set(glue_contract.prefer_with_pair_modes)
    ):
        raise _error("prefer_with_policy", "does not declare supported prefer_with resolver semantics")
    _validate_scope_priority_ambiguity(dimensions, scope_rules, "scope rules")
    _validate_runtime_semantics(
        glue_contract,
        fact_fields,
        source_kind_values,
        lifecycle,
        degradation,
        enforcement,
        governance,
        assignment_axes,
        assignment_actions,
        authorities,
        component_authority,
        competition_rules,
        enforcement_projection,
        effect_remaps,
        effect_remap_profiles,
        scoring,
        capabilities,
        outcomes,
        dimensions,
        scope_rules,
        effect_match_dimensions,
        warning_types,
        concern_warning_rules,
        non_warning_concern_kinds,
        relation_warning_rules,
        "runtime semantics",
    )
    rules = _rule_rows(root["rules"], "rules")
    tables = _tables(root["tables"])
    _validate_projection_duplicates(projection_raw, rules, tables)
    projection = RuntimeProjection(
        glue_contract,
        fact_fields,
        source_kind_values,
        assignment,
        assignment_actions,
        capabilities,
        governance,
        precedence,
        scoring,
        prefer_with_policy,
        enforcement,
        gates,
        lifecycle,
        degradation,
        dimensions,
        outcomes,
        effect_match_dimensions,
        assignment_axes,
        scope_rules,
        authorities,
        component_authority,
        competition_rules,
        enforcement_projection,
        effect_remaps,
        effect_remap_profiles,
        warning_types,
        warning_emitters,
        warning_trait_actions,
        concern_warning_rules,
        non_warning_concern_kinds,
        concern_review_statuses,
        relation_warning_rules,
        relation_review_statuses,
        relation_presence_statuses,
        relation_endpoint_policies,
    )
    return RuntimeProgram(
        fmt,
        schema,
        source_hash,
        provenance,
        protocol,
        projection,
        glue_contract,
        fact_fields,
        source_kind_values,
        lifecycle,
        enforcement,
        gates,
        governance,
        outcomes,
        dimensions,
        assignment,
        assignment_actions,
        scoring,
        prefer_with_policy,
        precedence,
        capabilities,
        effect_match_dimensions,
        assignment_axes,
        scope_rules,
        authorities,
        component_authority,
        competition_rules,
        enforcement_projection,
        effect_remaps,
        effect_remap_profiles,
        warning_types,
        warning_emitters,
        warning_trait_actions,
        concern_warning_rules,
        non_warning_concern_kinds,
        concern_review_statuses,
        relation_warning_rules,
        relation_review_statuses,
        relation_presence_statuses,
        relation_endpoint_policies,
        rules,
        tables,
    )
