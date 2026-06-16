"""show: regenerate schedule and print a human-readable pillbox layout to stdout."""

from __future__ import annotations

import contextlib
import io as _io
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from planner.contracts import CardLoadError
from planner.engine._types import ScheduleData, SchedulePillbox, ScheduleSlotEntry
from planner.engine.plan import cmd_plan
from planner.engine.results import ShowResult
from planner.paths import Paths
from planner.yaml_io import load_yaml

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

    pillboxes = schedule["pillboxes"]

    print()
    print("Here's your schedule for today:")
    print()

    for pillbox_key, pillbox in pillboxes.items():
        non_empty = _non_empty_slots(pillbox)
        if not non_empty:
            continue
        _print_pillbox(pillbox_key, pillbox, non_empty)

    _print_footer(schedule)
    return 0


def _load_schedule(schedule_path: Path) -> ScheduleData | None:
    try:
        data = cast(object, load_yaml(schedule_path))
    except CardLoadError as e:
        print(f"show: {e.message}", file=sys.stderr)
        return None

    if not isinstance(data, dict):
        print(f"show: {schedule_path}: expected mapping", file=sys.stderr)
        return None
    return cast(ScheduleData, data)


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
) -> None:
    pillbox_label = _str_field(pillbox, "label", pillbox_key)
    print(pillbox_label)
    print(SEPARATOR)

    for slot_key, slot in non_empty:
        slot_label = _str_field(slot, "label", slot_key)
        products = slot["products"]
        print()
        print(slot_label)
        for product in products:
            print(f"  • {product}")

    print()


def _print_footer(schedule: ScheduleData) -> None:
    print(SEPARATOR)
    sections: list[str] = []
    warnings = schedule["warnings"]
    if len(warnings) > 0:
        sections.append(f"warnings ({len(warnings)})")
    if schedule["placement_notes"]:
        sections.append("placement notes")

    if sections:
        print(f"Full details in schedule.yaml — {', '.join(sections)}.")
    else:
        print("Full details in schedule.yaml.")
