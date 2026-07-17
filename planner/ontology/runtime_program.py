"""Strict, immutable, typed view of the verified executable ontology projection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType
from typing import TypeAlias, cast
from urllib.parse import urlparse

from planner.ontology.errors import MALFORMED, OntologyInfrastructureError

_FORMAT = "ontology-runtime-program-v1"
_TOP_KEYS = frozenset({"format_version", "schema_version", "source_hash", "provenance", "protocol", "projection", "rules", "tables"})
_PROJECTION_KEYS = frozenset({"assignment_governance", "capability_rules", "constraint_governance", "constraint_precedence", "effect_scoring", "enforcement", "execution_gates", "lifecycle", "scope", "scope_outcomes"})
_RULE_FIELDS = {
    "capability": frozenset({"food_model", "formulations", "id", "kind", "near_to_model", "planner", "product_scope", "slot_models"}),
    "constraint_allowed_pair": frozenset({"enforcement_mode", "id", "kind", "lifecycle_state"}),
    "constraint_enforcement": frozenset({"executable", "id", "kind", "mode", "rank"}),
    "constraint_execution_gate": frozenset({"evidence_requirement", "executable", "id", "kind", "lifecycle_state"}),
    "constraint_lifecycle": frozenset({"executable", "id", "kind", "rank", "state"}),
    "degradation": frozenset({"advisory_action", "id", "kind", "lifecycle_state", "maximum_enforcement", "preference_action", "secondary_cap"}),
    "effect_score": frozenset({"id", "kind", "level", "score"}),
    "enforcement": frozenset({"effect_role", "executable", "id", "kind", "mode", "rank"}),
    "execution_gate": frozenset({"evidence_requirement", "executable", "id", "kind", "lifecycle_state"}),
    "lifecycle": frozenset({"executable", "id", "kind", "rank", "state"}),
    "precedence": frozenset({"id", "key", "kind", "rank"}),
    "scope_outcome": frozenset({"direct_product", "formulation", "id", "kind", "outcome", "scope_action"}),
}
_TABLE_FIELDS = {
    "lifecycle": frozenset({"executable", "id", "rank", "state"}),
    "degradation": frozenset({"advisory_action", "id", "lifecycle_state", "maximum_enforcement", "preference_action", "secondary_cap"}),
    "enforcement": frozenset({"effect_role", "executable", "id", "mode", "rank"}),
    "execution_gates": frozenset({"evidence_requirement", "executable", "id", "lifecycle_state"}),
    "constraint_lifecycle": frozenset({"executable", "id", "rank", "state"}),
    "constraint_enforcement": frozenset({"executable", "id", "mode", "rank"}),
    "constraint_execution_gates": frozenset({"evidence_requirement", "executable", "id", "lifecycle_state"}),
    "constraint_allowed_pairs": frozenset({"enforcement_mode", "id", "lifecycle_state"}),
    "scope_outcomes": frozenset({"direct_product", "formulation", "id", "outcome", "scope_action"}),
    "effect_scores": frozenset({"id", "level", "score"}),
    "constraint_precedence": frozenset({"id", "key", "rank"}),
}
_RULE_FIELD_TYPES: Mapping[str, Mapping[str, str]] = {
    "capability": {"id": "str", "kind": "kind", "planner": "str", "food_model": "str", "slot_models": "strings", "product_scope": "strings", "formulations": "strings", "near_to_model": "near_models"},
    "constraint_allowed_pair": {"id": "str", "kind": "kind", "lifecycle_state": "str", "enforcement_mode": "str"},
    "constraint_enforcement": {"id": "str", "kind": "kind", "mode": "str", "rank": "int", "executable": "bool"},
    "constraint_execution_gate": {"id": "str", "kind": "kind", "lifecycle_state": "str", "evidence_requirement": "str", "executable": "bool"},
    "constraint_lifecycle": {"id": "str", "kind": "kind", "state": "str", "rank": "int", "executable": "bool"},
    "degradation": {"id": "str", "kind": "kind", "lifecycle_state": "str", "advisory_action": "str", "preference_action": "str", "maximum_enforcement": "str", "secondary_cap": "str"},
    "effect_score": {"id": "str", "kind": "kind", "level": "str", "score": "number"},
    "enforcement": {"id": "str", "kind": "kind", "mode": "str", "rank": "int", "executable": "bool", "effect_role": "str"},
    "execution_gate": {"id": "str", "kind": "kind", "lifecycle_state": "str", "evidence_requirement": "str", "executable": "bool"},
    "lifecycle": {"id": "str", "kind": "kind", "state": "str", "rank": "int", "executable": "bool"},
    "precedence": {"id": "str", "kind": "kind", "key": "str", "rank": "int"},
    "scope_outcome": {"id": "str", "kind": "kind", "outcome": "str", "scope_action": "str", "direct_product": "str", "formulation": "str"},
}
_TABLE_FIELD_TYPES: Mapping[str, Mapping[str, str]] = {
    "lifecycle": {"id": "str", "state": "str", "rank": "int", "executable": "bool"},
    "degradation": {"id": "str", "lifecycle_state": "str", "advisory_action": "str", "preference_action": "str", "maximum_enforcement": "str", "secondary_cap": "str"},
    "enforcement": {"id": "str", "mode": "str", "rank": "int", "executable": "bool", "effect_role": "str"},
    "execution_gates": {"id": "str", "lifecycle_state": "str", "evidence_requirement": "str", "executable": "bool"},
    "constraint_lifecycle": {"id": "str", "state": "str", "rank": "int", "executable": "bool"},
    "constraint_enforcement": {"id": "str", "mode": "str", "rank": "int", "executable": "bool"},
    "constraint_execution_gates": {"id": "str", "lifecycle_state": "str", "evidence_requirement": "str", "executable": "bool"},
    "constraint_allowed_pairs": {"id": "str", "lifecycle_state": "str", "enforcement_mode": "str"},
    "scope_outcomes": {"id": "str", "outcome": "str", "scope_action": "str", "direct_product": "str", "formulation": "str"},
    "effect_scores": {"id": "str", "level": "str", "score": "number"},
    "constraint_precedence": {"id": "str", "key": "str", "rank": "int"},
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
class RuntimeLifecycleDecision:
    id: str
    state: str
    rank: int
    executable: bool


@dataclass(frozen=True, slots=True)
class RuntimeDegradationRule:
    id: str
    lifecycle_state: str
    advisory_action: str
    preference_action: str
    maximum_enforcement: str
    secondary_cap: str


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
    scope_action: str
    direct_product: str
    formulation: str


@dataclass(frozen=True, slots=True)
class RuntimeScopeDimension:
    id: str
    key: str
    values: tuple[str, ...]


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


@dataclass(frozen=True, slots=True)
class RuntimeProgram:
    format_version: str
    schema_version: str
    source_hash: str
    provenance: RuntimeProvenance
    protocol: RuntimeProtocol
    projection: RuntimeProjection
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


def _degradation(row: Mapping[str, object], label: str) -> RuntimeDegradationRule:
    return RuntimeDegradationRule(*(_str(row[key], f"{label}.{key}") for key in ("id", "lifecycle_state", "advisory_action", "preference_action", "maximum_enforcement", "secondary_cap")))


def _enforcement(row: Mapping[str, object], label: str) -> RuntimeEnforcementDecision:
    return RuntimeEnforcementDecision(_str(row["id"], f"{label}.id"), _str(row["mode"], f"{label}.mode"), _int(row["rank"], f"{label}.rank"), _bool(row["executable"], f"{label}.executable"), _str(row["effect_role"], f"{label}.effect_role"))


def _gate(row: Mapping[str, object], label: str) -> RuntimeExecutionGate:
    return RuntimeExecutionGate(_str(row["id"], f"{label}.id"), _str(row["lifecycle_state"], f"{label}.lifecycle_state"), _str(row["evidence_requirement"], f"{label}.evidence_requirement"), _bool(row["executable"], f"{label}.executable"))


def _scope_outcome(row: Mapping[str, object], label: str) -> RuntimeScopeOutcome:
    return RuntimeScopeOutcome(*(_str(row[key], f"{label}.{key}") for key in ("id", "outcome", "scope_action", "direct_product", "formulation")))


def _scope_dimension(row: Mapping[str, object], label: str) -> RuntimeScopeDimension:
    return RuntimeScopeDimension(_str(row["id"], f"{label}.id"), _str(row["key"], f"{label}.key"), _strings(row["values"], f"{label}.values"))


def _capability(row: Mapping[str, object], label: str) -> RuntimeCapabilityRule:
    near_rows = _rows(row["near_to_model"], f"{label}.near_to_model")
    near: list[RuntimeNearModel] = []
    for index, item in enumerate(near_rows):
        _require_fields(item, f"{label}.near_to_model[{index}]", frozenset({"id", "near", "model"}))
        near.append(RuntimeNearModel(_str(item["id"], "near.id"), _str(item["near"], "near.near"), _str(item["model"], "near.model")))
    return RuntimeCapabilityRule(_str(row["id"], f"{label}.id"), _str(row["planner"], f"{label}.planner"), _str(row["food_model"], f"{label}.food_model"), _strings(row["slot_models"], f"{label}.slot_models"), _strings(row["product_scope"], f"{label}.product_scope"), _strings(row["formulations"], f"{label}.formulations"), tuple(near))


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
    enforcement = cast(tuple[RuntimeEnforcementDecision, ...], _typed_rows(raw["enforcement_modes"], f"{label}.enforcement_modes", frozenset({"id", "mode", "rank", "executable"}), lambda row, name: RuntimeEnforcementDecision(_str(row["id"], f"{name}.id"), _str(row["mode"], f"{name}.mode"), _int(row["rank"], f"{name}.rank"), _bool(row["executable"], f"{name}.executable"), "constraint")))
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
    elif expected == "strings":
        _strings(value, label)
    elif expected == "near_models":
        rows = _rows(value, label)
        for index, row in enumerate(rows):
            _require_fields(row, f"{label}[{index}]", frozenset({"id", "near", "model"}))
            _str(row["id"], f"{label}[{index}].id")
            _str(row["near"], f"{label}[{index}].near")
            _str(row["model"], f"{label}[{index}].model")
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
        for row_index, row in enumerate(_sequence_rows(table["rows"], f"tables[{index}].rows")):
            _require_fields(row, f"tables[{index}].rows[{row_index}]", fields)
            _validate_typed_row(row, f"tables[{index}].rows[{row_index}]", table_id, _TABLE_FIELD_TYPES[table_id])
            _validate_runtime_value(row, f"tables[{index}].rows[{row_index}]")
            rows.append(_row_map(row))
        result.append(RuntimeTable(table_id, tuple(rows)))
    return tuple(result)


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
    lifecycle_raw = _exact_map(projection_raw["lifecycle"], "projection.lifecycle", frozenset({"states", "degradation"}))
    lifecycle = cast(tuple[RuntimeLifecycleDecision, ...], _typed_rows(lifecycle_raw["states"], "lifecycle.states", frozenset({"id", "state", "rank", "executable"}), _lifecycle))
    degradation = cast(tuple[RuntimeDegradationRule, ...], _typed_rows(lifecycle_raw["degradation"], "lifecycle.degradation", frozenset({"id", "lifecycle_state", "advisory_action", "preference_action", "maximum_enforcement", "secondary_cap"}), _degradation))
    enforcement_raw = _exact_map(projection_raw["enforcement"], "projection.enforcement", frozenset({"modes"}))
    enforcement = cast(tuple[RuntimeEnforcementDecision, ...], _typed_rows(enforcement_raw["modes"], "enforcement.modes", frozenset({"id", "mode", "rank", "executable", "effect_role"}), _enforcement))
    governance = _governance(projection_raw["constraint_governance"], "constraint_governance")
    gates = cast(tuple[RuntimeExecutionGate, ...], _typed_rows(projection_raw["execution_gates"], "execution_gates", frozenset({"id", "lifecycle_state", "evidence_requirement", "executable"}), _gate))
    outcomes = cast(tuple[RuntimeScopeOutcome, ...], _typed_rows(projection_raw["scope_outcomes"], "scope_outcomes", frozenset({"id", "outcome", "scope_action", "direct_product", "formulation"}), _scope_outcome))
    scope_raw = _exact_map(projection_raw["scope"], "projection.scope", frozenset({"dimensions"}))
    dimensions = cast(tuple[RuntimeScopeDimension, ...], _typed_rows(scope_raw["dimensions"], "scope.dimensions", frozenset({"id", "key", "values"}), _scope_dimension))
    precedence = cast(tuple[RuntimePrecedenceDecision, ...], _typed_rows(projection_raw["constraint_precedence"], "constraint_precedence", frozenset({"id", "key", "rank"}), _precedence))
    capabilities = cast(tuple[RuntimeCapabilityRule, ...], _typed_rows(projection_raw["capability_rules"], "capability_rules", frozenset({"id", "planner", "food_model", "slot_models", "product_scope", "formulations", "near_to_model"}), _capability))
    _ensure_unique(tuple(row.state for row in lifecycle), "lifecycle.states", "state")
    assignment_raw = _exact_map(projection_raw["assignment_governance"], "assignment_governance", frozenset({"id", "required", "required_fields", "secondary_enforcement_cap"}))
    assignment = _assignment(assignment_raw, "assignment_governance")
    scoring = _effect_scoring(projection_raw["effect_scoring"], "effect_scoring")
    _ensure_unique(tuple(row.mode for row in enforcement), "enforcement.modes", "mode")
    _ensure_unique(tuple(row.lifecycle_state for row in gates), "execution_gates", "lifecycle_state")
    _ensure_unique(tuple(row.outcome for row in outcomes), "scope_outcomes", "outcome")
    _ensure_unique(tuple(row.key for row in dimensions), "scope.dimensions", "key")
    _ensure_unique(tuple(row.key for row in precedence), "constraint_precedence", "key")
    projection = RuntimeProjection(assignment, capabilities, governance, precedence, scoring, enforcement, gates, lifecycle, degradation, dimensions, outcomes)
    return RuntimeProgram(fmt, schema, source_hash, provenance, protocol, projection, lifecycle, enforcement, gates, governance, outcomes, dimensions, assignment, scoring, precedence, capabilities, _rule_rows(root["rules"], "rules"), _tables(root["tables"]))
