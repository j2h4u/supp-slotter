"""show: regenerate schedule and print a human-readable pillbox layout to stdout."""

from __future__ import annotations

import contextlib
import io as _io
import sys
from pathlib import Path
from typing import Any, cast

from planner.contracts import CardLoadError
from planner.engine.plan import cmd_plan
from planner.engine.results import ShowResult
from planner.paths import Paths
from planner.yaml_io import load_yaml

SEPARATOR = "─" * 41


def _str_field(mapping: dict[str, Any], key: str, fallback: str) -> str:
    """Return mapping[key] if it is a non-empty str, otherwise fallback."""
    val = mapping.get(key)
    return val if isinstance(val, str) and val else fallback


def cmd_show(data_root: Path | None = None) -> ShowResult:
    """Regenerate schedule.yaml via cmd_plan, then print a pillbox layout to stdout.

    Returns ShowResult with exit_code 0 on success. When data_root is not None,
    captures printed output into ShowResult.output; otherwise prints to real stdout.
    """
    paths = Paths.from_root(data_root) if data_root is not None else Paths.default()
    plan_result = cmd_plan(data_root=data_root)
    if plan_result.exit_code != 0:
        return ShowResult(exit_code=plan_result.exit_code, output="")

    if data_root is not None:
        stdout_buf = _io.StringIO()
        with contextlib.redirect_stdout(stdout_buf):
            exit_code = _show_inner(paths.schedule_file)
        return ShowResult(exit_code=exit_code, output=stdout_buf.getvalue())
    exit_code = _show_inner(paths.schedule_file)
    return ShowResult(exit_code=exit_code, output="")


def _show_inner(schedule_path: Path) -> int:
    schedule = _load_schedule(schedule_path)
    if schedule is None:
        return 1

    raw_pillboxes = schedule.get("pillboxes")
    pillboxes: dict[str, Any] = cast(dict[str, Any], raw_pillboxes) if isinstance(raw_pillboxes, dict) else {}

    print()
    print("Here's your schedule for today:")
    print()

    for pillbox_key, pillbox_raw in pillboxes.items():
        if not isinstance(pillbox_raw, dict):
            continue
        pillbox: dict[str, Any] = cast(dict[str, Any], pillbox_raw)
        non_empty = _non_empty_slots(pillbox)
        if not non_empty:
            continue
        _print_pillbox(pillbox_key, pillbox, non_empty)

    _print_footer(schedule)
    return 0


def _load_schedule(schedule_path: Path) -> dict[str, Any] | None:
    try:
        data = load_yaml(schedule_path)
    except CardLoadError as e:
        print(f"show: {e.message}", file=sys.stderr)
        return None

    if not isinstance(data, dict):
        print(f"show: {schedule_path}: expected mapping", file=sys.stderr)
        return None
    return cast(dict[str, Any], data)


def _non_empty_slots(pillbox: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    raw_slots = pillbox.get("slots")
    slots: dict[str, Any] = cast(dict[str, Any], raw_slots) if isinstance(raw_slots, dict) else {}
    non_empty: list[tuple[str, dict[str, Any]]] = []
    for slot_key, slot_raw in slots.items():
        if not isinstance(slot_raw, dict):
            continue
        slot: dict[str, Any] = cast(dict[str, Any], slot_raw)
        raw_products = slot.get("products")
        if isinstance(raw_products, list) and raw_products:
            non_empty.append((slot_key, slot))
    return non_empty


def _print_pillbox(
    pillbox_key: str,
    pillbox: dict[str, Any],
    non_empty: list[tuple[str, dict[str, Any]]],
) -> None:
    pillbox_label = _str_field(pillbox, "label", pillbox_key)
    print(pillbox_label)
    print(SEPARATOR)

    for slot_key, slot in non_empty:
        slot_label = _str_field(slot, "label", slot_key)
        products = cast(list[Any], slot.get("products"))
        print()
        print(slot_label)
        for product in products:
            print(f"  • {product}")

    print()


def _print_footer(schedule: dict[str, Any]) -> None:
    print(SEPARATOR)
    sections: list[str] = []
    raw_warnings = schedule.get("warnings")
    warnings: list[Any] = cast(list[Any], raw_warnings) if isinstance(raw_warnings, list) else []
    if len(warnings) > 0:
        sections.append(f"warnings ({len(warnings)})")
    if schedule.get("placement_notes"):
        sections.append("placement notes")

    if sections:
        print(f"Full details in schedule.yaml — {', '.join(sections)}.")
    else:
        print("Full details in schedule.yaml.")
