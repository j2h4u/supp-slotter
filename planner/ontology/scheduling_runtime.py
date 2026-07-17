"""Generic interpreter for the executable scheduling ontology.

The interpreter intentionally knows only the row shapes exposed by
``RuntimeProgram``.  Scheduling behaviour is selected by identifiers and
conditions in the verified program; no planner-engine policy is imported.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from numbers import Real
from typing import Any, cast

from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.runtime_program import RuntimeConstraintGovernance, RuntimeProgram, RuntimeScopeOutcome, RuntimeScopeRule, RuntimeValue


@dataclass(frozen=True, slots=True)
class RuntimeScopeDecision:
    outcome: str
    action: str
    enforcement_cap: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeAuthorityDecision:
    authority: str
    rank: int
    enforcement_cap: str
    score_weight: float


@dataclass(frozen=True, slots=True)
class RuntimeShadowDecision:
    assignment_id: str
    action: str
    enforcement_cap: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeEffectiveEnforcementDecision:
    mode: str
    effect_role: str
    action_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeScoreDecision:
    level: str
    block: bool
    score_delta: float
    action_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeConstraintDecision:
    executable: bool
    effect_role: str
    blocks: bool
    score_delta: float
    action_codes: tuple[str, ...]


def _error(label: str, message: str) -> OntologyInfrastructureError:
    return OntologyInfrastructureError(f"scheduling runtime {label} {message}", code=MALFORMED)


def _condition_fields(value: RuntimeValue) -> frozenset[str]:
    """Return condition paths declared by one validated runtime value."""
    decoded = _condition_value(value)
    if isinstance(decoded, Mapping):
        clauses: tuple[object, ...] = (decoded,)
    elif isinstance(decoded, tuple):
        clauses = decoded
    else:
        raise _error("condition", "has malformed immutable representation")
    fields: set[str] = set()

    def visit(condition: object) -> None:
        if not isinstance(condition, Mapping):
            raise _error("condition", "clauses must be mappings")
        operator = condition.get("operator")
        if not isinstance(operator, str):
            raise _error("condition", "operator is missing")
        if operator in {"equals", "contains", "is_true", "is_false"}:
            field = condition.get("field")
            if not isinstance(field, str) or not field:
                raise _error("condition", "field is missing")
            fields.add(field)
            return
        if operator not in {"all", "any", "not"}:
            raise _error("condition", f"unknown operator {operator!r}")
        children = condition.get("conditions")
        if not isinstance(children, Sequence) or isinstance(children, (str, bytes)) or not children:
            raise _error("condition", "compound condition has no children")
        if operator == "not" and len(children) != 1:
            raise _error("condition", "not requires one child")
        for child in children:
            visit(child)

    if not clauses or any(not isinstance(item, Mapping) for item in clauses):
        raise _error("condition", "clauses must be non-empty mappings")
    for clause in clauses:
        visit(clause)
    return frozenset(fields)


def _declared_condition_fields(rows: Iterable[Any]) -> frozenset[str]:
    fields: set[str] = set()
    for row in rows:
        fields.update(_condition_fields(row.conditions))
    return frozenset(fields)


def _facts(rows: Iterable[Any], facts: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(facts, Mapping) or any(not isinstance(key, str) for key in facts):
        raise _error("facts", "must be a mapping with string keys")
    allowed = _declared_condition_fields(rows)
    unknown = set(facts) - allowed
    if unknown:
        raise _error("facts", f"unknown dimensions {sorted(unknown)!r}")
    return facts


def _condition_value(value: object) -> object:
    """Decode the recursive immutable representation used by RuntimeValue."""
    if isinstance(value, tuple):
        # A mapping is encoded as tuple[(string key, RuntimeValue), ...].
        if all(isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) for item in value):
            return {cast(str, key): _condition_value(item_value) for key, item_value in value}
        return tuple(_condition_value(item) for item in value)
    return value


def _matches_condition(condition: Mapping[str, object], facts: Mapping[str, object]) -> bool:
    operator = condition.get("operator")
    if not isinstance(operator, str):
        raise _error("condition", "operator is missing")
    if operator in {"equals", "contains", "is_true", "is_false"}:
        field = condition.get("field")
        if not isinstance(field, str):
            raise _error("condition", "field is missing")
        if field not in facts:
            return False
        actual = facts[field]
        if operator == "equals":
            return actual == condition.get("value")
        if operator == "contains":
            return isinstance(actual, str) and str(condition.get("value")) in actual
        if not isinstance(actual, bool):
            return False
        return actual if operator == "is_true" else not actual
    children = condition.get("conditions")
    if not isinstance(children, Sequence) or isinstance(children, (str, bytes)):
        raise _error("condition", "compound condition has no children")
    decoded = []
    for child in children:
        if not isinstance(child, Mapping):
            raise _error("condition", "compound child is not a mapping")
        decoded.append(_matches_condition(cast(Mapping[str, object], child), facts))
    if operator == "all":
        return all(decoded)
    if operator == "any":
        return any(decoded)
    if operator == "not":
        if len(decoded) != 1:
            raise _error("condition", "not requires one child")
        return not decoded[0]
    raise _error("condition", f"unknown operator {operator!r}")


def _condition_matches(value: RuntimeValue, facts: Mapping[str, object]) -> bool:
    # A condition row is encoded as a tuple of mappings, one for each clause.
    decoded = _condition_value(value)
    if isinstance(decoded, Mapping):
        clauses: tuple[object, ...] = (decoded,)
    elif isinstance(decoded, tuple):
        clauses = decoded
    else:
        raise _error("condition", "has malformed immutable representation")
    if not clauses or any(not isinstance(item, Mapping) for item in clauses):
        raise _error("condition", "clauses must be non-empty mappings")
    return all(_matches_condition(cast(Mapping[str, object], item), facts) for item in clauses)


def _best(rows: Sequence[Any], label: str) -> Any | None:
    if not rows:
        return None
    maximum = max(row.priority for row in rows)
    winners = tuple(row for row in rows if row.priority == maximum)
    if len(winners) != 1:
        raise _error(label, "has ambiguous highest-priority matches")
    return winners[0]


def _outcome(program: RuntimeProgram, identifier: str) -> RuntimeScopeOutcome:
    rows = tuple(row for row in program.scope_outcomes if row.id == identifier or row.outcome == identifier)
    if len(rows) != 1:
        raise _error("scope outcome", f"{identifier!r} is missing or ambiguous")
    return rows[0]


def evaluate_scope(program: RuntimeProgram, scope: str, facts: Mapping[str, object]) -> RuntimeScopeDecision:
    """Evaluate one named scope dimension against generic fact values."""
    if not isinstance(scope, str) or not scope:
        raise _error("scope", "must be a non-empty dimension key")
    dimension = next((row for row in program.scope_dimensions if row.key == scope), None)
    if dimension is None:
        raise _error("scope", f"unknown dimension {scope!r}")
    rules: list[RuntimeScopeRule] = []
    for rule_id in dimension.rule_ids:
        matches = tuple(row for row in program.scope_rules if row.id == rule_id)
        if len(matches) != 1:
            raise _error("scope", f"dimension {scope!r} references missing or ambiguous rule {rule_id!r}")
        rules.append(matches[0])
    facts = _facts(program.scope_rules, facts)
    candidates = [rule for rule in rules if _condition_matches(rule.conditions, facts)]
    winner = _best(candidates, "scope")
    if winner is None:
        outcome = _outcome(program, dimension.default_outcome)
        reasons = (outcome.id,)
    else:
        outcome = _outcome(program, winner.outcome)
        reasons = (winner.id,)
    return RuntimeScopeDecision(outcome.outcome, outcome.scope_action, outcome.enforcement_cap, reasons)


def resolve_authority(program: RuntimeProgram, facts: Mapping[str, object]) -> RuntimeAuthorityDecision:
    facts = _facts(program.authorities, facts)
    matches = tuple(row for row in program.authorities if _condition_matches(row.conditions, facts))
    winner = _best(matches, "authority")
    if winner is None:
        raise _error("authority", "has no matching declarative rule")
    return RuntimeAuthorityDecision(winner.authority, winner.priority, _highest_cap(program), 1.0)


def _highest_cap(program: RuntimeProgram) -> str:
    rows = tuple(program.enforcement)
    if not rows:
        raise _error("enforcement", "has no declarative modes")
    return max(rows, key=lambda row: row.rank).mode


def apply_shadow_rules(program: RuntimeProgram, assignments: Sequence[Mapping[str, object]]) -> tuple[RuntimeShadowDecision, ...]:
    if not isinstance(assignments, Sequence) or isinstance(assignments, (str, bytes)):
        raise _error("assignments", "must be a sequence of mappings")
    decisions: list[RuntimeShadowDecision] = []
    for index, assignment in enumerate(assignments):
        if not isinstance(assignment, Mapping):
            raise _error(f"assignments[{index}]", "must be a mapping")
        assignment_id = assignment.get("assignment_id")
        if not isinstance(assignment_id, str) or not assignment_id:
            raise _error(f"assignments[{index}]", "assignment_id must be a non-empty string")
        facts = _facts(program.shadow_rules, assignment.get("facts", assignment))
        matches = tuple(row for row in program.shadow_rules if _condition_matches(row.conditions, facts))
        winner = _best(matches, "shadow")
        original_cap = assignment.get("enforcement_cap")
        if not isinstance(original_cap, str) or not original_cap:
            raise _error(f"assignments[{index}]", "enforcement_cap must be a non-empty string")
        if winner is None:
            raise _error(f"assignments[{index}]", "has no matching declarative shadow rule")
        else:
            decisions.append(RuntimeShadowDecision(assignment_id, winner.action, program.assignment_governance.secondary_enforcement_cap, (winner.id,)))
    return tuple(decisions)


def decide_enforcement(program: RuntimeProgram, requested_mode: str, caps: Iterable[str]) -> RuntimeEffectiveEnforcementDecision:
    if not isinstance(requested_mode, str) or not requested_mode:
        raise _error("enforcement", "requested mode must be a non-empty string")
    requested = next((row for row in program.enforcement if row.mode == requested_mode), None)
    if requested is None:
        raise _error("enforcement", f"unknown requested mode {requested_mode!r}")
    cap_values = tuple(caps)
    for cap in cap_values:
        if not isinstance(cap, str) or not any(row.mode == cap for row in program.enforcement):
            raise _error("enforcement", f"unknown cap {cap!r}")
    effective = min((requested, *tuple(row for row in program.enforcement if row.mode in cap_values)), key=lambda row: row.rank) if cap_values else requested
    projection = tuple(row for row in program.enforcement_projection if row.mode == effective.mode)
    if len(projection) != 1:
        raise _error("enforcement", f"projection for {effective.mode!r} is missing or ambiguous")
    return RuntimeEffectiveEnforcementDecision(effective.mode, projection[0].effect_role, (effective.id, projection[0].id))


def decide_effect(program: RuntimeProgram, mode: str, level: str, block: bool, weight: float) -> RuntimeScoreDecision:
    if not isinstance(mode, str) or not isinstance(level, str) or not mode or not level:
        raise _error("effect", "mode and level must be non-empty strings")
    if not isinstance(block, bool) or isinstance(weight, bool) or not isinstance(weight, Real):
        raise _error("effect", "block must be boolean and weight must be numeric")
    remaps = tuple(row for row in program.effect_remaps if row.mode == mode and row.level == level)
    if len(remaps) != 1:
        raise _error("effect", f"remap for {mode!r}/{level!r} is missing or ambiguous")
    remap = remaps[0]
    scores = tuple(row for row in program.effect_scoring.scores if row.level == remap.result)
    if len(scores) != 1:
        raise _error("effect", f"score for result level {remap.result!r} is missing or ambiguous")
    return RuntimeScoreDecision(remap.result, block and remap.block, float(scores[0].score) * float(remap.weight) * float(weight), (remap.id, scores[0].id))


def _evidence_ok(governance: RuntimeConstraintGovernance, requirement: str, has_evidence: bool) -> bool:
    if not isinstance(has_evidence, bool):
        raise _error("constraint", "has_evidence must be boolean")
    if requirement == "required":
        return has_evidence
    if requirement == "prohibited":
        return not has_evidence
    if requirement == "evidence_or_gap":
        return True
    raise _error("constraint", f"unknown evidence requirement {requirement!r}")


def _constraint_score(program: RuntimeProgram, mode: str, match_count: int, effect_role: str) -> float:
    """Compute the declarative score for a validated, executable constraint row."""
    if not isinstance(mode, str) or not mode:
        raise _error("constraint", "mode must be a non-empty string")
    if isinstance(match_count, bool) or not isinstance(match_count, int) or match_count < 0:
        raise _error("constraint", "match_count must be a non-negative integer")
    modes = tuple(row for row in program.constraint_governance.enforcement_modes if row.mode == mode)
    if len(modes) != 1:
        raise _error("constraint", f"unknown or ambiguous mode {mode!r}")
    if not isinstance(effect_role, str) or not effect_role:
        raise _error("constraint", "effect role must be a non-empty string")
    declared_roles = frozenset(row.effect_role for row in program.enforcement_projection)
    if effect_role not in declared_roles or effect_role not in {"none", "warning", "blocking"}:
        raise _error("constraint", f"unknown effect role {effect_role!r}")
    if match_count == 0 or effect_role != "warning":
        return 0.0
    return float(program.effect_scoring.advisory_constraint_score_delta)


def decide_constraint(program: RuntimeProgram, lifecycle: str, mode: str, has_evidence: bool, match_count: int) -> RuntimeConstraintDecision:
    if not isinstance(lifecycle, str) or not isinstance(mode, str) or not lifecycle or not mode:
        raise _error("constraint", "lifecycle and mode must be non-empty strings")
    if isinstance(match_count, bool) or not isinstance(match_count, int) or match_count < 0:
        raise _error("constraint", "match_count must be a non-negative integer")
    governance = program.constraint_governance
    life = tuple(row for row in governance.lifecycle_states if row.state == lifecycle)
    enforcement = tuple(row for row in governance.enforcement_modes if row.mode == mode)
    gates = tuple(row for row in governance.execution_gates if row.lifecycle_state == lifecycle)
    if len(life) != 1 or len(enforcement) != 1 or len(gates) != 1:
        raise _error("constraint", "lifecycle, mode, or execution gate is missing or ambiguous")
    allowed = (lifecycle, mode) in governance.allowed_pairs
    evidence = _evidence_ok(governance, gates[0].evidence_requirement, has_evidence)
    executable = life[0].executable and enforcement[0].executable and gates[0].executable and allowed and evidence
    declared_delta = _constraint_score(program, mode, match_count, enforcement[0].effect_role)
    blocks = executable and enforcement[0].effect_role == "blocking" and match_count > 0
    delta = declared_delta if executable else 0.0
    return RuntimeConstraintDecision(executable, enforcement[0].effect_role, blocks, delta, (life[0].id, enforcement[0].id, gates[0].id))


__all__ = [
    "RuntimeAuthorityDecision",
    "RuntimeConstraintDecision",
    "RuntimeEffectiveEnforcementDecision",
    "RuntimeScoreDecision",
    "RuntimeScopeDecision",
    "RuntimeShadowDecision",
    "apply_shadow_rules",
    "decide_constraint",
    "decide_effect",
    "decide_enforcement",
    "evaluate_scope",
    "resolve_authority",
]
