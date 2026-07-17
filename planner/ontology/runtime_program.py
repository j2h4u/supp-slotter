"""Strict, immutable, typed view of the verified executable ontology projection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from numbers import Real
from types import MappingProxyType
from typing import TypeAlias, cast
from urllib.parse import urlparse

from planner.ontology.errors import MALFORMED, OntologyInfrastructureError

_FORMAT = "ontology-runtime-program-v1"
_TOP_KEYS = frozenset({"format_version", "schema_version", "source_hash", "provenance", "protocol", "projection", "rules", "tables"})
_PROJECTION_KEYS = frozenset({"fact_fields", "assignment_governance", "assignment_axes", "capability_rules", "constraint_governance", "constraint_precedence", "effect_scoring", "enforcement", "execution_gates", "lifecycle", "scope", "scope_outcomes", "schedule_axes", "scope_dimensions", "scope_rules", "authorities", "competition_rules", "enforcement_projection", "effect_remaps"})
_RULE_FIELDS = {
    "capability": frozenset({"base_slot_models", "food_model", "formulations", "id", "kind", "near_to_model", "planner", "product_scope", "slot_models"}),
    "constraint_allowed_pair": frozenset({"enforcement_mode", "id", "kind", "lifecycle_state"}),
    "constraint_enforcement": frozenset({"effect_role", "executable", "id", "kind", "mode", "rank"}),
    "constraint_execution_gate": frozenset({"evidence_requirement", "executable", "id", "kind", "lifecycle_state"}),
    "constraint_lifecycle": frozenset({"executable", "id", "kind", "rank", "state"}),
    "degradation": frozenset({"effective_mode", "id", "incoming_mode", "kind", "lifecycle_state"}),
    "effect_score": frozenset({"id", "kind", "level", "score"}),
    "enforcement": frozenset({"effect_role", "executable", "id", "kind", "mode", "rank"}),
    "execution_gate": frozenset({"evidence_requirement", "executable", "id", "kind", "lifecycle_state"}),
    "lifecycle": frozenset({"executable", "id", "kind", "rank", "state"}),
    "precedence": frozenset({"id", "key", "kind", "rank"}),
    "scope_outcome": frozenset({"direct_product", "enforcement_cap", "formulation", "id", "kind", "outcome", "rank", "scope_action"}),
    "schedule_axis": frozenset({"axis", "id", "kind", "values"}),
    "scope_dimension": frozenset({"default_outcome", "id", "key", "kind", "rule_ids", "values"}),
    "scope_rule": frozenset({"conditions", "id", "kind", "outcome", "priority"}),
    "authority": frozenset({"action_code", "authority", "conditions", "control_rank", "enforcement_cap", "id", "kind", "priority", "reason_code", "score_weight"}),
    "enforcement_projection": frozenset({"effect_role", "id", "kind", "mode"}),
    "effect_remap": frozenset({"block_behavior", "block_code", "default_code", "id", "kind", "level", "level_code", "mode", "projected_level", "score_enabled"}),
}
_TABLE_FIELDS = {
    "schedule_axes": frozenset({"axis", "id", "values"}),
    "assignment_axes": frozenset({"assignment_field", "assignment_source", "axis", "id", "order"}),
    "scope_dimensions_table": frozenset({"default_outcome", "id", "key", "rule_ids", "values"}),
    "scope_rules": frozenset({"conditions", "id", "outcome", "priority"}),
    "authorities": frozenset({"action_code", "authority", "conditions", "control_rank", "enforcement_cap", "id", "priority", "reason_code", "score_weight"}),
    "competition_rules": frozenset({"action_code", "conditions", "id", "priority", "reason_code"}),
    "enforcement_projection_table": frozenset({"effect_role", "id", "mode"}),
    "effect_remaps": frozenset({"block_behavior", "block_code", "default_code", "id", "level", "level_code", "mode", "projected_level", "score_enabled"}),
    "lifecycle": frozenset({"executable", "id", "rank", "state"}),
    "degradation": frozenset({"effective_mode", "id", "incoming_mode", "lifecycle_state"}),
    "enforcement": frozenset({"effect_role", "executable", "id", "mode", "rank"}),
    "execution_gates": frozenset({"evidence_requirement", "executable", "id", "lifecycle_state"}),
    "constraint_lifecycle": frozenset({"executable", "id", "rank", "state"}),
    "constraint_enforcement": frozenset({"effect_role", "executable", "id", "mode", "rank"}),
    "constraint_execution_gates": frozenset({"evidence_requirement", "executable", "id", "lifecycle_state"}),
    "constraint_allowed_pairs": frozenset({"enforcement_mode", "id", "lifecycle_state"}),
    "scope_outcomes": frozenset({"direct_product", "enforcement_cap", "formulation", "id", "outcome", "rank", "scope_action"}),
    "effect_scores": frozenset({"id", "level", "score"}),
    "constraint_precedence": frozenset({"id", "key", "rank"}),
}
_RULE_FIELD_TYPES: Mapping[str, Mapping[str, str]] = {
    "capability": {"id": "str", "kind": "kind", "planner": "str", "food_model": "str", "base_slot_models": "strings", "slot_models": "strings", "product_scope": "strings", "formulations": "strings", "near_to_model": "near_models"},
    "constraint_allowed_pair": {"id": "str", "kind": "kind", "lifecycle_state": "str", "enforcement_mode": "str"},
    "constraint_enforcement": {"id": "str", "kind": "kind", "mode": "str", "rank": "int", "executable": "bool", "effect_role": "str"},
    "constraint_execution_gate": {"id": "str", "kind": "kind", "lifecycle_state": "str", "evidence_requirement": "str", "executable": "bool"},
    "constraint_lifecycle": {"id": "str", "kind": "kind", "state": "str", "rank": "int", "executable": "bool"},
    "degradation": {"id": "str", "kind": "kind", "lifecycle_state": "str", "incoming_mode": "str", "effective_mode": "str"},
    "effect_score": {"id": "str", "kind": "kind", "level": "str", "score": "number"},
    "enforcement": {"id": "str", "kind": "kind", "mode": "str", "rank": "int", "executable": "bool", "effect_role": "str"},
    "execution_gate": {"id": "str", "kind": "kind", "lifecycle_state": "str", "evidence_requirement": "str", "executable": "bool"},
    "lifecycle": {"id": "str", "kind": "kind", "state": "str", "rank": "int", "executable": "bool"},
    "precedence": {"id": "str", "kind": "kind", "key": "str", "rank": "int"},
    "scope_outcome": {"id": "str", "kind": "kind", "outcome": "str", "rank": "int", "scope_action": "str", "direct_product": "str", "formulation": "str", "enforcement_cap": "str"},
    "schedule_axis": {"id": "str", "kind": "kind", "axis": "str", "values": "strings"},
    "scope_dimension": {"id": "str", "kind": "kind", "key": "str", "values": "strings", "rule_ids": "strings", "default_outcome": "str"},
    "scope_rule": {"id": "str", "kind": "kind", "priority": "int", "conditions": "any", "outcome": "str"},
    "authority": {"id": "str", "kind": "kind", "priority": "int", "conditions": "any", "authority": "str", "enforcement_cap": "str", "score_weight": "number", "control_rank": "int", "action_code": "str", "reason_code": "str"},
    "enforcement_projection": {"id": "str", "kind": "kind", "mode": "str", "effect_role": "str"},
    "effect_remap": {"id": "str", "kind": "kind", "mode": "str", "level": "str", "projected_level": "nullable_str", "score_enabled": "bool", "block_behavior": "str", "level_code": "str", "block_code": "str", "default_code": "str"},
}
_TABLE_FIELD_TYPES: Mapping[str, Mapping[str, str]] = {
    "schedule_axes": {"id": "str", "axis": "str", "values": "strings"},
    "assignment_axes": {"id": "str", "axis": "str", "order": "int", "assignment_source": "str", "assignment_field": "str"},
    "scope_dimensions_table": {"id": "str", "key": "str", "values": "strings", "rule_ids": "strings", "default_outcome": "str"},
    "scope_rules": {"id": "str", "priority": "int", "conditions": "conditions", "outcome": "str"},
    "authorities": {"id": "str", "priority": "int", "conditions": "conditions", "authority": "str", "enforcement_cap": "str", "score_weight": "number", "control_rank": "int", "action_code": "str", "reason_code": "str"},
    "competition_rules": {"id": "str", "priority": "int", "conditions": "optional_conditions", "action_code": "str", "reason_code": "str"},
    "enforcement_projection_table": {"id": "str", "mode": "str", "effect_role": "str"},
    "effect_remaps": {"id": "str", "mode": "str", "level": "str", "projected_level": "nullable_str", "score_enabled": "bool", "block_behavior": "str", "level_code": "str", "block_code": "str", "default_code": "str"},
    "lifecycle": {"id": "str", "state": "str", "rank": "int", "executable": "bool"},
    "degradation": {"id": "str", "lifecycle_state": "str", "incoming_mode": "str", "effective_mode": "str"},
    "enforcement": {"id": "str", "mode": "str", "rank": "int", "executable": "bool", "effect_role": "str"},
    "execution_gates": {"id": "str", "lifecycle_state": "str", "evidence_requirement": "str", "executable": "bool"},
    "constraint_lifecycle": {"id": "str", "state": "str", "rank": "int", "executable": "bool"},
    "constraint_enforcement": {"id": "str", "mode": "str", "rank": "int", "executable": "bool", "effect_role": "str"},
    "constraint_execution_gates": {"id": "str", "lifecycle_state": "str", "evidence_requirement": "str", "executable": "bool"},
    "constraint_allowed_pairs": {"id": "str", "lifecycle_state": "str", "enforcement_mode": "str"},
    "scope_outcomes": {"id": "str", "outcome": "str", "rank": "int", "scope_action": "str", "direct_product": "str", "formulation": "str", "enforcement_cap": "str"},
    "effect_scores": {"id": "str", "level": "str", "score": "number"},
    "constraint_precedence": {"id": "str", "key": "str", "rank": "int"},
}

_CONDITION_OPERATORS = frozenset({"equals", "equals_field", "member_of_field", "contains", "is_true", "is_false", "all", "any", "not"})
_CONDITION_PATH_TYPES: Mapping[str, str] = {
    "planner": "string",
    "food_model": "string",
    "slot_model": "string",
    "intended_use": "string",
    "substrate": "string",
    "product": "string",
    "formulation": "string",
    "requested_value": "string",
    "supported_value": "string",
    "supported_values": "strings",
    "source_kind": "string",
    "source_form": "string",
    "scope_kind": "string",
    "requested_product_id": "string",
    "actual_product_id": "string",
    "left_authority": "string",
    "right_authority": "string",
    "left_source_kind": "string",
    "right_source_kind": "string",
    "left_axis": "string",
    "right_axis": "string",
    "left_policy_id": "string",
    "right_policy_id": "string",
}


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
        raise _error(label, f"has invalid fields (missing={sorted(fields - actual)}, unknown={sorted(actual - fields)})")


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
class RuntimeFactField:
    id: str
    field: str
    value_type: str


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


@dataclass(frozen=True, slots=True)
class RuntimeScheduleAxis:
    id: str
    axis: str
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeAssignmentAxis:
    id: str
    axis: str
    order: int
    assignment_source: str
    assignment_field: str


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
    level: str
    projected_level: str | None
    score_enabled: bool
    block_behavior: str
    level_code: str
    block_code: str
    default_code: str


@dataclass(frozen=True, slots=True)
class RuntimeNearModel:
    id: str
    near: str
    model: str


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
    secondary_component_weight: float | int
    balance_weight: float | int
    prefer_with_bonus: float | int
    advisory_constraint_score_delta: float | int
    advisory_match_direction: str

    @property
    def scores_by_level(self) -> Mapping[str, RuntimeEffectScore]:
        return MappingProxyType({row.level: row for row in self.scores})


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
        return parsed.scheme == self.scheme and (not self.require_host or bool(parsed.netloc)) and (not self.forbid_userinfo or not has_userinfo)


@dataclass(frozen=True, slots=True)
class RuntimeConstraintGovernance:
    evidence_format: RuntimeEvidenceFormat
    lifecycle_states: tuple[RuntimeLifecycleDecision, ...]
    enforcement_modes: tuple[RuntimeEnforcementDecision, ...]
    execution_gates: tuple[RuntimeExecutionGate, ...]
    allowed_pairs: frozenset[tuple[str, str]]


RuntimeValue: TypeAlias = str | bool | int | float | None | tuple["RuntimeValue", ...] | tuple[tuple[str, "RuntimeValue"], ...]


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
    fact_fields: tuple[RuntimeFactField, ...]
    assignment_governance: RuntimeAssignmentGovernance
    capability_rules: tuple[RuntimeCapabilityRule, ...]
    constraint_governance: RuntimeConstraintGovernance
    constraint_precedence: tuple[RuntimePrecedenceDecision, ...]
    effect_scoring: RuntimeEffectScoring
    enforcement: tuple[RuntimeEnforcementDecision, ...]
    execution_gates: tuple[RuntimeExecutionGate, ...]
    lifecycle: tuple[RuntimeLifecycleDecision, ...]
    degradation: tuple[RuntimeDegradationRule, ...]
    scope_dimensions: tuple[RuntimeScopeDimension, ...]
    scope_outcomes: tuple[RuntimeScopeOutcome, ...]
    schedule_axes: tuple[RuntimeScheduleAxis, ...]
    assignment_axes: tuple[RuntimeAssignmentAxis, ...]
    scope_rules: tuple[RuntimeScopeRule, ...]
    authorities: tuple[RuntimeAuthority, ...]
    competition_rules: tuple[RuntimeCompetitionRule, ...]
    enforcement_projection: tuple[RuntimeEnforcementProjection, ...]
    effect_remaps: tuple[RuntimeEffectRemap, ...]


@dataclass(frozen=True, slots=True)
class RuntimeProgram:
    format_version: str
    schema_version: str
    source_hash: str
    provenance: RuntimeProvenance
    protocol: RuntimeProtocol
    projection: RuntimeProjection
    fact_fields: tuple[RuntimeFactField, ...]
    lifecycle: tuple[RuntimeLifecycleDecision, ...]
    enforcement: tuple[RuntimeEnforcementDecision, ...]
    execution_gates: tuple[RuntimeExecutionGate, ...]
    constraint_governance: RuntimeConstraintGovernance
    scope_outcomes: tuple[RuntimeScopeOutcome, ...]
    scope_dimensions: tuple[RuntimeScopeDimension, ...]
    assignment_governance: RuntimeAssignmentGovernance
    effect_scoring: RuntimeEffectScoring
    constraint_precedence: tuple[RuntimePrecedenceDecision, ...]
    capability_rules: tuple[RuntimeCapabilityRule, ...]
    schedule_axes: tuple[RuntimeScheduleAxis, ...]
    assignment_axes: tuple[RuntimeAssignmentAxis, ...]
    scope_rules: tuple[RuntimeScopeRule, ...]
    authorities: tuple[RuntimeAuthority, ...]
    competition_rules: tuple[RuntimeCompetitionRule, ...]
    enforcement_projection: tuple[RuntimeEnforcementProjection, ...]
    effect_remaps: tuple[RuntimeEffectRemap, ...]
    rules: tuple[RuntimeRule, ...]
    tables: tuple[RuntimeTable, ...]

    @property
    def lifecycle_by_state(self) -> Mapping[str, RuntimeLifecycleDecision]:
        return MappingProxyType({row.state: row for row in self.lifecycle})

    @property
    def enforcement_by_mode(self) -> Mapping[str, RuntimeEnforcementDecision]:
        return MappingProxyType({row.mode: row for row in self.enforcement})

    @property
    def scope_by_key(self) -> Mapping[str, RuntimeScopeDimension]:
        return MappingProxyType({row.key: row for row in self.scope_dimensions})

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

    def lifecycle_decision(self, state: str) -> RuntimeLifecycleDecision | None:
        return self.lifecycle_by_state.get(state)

    def enforcement_decision(self, mode: str) -> RuntimeEnforcementDecision | None:
        return self.enforcement_by_mode.get(mode)

    def execution_gate_for(self, state: str) -> RuntimeExecutionGate | None:
        return next((gate for gate in self.execution_gates if gate.lifecycle_state == state), None)

    def constraint_execution_gate_for(self, state: str) -> RuntimeExecutionGate | None:
        return next((gate for gate in self.constraint_governance.execution_gates if gate.lifecycle_state == state), None)

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
        return tuple((str(key), _runtime_value(item)) for key, item in sorted(value.items(), key=lambda pair: str(pair[0])))
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


def _lifecycle(row: Mapping[str, object], label: str) -> RuntimeLifecycleDecision:
    return RuntimeLifecycleDecision(_str(row["id"], f"{label}.id"), _str(row["state"], f"{label}.state"), _int(row["rank"], f"{label}.rank"), _bool(row["executable"], f"{label}.executable"))


def _fact_field(row: Mapping[str, object], label: str) -> RuntimeFactField:
    return RuntimeFactField(*(_str(row[key], f"{label}.{key}") for key in ("id", "field", "value_type")))


def _degradation(row: Mapping[str, object], label: str) -> RuntimeDegradationRule:
    return RuntimeDegradationRule(*(_str(row[key], f"{label}.{key}") for key in ("id", "lifecycle_state", "incoming_mode", "effective_mode")))


def _enforcement(row: Mapping[str, object], label: str) -> RuntimeEnforcementDecision:
    return RuntimeEnforcementDecision(_str(row["id"], f"{label}.id"), _str(row["mode"], f"{label}.mode"), _int(row["rank"], f"{label}.rank"), _bool(row["executable"], f"{label}.executable"), _str(row["effect_role"], f"{label}.effect_role"))


def _gate(row: Mapping[str, object], label: str) -> RuntimeExecutionGate:
    return RuntimeExecutionGate(_str(row["id"], f"{label}.id"), _str(row["lifecycle_state"], f"{label}.lifecycle_state"), _str(row["evidence_requirement"], f"{label}.evidence_requirement"), _bool(row["executable"], f"{label}.executable"))


def _scope_outcome(row: Mapping[str, object], label: str) -> RuntimeScopeOutcome:
    return RuntimeScopeOutcome(_str(row["id"], f"{label}.id"), _str(row["outcome"], f"{label}.outcome"), _int(row["rank"], f"{label}.rank"), _str(row["scope_action"], f"{label}.scope_action"), _str(row["direct_product"], f"{label}.direct_product"), _str(row["formulation"], f"{label}.formulation"), _str(row["enforcement_cap"], f"{label}.enforcement_cap"))


def _scope_dimension(row: Mapping[str, object], label: str) -> RuntimeScopeDimension:
    return RuntimeScopeDimension(_str(row["id"], f"{label}.id"), _str(row["key"], f"{label}.key"), _strings(row["values"], f"{label}.values"), _strings(row["rule_ids"], f"{label}.rule_ids"), _str(row["default_outcome"], f"{label}.default_outcome"))


def _schedule_axis(row: Mapping[str, object], label: str) -> RuntimeScheduleAxis:
    return RuntimeScheduleAxis(_str(row["id"], f"{label}.id"), _str(row["axis"], f"{label}.axis"), _strings(row["values"], f"{label}.values"))


def _assignment_axis(row: Mapping[str, object], label: str) -> RuntimeAssignmentAxis:
    return RuntimeAssignmentAxis(
        _str(row["id"], f"{label}.id"),
        _str(row["axis"], f"{label}.axis"),
        _int(row["order"], f"{label}.order"),
        _str(row["assignment_source"], f"{label}.assignment_source"),
        _str(row["assignment_field"], f"{label}.assignment_field"),
    )


def _condition_rows(value: object, label: str, *, allow_empty: bool = False) -> RuntimeValue:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or (not value and not allow_empty):
        requirement = "a list" if allow_empty else "a non-empty list"
        raise _error(label, f"must be {requirement}")
    for index, item in enumerate(value):
        _condition(value_item=item, label=f"{label}[{index}]")
    return cast(RuntimeValue, _runtime_value(value))


def _condition(value_item: object, label: str) -> None:
    row = _map(value_item, label)
    operator = _str(row.get("operator"), f"{label}.operator")
    if operator not in _CONDITION_OPERATORS:
        raise _error(f"{label}.operator", f"unknown operator {operator!r}")
    if operator in {"equals", "equals_field", "member_of_field", "contains", "is_true", "is_false"}:
        expected = frozenset({"operator", "field", "value"}) if operator in {"equals", "equals_field", "member_of_field", "contains"} else frozenset({"operator", "field"})
        _require_fields(row, label, expected)
        field = _str(row["field"], f"{label}.field")
        field_type = _CONDITION_PATH_TYPES.get(field)
        if field_type is None:
            raise _error(f"{label}.field", "references an unknown condition path")
        if operator in {"is_true", "is_false"}:
            if field_type != "boolean":
                raise _error(label, "boolean operator requires a boolean path")
            return
        operand = row["value"]
        if operator in {"equals_field", "member_of_field"}:
            other = _str(operand, f"{label}.value")
            other_type = _CONDITION_PATH_TYPES.get(other)
            compatible = field_type == other_type if operator == "equals_field" else field_type == "string" and other_type == "strings"
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
        _condition(child, f"{label}.conditions[{index}]")


def _scope_rule(row: Mapping[str, object], label: str) -> RuntimeScopeRule:
    return RuntimeScopeRule(_str(row["id"], f"{label}.id"), _int(row["priority"], f"{label}.priority"), _condition_rows(row["conditions"], f"{label}.conditions"), _str(row["outcome"], f"{label}.outcome"))


def _authority(row: Mapping[str, object], label: str) -> RuntimeAuthority:
    return RuntimeAuthority(
        _str(row["id"], f"{label}.id"),
        _int(row["priority"], f"{label}.priority"),
        _condition_rows(row["conditions"], f"{label}.conditions"),
        _str(row["authority"], f"{label}.authority"),
        _str(row["enforcement_cap"], f"{label}.enforcement_cap"),
        _number(row["score_weight"], f"{label}.score_weight"),
        _int(row["control_rank"], f"{label}.control_rank"),
        _str(row["action_code"], f"{label}.action_code"),
        _str(row["reason_code"], f"{label}.reason_code"),
    )


def _competition_rule(row: Mapping[str, object], label: str) -> RuntimeCompetitionRule:
    return RuntimeCompetitionRule(
        _str(row["id"], f"{label}.id"),
        _int(row["priority"], f"{label}.priority"),
        _condition_rows(row["conditions"], f"{label}.conditions", allow_empty=True),
        _str(row["action_code"], f"{label}.action_code"),
        _str(row["reason_code"], f"{label}.reason_code"),
    )


def _enforcement_projection(row: Mapping[str, object], label: str) -> RuntimeEnforcementProjection:
    return RuntimeEnforcementProjection(_str(row["id"], f"{label}.id"), _str(row["mode"], f"{label}.mode"), _str(row["effect_role"], f"{label}.effect_role"))


def _effect_remap(row: Mapping[str, object], label: str) -> RuntimeEffectRemap:
    projected = row["projected_level"]
    if projected is not None:
        projected = _str(projected, f"{label}.projected_level")
    return RuntimeEffectRemap(
        _str(row["id"], f"{label}.id"),
        _str(row["mode"], f"{label}.mode"),
        _str(row["level"], f"{label}.level"),
        cast(str | None, projected),
        _bool(row["score_enabled"], f"{label}.score_enabled"),
        _str(row["block_behavior"], f"{label}.block_behavior"),
        _str(row["level_code"], f"{label}.level_code"),
        _str(row["block_code"], f"{label}.block_code"),
        _str(row["default_code"], f"{label}.default_code"),
    )


def _capability(row: Mapping[str, object], label: str) -> RuntimeCapabilityRule:
    near_rows = _rows(row["near_to_model"], f"{label}.near_to_model")
    near: list[RuntimeNearModel] = []
    for index, item in enumerate(near_rows):
        _require_fields(item, f"{label}.near_to_model[{index}]", frozenset({"id", "near", "model"}))
        near.append(RuntimeNearModel(_str(item["id"], "near.id"), _str(item["near"], "near.near"), _str(item["model"], "near.model")))
    return RuntimeCapabilityRule(_str(row["id"], f"{label}.id"), _str(row["planner"], f"{label}.planner"), _str(row["food_model"], f"{label}.food_model"), _strings(row["base_slot_models"], f"{label}.base_slot_models"), _strings(row["slot_models"], f"{label}.slot_models"), _strings(row["product_scope"], f"{label}.product_scope"), _strings(row["formulations"], f"{label}.formulations"), tuple(near))


def _assignment(row: Mapping[str, object], label: str) -> RuntimeAssignmentGovernance:
    return RuntimeAssignmentGovernance(_str(row["id"], f"{label}.id"), _bool(row["required"], f"{label}.required"), _strings(row["required_fields"], f"{label}.required_fields"), _str(row["secondary_enforcement_cap"], f"{label}.secondary_enforcement_cap"))


def _effect_score(row: Mapping[str, object], label: str) -> RuntimeEffectScore:
    return RuntimeEffectScore(_str(row["id"], f"{label}.id"), _str(row["level"], f"{label}.level"), _number(row["score"], f"{label}.score"))


def _precedence(row: Mapping[str, object], label: str) -> RuntimePrecedenceDecision:
    return RuntimePrecedenceDecision(_str(row["id"], f"{label}.id"), _str(row["key"], f"{label}.key"), _int(row["rank"], f"{label}.rank"))


def _governance(value: object, label: str) -> RuntimeConstraintGovernance:
    raw = _exact_map(value, label, frozenset({"id", "evidence_format", "lifecycle_states", "enforcement_modes", "execution_gates", "allowed_pairs"}))
    evidence = _exact_map(raw["evidence_format"], f"{label}.evidence_format", frozenset({"id", "scheme", "require_host", "forbid_userinfo"}))
    evidence_format = RuntimeEvidenceFormat(_str(evidence["scheme"], "evidence.scheme"), _bool(evidence["require_host"], "evidence.require_host"), _bool(evidence["forbid_userinfo"], "evidence.forbid_userinfo"))
    lifecycle = cast(tuple[RuntimeLifecycleDecision, ...], _typed_rows(raw["lifecycle_states"], f"{label}.lifecycle_states", frozenset({"id", "state", "rank", "executable"}), _lifecycle))
    enforcement = cast(tuple[RuntimeEnforcementDecision, ...], _typed_rows(raw["enforcement_modes"], f"{label}.enforcement_modes", frozenset({"id", "mode", "rank", "executable", "effect_role"}), lambda row, name: RuntimeEnforcementDecision(_str(row["id"], f"{name}.id"), _str(row["mode"], f"{name}.mode"), _int(row["rank"], f"{name}.rank"), _bool(row["executable"], f"{name}.executable"), _str(row["effect_role"], f"{name}.effect_role"))))
    gates = cast(tuple[RuntimeExecutionGate, ...], _typed_rows(raw["execution_gates"], f"{label}.execution_gates", frozenset({"id", "lifecycle_state", "evidence_requirement", "executable"}), _gate))
    _ensure_unique(tuple(row.state for row in lifecycle), f"{label}.lifecycle_states", "state")
    _ensure_unique(tuple(row.mode for row in enforcement), f"{label}.enforcement_modes", "mode")
    _ensure_unique(tuple(row.lifecycle_state for row in gates), f"{label}.execution_gates", "lifecycle_state")
    pairs = _rows(raw["allowed_pairs"], f"{label}.allowed_pairs")
    allowed = frozenset((_str(row["lifecycle_state"], "pair.lifecycle_state"), _str(row["enforcement_mode"], "pair.enforcement_mode")) for row in pairs if frozenset(row) == frozenset({"id", "lifecycle_state", "enforcement_mode"}))
    if len(allowed) != len(pairs):
        raise _error(f"{label}.allowed_pairs", "contains malformed records")
    return RuntimeConstraintGovernance(evidence_format, tuple(lifecycle), tuple(enforcement), tuple(gates), allowed)


def _effect_scoring(value: object, label: str) -> RuntimeEffectScoring:
    raw = _exact_map(value, label, frozenset({"id", "scores", "secondary_component_weight", "balance_weight", "prefer_with_bonus", "advisory_constraint_score_delta", "advisory_match_direction"}))
    scores = cast(tuple[RuntimeEffectScore, ...], _typed_rows(raw["scores"], f"{label}.scores", frozenset({"id", "level", "score"}), _effect_score))
    _ensure_unique(tuple(row.level for row in scores), f"{label}.scores", "level")
    return RuntimeEffectScoring(_str(raw["id"], f"{label}.id"), scores, _number(raw["secondary_component_weight"], f"{label}.secondary_component_weight"), _number(raw["balance_weight"], f"{label}.balance_weight"), _number(raw["prefer_with_bonus"], f"{label}.prefer_with_bonus"), _number(raw["advisory_constraint_score_delta"], f"{label}.advisory_constraint_score_delta"), _str(raw["advisory_match_direction"], f"{label}.advisory_match_direction"))


def _rule_rows(value: object, label: str) -> tuple[RuntimeRule, ...]:
    result: list[RuntimeRule] = []
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(_sequence_rows(value, label)):
        kind = _str(row.get("kind"), f"{label}[{index}].kind")
        fields = _RULE_FIELDS.get(kind)
        if fields is None:
            raise _error(f"{label}[{index}].kind", f"unknown rule kind {kind!r}")
        _require_fields(row, f"{label}[{index}]", fields)
        identifier = _str(row["id"], f"{label}[{index}].id")
        key = (kind, identifier)
        if key in seen:
            raise _error(label, f"has duplicate kind/id {kind}:{identifier}")
        seen.add(key)
        _validate_typed_row(row, f"{label}[{index}]", kind, _RULE_FIELD_TYPES[kind])
        _validate_runtime_value(row, f"{label}[{index}]")
        result.append(RuntimeRule(identifier, kind, _row_map(row)))
    return tuple(result)


def _validate_runtime_value(value: object, label: str) -> None:
    if value is None or isinstance(value, (str, bool)) or (isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float):
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


def _validate_field(value: object, label: str, expected: str, kind: str) -> None:
    if expected == "str":
        _str(value, label)
    elif expected == "bool":
        _bool(value, label)
    elif expected == "int":
        _int(value, label)
    elif expected == "number":
        _number(value, label)
    elif expected == "nullable_str":
        if value is not None:
            _str(value, label)
    elif expected == "strings":
        _strings(value, label)
    elif expected == "near_models":
        rows = _rows(value, label)
        for index, row in enumerate(rows):
            _require_fields(row, f"{label}[{index}]", frozenset({"id", "near", "model"}))
            _str(row["id"], f"{label}[{index}].id")
            _str(row["near"], f"{label}[{index}].near")
            _str(row["model"], f"{label}[{index}].model")
    elif expected == "conditions":
        _condition_rows(value, label)
    elif expected == "optional_conditions":
        _condition_rows(value, label, allow_empty=True)
    elif expected == "kind":
        if _str(value, label) != kind:
            raise _error(label, f"must equal rule kind {kind!r}")
    else:
        raise _error(label, f"has unsupported field type {expected!r}")


def _validate_typed_row(row: Mapping[str, object], label: str, kind: str, schema: Mapping[str, str]) -> None:
    for field, expected in schema.items():
        _validate_field(row[field], f"{label}.{field}", expected, kind)


def _tables(value: object) -> tuple[RuntimeTable, ...]:
    result: list[RuntimeTable] = []
    seen: set[str] = set()
    for index, table_value in enumerate(_sequence_rows(value, "tables")):
        table = _exact_map(table_value, f"tables[{index}]", frozenset({"id", "rows"}))
        table_id = _str(table["id"], f"tables[{index}].id")
        if table_id in seen:
            raise _error("tables", f"has duplicate id {table_id!r}")
        seen.add(table_id)
        fields = _TABLE_FIELDS.get(table_id)
        if fields is None:
            raise _error(f"tables[{index}].id", f"unknown table id {table_id!r}")
        rows: list[tuple[tuple[str, RuntimeValue], ...]] = []
        row_ids: set[str] = set()
        ordering: set[object] = set()
        for row_index, row in enumerate(_sequence_rows(table["rows"], f"tables[{index}].rows")):
            _require_fields(row, f"tables[{index}].rows[{row_index}]", fields)
            _validate_typed_row(row, f"tables[{index}].rows[{row_index}]", table_id, _TABLE_FIELD_TYPES[table_id])
            _validate_runtime_value(row, f"tables[{index}].rows[{row_index}]")
            row_id = _str(row["id"], f"tables[{index}].rows[{row_index}].id")
            if row_id in row_ids:
                raise _error(f"tables[{index}].rows", f"has duplicate id {row_id!r}")
            row_ids.add(row_id)
            for field in (() if table_id == "scope_rules" else ("rank", "priority")):
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
        priorities = {
            cast(str, dict(row).get("id")): cast(int, dict(row).get("priority"))
            for row in scope_rules.rows
        }
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
        "schedule_axes": projection["schedule_axes"],
        "assignment_axes": projection["assignment_axes"],
        "scope_dimensions_table": projection["scope_dimensions"],
        "scope_rules": projection["scope_rules"],
        "authorities": projection["authorities"],
        "competition_rules": projection["competition_rules"],
        "enforcement_projection_table": projection["enforcement_projection"],
        "effect_remaps": projection["effect_remaps"],
        "lifecycle": lifecycle["states"],
        "degradation": lifecycle["degradation"],
        "enforcement": enforcement["modes"],
        "execution_gates": projection["execution_gates"],
        "constraint_lifecycle": governance["lifecycle_states"],
        "constraint_enforcement": governance["enforcement_modes"],
        "constraint_execution_gates": governance["execution_gates"],
        "constraint_allowed_pairs": governance["allowed_pairs"],
        "scope_outcomes": projection["scope_outcomes"],
        "effect_scores": scoring["scores"],
        "constraint_precedence": projection["constraint_precedence"],
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
        "scope_outcome": projection["scope_outcomes"],
        "effect_score": scoring["scores"],
        "precedence": projection["constraint_precedence"],
        "capability": projection["capability_rules"],
    }
    actual_kinds = {rule.kind for rule in rules}
    if actual_kinds != set(rule_sources):
        raise _error("rules", "does not exactly match projected rule sources")
    for kind, source in rule_sources.items():
        expected = tuple(
            _row_map({"kind": kind, **dict(row)})
            for row in _rows(source, f"projection rule source {kind}")
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


def _mirror_condition_value(value: RuntimeValue) -> RuntimeValue:
    if not isinstance(value, tuple):
        return value
    is_mapping = all(
        isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str)
        for item in value
    )
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


def _validate_runtime_semantics(
    fact_fields: Sequence[RuntimeFactField],
    lifecycle: Sequence[RuntimeLifecycleDecision],
    degradation: Sequence[RuntimeDegradationRule],
    enforcement: Sequence[RuntimeEnforcementDecision],
    governance: RuntimeConstraintGovernance,
    assignment_axes: Sequence[RuntimeAssignmentAxis],
    authorities: Sequence[RuntimeAuthority],
    competition_rules: Sequence[RuntimeCompetitionRule],
    enforcement_projection: Sequence[RuntimeEnforcementProjection],
    effect_remaps: Sequence[RuntimeEffectRemap],
    scores: Sequence[RuntimeEffectScore],
    capabilities: Sequence[RuntimeCapabilityRule],
    scope_outcomes: Sequence[RuntimeScopeOutcome],
    scope_dimensions: Sequence[RuntimeScopeDimension],
    scope_rules: Sequence[RuntimeScopeRule],
    label: str,
) -> None:
    declared_fact_fields = {row.field: row.value_type for row in fact_fields}
    if len(declared_fact_fields) != len(fact_fields) or declared_fact_fields != _CONDITION_PATH_TYPES:
        raise _error(label, "fact fields must exactly declare the condition vocabulary")
    if any(row.value_type not in {"string", "strings", "boolean"} for row in fact_fields):
        raise _error(label, "fact fields contain an unknown value type")
    modes = {row.mode for row in enforcement}
    states = {row.state for row in lifecycle}
    main_roles = {row.effect_role for row in enforcement}
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

    axis_names = tuple(row.axis for row in assignment_axes)
    axis_orders = tuple(row.order for row in assignment_axes)
    _ensure_unique(axis_names, label, "assignment axis")
    if len(set(axis_orders)) != len(axis_orders) or set(axis_orders) != set(range(len(axis_orders))):
        raise _error(label, "assignment axis order must be unique and contiguous from zero")
    if any(row.assignment_field != row.axis for row in assignment_axes):
        raise _error(label, "assignment fields must identify their declared axis")

    _ensure_unique(tuple(row.authority for row in authorities), label, "authority")
    if len({row.priority for row in authorities}) != len(authorities) or len({row.control_rank for row in authorities}) != len(authorities):
        raise _error(label, "authorities must have unique priorities and control ranks")
    for row in authorities:
        if row.enforcement_cap not in modes or row.score_weight <= 0 or row.score_weight > 1:
            raise _error(label, f"authority {row.id!r} has an invalid cap or score weight")

    if len({row.priority for row in competition_rules}) != len(competition_rules):
        raise _error(label, "competition rules must have unique priorities")
    fallbacks = tuple(row for row in competition_rules if row.conditions == ())
    if len(fallbacks) != 1 or fallbacks[0].priority != min(row.priority for row in competition_rules) or fallbacks[0].action_code != "no_action":
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

    score_levels = tuple(row.level for row in scores)
    score_values = {row.level: float(row.score) for row in scores}
    maximum_score_magnitude = max(abs(value) for value in score_values.values())
    expected = {(row.mode, level) for row in enforcement for level in score_levels}
    pairs: set[tuple[str, str]] = set()
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
        if row.block_behavior not in {"preserve", "suppress"}:
            raise _error(label, f"effect remap {row.id!r} has an unknown block behavior")
        if row.block_behavior == "preserve" and row.projected_level != row.level:
            raise _error(label, f"effect remap {row.id!r} may preserve blocking only for identity projection")
        if row.score_enabled and row.block_behavior == "suppress" and abs(score_values[row.level]) == maximum_score_magnitude:
            if abs(score_values[cast(str, row.projected_level)]) >= maximum_score_magnitude:
                raise _error(label, f"effect remap {row.id!r} must downgrade a strongest level")
        pairs.add(pair)
        profiles[row.mode].add((row.score_enabled, row.block_behavior))
    if pairs != expected:
        raise _error(label, "effect remaps must cover every enforcement-mode/effect-level pair exactly once")
    if any(len(profile) != 1 for profile in profiles.values()):
        raise _error(label, "effect remap mechanics must be consistent within each enforcement mode")
    frozen_profiles = tuple(frozenset(profile) for profile in profiles.values())
    profile_counts = {profile: frozen_profiles.count(profile) for profile in set(frozen_profiles)}
    if profile_counts != {
        frozenset({(False, "suppress")}): 2,
        frozenset({(True, "suppress")}): 1,
        frozenset({(True, "preserve")}): 1,
    }:
        raise _error(label, "effect remaps have invalid enforcement profiles")

    capability_keys: set[tuple[str, str]] = set()
    for row in capabilities:
        key = (row.planner, row.food_model)
        if key in capability_keys:
            raise _error(label, f"capability planner/food-model pair {key!r} is duplicated")
        capability_keys.add(key)
        if not set(row.base_slot_models) <= set(row.slot_models) or row.food_model not in row.base_slot_models:
            raise _error(label, f"capability {row.id!r} has invalid base slot models")
        near_keys = tuple(item.near for item in row.near_to_model)
        if len(set(near_keys)) != len(near_keys) or any(item.model not in row.slot_models for item in row.near_to_model):
            raise _error(label, f"capability {row.id!r} has invalid near-model mappings")


def decode_runtime_program(payload: Mapping[str, object]) -> RuntimeProgram:
    """Decode one compiler- and manifest-verified JSON snapshot, fail closed."""
    root = _exact_map(payload, "", _TOP_KEYS)
    fmt = _str(root["format_version"], "format_version")
    if fmt != _FORMAT:
        raise _error("format_version", f"must equal {_FORMAT!r}")
    schema = _str(root["schema_version"], "schema_version")
    source_hash = _str(root["source_hash"], "source_hash")
    provenance_raw = _exact_map(root["provenance"], "provenance", frozenset({"source", "source_sha256", "manifest_schema_version", "compiler_sha256"}))
    provenance = RuntimeProvenance(*(_str(provenance_raw[key], f"provenance.{key}") for key in ("source", "source_sha256", "manifest_schema_version", "compiler_sha256")))
    protocol_raw = _exact_map(root["protocol"], "protocol", frozenset({"condition_classes", "action_classes", "gate_classes", "policy_class"}))
    protocol = RuntimeProtocol(_strings(protocol_raw["condition_classes"], "protocol.condition_classes"), _strings(protocol_raw["action_classes"], "protocol.action_classes"), _strings(protocol_raw["gate_classes"], "protocol.gate_classes"), _str(protocol_raw["policy_class"], "protocol.policy_class"))
    projection_raw = _exact_map(root["projection"], "projection", _PROJECTION_KEYS)
    fact_fields = cast(tuple[RuntimeFactField, ...], _typed_rows(projection_raw["fact_fields"], "fact_fields", frozenset({"id", "field", "value_type"}), _fact_field))
    lifecycle_raw = _exact_map(projection_raw["lifecycle"], "projection.lifecycle", frozenset({"states", "degradation"}))
    lifecycle = cast(tuple[RuntimeLifecycleDecision, ...], _typed_rows(lifecycle_raw["states"], "lifecycle.states", frozenset({"id", "state", "rank", "executable"}), _lifecycle))
    degradation = cast(tuple[RuntimeDegradationRule, ...], _typed_rows(lifecycle_raw["degradation"], "lifecycle.degradation", frozenset({"id", "lifecycle_state", "incoming_mode", "effective_mode"}), _degradation))
    enforcement_raw = _exact_map(projection_raw["enforcement"], "projection.enforcement", frozenset({"modes"}))
    enforcement = cast(tuple[RuntimeEnforcementDecision, ...], _typed_rows(enforcement_raw["modes"], "enforcement.modes", frozenset({"id", "mode", "rank", "executable", "effect_role"}), _enforcement))
    governance = _governance(projection_raw["constraint_governance"], "constraint_governance")
    gates = cast(tuple[RuntimeExecutionGate, ...], _typed_rows(projection_raw["execution_gates"], "execution_gates", frozenset({"id", "lifecycle_state", "evidence_requirement", "executable"}), _gate))
    outcomes = cast(tuple[RuntimeScopeOutcome, ...], _typed_rows(projection_raw["scope_outcomes"], "scope_outcomes", _RULE_FIELDS["scope_outcome"] - {"kind"}, _scope_outcome))
    scope_raw = _exact_map(projection_raw["scope"], "projection.scope", frozenset({"dimensions"}))
    dimensions = cast(tuple[RuntimeScopeDimension, ...], _typed_rows(scope_raw["dimensions"], "scope.dimensions", _TABLE_FIELDS["scope_dimensions_table"], _scope_dimension))
    schedule_axes = cast(tuple[RuntimeScheduleAxis, ...], _typed_rows(projection_raw["schedule_axes"], "schedule_axes", _TABLE_FIELDS["schedule_axes"], _schedule_axis))
    assignment_axes = cast(tuple[RuntimeAssignmentAxis, ...], _typed_rows(projection_raw["assignment_axes"], "assignment_axes", _TABLE_FIELDS["assignment_axes"], _assignment_axis))
    scope_rules = cast(tuple[RuntimeScopeRule, ...], _typed_rows(projection_raw["scope_rules"], "scope_rules", _TABLE_FIELDS["scope_rules"], _scope_rule))
    authorities = cast(tuple[RuntimeAuthority, ...], _typed_rows(projection_raw["authorities"], "authorities", _TABLE_FIELDS["authorities"], _authority))
    competition_rules = cast(tuple[RuntimeCompetitionRule, ...], _typed_rows(projection_raw["competition_rules"], "competition_rules", _TABLE_FIELDS["competition_rules"], _competition_rule))
    enforcement_projection = cast(tuple[RuntimeEnforcementProjection, ...], _typed_rows(projection_raw["enforcement_projection"], "enforcement_projection", _TABLE_FIELDS["enforcement_projection_table"], _enforcement_projection))
    effect_remaps = cast(tuple[RuntimeEffectRemap, ...], _typed_rows(projection_raw["effect_remaps"], "effect_remaps", _TABLE_FIELDS["effect_remaps"], _effect_remap))
    precedence = cast(tuple[RuntimePrecedenceDecision, ...], _typed_rows(projection_raw["constraint_precedence"], "constraint_precedence", frozenset({"id", "key", "rank"}), _precedence))
    capabilities = cast(tuple[RuntimeCapabilityRule, ...], _typed_rows(projection_raw["capability_rules"], "capability_rules", frozenset({"id", "planner", "food_model", "base_slot_models", "slot_models", "product_scope", "formulations", "near_to_model"}), _capability))
    _ensure_unique(tuple(row.state for row in lifecycle), "lifecycle.states", "state")
    assignment_raw = _exact_map(projection_raw["assignment_governance"], "assignment_governance", frozenset({"id", "required", "required_fields", "secondary_enforcement_cap"}))
    assignment = _assignment(assignment_raw, "assignment_governance")
    scoring = _effect_scoring(projection_raw["effect_scoring"], "effect_scoring")
    _ensure_unique(tuple(row.mode for row in enforcement), "enforcement.modes", "mode")
    _ensure_unique(tuple(row.lifecycle_state for row in gates), "execution_gates", "lifecycle_state")
    _ensure_unique(tuple(row.outcome for row in outcomes), "scope_outcomes", "outcome")
    _ensure_unique(tuple(row.rank for row in outcomes), "scope_outcomes", "rank")
    _ensure_unique(tuple(row.key for row in dimensions), "scope.dimensions", "key")
    _ensure_unique(tuple(row.key for row in precedence), "constraint_precedence", "key")
    _validate_scope_priority_ambiguity(dimensions, scope_rules, "scope rules")
    _validate_runtime_semantics(fact_fields, lifecycle, degradation, enforcement, governance, assignment_axes, authorities, competition_rules, enforcement_projection, effect_remaps, scoring.scores, capabilities, outcomes, dimensions, scope_rules, "runtime semantics")
    rules = _rule_rows(root["rules"], "rules")
    tables = _tables(root["tables"])
    _validate_projection_duplicates(projection_raw, rules, tables)
    projection = RuntimeProjection(fact_fields, assignment, capabilities, governance, precedence, scoring, enforcement, gates, lifecycle, degradation, dimensions, outcomes, schedule_axes, assignment_axes, scope_rules, authorities, competition_rules, enforcement_projection, effect_remaps)
    return RuntimeProgram(fmt, schema, source_hash, provenance, protocol, projection, fact_fields, lifecycle, enforcement, gates, governance, outcomes, dimensions, assignment, scoring, precedence, capabilities, schedule_axes, assignment_axes, scope_rules, authorities, competition_rules, enforcement_projection, effect_remaps, rules, tables)
