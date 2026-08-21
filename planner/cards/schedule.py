"""Schedule output: action points, placement notes, summary."""

from __future__ import annotations

from typing import cast

from planner.contracts import Product, StackEntry

NOT_EVERY_DAY_USE_PATTERN = "not_every_day"


def build_placement_notes(schedule: dict[str, object]) -> list[dict[str, object]]:
    """Extract per-product placement notes for products that have a scheduling tradeoff.

    Only why_here entries that contain the substring "tradeoff" (case-insensitive) are
    included. Products where every why_here entry is a positive fit reason produce no note
    and are omitted from the result.
    """
    notes: list[dict[str, object]] = []
    explanations_obj = schedule.get("explanations", {})
    if not isinstance(explanations_obj, dict):
        return notes
    explanations = cast(dict[str, object], explanations_obj)
    for product_name, explanation_obj in explanations.items():
        if not isinstance(explanation_obj, dict):
            continue
        explanation = cast(dict[str, object], explanation_obj)
        why_here_raw = explanation.get("why_here", [])
        if not isinstance(why_here_raw, list):
            continue
        why_here_list = why_here_raw
        why_here = [note for note in why_here_list if isinstance(note, str) and "tradeoff" in note.lower()]
        if not why_here:
            continue
        notes.append({
            "product": product_name,
            "pillbox": explanation.get("pillbox"),
            "slot": explanation.get("slot"),
            "notes": why_here,
        })
    return sorted(notes, key=lambda entry: str(entry["product"]).casefold())


def build_schedule_summary(
    schedule: dict[str, object],
    products: dict[str, Product] | None = None,
    stack_entries: dict[str, StackEntry] | None = None,
) -> dict[str, object]:
    take = _build_take(schedule)
    usage_groups = _build_usage_groups(products, stack_entries)
    return {"take": take, "usage_groups": usage_groups}


def _build_take(schedule: dict[str, object]) -> dict[str, list[str]]:
    take: dict[str, list[str]] = {}
    pillboxes_obj = schedule.get("pillboxes", {})
    if not isinstance(pillboxes_obj, dict):
        return take
    pillboxes = cast(dict[str, object], pillboxes_obj)
    for pillbox_name, pillbox_obj in pillboxes.items():
        if not isinstance(pillbox_obj, dict):
            continue
        pillbox = cast(dict[str, object], pillbox_obj)
        slots_obj = pillbox.get("slots", {})
        if not isinstance(slots_obj, dict):
            continue
        slots = cast(dict[str, object], slots_obj)
        lines: list[str] = []
        for slot_obj in slots.values():
            if not isinstance(slot_obj, dict):
                continue
            slot = cast(dict[str, object], slot_obj)
            products = slot.get("products")
            if not products:
                continue
            if isinstance(products, list):
                product_names = cast(list[object], products)
                lines.append(f"{cast(str, slot.get('label'))}: {', '.join(str(product) for product in product_names)}")
        if lines:
            take[pillbox_name] = lines
    return take


def _build_usage_groups(
    products: dict[str, Product] | None,
    stack_entries: dict[str, StackEntry] | None,
) -> dict[str, list[str]]:
    usage_groups: dict[str, list[str]] = {"daily_base": [], "not_every_day": []}
    if products is None or stack_entries is None:
        return usage_groups
    for product_id, entry in stack_entries.items():
        if entry.get("stack") != "daily":
            continue
        product = products.get(product_id)
        if product is None:
            continue
        product_name = _product_display_name(product)
        group = "not_every_day" if product.use_pattern == NOT_EVERY_DAY_USE_PATTERN else "daily_base"
        usage_groups[group].append(product_name)
    for group in usage_groups.values():
        group.sort(key=str.casefold)
    return usage_groups


def _product_display_name(product: Product) -> str:
    if product.brand and product.brand != "unknown":
        return f"{product.brand} - {product.name}"
    return product.name or product.id
