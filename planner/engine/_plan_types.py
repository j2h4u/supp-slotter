"""Shared plan-command data containers."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from planner.contracts import (
    Pillbox,
    Product,
    Relation,
    SchedulingConstraint,
    SchedulingPolicy,
    Slot,
    StackEntry,
    Substance,
)
from planner.query_model.relation_conflicts import RelationConflictWarningRow


class PlanInputs(NamedTuple):
    slots: dict[str, Slot]
    policies: dict[str, SchedulingPolicy]
    scheduling_constraints: tuple[SchedulingConstraint, ...]
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
    intra_product_relation_conflicts_by_item: dict[str, list[RelationConflictWarningRow]]
    item_stacks: dict[str, str]


class BlockingContext(NamedTuple):
    active_components: dict[str, list[str]]
    substances: dict[str, Substance]
    scheduling_constraints: tuple[SchedulingConstraint, ...]
