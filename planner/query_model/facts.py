"""Active and inactive stack membership queries for the planner read model."""

from __future__ import annotations

from planner.query_model.data import ReadModelData


def _stack_partition_substance_ids(data: ReadModelData, *, inactive: bool, inactive_stack_name: str) -> set[str]:
    """Substance IDs referenced by products in stacks matching the partition."""
    target_product_ids: set[str] = set()
    for name, product_ids in data.stacks.items():
        if (name == inactive_stack_name) is inactive:
            target_product_ids.update(product_ids)

    result: set[str] = set()
    for product_id in target_product_ids:
        product = data.products[product_id]
        result.update(component.substance for component in product.components)
    return result


def active_substance_ids(data: ReadModelData, inactive_stack_name: str) -> set[str]:
    """Substance IDs referenced by any product in a non-inactive stack."""
    return _stack_partition_substance_ids(data, inactive=False, inactive_stack_name=inactive_stack_name)


def inactive_substance_ids(data: ReadModelData, inactive_stack_name: str) -> set[str]:
    """Substance IDs referenced by products in the authored inactive stack."""
    return _stack_partition_substance_ids(data, inactive=True, inactive_stack_name=inactive_stack_name)
