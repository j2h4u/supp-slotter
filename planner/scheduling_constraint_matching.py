"""Shared deterministic selector matching for scheduling diagnostics and coverage."""

from __future__ import annotations

from planner.contracts import RelationSelector, SchedulingConstraint, Substance


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
    item_components: list[str],
    existing_components: list[str],
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
    components: list[str],
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
