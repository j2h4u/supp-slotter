"""Generic, fail-closed interpreter for the executable scheduling ontology.

The interpreter performs only structural mechanics: fact comparison, rule
ranking, enforcement-cap ranking, and numeric score multiplication. Policy
identifiers and outcomes are supplied exclusively by the verified program.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from numbers import Real
from types import MappingProxyType
from typing import Any, cast

from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.runtime_program import (
    RuntimeEnforcementDecision,
    RuntimeProgram,
    RuntimeScopeOutcome,
    RuntimeScopeRule,
    RuntimeValue,
)


@dataclass(frozen=True, slots=True)
class RuntimeCapabilityDecision:
    capability_id: str
    base_slot_models: tuple[str, ...]
    slot_models: tuple[str, ...]
    product_scope: tuple[str, ...]
    formulations: tuple[str, ...]
    near_to_model: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class RuntimeScopeDecision:
    outcome: str
    action: str
    enforcement_cap: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeAssignmentAuthorityDecision:
    authority: str
    priority: int
    enforcement_cap: str
    score_weight: float
    control_rank: int
    action_code: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeComponentAuthorityDecision:
    outcome: str
    priority: int
    rule_id: str


@dataclass(frozen=True, slots=True)
class RuntimeCompetitionDecision:
    action_code: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeEffectiveEnforcementDecision:
    requested_mode: str
    mode: str
    effect_role: str
    executable: bool
    action_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeScoreDecision:
    level: str | None
    block: bool
    score_delta: float
    action_codes: tuple[str, ...]


def _error(label: str, message: str) -> OntologyInfrastructureError:
    return OntologyInfrastructureError(f"scheduling runtime {label} {message}", code=MALFORMED)


def _condition_value(value: object) -> object:
    if isinstance(value, tuple):
        if not value:
            return ()
        if all(isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) for item in value):
            return {cast(str, key): _condition_value(item) for key, item in value}
        return tuple(_condition_value(item) for item in value)
    return value


def _conditions(value: RuntimeValue) -> tuple[Mapping[str, object], ...]:
    decoded = _condition_value(value)
    if isinstance(decoded, Mapping):
        return (cast(Mapping[str, object], decoded),)
    if isinstance(decoded, tuple) and all(isinstance(item, Mapping) for item in decoded):
        return cast(tuple[Mapping[str, object], ...], decoded)
    raise _error("condition", "has malformed immutable representation")


def _condition_fields(value: RuntimeValue) -> frozenset[str]:
    fields: set[str] = set()

    def visit(condition: Mapping[str, object]) -> None:
        operator = condition.get("operator")
        if not isinstance(operator, str):
            raise _error("condition", "operator is missing")
        if operator in {"equals", "equals_field", "member_of_field", "contains", "is_true", "is_false"}:
            field = condition.get("field")
            if not isinstance(field, str) or not field:
                raise _error("condition", "field is missing")
            fields.add(field)
            if operator in {"equals_field", "member_of_field"}:
                other = condition.get("value")
                if not isinstance(other, str) or not other:
                    raise _error("condition", "field operand is missing")
                fields.add(other)
            return
        if operator not in {"all", "any", "not"}:
            raise _error("condition", f"unknown operator {operator!r}")
        children = condition.get("conditions")
        if not isinstance(children, Sequence) or isinstance(children, (str, bytes)) or not children:
            raise _error("condition", "compound condition has no children")
        if operator == "not" and len(children) != 1:
            raise _error("condition", "not requires one child")
        for child in children:
            if not isinstance(child, Mapping):
                raise _error("condition", "compound child is not a mapping")
            visit(cast(Mapping[str, object], child))

    for clause in _conditions(value):
        visit(clause)
    return frozenset(fields)


def _facts(program: RuntimeProgram, rows: Iterable[Any], facts: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(facts, Mapping) or any(not isinstance(key, str) for key in facts):
        raise _error("facts", "must be a mapping with string keys")
    declarations = {row.field: row.value_type for row in program.fact_fields}
    for field, value in facts.items():
        value_type = declarations.get(field)
        if value_type is None:
            raise _error("facts", f"contains undeclared field {field!r}")
        if value_type == "string":
            if not isinstance(value, str) or not value:
                raise _error("facts", f"field {field!r} must be a non-empty string")
        elif value_type == "strings":
            if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
                raise _error("facts", f"field {field!r} must be a non-empty sequence of strings")
            if any(not isinstance(item, str) or not item for item in value):
                raise _error("facts", f"field {field!r} must contain only non-empty strings")
        elif value_type == "boolean":
            if not isinstance(value, bool):
                raise _error("facts", f"field {field!r} must be boolean")
        else:
            raise _error("facts", f"field {field!r} has unknown declared type {value_type!r}")
    declared: set[str] = set()
    for row in rows:
        declared.update(_condition_fields(row.conditions))
    actual = set(facts)
    if actual != declared:
        raise _error("facts", f"has invalid dimensions (missing={sorted(declared - actual)}, unknown={sorted(actual - declared)})")
    return facts


def _matches_condition(condition: Mapping[str, object], facts: Mapping[str, object]) -> bool:
    operator = condition.get("operator")
    if not isinstance(operator, str):
        raise _error("condition", "operator is missing")
    if operator in {"equals", "equals_field", "member_of_field", "contains", "is_true", "is_false"}:
        field = condition.get("field")
        if not isinstance(field, str) or field not in facts:
            raise _error("condition", "references an unavailable field")
        actual = facts[field]
        if operator == "equals":
            return actual == condition.get("value")
        if operator in {"equals_field", "member_of_field"}:
            other = condition.get("value")
            if not isinstance(other, str) or other not in facts:
                raise _error("condition", "references an unavailable operand field")
            operand = facts[other]
            if operator == "equals_field":
                return actual == operand
            if not isinstance(operand, Sequence) or isinstance(operand, (str, bytes)):
                raise _error("condition", "member operand must be a sequence")
            return actual in operand
        if operator == "contains":
            operand = condition.get("value")
            return isinstance(actual, str) and isinstance(operand, str) and operand in actual
        if not isinstance(actual, bool):
            return False
        return actual if operator == "is_true" else not actual
    children = condition.get("conditions")
    if not isinstance(children, Sequence) or isinstance(children, (str, bytes)) or not children:
        raise _error("condition", "compound condition has no children")
    results = tuple(
        _matches_condition(cast(Mapping[str, object], child), facts)
        for child in children
        if isinstance(child, Mapping)
    )
    if len(results) != len(children):
        raise _error("condition", "compound child is not a mapping")
    if operator == "all":
        return all(results)
    if operator == "any":
        return any(results)
    if operator == "not" and len(results) == 1:
        return not results[0]
    raise _error("condition", f"unknown or malformed operator {operator!r}")


def _condition_matches(value: RuntimeValue, facts: Mapping[str, object]) -> bool:
    return all(_matches_condition(clause, facts) for clause in _conditions(value))


def _best(rows: Sequence[Any], label: str) -> Any | None:
    if not rows:
        return None
    priority = max(row.priority for row in rows)
    winners = tuple(row for row in rows if row.priority == priority)
    if len(winners) != 1:
        raise _error(label, "has ambiguous highest-priority matches")
    return winners[0]


def _outcome(program: RuntimeProgram, identifier: str) -> RuntimeScopeOutcome:
    rows = tuple(row for row in program.scope_outcomes if row.id == identifier)
    if len(rows) != 1:
        raise _error("scope outcome", f"{identifier!r} is missing or ambiguous")
    return rows[0]


def resolve_capability(program: RuntimeProgram, planner: str, food_model: str) -> RuntimeCapabilityDecision:
    """Resolve the sole capability row for an exact planner/food-model pair."""
    if not isinstance(planner, str) or not planner or not isinstance(food_model, str) or not food_model:
        raise _error("capability", "planner and food model must be non-empty strings")
    rows = tuple(row for row in program.capability_rules if row.planner == planner and row.food_model == food_model)
    if len(rows) != 1:
        raise _error("capability", "planner/food-model pair is missing or ambiguous")
    row = rows[0]
    near = {item.near: item.model for item in row.near_to_model}
    if len(near) != len(row.near_to_model):
        raise _error("capability", "near-model keys are ambiguous")
    return RuntimeCapabilityDecision(
        row.id,
        row.base_slot_models,
        row.slot_models,
        row.product_scope,
        row.formulations,
        MappingProxyType(near),
    )


def evaluate_scope(program: RuntimeProgram, scope: str, facts: Mapping[str, object]) -> RuntimeScopeDecision:
    """Evaluate one named scope dimension against its exact declared fact shape."""
    if not isinstance(scope, str) or not scope:
        raise _error("scope", "must be a non-empty dimension key")
    dimension = next((row for row in program.scope_dimensions if row.key == scope), None)
    if dimension is None:
        raise _error("scope", f"unknown dimension {scope!r}")
    rules: list[RuntimeScopeRule] = []
    for rule_id in dimension.rule_ids:
        rows = tuple(row for row in program.scope_rules if row.id == rule_id)
        if len(rows) != 1:
            raise _error("scope", f"dimension references missing or ambiguous rule {rule_id!r}")
        rules.append(rows[0])
    checked = _facts(program, rules, facts)
    winner = _best(tuple(row for row in rules if _condition_matches(row.conditions, checked)), "scope")
    outcome = _outcome(program, dimension.default_outcome if winner is None else winner.outcome)
    reason = outcome.id if winner is None else winner.id
    return RuntimeScopeDecision(outcome.outcome, outcome.scope_action, outcome.enforcement_cap, (reason,))


def resolve_assignment_authority(program: RuntimeProgram, facts: Mapping[str, object]) -> RuntimeAssignmentAuthorityDecision:
    checked = _facts(program, program.authorities, facts)
    winner = _best(tuple(row for row in program.authorities if _condition_matches(row.conditions, checked)), "assignment authority")
    if winner is None:
        raise _error("assignment authority", "has no matching declarative rule")
    return RuntimeAssignmentAuthorityDecision(
        winner.authority,
        winner.priority,
        winner.enforcement_cap,
        float(winner.score_weight),
        winner.control_rank,
        winner.action_code,
        (winner.reason_code, winner.id),
    )


def resolve_component_authority(program: RuntimeProgram, facts: Mapping[str, object]) -> RuntimeComponentAuthorityDecision:
    """Resolve component authority from the authored, typed component table."""
    checked = _facts(program, program.component_authority, facts)
    winner = _best(
        tuple(row for row in program.component_authority if _condition_matches(row.conditions, checked)),
        "component authority",
    )
    if winner is None:
        raise _error("component authority", "has no matching declarative rule")
    return RuntimeComponentAuthorityDecision(winner.outcome, winner.priority, winner.id)


def decide_competition(program: RuntimeProgram, facts: Mapping[str, object]) -> RuntimeCompetitionDecision:
    checked = _facts(program, program.competition_rules, facts)
    winner = _best(tuple(row for row in program.competition_rules if _condition_matches(row.conditions, checked)), "competition")
    if winner is None:
        raise _error("competition", "has no matching declarative rule")
    return RuntimeCompetitionDecision(winner.action_code, (winner.reason_code, winner.id))


def _enforcement_row(program: RuntimeProgram, mode: str) -> RuntimeEnforcementDecision:
    rows = tuple(row for row in program.enforcement if row.mode == mode)
    if len(rows) != 1:
        raise _error("enforcement", f"mode {mode!r} is missing or ambiguous")
    return rows[0]


def decide_assignment_enforcement(
    program: RuntimeProgram,
    requested_mode: str,
    lifecycle_states: Iterable[str],
    caps: Iterable[str],
) -> RuntimeEffectiveEnforcementDecision:
    """Apply authored caps, then exact lifecycle/incoming-mode remaps."""
    if not isinstance(requested_mode, str) or not requested_mode:
        raise _error("enforcement", "requested mode must be a non-empty string")
    if isinstance(caps, (str, bytes)) or isinstance(lifecycle_states, (str, bytes)):
        raise _error("enforcement", "caps and lifecycle states must be iterables of strings")
    try:
        cap_values = tuple(caps)
        state_values = tuple(lifecycle_states)
    except TypeError as error:
        raise _error("enforcement", "caps and lifecycle states must be iterables of strings") from error
    if not state_values:
        raise _error("enforcement", "at least one lifecycle state is required")
    requested = _enforcement_row(program, requested_mode)
    candidates = [requested]
    codes: list[str] = [requested.id]
    for cap in cap_values:
        if not isinstance(cap, str) or not cap:
            raise _error("enforcement", "caps must be non-empty strings")
        row = _enforcement_row(program, cap)
        candidates.append(row)
        codes.append(row.id)
    capped = min(candidates, key=lambda row: row.rank)
    lifecycle_executable = True
    lifecycle_candidates = [capped]
    for state in state_values:
        if not isinstance(state, str) or not state:
            raise _error("enforcement", "lifecycle states must be non-empty strings")
        lifecycle = tuple(row for row in program.lifecycle if row.state == state)
        degradation = tuple(
            row
            for row in program.projection.degradation
            if row.lifecycle_state == state and row.incoming_mode == capped.mode
        )
        if len(lifecycle) != 1 or len(degradation) != 1:
            raise _error("enforcement", f"lifecycle/mode pair {(state, capped.mode)!r} is missing or ambiguous")
        lifecycle_executable = lifecycle_executable and lifecycle[0].executable
        lifecycle_candidates.append(_enforcement_row(program, degradation[0].effective_mode))
        codes.extend((lifecycle[0].id, degradation[0].id))
    effective = min(lifecycle_candidates, key=lambda row: row.rank)
    projection = tuple(row for row in program.enforcement_projection if row.mode == effective.mode)
    if len(projection) != 1:
        raise _error("enforcement", "effective projection is missing or ambiguous")
    codes.append(projection[0].id)
    return RuntimeEffectiveEnforcementDecision(
        requested.mode,
        effective.mode,
        projection[0].effect_role,
        lifecycle_executable and effective.executable,
        tuple(codes),
    )


def decide_effect(program: RuntimeProgram, mode: str, level: str | None, block: bool, weight: float) -> RuntimeScoreDecision:
    if not isinstance(mode, str) or not mode or (level is not None and (not isinstance(level, str) or not level)):
        raise _error("effect", "mode must be a non-empty string and level must be null or a non-empty string")
    if not isinstance(block, bool) or isinstance(weight, bool) or not isinstance(weight, Real):
        raise _error("effect", "block must be boolean and weight must be numeric")
    if not isfinite(float(weight)) or float(weight) < 0:
        raise _error("effect", "weight must be finite and non-negative")
    rows = tuple(row for row in program.effect_remaps if row.mode == mode and row.level == level)
    if len(rows) != 1:
        raise _error("effect", "remap is missing or ambiguous")
    remap = rows[0]
    score = 0.0
    score_id: str | None = None
    if remap.score_enabled:
        scores = tuple(row for row in program.effect_scoring.scores if row.level == remap.projected_level)
        if len(scores) != 1:
            raise _error("effect", "projected score is missing or ambiguous")
        score = float(scores[0].score) * float(weight)
        score_id = scores[0].id
    elif remap.projected_level is not None:
        raise _error("effect", "disabled score has a projected level")
    if remap.block_behavior == "preserve":
        effective_block = block
    elif remap.block_behavior == "suppress":
        effective_block = False
    else:
        raise _error("effect", "unknown block behavior")
    decisions: list[str] = []
    if remap.projected_level != level:
        decisions.append(remap.level_code)
    if block:
        decisions.append(remap.block_code)
    if not decisions:
        decisions.append(remap.default_code)
    codes = (remap.id, *decisions) if score_id is None else (remap.id, score_id, *decisions)
    return RuntimeScoreDecision(remap.projected_level, effective_block, score, codes)


__all__ = [
    "RuntimeAssignmentAuthorityDecision",
    "RuntimeCapabilityDecision",
    "RuntimeCompetitionDecision",
    "RuntimeEffectiveEnforcementDecision",
    "RuntimeScoreDecision",
    "RuntimeScopeDecision",
    "decide_assignment_enforcement",
    "decide_competition",
    "decide_effect",
    "evaluate_scope",
    "resolve_assignment_authority",
    "resolve_capability",
]
