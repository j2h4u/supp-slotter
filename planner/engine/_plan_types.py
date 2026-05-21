"""Shared plan-command data containers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

from planner.contracts import Pillbox, Product, Relation, Slot, StackEntry, Substance, TraitDef


class PlanInputs(NamedTuple):
    slots: dict[str, Slot]
    trait_defs: dict[str, TraitDef]
    substances: dict[str, Substance]
    products: dict[str, Product]
    global_relations: list[Relation]
    dashboard_files: list[Path]
    stack_entries: dict[str, StackEntry]
    pillboxes: dict[str, Pillbox]


class ActiveIndex(NamedTuple):
    item_traits: dict[str, set[str]]
    secondary_traits_by_item: dict[str, set[str]]
    item_products: dict[str, str]
    active_components: dict[str, list[str]]
    trait_sources_by_item: dict[str, dict[str, list[str]]]
    intra_product_relation_conflicts_by_item: dict[str, list[dict[str, Any]]]
    item_stacks: dict[str, str]
