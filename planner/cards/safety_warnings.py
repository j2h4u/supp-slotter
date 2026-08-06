"""Raw safety-warning collection for active schedule items."""

from __future__ import annotations

from dataclasses import dataclass

from planner.contracts import Product, Substance
from planner.ontology.runtime_program import RuntimeProgram


@dataclass(frozen=True)
class SafetyConcernInput:
    active_order: list[str]
    active_components: dict[str, list[str]]
    item_products: dict[str, str]
    products: dict[str, Product]
    runtime_program: RuntimeProgram
    substances: dict[str, Substance]


@dataclass
class _SafetyWarningContext:
    warnings: list[dict[str, object]]
    seen: set[tuple[str, str, str]]
    scope: str
    scope_id: str
    warning: dict[str, object]
    message: str
    concern_kind: str
    warning_type: str | None


def collect_active_safety_concerns(
    input_data: SafetyConcernInput,
) -> list[dict[str, object]]:
    warnings: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for item_id in input_data.active_order:
        product_id = input_data.item_products[item_id]
        product = input_data.products.get(product_id)
        if product is not None:
            for concern in product.concerns:
                warning_type = input_data.runtime_program.warning_type_by_concern_kind.get(concern.kind)
                _append_safety_warning(
                    _SafetyWarningContext(
                        warnings=warnings,
                        seen=seen,
                        scope="product",
                        scope_id=product_id,
                        warning={
                            "type": warning_type or "",
                            "item": item_id,
                            "product": product_id,
                            "message": concern.text,
                        },
                        message=concern.text,
                        concern_kind=concern.kind,
                        warning_type=warning_type,
                    )
                )
        for substance_id in input_data.active_components[item_id]:
            substance = input_data.substances.get(substance_id)
            if substance is None:
                continue
            for concern in substance.concerns:
                warning_type = input_data.runtime_program.warning_type_by_concern_kind.get(concern.kind)
                _append_safety_warning(
                    _SafetyWarningContext(
                        warnings=warnings,
                        seen=seen,
                        scope="substance",
                        scope_id=substance_id,
                        warning={
                            "type": warning_type or "",
                            "item": item_id,
                            "product": product_id,
                            "substance": substance_id,
                            "message": concern.text,
                        },
                        message=concern.text,
                        concern_kind=concern.kind,
                        warning_type=warning_type,
                    )
                )
    return warnings


def _append_safety_warning(
    warning_context: _SafetyWarningContext,
) -> None:
    if warning_context.warning_type is None:
        return
    key = (warning_context.scope, warning_context.scope_id, warning_context.message)
    if key in warning_context.seen:
        return
    warning_context.seen.add(key)
    warning_context.warnings.append(warning_context.warning)
