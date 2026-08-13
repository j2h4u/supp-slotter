"""Compilation of authored separate-slot constraints into runtime instructions."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from planner.contracts import RelationSelector, SchedulingConstraint, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.runtime_program import RuntimeConstraintExecutionPolicy, RuntimeProgram
from planner.ontology.schema_enums import schema_enum_values
from planner.ontology.selector import resolve_selector


@dataclass(frozen=True, slots=True)
class SchedulingConstraintExecutionPlan:
    """Fully resolved instruction for one scheduling constraint."""

    id: str
    source_substance_ids: tuple[str, ...]
    target_substance_ids: tuple[str, ...]
    operation: str
    executable: bool
    blocks_slots: bool
    scores_advisory: bool
    score_delta: int
    match_direction: str
    aggregation: str
    selector_resolution: str
    selector_resolution_outcome: str
    action: str | None = None
    source_selector: RelationSelector | None = None
    target_selector: RelationSelector | None = None
    rationale: str | None = None

    @property
    def source_ids(self) -> tuple[str, ...]:
        return self.source_substance_ids

    @property
    def target_ids(self) -> tuple[str, ...]:
        return self.target_substance_ids


@dataclass(frozen=True, slots=True)
class _AuthoredExecutionGrammar:
    operation_values: tuple[str, ...]
    direction_values: tuple[str, ...]
    aggregation_values: tuple[str, ...]


def compile_scheduling_constraint_execution_plans(
    constraints: Iterable[SchedulingConstraint],
    substances: dict[str, Substance],
    runtime_program: RuntimeProgram,
    *,
    ontology_bundle: OntologyBundle,
) -> tuple[SchedulingConstraintExecutionPlan, ...]:
    """Compile constraints against one verified runtime program.

    The authored operation and selector contract are required inputs.  Invalid
    operation/selector values fail at this boundary so search cannot silently
    proceed with a zero-effect default plan.
    """

    plans: list[SchedulingConstraintExecutionPlan] = []
    grammar = _authored_execution_grammar(ontology_bundle)
    for constraint in constraints:
        operation = constraint.operation
        if not operation:
            raise OntologyInfrastructureError(
                f"scheduling constraint {constraint.id}: operation must name a runtime execution operation",
                code=MALFORMED,
            )
        execution_policy = runtime_program.constraint_execution_policy_for(operation)
        if execution_policy is None:
            raise OntologyInfrastructureError(
                f"scheduling constraint {constraint.id}: unsupported operation '{operation}'",
                code=MALFORMED,
            )
        _validate_execution_grammar(
            constraint.id,
            operation,
            execution_policy.match_direction,
            execution_policy.aggregation,
            grammar=grammar,
        )
        _handler_for_operation(constraint.id, operation)
        _validate_selector_scope(constraint.id, constraint.source_selector, substances)
        _validate_selector_scope(constraint.id, constraint.target_selector, substances)
        source_resolution = resolve_selector(constraint.source_selector, substances, ontology_bundle)
        target_resolution = resolve_selector(constraint.target_selector, substances, ontology_bundle)
        source_ids, source_outcome = source_resolution.substance_ids, source_resolution.outcome
        target_ids, target_outcome = target_resolution.substance_ids, target_resolution.outcome
        selector_outcome = _combine_selector_outcomes(source_outcome, target_outcome)
        if selector_outcome in {"malformed_selector", "unsupported_selector"}:
            raise OntologyInfrastructureError(
                f"scheduling constraint {constraint.id}: {selector_outcome}",
                code=MALFORMED,
            )
        if selector_outcome == "empty" and execution_policy.selector_resolution == "require_nonempty":
            raise OntologyInfrastructureError(
                f"scheduling constraint {constraint.id}: selector resolution is empty",
                code=MALFORMED,
            )
        executable = selector_outcome == "resolved"
        blocks_slots = bool(
            executable
            and (constraint.blocks_slots if constraint.blocks_slots is not None else execution_policy.blocks_slots)
        )
        scores_advisory = bool(
            executable
            and (
                constraint.scores_advisory
                if constraint.scores_advisory is not None
                else execution_policy.scores_advisory
            )
        )
        plans.append(
            SchedulingConstraintExecutionPlan(
                id=constraint.id,
                source_substance_ids=source_ids,
                target_substance_ids=target_ids,
                operation=operation,
                executable=executable,
                blocks_slots=blocks_slots,
                scores_advisory=scores_advisory,
                score_delta=(
                    constraint.score_delta if constraint.score_delta is not None else execution_policy.score_delta
                )
                if scores_advisory
                else 0,
                match_direction=execution_policy.match_direction,
                aggregation=execution_policy.aggregation,
                selector_resolution=execution_policy.selector_resolution,
                selector_resolution_outcome=selector_outcome,
                action=constraint.action,
                source_selector=constraint.source_selector,
                target_selector=constraint.target_selector,
                rationale=constraint.rationale,
            )
        )
    return tuple(plans)


def _validate_selector_scope(
    constraint_id: str,
    selector: RelationSelector,
    substances: Mapping[str, Substance],
) -> None:
    """Require an explicit exact-form scope for ambiguous entity IDs.

    Resolution itself remains delegated to the generic selector resolver.  This
    guard only prevents an exact ID from silently becoming an accidental
    family-wide rule when sibling substance cards share its name.
    """

    if selector.scope not in {None, "exact_form"}:
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: unsupported selector scope {selector.scope!r}",
            code=MALFORMED,
        )
    if selector.scope is not None and selector.entity_id is None:
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: exact_form scope requires entity_id",
            code=MALFORMED,
        )
    if selector.entity_id is None or selector.entity_id not in substances:
        return
    substance = substances[selector.entity_id]
    sibling_ids = tuple(
        sorted(
            substance_id
            for substance_id, candidate in substances.items()
            if candidate.name == substance.name and substance_id != selector.entity_id
        )
    )
    if sibling_ids and selector.scope != "exact_form":
        siblings = ", ".join(sibling_ids)
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: entity_id selector {selector.entity_id!r} "
            f"has same-name sibling substance cards [{siblings}]; declare scope: exact_form",
            code=MALFORMED,
        )


def executable_blocking_plans(
    plans: Iterable[SchedulingConstraintExecutionPlan],
) -> tuple[SchedulingConstraintExecutionPlan, ...]:
    """Return executable plans that contribute hard slot blocking."""
    return tuple(plan for plan in plans if plan.executable and plan.blocks_slots)


def _combine_selector_outcomes(source: str, target: str) -> str:
    if source == "resolved" and target == "resolved":
        return "resolved"
    if "unsupported_selector" in {source, target}:
        return "unsupported_selector"
    if "malformed_selector" in {source, target}:
        return "malformed_selector"
    return "empty"


def _authored_execution_grammar(bundle: OntologyBundle) -> _AuthoredExecutionGrammar:
    """Read execution vocabulary from the verified authored schema."""

    return _AuthoredExecutionGrammar(
        operation_values=schema_enum_values(bundle, "ConstraintExecutionOperation"),
        direction_values=schema_enum_values(bundle, "ConstraintExecutionMatchDirection"),
        aggregation_values=schema_enum_values(bundle, "ConstraintExecutionAggregation"),
    )


def _validate_execution_grammar(
    constraint_id: str,
    operation: str,
    direction: str,
    aggregation: str,
    *,
    grammar: _AuthoredExecutionGrammar,
) -> None:
    """Validate IDs against authored enum metadata, never a Python allow-list."""

    if aggregation not in grammar.aggregation_values:
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: unsupported aggregation {aggregation!r}",
            code=MALFORMED,
        )
    if direction not in grammar.direction_values:
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: unsupported match direction {direction!r}",
            code=MALFORMED,
        )
    if operation not in grammar.operation_values:
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: unsupported operation {operation!r}",
            code=MALFORMED,
        )


def _handler_for_operation(constraint_id: str, operation: str) -> Callable[..., bool]:
    handler = _EXECUTION_HANDLERS.get(operation)
    if handler is None:
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: no runtime handler for operation {operation!r}",
            code=MALFORMED,
        )
    return handler


def _interpret_separate_products_same_slot(
    direction: str,
    item_components: Sequence[str],
    existing_components: Sequence[str],
    source_ids: Sequence[str],
    target_ids: Sequence[str],
) -> bool:
    source_matches_item = bool(set(item_components) & set(source_ids))
    target_matches_existing = bool(set(existing_components) & set(target_ids))
    target_matches_item = bool(set(item_components) & set(target_ids))
    source_matches_existing = bool(set(existing_components) & set(source_ids))
    forward = source_matches_item and target_matches_existing
    if direction == "directed":
        return forward
    if direction == "symmetric":
        return forward or (target_matches_item and source_matches_existing)
    raise OntologyInfrastructureError(
        f"unsupported match direction {direction!r}",
        code=MALFORMED,
    )


_EXECUTION_HANDLERS: dict[str, Callable[..., bool]] = {
    "separate_products_same_slot": _interpret_separate_products_same_slot,
}


def interpret_execution_component_pair(
    execution: Mapping[str, object],
    item_components: Sequence[str],
    existing_components: Sequence[str],
    runtime_program: RuntimeProgram,
) -> bool:
    """Interpret a resolved execution row against the compiled runtime policy."""

    constraint_id = execution.get("id")
    operation = execution.get("operation")
    match_direction = execution.get("match_direction")
    aggregation = execution.get("aggregation")
    source_substances = execution.get("source_substances")
    target_substances = execution.get("target_substances")
    if not isinstance(constraint_id, str) or not constraint_id.strip():
        raise OntologyInfrastructureError("scheduling constraint execution row has invalid id", code=MALFORMED)
    if not isinstance(operation, str) or not operation.strip():
        raise OntologyInfrastructureError(f"scheduling constraint {constraint_id}: invalid operation", code=MALFORMED)
    if not isinstance(match_direction, str) or not match_direction.strip():
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: invalid match direction", code=MALFORMED
        )
    if not isinstance(aggregation, str) or not aggregation.strip():
        raise OntologyInfrastructureError(f"scheduling constraint {constraint_id}: invalid aggregation", code=MALFORMED)
    if not isinstance(source_substances, Sequence) or isinstance(source_substances, (str, bytes)):
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: malformed source substances", code=MALFORMED
        )
    if not isinstance(target_substances, Sequence) or isinstance(target_substances, (str, bytes)):
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: malformed target substances", code=MALFORMED
        )
    if not all(isinstance(item, str) for item in source_substances) or not all(
        isinstance(item, str) for item in target_substances
    ):
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: malformed source or target substances", code=MALFORMED
        )
    execution_policy = _execution_policy_for_operation(runtime_program, constraint_id, operation)
    _validate_policy_fields(
        constraint_id,
        operation=operation,
        match_direction=match_direction,
        aggregation=aggregation,
        execution_policy=execution_policy,
    )
    handler = _handler_for_operation(constraint_id, operation)
    return handler(
        execution_policy.match_direction,
        item_components,
        existing_components,
        source_substances,
        target_substances,
    )


def interpret_constraint_component_pair(
    constraint: SchedulingConstraintExecutionPlan,
    item_components: Sequence[str],
    existing_components: Sequence[str],
    runtime_program: RuntimeProgram,
) -> bool:
    """Interpret the closed runtime grammar for one unordered component pair."""

    execution_policy = _execution_policy_for_operation(runtime_program, constraint.id, constraint.operation)
    _validate_policy_fields(
        constraint.id,
        operation=constraint.operation,
        match_direction=constraint.match_direction,
        aggregation=constraint.aggregation,
        execution_policy=execution_policy,
    )

    return interpret_execution_component_pair(
        {
            "id": constraint.id,
            "operation": constraint.operation,
            "match_direction": constraint.match_direction,
            "aggregation": constraint.aggregation,
            "source_substances": constraint.source_substance_ids,
            "target_substances": constraint.target_substance_ids,
        },
        item_components,
        existing_components,
        runtime_program,
    )


def _execution_policy_for_operation(
    runtime_program: RuntimeProgram,
    constraint_id: str,
    operation: str,
) -> RuntimeConstraintExecutionPolicy:
    execution_policy = runtime_program.constraint_execution_policy_for(operation)
    if execution_policy is None:
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: unsupported operation {operation!r}",
            code=MALFORMED,
        )
    return execution_policy


def _validate_policy_fields(
    constraint_id: str,
    *,
    operation: str,
    match_direction: str,
    aggregation: str,
    execution_policy: RuntimeConstraintExecutionPolicy,
) -> None:
    if execution_policy.operation != operation:
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: operation does not match compiled policy",
            code=MALFORMED,
        )
    if match_direction != execution_policy.match_direction:
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: match direction {match_direction!r} does not match "
            f"compiled policy {execution_policy.match_direction!r}",
            code=MALFORMED,
        )
    if aggregation != execution_policy.aggregation:
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint_id}: unsupported aggregation {aggregation!r}",
            code=MALFORMED,
        )


__all__ = [
    "SchedulingConstraintExecutionPlan",
    "compile_scheduling_constraint_execution_plans",
    "interpret_constraint_component_pair",
    "interpret_execution_component_pair",
]
