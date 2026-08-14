"""Raw safety-warning collection for active schedule items."""

from __future__ import annotations

from dataclasses import dataclass

from planner.contracts import Concern, ConcernRecord, Product, Substance
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


@dataclass(frozen=True, slots=True)
class _ActiveConcern:
    record: ConcernRecord
    item_id: str
    product_id: str


def collect_active_safety_concerns(
    input_data: SafetyConcernInput,
) -> list[dict[str, object]]:
    warnings: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for active_concern in _active_concerns(input_data):
        record = active_concern.record
        warning_type = input_data.runtime_program.concern_warning_catalog_by_kind.get(record.concern_kind)
        if warning_type is None:
            continue
        warning: dict[str, object] = {
            "type": warning_type,
            "item": active_concern.item_id,
            "product": active_concern.product_id,
            "message": record.text,
        }
        if record.subject_kind == "substance":
            warning["substance"] = record.subject_id
        _append_safety_warning(
            _SafetyWarningContext(
                warnings=warnings,
                seen=seen,
                scope=record.subject_kind,
                scope_id=record.subject_id,
                warning=warning,
                message=record.text,
            )
        )
    return warnings


def _active_concerns(input_data: SafetyConcernInput) -> tuple[_ActiveConcern, ...]:
    """Project product and substance cards through one concern interpreter input."""
    projected: list[_ActiveConcern] = []
    for item_id in input_data.active_order:
        product_id = input_data.item_products.get(item_id)
        if product_id is None:
            continue
        product = input_data.products.get(product_id)
        subjects: list[tuple[str, str, tuple[Concern, ...]]] = []
        if product is not None:
            subjects.append(("product", product.id, product.concerns))
        for substance_id in input_data.active_components.get(item_id, []):
            substance = input_data.substances.get(substance_id)
            if substance is not None:
                subjects.append(("substance", substance.id, substance.concerns))
        for subject_kind, subject_id, concerns in subjects:
            projected.extend(
                _ActiveConcern(
                    record=ConcernRecord(subject_kind, subject_id, concern.kind, concern.text),
                    item_id=item_id,
                    product_id=product_id,
                )
                for concern in concerns
            )
    return tuple(projected)


def _append_safety_warning(
    warning_context: _SafetyWarningContext,
) -> None:
    key = (warning_context.scope, warning_context.scope_id, warning_context.message)
    if key in warning_context.seen:
        return
    warning_context.seen.add(key)
    warning_context.warnings.append(warning_context.warning)
