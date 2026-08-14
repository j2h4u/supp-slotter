"""Slot blocking checks for plan search."""

from __future__ import annotations

from typing import NamedTuple

from planner.contracts import Relation, Substance
from planner.engine._plan_types import BlockingContext


class _ClassCompetesContext(NamedTuple):
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
    class_competes_context = _ClassCompetesContext(
        slot_items=slot_items,
        active_components=blocking.active_components,
        substances=blocking.substances,
        global_relations=blocking.global_relations,
    )
    if _class_competes_blocks_item(
        item,
        slot_name,
        class_competes_context,
    ):
        return True
    return _substance_competes_blocks_item(
        item,
        slot_name,
        slot_items,
        blocking.active_components,
        blocking.competes_pairs,
    )


def _class_competes_blocks_item(
    item: str,
    slot_name: str,
    context: _ClassCompetesContext,
) -> bool:
    class_competes = [
        relation
        for relation in context.global_relations
        if relation.type == "competes" and relation.source_class and relation.target_class
    ]
    if not class_competes:
        return False

    item_classes = _item_classes(item, context.active_components, context.substances)
    for existing_item in context.slot_items[slot_name]:
        existing_classes = _item_classes(existing_item, context.active_components, context.substances)
        for relation in class_competes:
            src, tgt = relation.source_class, relation.target_class
            if (src in item_classes and tgt in existing_classes) or (tgt in item_classes and src in existing_classes):
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


def _item_classes(
    item: str,
    active_components: dict[str, list[str]],
    substances: dict[str, Substance],
) -> set[str]:
    return {
        cls
        for component in active_components[item]
        for substance in [substances.get(component)]
        if substance
        for cls in substance.is_
    }
