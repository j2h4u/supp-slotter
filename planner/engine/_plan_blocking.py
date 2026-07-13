"""Slot blocking checks for plan search."""

from __future__ import annotations

from typing import NamedTuple

from planner.contracts import RelationSelector, SchedulingConstraint, Substance
from planner.engine._plan_types import BlockingContext


class _SchedulingConstraintContext(NamedTuple):
    slot_items: dict[str, list[str]]
    active_components: dict[str, list[str]]
    substances: dict[str, Substance]
    constraints: tuple[SchedulingConstraint, ...]


class _ItemSelectorMatch(NamedTuple):
    terms: set[tuple[str, str]]
    components: list[str]


def slot_is_blocked(
    item: str,
    slot_name: str,
    slot_items: dict[str, list[str]],
    blocking: BlockingContext,
) -> bool:
    """Return True if placing an item violates a first-class block constraint."""
    constraints_context = _SchedulingConstraintContext(
        slot_items=slot_items,
        active_components=blocking.active_components,
        substances=blocking.substances,
        constraints=blocking.scheduling_constraints,
    )
    return _scheduling_constraint_blocks_item(
        item,
        slot_name,
        constraints_context,
    )


def _scheduling_constraint_blocks_item(
    item: str,
    slot_name: str,
    context: _SchedulingConstraintContext,
) -> bool:
    constraints = tuple(
        constraint
        for constraint in context.constraints
        if constraint.effect == "separate_slots" and constraint.enforcement == "block"
    )
    if not constraints:
        return False

    item_match = _ItemSelectorMatch(
        _item_terms(item, context.active_components, context.substances),
        context.active_components[item],
    )
    for existing_item in context.slot_items[slot_name]:
        existing_match = _ItemSelectorMatch(
            _item_terms(existing_item, context.active_components, context.substances),
            context.active_components[existing_item],
        )
        for constraint in constraints:
            if _constraint_matches_pair(
                constraint,
                item_match,
                existing_match,
                context.substances,
            ):
                return True
    return False


def _constraint_matches_pair(
    constraint: SchedulingConstraint,
    item: _ItemSelectorMatch,
    existing: _ItemSelectorMatch,
    substances: dict[str, Substance],
) -> bool:
    return (
        _selector_matches_terms(constraint.source_selector, item.terms, item.components, substances)
        and _selector_matches_terms(constraint.target_selector, existing.terms, existing.components, substances)
    ) or (
        _selector_matches_terms(constraint.target_selector, item.terms, item.components, substances)
        and _selector_matches_terms(constraint.source_selector, existing.terms, existing.components, substances)
    )


def _selector_matches_terms(
    selector: RelationSelector,
    terms: set[tuple[str, str]],
    components: list[str],
    substances: dict[str, Substance],
) -> bool:
    if selector.entity_id is not None:
        return selector.entity_id in components
    if selector.entity_name is not None:
        return any(
            substances.get(component) is not None and substances[component].name == selector.entity_name
            for component in components
        )
    return (selector.category, selector.term) in terms


def _item_terms(
    item: str,
    active_components: dict[str, list[str]],
    substances: dict[str, Substance],
) -> set[tuple[str, str]]:
    return {
        (category, term)
        for component in active_components[item]
        for substance in [substances.get(component)]
        if substance
        for category, terms in (
            ("kind", substance.kind),
            ("role", substance.role),
            ("quality", substance.quality),
            ("effect", substance.effect),
            ("risk", substance.risk),
            ("context", substance.context),
            ("pathway", substance.pathway),
        )
        for term in terms
    }
