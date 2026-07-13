"""Slot blocking checks for plan search."""

from __future__ import annotations

from typing import NamedTuple

from planner.contracts import Relation, Substance
from planner.engine._plan_types import BlockingContext


class _SelectorCompetesContext(NamedTuple):
    slot_items: dict[str, list[str]]
    active_components: dict[str, list[str]]
    substances: dict[str, Substance]
    global_relations: list[Relation]


def slot_is_blocked(
    item: str,
    slot_name: str,
    slot_items: dict[str, list[str]],
    blocking: BlockingContext,
) -> bool:
    """Return True if placing item in slot_name violates competes relations."""
    selector_competes_context = _SelectorCompetesContext(
        slot_items=slot_items,
        active_components=blocking.active_components,
        substances=blocking.substances,
        global_relations=blocking.global_relations,
    )
    if _selector_competes_blocks_item(
        item,
        slot_name,
        selector_competes_context,
    ):
        return True
    return _substance_competes_blocks_item(
        item,
        slot_name,
        slot_items,
        blocking.active_components,
        blocking.competes_pairs,
    )


def _selector_competes_blocks_item(
    item: str,
    slot_name: str,
    context: _SelectorCompetesContext,
) -> bool:
    selector_competes = [
        relation
        for relation in context.global_relations
        if relation.type == "competes"
        and relation.source_selector.category is not None
        and relation.source_selector.term is not None
        and relation.target_selector.category is not None
        and relation.target_selector.term is not None
    ]
    if not selector_competes:
        return False

    item_terms = _item_terms(item, context.active_components, context.substances)
    for existing_item in context.slot_items[slot_name]:
        existing_terms = _item_terms(existing_item, context.active_components, context.substances)
        for relation in selector_competes:
            src = (relation.source_selector.category, relation.source_selector.term)
            tgt = (relation.target_selector.category, relation.target_selector.term)
            if (src in item_terms and tgt in existing_terms) or (tgt in item_terms and src in existing_terms):
                return True
    return False


def _substance_competes_blocks_item(
    item: str,
    slot_name: str,
    slot_items: dict[str, list[str]],
    active_components: dict[str, list[str]],
    competes_pairs: set[frozenset[str]],
) -> bool:
    item_components = active_components[item]
    for existing_item in slot_items[slot_name]:
        for left in item_components:
            for right in active_components[existing_item]:
                if left != right and frozenset({left, right}) in competes_pairs:
                    return True
    return False


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
