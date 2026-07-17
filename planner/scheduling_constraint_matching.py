"""Shared deterministic selector matching for scheduling diagnostics and coverage."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import combinations

from planner.contracts import RelationSelector, SchedulingConstraint, Substance
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.runtime_program import RuntimeEffectScoring


def advisory_penalty_for_candidate(
    item_id: str,
    existing_slot_item_ids: list[str] | tuple[str, ...],
    active_components: dict[str, list[str]],
    substances_by_id: dict[str, Substance],
    advisory_constraints: tuple[SchedulingConstraint, ...],
    effect_scoring: RuntimeEffectScoring,
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
        effect_scoring,
    )
    after_penalty, after_ids = advisory_penalty_for_slot(
        (*existing_slot_item_ids, item_id),
        active_components,
        substances_by_id,
        advisory_constraints,
        effect_scoring,
    )
    introduced_ids = tuple(sorted(set(after_ids) - set(before_ids)))
    return after_penalty - before_penalty, introduced_ids


def advisory_penalty_for_slot(
    slot_item_ids: Sequence[str],
    active_components: dict[str, list[str]],
    substances_by_id: dict[str, Substance],
    advisory_constraints: tuple[SchedulingConstraint, ...],
    effect_scoring: RuntimeEffectScoring,
) -> tuple[int, tuple[str, ...]]:
    """Evaluate advisory rules once per slot, independently of item order."""
    direction = effect_scoring.advisory_match_direction
    _validate_advisory_direction(direction)
    canonical_item_ids = tuple(sorted(set(slot_item_ids)))
    matched = {
        constraint.id
        for left_id, right_id in combinations(canonical_item_ids, 2)
        for constraint in advisory_constraints
        if constraint_matches_component_pair(
            constraint,
            active_components.get(left_id, []),
            active_components.get(right_id, []),
            substances_by_id,
            direction=direction,
        )
    }
    matched_ids = tuple(sorted(matched))
    return effect_scoring.advisory_constraint_score_delta * len(matched_ids), matched_ids


def selector_matching_substance_ids(
    selector: RelationSelector,
    substances: dict[str, Substance],
) -> tuple[str, ...]:
    """Resolve a selector to canonical substance IDs in deterministic order."""
    return tuple(
        substance_id
        for substance_id, substance in sorted(substances.items())
        if _selector_matches_substance(selector, substance_id, substance)
    )


def constraint_matches_component_pair(
    constraint: SchedulingConstraint,
    item_components: Sequence[str],
    existing_components: Sequence[str],
    substances: dict[str, Substance],
    *,
    direction: str = "symmetric",
) -> bool:
    """Match a constraint across an unordered item pair using declared roles."""
    _validate_advisory_direction(direction)
    forward = (
        _selector_matches_components(constraint.source_selector, item_components, substances)
        and _selector_matches_components(constraint.target_selector, existing_components, substances)
    )
    reverse_item_roles = (
        _selector_matches_components(constraint.target_selector, item_components, substances)
        and _selector_matches_components(constraint.source_selector, existing_components, substances)
    )
    if direction == "directed":
        # The pair itself has no traversal direction.  Either item may realize
        # the declared source role, but selectors are never reversed.
        return forward or reverse_item_roles
    return forward or reverse_item_roles


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
) -> bool:
    return any(
        substance is not None and _selector_matches_substance(selector, component, substance)
        for component in components
        for substance in [substances.get(component)]
    )


def _selector_matches_substance(
    selector: RelationSelector,
    substance_id: str,
    substance: Substance,
) -> bool:
    if selector.entity_id is not None:
        return selector.entity_id == substance_id
    if selector.entity_name is not None:
        return selector.entity_name == substance.name
    values = getattr(substance, selector.category or "", ())
    return isinstance(values, tuple) and selector.term in values
