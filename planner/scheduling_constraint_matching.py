"""Shared deterministic selector matching for scheduling diagnostics and coverage."""

from __future__ import annotations

from collections.abc import Sequence

from planner.contracts import RelationSelector, SchedulingConstraint, Substance


def advisory_penalty_for_candidate(
    item_id: str,
    existing_slot_item_ids: list[str] | tuple[str, ...],
    active_components: dict[str, list[str]],
    substances_by_id: dict[str, Substance],
    advisory_constraints: tuple[SchedulingConstraint, ...],
) -> tuple[int, tuple[str, ...]]:
    """Return deterministic advisory penalties for a candidate and slot state.

    Matching is deliberately pure and symmetric.  Each distinct rule contributes
    exactly ``-1``; callers may use the returned IDs for diagnostics only.
    """
    item_components = active_components.get(item_id, [])
    matched = {
        constraint.id
        for existing_id in existing_slot_item_ids
        for constraint in advisory_constraints
        if constraint_matches_component_pair(
            constraint,
            item_components,
            active_components.get(existing_id, []),
            substances_by_id,
        )
    }
    matched_ids = tuple(sorted(matched))
    return -len(matched_ids), matched_ids


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
) -> bool:
    """Match a constraint symmetrically against two diagnostic component sets."""
    return (
        _selector_matches_components(constraint.source_selector, item_components, substances)
        and _selector_matches_components(constraint.target_selector, existing_components, substances)
    ) or (
        _selector_matches_components(constraint.target_selector, item_components, substances)
        and _selector_matches_components(constraint.source_selector, existing_components, substances)
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
