"""Slot blocking checks for plan search."""

from __future__ import annotations

from typing import NamedTuple

from planner.contracts import RelationSelector, SchedulingConstraint, Substance
from planner.engine._plan_types import BlockingContext
from planner.scheduling_constraint_matching import constraint_matches_component_pair


class _SchedulingConstraintContext(NamedTuple):
    slot_items: dict[str, list[str]]
    active_components: dict[str, list[str]]
    substances: dict[str, Substance]
    constraints: tuple[SchedulingConstraint, ...]


class _ItemSelectorMatch(NamedTuple):
    terms: set[tuple[str, str]]
    components: list[str]


class SchedulingConstraintDiagnostic(NamedTuple):
    """Stable explanation of a hard constraint that blocked a candidate slot."""

    id: str
    action: str | None
    metadata: dict[str, object]


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


def blocking_constraint_diagnostics(
    item: str,
    slot_name: str,
    slot_items: dict[str, list[str]],
    blocking: BlockingContext,
) -> tuple[SchedulingConstraintDiagnostic, ...]:
    """Return matching hard constraints, preserving boolean blocking parity.

    This is intentionally separate from :func:`slot_is_blocked` so the planner's
    hot search loop keeps its allocation-free boolean path.
    """
    context = _SchedulingConstraintContext(
        slot_items=slot_items,
        active_components=blocking.active_components,
        substances=blocking.substances,
        constraints=blocking.scheduling_constraints,
    )
    matches = _matching_constraints(item, slot_name, context)
    return tuple(
        SchedulingConstraintDiagnostic(
            id=constraint.id,
            action=constraint.action,
            metadata={
                "rationale": constraint.rationale,
                "semantic_note": constraint.semantic_note,
                "status": constraint.status,
                "evidence": constraint.evidence,
                "scope": constraint.scope,
                "owner": constraint.owner,
                "review_by": constraint.review_by,
                "assertion_type": constraint.assertion_type,
                "legacy_preserved": constraint.legacy_preserved,
                "legacy_relation_id": constraint.legacy_relation_id,
            },
        )
        for constraint in matches
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
    for existing_item in context.slot_items.get(slot_name, []):
        existing_match = _ItemSelectorMatch(
            _item_terms(existing_item, context.active_components, context.substances),
            context.active_components[existing_item],
        )
        for constraint in constraints:
            if _constraint_matches_pair(constraint, item_match, existing_match, context.substances):
                return True
    return False


def _matching_constraints(
    item: str,
    slot_name: str,
    context: _SchedulingConstraintContext,
) -> tuple[SchedulingConstraint, ...]:
    constraints = tuple(
        constraint
        for constraint in context.constraints
        if constraint.effect == "separate_slots" and constraint.enforcement == "block"
    )
    if not constraints:
        return ()

    item_match = _ItemSelectorMatch(
        _item_terms(item, context.active_components, context.substances),
        context.active_components[item],
    )
    matched: list[SchedulingConstraint] = []
    for existing_item in context.slot_items.get(slot_name, []):
        existing_match = _ItemSelectorMatch(
            _item_terms(existing_item, context.active_components, context.substances),
            context.active_components[existing_item],
        )
        for constraint in constraints:
            if (
                constraint_matches_component_pair(
                    constraint,
                    item_match.components,
                    existing_match.components,
                    context.substances,
                )
                and constraint not in matched
            ):
                matched.append(constraint)
    return tuple(matched)


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
