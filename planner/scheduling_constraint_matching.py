"""Shared deterministic selector matching for scheduling diagnostics and coverage."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import combinations
from typing import TYPE_CHECKING

from planner.contracts import RelationSelector, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.substance_fields import substance_terms_for_category

if TYPE_CHECKING:
    from planner.scheduling_constraint_execution import SchedulingConstraintExecutionPlan


def advisory_penalty_for_candidate(
    item_id: str,
    existing_slot_item_ids: list[str] | tuple[str, ...],
    active_components: dict[str, list[str]],
    substances_by_id: dict[str, Substance],
    advisory_constraints: tuple[SchedulingConstraintExecutionPlan, ...],
) -> tuple[int, tuple[str, ...]]:
    """Return deterministic advisory penalties for a candidate and slot state.

    Matching and per-rule score contribution come from the verified runtime
    scoring contract; callers may use the returned IDs for diagnostics only.
    """
    before_penalty, before_ids = advisory_penalty_for_slot(
        existing_slot_item_ids,
        active_components,
        substances_by_id,
        advisory_constraints,
    )
    after_penalty, after_ids = advisory_penalty_for_slot(
        (*existing_slot_item_ids, item_id),
        active_components,
        substances_by_id,
        advisory_constraints,
    )
    introduced_ids = tuple(sorted(set(after_ids) - set(before_ids)))
    return after_penalty - before_penalty, introduced_ids


def advisory_penalty_for_slot(
    slot_item_ids: Sequence[str],
    active_components: dict[str, list[str]],
    substances_by_id: dict[str, Substance],
    advisory_constraints: tuple[SchedulingConstraintExecutionPlan, ...],
) -> tuple[int, tuple[str, ...]]:
    """Evaluate advisory rules once per slot, independently of item order."""
    canonical_item_ids = tuple(sorted(set(slot_item_ids)))
    matched: set[str] = set()
    penalty = 0
    for left_id, right_id in combinations(canonical_item_ids, 2):
        for constraint in sorted(advisory_constraints, key=lambda item: item.id):
            if not (constraint.executable and constraint.scores_advisory):
                continue
            if (
                constraint_matches_component_pair(
                    constraint,
                    active_components.get(left_id, []),
                    active_components.get(right_id, []),
                    substances_by_id,
                )
                and constraint.id not in matched
            ):
                matched.add(constraint.id)
                penalty += _score_delta(constraint)
    return penalty, tuple(sorted(matched))


def selector_matching_substance_ids(
    selector: RelationSelector,
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> tuple[str, ...]:
    """Resolve a selector to canonical substance IDs in deterministic order."""
    return tuple(
        substance_id
        for substance_id, substance in sorted(substances.items())
        if _selector_matches_substance(selector, substance_id, substance, ontology_bundle)
    )


def constraint_matches_component_pair(
    constraint: SchedulingConstraintExecutionPlan,
    item_components: Sequence[str],
    existing_components: Sequence[str],
    substances: dict[str, Substance],
) -> bool:
    """Match a constraint across an unordered item pair using declared roles."""
    # The runtime contract currently exposes one aggregation mode.  Keep the
    # matcher fail-closed if a malformed or hand-built execution plan reaches
    # this boundary without passing ontology validation.
    if constraint.aggregation != "distinct_constraint":
        raise OntologyInfrastructureError(
            f"scheduling constraint {constraint.id}: unsupported aggregation {constraint.aggregation!r}",
            code=MALFORMED,
        )
    source_matches_item = bool(set(item_components) & set(constraint.source_substance_ids))
    target_matches_existing = bool(set(existing_components) & set(constraint.target_substance_ids))
    target_matches_item = bool(set(item_components) & set(constraint.target_substance_ids))
    source_matches_existing = bool(set(existing_components) & set(constraint.source_substance_ids))
    forward = source_matches_item and target_matches_existing
    reverse_item_roles = target_matches_item and source_matches_existing
    if constraint.match_direction == "directed":
        return forward
    if constraint.match_direction == "symmetric":
        return forward or reverse_item_roles
    _validate_advisory_direction(constraint.match_direction)
    return False


def _validate_advisory_direction(direction: str) -> None:
    if direction in {"symmetric", "directed"}:
        return
    raise OntologyInfrastructureError(
        f"runtime program effect_scoring.advisory_match_direction has unsupported value {direction!r}",
        code=MALFORMED,
    )


def _selector_matches_components(
    selector: RelationSelector,
    components: Sequence[str],
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> bool:
    return any(
        substance is not None and _selector_matches_substance(selector, component, substance, ontology_bundle)
        for component in components
        for substance in [substances.get(component)]
    )


def _score_delta(constraint: SchedulingConstraintExecutionPlan) -> int:
    return constraint.score_delta


def _selector_matches_substance(
    selector: RelationSelector,
    substance_id: str,
    substance: Substance,
    ontology_bundle: OntologyBundle,
) -> bool:
    if selector.entity_id is not None:
        return selector.entity_id == substance_id
    if selector.entity_name is not None:
        return selector.entity_name == substance.name
    if selector.category is None or selector.term is None:
        return False
    values = substance_terms_for_category(substance, selector.category, ontology_bundle)
    return values is not None and selector.term in values
