"""Build the canonical planner's active item index."""

from __future__ import annotations

from collections.abc import Mapping
from typing import NamedTuple

from planner.cards.product import product_component_substances
from planner.contracts import Product, StackEntry, Substance
from planner.engine._plan_types import ActiveIndex
from planner.ontology.canonical_inference import execute_canonical_inference
from planner.ontology.runtime_program import RuntimeCanonicalFactCatalog, RuntimeCanonicalLaw, RuntimeProgram


class ActiveIndexInput(NamedTuple):
    runtime_program: RuntimeProgram
    products: Mapping[str, Product]
    substances: Mapping[str, Substance]
    canonical_fact_catalog: RuntimeCanonicalFactCatalog
    canonical_laws: tuple[RuntimeCanonicalLaw, ...]


def build_active_index(
    stack_entries: Mapping[str, StackEntry],
    index_input: ActiveIndexInput,
) -> ActiveIndex:
    """Resolve every active scenario item and execute canonical inference."""
    item_products: dict[str, str] = {}
    active_components: dict[str, list[str]] = {}
    item_stacks: dict[str, str] = {}
    inactive_stack = index_input.runtime_program.glue_contract.inactive_stack_name

    for item_id, entry in sorted(stack_entries.items()):
        if not isinstance(item_id, str) or not isinstance(entry, Mapping):
            raise ValueError("stack entries must have string IDs and mapping values")
        stack = entry.get("stack")
        product_id = entry.get("product")
        if stack == inactive_stack:
            continue
        if not isinstance(stack, str) or not isinstance(product_id, str):
            raise ValueError(f"active stack entry {item_id!r} must name a stack and product")
        product = index_input.products.get(product_id)
        if product is None:
            raise ValueError(f"active item {item_id!r} references missing product {product_id!r}")
        item_products[item_id] = product_id
        active_components[item_id] = product_component_substances(product)
        item_stacks[item_id] = stack

    if not item_products:
        raise ValueError("no non-inactive stack items")
    canonical_inference = execute_canonical_inference(
        index_input.canonical_fact_catalog,
        item_products,
        index_input.canonical_laws,
    )
    return ActiveIndex(
        item_products=item_products,
        active_components=active_components,
        item_stacks=item_stacks,
        canonical_inference=canonical_inference,
    )


__all__ = ["ActiveIndexInput", "build_active_index"]
