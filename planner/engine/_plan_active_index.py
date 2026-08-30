"""Build the canonical planner's active item index."""

from __future__ import annotations

from collections.abc import Mapping
from typing import NamedTuple

from planner.contracts import Product, StackEntry, Substance
from planner.engine._plan_types import ActiveIndex
from planner.ontology.canonical_facts import composition_roles_for_products
from planner.ontology.canonical_inference import execute_canonical_inference
from planner.ontology.runtime_program import RuntimeCanonicalScheduling, RuntimeProgram


class ActiveIndexInput(NamedTuple):
    runtime_program: RuntimeProgram
    products: Mapping[str, Product]
    substances: Mapping[str, Substance]
    canonical_scheduling: RuntimeCanonicalScheduling


def build_active_index(
    stack_entries: Mapping[str, StackEntry],
    index_input: ActiveIndexInput,
) -> ActiveIndex:
    """Resolve every active scenario item and execute canonical inference."""
    item_products: dict[str, str] = {}
    item_stacks: dict[str, str] = {}
    routable_stacks = set(index_input.runtime_program.glue_contract.stack_partition.routable_stack_names)

    for item_id, entry in sorted(stack_entries.items()):
        if not isinstance(item_id, str) or not isinstance(entry, Mapping):
            raise ValueError("stack entries must have string IDs and mapping values")
        stack = entry.get("stack")
        product_id = entry.get("product")
        if stack not in routable_stacks:
            continue
        if not isinstance(stack, str) or not isinstance(product_id, str):
            raise ValueError(f"active stack entry {item_id!r} must name a stack and product")
        product = index_input.products.get(product_id)
        if product is None:
            raise ValueError(f"active item {item_id!r} references missing product {product_id!r}")
        item_products[item_id] = product_id
        item_stacks[item_id] = stack

    if not item_products:
        raise ValueError("no non-inactive stack items")
    canonical_inference = execute_canonical_inference(
        index_input.canonical_scheduling,
        item_products,
        index_input.canonical_scheduling.laws,
        composition_roles=composition_roles_for_products(index_input.products),
    )
    return ActiveIndex(
        item_products=item_products,
        item_stacks=item_stacks,
        canonical_inference=canonical_inference,
    )


__all__ = ["ActiveIndexInput", "build_active_index"]
