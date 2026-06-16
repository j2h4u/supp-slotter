"""Raw safety-warning collection for active schedule items."""

from __future__ import annotations

from dataclasses import dataclass

from planner.contracts import Product, Substance


@dataclass
class _SafetyWarningContext:
    warnings: list[dict[str, object]]
    seen: set[tuple[str, str, str]]
    scope: str
    scope_id: str
    warning: dict[str, object]
    message: str
    concern_kind: str


def collect_active_safety_concerns(
    *,
    active_order: list[str],
    active_components: dict[str, list[str]],
    item_products: dict[str, str],
    products: dict[str, Product],
    substances: dict[str, Substance],
) -> list[dict[str, object]]:
    warnings: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for item_id in active_order:
        product_id = item_products[item_id]
        product = products.get(product_id)
        if product is not None:
            for concern in product.concerns:
                _append_safety_warning(
                    _SafetyWarningContext(
                        warnings=warnings,
                        seen=seen,
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
                )
        for substance_id in active_components[item_id]:
            substance = substances.get(substance_id)
            if substance is None:
                continue
            for concern in substance.concerns:
                _append_safety_warning(
                    _SafetyWarningContext(
                        warnings=warnings,
                        seen=seen,
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
                )
    return warnings


def _append_safety_warning(
    warning_context: _SafetyWarningContext,
) -> None:
    if warning_context.concern_kind != "safety":
        return
    key = (warning_context.scope, warning_context.scope_id, warning_context.message)
    if key in warning_context.seen:
        return
    warning_context.seen.add(key)
    warning_context.warnings.append(warning_context.warning)
