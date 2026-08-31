"""Active stack membership query for the planner read model."""

from __future__ import annotations

from planner.query_model.data import ReadModelData


def active_substance_ids(data: ReadModelData, routable_stack_names: set[str]) -> set[str]:
    """Substance IDs referenced by any product in a routable stack."""
    target_product_ids: set[str] = set()
    for name, product_ids in data.stacks.items():
        if name in routable_stack_names:
            target_product_ids.update(product_ids)

    result: set[str] = set()
    for product_id in target_product_ids:
        product = data.products[product_id]
        result.update(component.substance for component in product.components)
    return result
