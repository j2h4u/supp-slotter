"""show: regenerate schedule and print a human-readable pillbox layout to stdout."""

from __future__ import annotations

import sys
from typing import Any, cast

from planner.contracts import CardLoadError
from planner.engine.plan import cmd_plan
from planner.io import SCHEDULE_PATH, load_yaml

SEPARATOR = "─" * 41


def _str_field(mapping: dict[str, Any], key: str, fallback: str) -> str:
    """Return mapping[key] if it is a non-empty str, otherwise fallback."""
    val = mapping.get(key)
    return val if isinstance(val, str) and val else fallback


def cmd_show() -> int:
    """Regenerate schedule.yaml via cmd_plan, then print a pillbox layout to stdout.

    Returns 0 on success, or the non-zero exit code from cmd_plan / load_yaml on failure.
    """
    plan_rc = cmd_plan()
    if plan_rc != 0:
        return plan_rc

    try:
        data = load_yaml(SCHEDULE_PATH)
    except CardLoadError as e:
        print(f"show: {e.message}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print(f"show: {SCHEDULE_PATH}: expected mapping", file=sys.stderr)
        return 1

    schedule = cast(dict[str, Any], data)

    raw_pillboxes = schedule.get("pillboxes")
    pillboxes: dict[str, Any] = (
        cast(dict[str, Any], raw_pillboxes)
        if isinstance(raw_pillboxes, dict)
        else {}
    )

    print()
    print("Here's your schedule for today:")
    print()

    for pillbox_key, pillbox_raw in pillboxes.items():
        if not isinstance(pillbox_raw, dict):
            continue
        pillbox: dict[str, Any] = cast(dict[str, Any], pillbox_raw)

        raw_slots = pillbox.get("slots")
        slots: dict[str, Any] = (
            cast(dict[str, Any], raw_slots) if isinstance(raw_slots, dict) else {}
        )

        # Collect non-empty slots: slot must be a dict with a non-empty products list
        non_empty: list[tuple[str, dict[str, Any]]] = []
        for slot_key, slot_raw in slots.items():
            if not isinstance(slot_raw, dict):
                continue
            slot: dict[str, Any] = cast(dict[str, Any], slot_raw)
            raw_products = slot.get("products")
            if isinstance(raw_products, list):
                products_list = cast(list[Any], raw_products)
                if len(products_list) > 0:
                    non_empty.append((slot_key, slot))

        # Skip pillboxes where every slot is empty
        if not non_empty:
            continue

        pillbox_label = _str_field(pillbox, "label", pillbox_key)
        print(pillbox_label)
        print(SEPARATOR)

        for slot_key, slot in non_empty:
            slot_label = _str_field(slot, "label", slot_key)
            raw_products = slot.get("products")
            products: list[Any] = cast(list[Any], raw_products)
            print()
            print(slot_label)
            for product in products:
                print(f"  • {product}")

        print()

    # Footer
    print(SEPARATOR)
    sections: list[str] = []
    raw_warnings = schedule.get("warnings")
    warnings: list[Any] = (
        cast(list[Any], raw_warnings) if isinstance(raw_warnings, list) else []
    )
    if len(warnings) > 0:
        sections.append(f"warnings ({len(warnings)})")
    if schedule.get("action_points"):
        sections.append("action points")
    if schedule.get("placement_notes"):
        sections.append("placement notes")
    if schedule.get("review_contexts"):
        sections.append("review contexts")

    if sections:
        print(f"Full details in schedule.yaml — {', '.join(sections)}.")
    else:
        print("Full details in schedule.yaml.")

    return 0
