"""Compilation of authored scheduling constraints into runtime instructions.

The YAML-backed :class:`SchedulingConstraint` is an audit/provenance DTO.  A
planner command compiles it once, resolving selectors and runtime governance,
then passes only :class:`SchedulingConstraintExecutionPlan` to behavioural
consumers.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from planner.contracts import RelationSelector, SchedulingConstraint, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.runtime_program import RuntimeProgram
from planner.ontology.substance_fields import allowed_predicate_fields_for_category, substance_terms_for_category


@dataclass(frozen=True, slots=True)
class SchedulingConstraintExecutionPlan:
    """Fully resolved instruction for one scheduling constraint."""

    id: str
    source_substance_ids: tuple[str, ...]
    target_substance_ids: tuple[str, ...]
    operation: str
    enforcement_mode: str
    effect_role: str
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
    status: str | None = None
    evidence: tuple[str, ...] = ()
    rationale: str | None = None
    semantic_note: str | None = None
    owner: str | None = None
    review_by: str | None = None
    assertion_type: str | None = None

    @property
    def source_ids(self) -> tuple[str, ...]:
        return self.source_substance_ids

    @property
    def target_ids(self) -> tuple[str, ...]:
        return self.target_substance_ids


def compile_scheduling_constraint_execution_plans(
    constraints: Iterable[SchedulingConstraint],
    substances: dict[str, Substance],
    runtime_program: RuntimeProgram,
    *,
    allow_empty_selector_resolution: bool = False,
    ontology_bundle: OntologyBundle,
) -> tuple[SchedulingConstraintExecutionPlan, ...]:
    """Compile constraints against one verified runtime program.

    The authored operation and selector contract are required inputs.  Invalid
    operation/selector values fail at this boundary so search cannot silently
    proceed with a zero-effect default plan.  Governance-inactive constraints
    remain auditable and non-executable after those structural checks pass.
    """

    plans: list[SchedulingConstraintExecutionPlan] = []
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
        lifecycle = (
            runtime_program.lifecycle_decision(constraint.status) if isinstance(constraint.status, str) else None
        )
        gate = (
            runtime_program.constraint_execution_gate_for(constraint.status)
            if isinstance(constraint.status, str)
            else None
        )
        enforcement = runtime_program.enforcement_decision(constraint.enforcement)
        governance_executable = bool(
            lifecycle is not None
            and gate is not None
            and enforcement is not None
            and (constraint.status, constraint.enforcement) in runtime_program.constraint_allowed_pairs
            and lifecycle.executable
            and gate.executable
            and enforcement.executable
        )
        role = enforcement.effect_role if enforcement is not None else "none"
        source_ids, source_outcome = _selector_matching_substance_ids(
            constraint.source_selector, substances, ontology_bundle
        )
        target_ids, target_outcome = _selector_matching_substance_ids(
            constraint.target_selector, substances, ontology_bundle
        )
        selector_outcome = _combine_selector_outcomes(source_outcome, target_outcome)
        if selector_outcome in {"malformed_selector", "unsupported_selector"}:
            raise OntologyInfrastructureError(
                f"scheduling constraint {constraint.id}: {selector_outcome}",
                code=MALFORMED,
            )
        if (
            selector_outcome == "empty"
            and execution_policy.selector_resolution == "require_nonempty"
            and not allow_empty_selector_resolution
        ):
            raise OntologyInfrastructureError(
                f"scheduling constraint {constraint.id}: selector resolution is empty",
                code=MALFORMED,
            )
        executable = governance_executable and selector_outcome == "resolved"
        blocks_slots = bool(executable and execution_policy.blocks_slots and role == "blocking")
        scores_advisory = bool(executable and execution_policy.scores_advisory and role == "warning")
        plans.append(
            SchedulingConstraintExecutionPlan(
                id=constraint.id,
                source_substance_ids=source_ids,
                target_substance_ids=target_ids,
                operation=operation,
                enforcement_mode=constraint.enforcement,
                effect_role=role,
                executable=executable,
                blocks_slots=blocks_slots,
                scores_advisory=scores_advisory,
                score_delta=execution_policy.score_delta if scores_advisory else 0,
                match_direction=execution_policy.match_direction,
                aggregation=execution_policy.aggregation,
                selector_resolution=execution_policy.selector_resolution,
                selector_resolution_outcome=selector_outcome,
                action=constraint.action,
                source_selector=constraint.source_selector,
                target_selector=constraint.target_selector,
                status=constraint.status,
                evidence=constraint.evidence,
                rationale=constraint.rationale,
                semantic_note=constraint.semantic_note,
                owner=constraint.owner,
                review_by=constraint.review_by,
                assertion_type=constraint.assertion_type,
            )
        )
    return tuple(plans)


def _selector_matching_substance_ids(
    selector: RelationSelector | None,
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> tuple[tuple[str, ...], str]:
    if selector is None:
        return (), "missing"
    populated = sum(
        value is not None for value in (selector.entity_id, selector.entity_name, selector.category, selector.term)
    )
    if (
        populated not in {1, 2}
        or (selector.entity_id is not None and selector.entity_name is not None)
        or (selector.category is not None and selector.term is None)
        or (selector.category is None and selector.term is not None)
    ):
        return (), "malformed_selector"

    def matches(substance_id: str, substance: Substance) -> bool:
        if selector.entity_id is not None:
            return selector.entity_id == substance_id
        if selector.entity_name is not None:
            return selector.entity_name == substance.name
        if selector.category is None or selector.term is None:
            return False
        values = substance_terms_for_category(substance, selector.category, ontology_bundle)
        return values is not None and selector.term in values

    matched = tuple(
        substance_id for substance_id, substance in sorted(substances.items()) if matches(substance_id, substance)
    )
    if (
        selector.entity_id is None
        and selector.entity_name is None
        and (
            selector.category is None
            or selector.term is None
            or allowed_predicate_fields_for_category(ontology_bundle, selector.category) is None
        )
    ):
        return (), "unsupported_selector"
    return matched, "resolved" if matched else "empty"


def _combine_selector_outcomes(source: str, target: str) -> str:
    if source == "resolved" and target == "resolved":
        return "resolved"
    if "unsupported_selector" in {source, target}:
        return "unsupported_selector"
    if "malformed_selector" in {source, target}:
        return "malformed_selector"
    if "missing" in {source, target}:
        return "missing"
    return "empty"


__all__ = [
    "SchedulingConstraintExecutionPlan",
    "compile_scheduling_constraint_execution_plans",
]
