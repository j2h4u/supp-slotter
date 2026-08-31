"""show: regenerate schedule and print a human-readable pillbox layout to stdout."""

from __future__ import annotations

import contextlib
import io as _io
from collections.abc import Iterable, Mapping
from pathlib import Path

from planner.engine.plan import cmd_plan
from planner.engine.results import ShowResult
from planner.schedule_types import CanonicalScheduleData, SchedulePillbox, ScheduleProductEntry, ScheduleSlotEntry

SEPARATOR = "─" * 41


def _str_field(mapping: Mapping[str, object], key: str, fallback: str) -> str:
    """Return mapping[key] if it is a non-empty str, otherwise fallback."""
    val = mapping.get(key)
    return val if isinstance(val, str) and val else fallback


def cmd_show(data_root: Path | None = None) -> ShowResult:
    """Regenerate schedule.yaml via cmd_plan, then print a pillbox layout to stdout.

    Returns ShowResult with exit_code 0 on success. When data_root is not None,
    captures printed output into ShowResult.output; otherwise prints to real stdout.
    """
    plan_result = cmd_plan(data_root=data_root)
    if plan_result.exit_code != 0 or plan_result.schedule is None:
        return ShowResult(exit_code=plan_result.exit_code, output="")

    if data_root is not None:
        stdout_buf = _io.StringIO()
        with contextlib.redirect_stdout(stdout_buf):
            exit_code = _show_inner(plan_result.schedule)
        return ShowResult(exit_code=exit_code, output=stdout_buf.getvalue())
    exit_code = _show_inner(plan_result.schedule)
    return ShowResult(exit_code=exit_code, output="")


def _show_inner(schedule: CanonicalScheduleData) -> int:
    pillboxes = schedule["pillboxes"]
    balance_only_items = _balance_only_items(schedule)

    print()
    print("Current plan:")
    print()

    _print_current_plan_groups(schedule)
    for pillbox_key, pillbox in pillboxes.items():
        if pillbox_key != "training":
            continue
        non_empty = _non_empty_slots(pillbox)
        if non_empty:
            _print_pillbox(pillbox_key, pillbox, non_empty, balance_only_items)

    print(SEPARATOR)
    print("[balance-only] = no pressure match was satisfied; load balance and stable tie-break chose the slot.")
    return 0


def _print_current_plan_groups(schedule: CanonicalScheduleData) -> None:
    """Print current-plan placement groups, retaining their logical-slot detail."""
    groups = _placement_groups(schedule)
    pillboxes = schedule["pillboxes"]
    daily_products = _daily_products(pillboxes)
    for group_key, label in (("routine", "Routine placements"), ("episodic", "Episodic placements")):
        names = _active_group_names(groups.get(group_key, []), daily_products)
        if not names:
            continue
        _print_usage_group(label, names, pillboxes, _balance_only_items(schedule))


def _placement_groups(schedule: CanonicalScheduleData) -> dict[str, list[str]]:
    summary = schedule.get("summary", {})
    raw_groups = summary.get("placement_groups", {}) if isinstance(summary, dict) else {}
    return raw_groups if isinstance(raw_groups, dict) else {}


def _daily_products(pillboxes: dict[str, SchedulePillbox]) -> set[str]:
    return {
        item_id
        for key, pillbox in pillboxes.items()
        if key != "training"
        for _slot_key, slot in _non_empty_slots(pillbox)
        for product in slot["products"]
        if isinstance(product.get("item_id"), str)
        for item_id in [product["item_id"]]
    }


def _active_group_names(raw_names: Iterable[object], daily_products: set[str]) -> list[str]:
    return [name for name in raw_names if isinstance(name, str) and name in daily_products]


def _print_usage_group(
    label: str,
    names: list[str],
    pillboxes: dict[str, SchedulePillbox],
    balance_only_items: set[str],
) -> None:
    print(label)
    print(SEPARATOR)
    wanted = set(names)
    for pillbox_key, pillbox in pillboxes.items():
        if pillbox_key == "training":
            continue
        filtered = _group_slots(pillbox, wanted)
        if filtered:
            _print_pillbox_slots(pillbox, filtered, wanted, balance_only_items)
    print()


def _group_slots(
    pillbox: SchedulePillbox,
    wanted: set[str],
) -> list[tuple[str, ScheduleSlotEntry]]:
    return [
        (slot_key, slot)
        for slot_key, slot in _non_empty_slots(pillbox)
        if any(product["item_id"] in wanted for product in slot["products"])
    ]


def _non_empty_slots(pillbox: SchedulePillbox) -> list[tuple[str, ScheduleSlotEntry]]:
    slots = pillbox["slots"]
    non_empty: list[tuple[str, ScheduleSlotEntry]] = []
    for slot_key, slot in slots.items():
        if slot["products"]:
            non_empty.append((slot_key, slot))
    return non_empty


def _print_pillbox(
    pillbox_key: str,
    pillbox: SchedulePillbox,
    non_empty: list[tuple[str, ScheduleSlotEntry]],
    balance_only_items: set[str],
) -> None:
    pillbox_label = _str_field(pillbox, "label", pillbox_key)
    print(pillbox_label)
    print(SEPARATOR)

    for slot_key, slot in non_empty:
        slot_label = _str_field(slot, "label", slot_key)
        products = slot["products"]
        print()
        print(_slot_heading(slot_key, slot_label))
        for product in products:
            _print_product(product, balance_only_items)

    print()


def _print_pillbox_slots(
    pillbox: SchedulePillbox,
    non_empty: list[tuple[str, ScheduleSlotEntry]],
    wanted: set[str],
    balance_only_items: set[str],
) -> None:
    """Render filtered slots for one daily presentation group."""
    del pillbox
    for slot_key, slot in non_empty:
        _print_filtered_slot(slot_key, slot, wanted, balance_only_items)


def _print_filtered_slot(
    slot_key: str, slot: ScheduleSlotEntry, wanted: set[str], balance_only_items: set[str]
) -> None:
    products = [product for product in slot["products"] if product["item_id"] in wanted]
    if not products:
        return
    print()
    print(_slot_heading(slot_key, _str_field(slot, "label", slot_key)))
    for product in products:
        _print_product(product, balance_only_items)


def _balance_only_items(schedule: CanonicalScheduleData) -> set[str]:
    explanations = schedule.get("canonical_explanations", {})
    if not isinstance(explanations, dict):
        return set()
    return {
        item_id
        for explanation in explanations.values()
        for item_id in [str(explanation.get("item_id", ""))]
        if isinstance(explanation, dict)
        if isinstance(explanation, dict)
        and explanation.get("placement_basis") == "balance_and_tie_break_only"
        and item_id
    }


def _slot_heading(slot_key: str, label: str) -> str:
    del slot_key
    return label


def _print_product(product: ScheduleProductEntry, balance_only_items: set[str]) -> None:
    marker = " [balance-only]" if product["item_id"] in balance_only_items else ""
    print(f"  • {product['label']}{marker}")
