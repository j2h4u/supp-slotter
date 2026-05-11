"""Schedule output: action points, placement notes, summary."""

from __future__ import annotations

from typing import Any, cast


def build_placement_notes(schedule: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract per-product placement notes for products that have a scheduling tradeoff.

    Only why_here entries that contain the substring "tradeoff" (case-insensitive) are
    included. Products where every why_here entry is a positive fit reason produce no note
    and are omitted from the result.
    """
    notes: list[dict[str, Any]] = []
    explanations_obj = schedule.get("explanations", {})
    if not isinstance(explanations_obj, dict):
        return notes
    explanations = cast(dict[str, Any], explanations_obj)
    for product_name, explanation_obj in explanations.items():
        if not isinstance(explanation_obj, dict):
            continue
        explanation = cast(dict[str, Any], explanation_obj)
        why_here_raw = explanation.get("why_here", [])
        if not isinstance(why_here_raw, list):
            continue
        why_here_list = cast(list[Any], why_here_raw)
        why_here = [
            note
            for note in why_here_list
            if isinstance(note, str) and "tradeoff" in note.lower()
        ]
        if not why_here:
            continue
        notes.append(
            {
                "product": product_name,
                "pillbox": cast(Any, explanation.get("pillbox")),
                "slot": cast(Any, explanation.get("slot")),
                "notes": why_here,
            }
        )
    return sorted(notes, key=lambda entry: str(entry["product"]).casefold())


def build_schedule_summary(schedule: dict[str, Any]) -> dict[str, Any]:
    take: dict[str, list[str]] = {}
    pillboxes_obj = schedule.get("pillboxes", {})
    if not isinstance(pillboxes_obj, dict):
        return {"take": take}
    pillboxes = cast(dict[str, Any], pillboxes_obj)
    for pillbox_name, pillbox_obj in pillboxes.items():
        if not isinstance(pillbox_obj, dict):
            continue
        pillbox = cast(dict[str, Any], pillbox_obj)
        slots_obj = pillbox.get("slots", {})
        if not isinstance(slots_obj, dict):
            continue
        slots = cast(dict[str, Any], slots_obj)
        lines: list[str] = []
        for slot_obj in slots.values():
            if not isinstance(slot_obj, dict):
                continue
            slot = cast(dict[str, Any], slot_obj)
            products = slot.get("products")
            if not products:
                continue
            lines.append(f"{cast(str, slot.get('label'))}: {', '.join(cast(list[str], products))}")
        if lines:
            take[pillbox_name] = lines
    return {"take": take}
