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
                _append_safety_warning(
                    warnings,
                    seen,
                    scope="product",
                    scope_id=product_id,
                    warning={
                        "type": "safety_concern",
                        "item": item_id,
                        "product": product_id,
                        "message": concern.text,
                    },
                    message=concern.text,
                    concern_kind=concern.kind,
                )
        for substance_id in active_components[item_id]:
            substance = substances.get(substance_id)
            if substance is None:
                continue
            for concern in substance.concerns:
                _append_safety_warning(
                    warnings,
                    seen,
                    scope="substance",
                    scope_id=substance_id,
                    warning={
                        "type": "safety_concern",
                        "item": item_id,
                        "product": product_id,
                        "substance": substance_id,
                        "message": concern.text,
                    },
                    message=concern.text,
                    concern_kind=concern.kind,
                )
    return warnings


def _append_safety_warning(
    warnings: list[dict[str, Any]],
    seen: set[tuple[str, str, str]],
    *,
    scope: str,
    scope_id: str,
    warning: dict[str, Any],
    message: str,
    concern_kind: str,
) -> None:
    if concern_kind != "safety":
        return
    key = (scope, scope_id, message)
    if key in seen:
        return
    seen.add(key)
    warnings.append(warning)
