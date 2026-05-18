"""Raw safety-warning collection for active schedule items."""

from __future__ import annotations

from typing import Any

from planner.contracts import Product, Substance


def collect_active_safety_concerns(
    *,
    active_order: list[str],
    active_components: dict[str, list[str]],
    item_products: dict[str, str],
    products: dict[str, Product],
    substances: dict[str, Substance],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item_id in active_order:
        product_id = item_products[item_id]
        product = products.get(product_id)
        if product is not None:
            for concern in product.concerns:
                if concern.kind != "safety":
                    continue
                key = ("product", product_id, concern.text)
                if key in seen:
                    continue
                seen.add(key)
                warnings.append(
                    {
                        "type": "safety_concern",
                        "item": item_id,
                        "product": product_id,
                        "message": concern.text,
                    }
                )
        for substance_id in active_components[item_id]:
            substance = substances.get(substance_id)
            if substance is None:
                continue
            for concern in substance.concerns:
                if concern.kind != "safety":
                    continue
                key = ("substance", substance_id, concern.text)
                if key in seen:
                    continue
                seen.add(key)
                warnings.append(
                    {
                        "type": "safety_concern",
                        "item": item_id,
                        "product": product_id,
                        "substance": substance_id,
                        "message": concern.text,
                    }
                )
    return warnings
