"""Pillbox slot loading, flattening, and id-uniqueness validation."""

from __future__ import annotations

from pathlib import Path

from planner.io import SLOT_META_FIELDS


def derive_slot_fields(slots_data: dict) -> set[str]:
    fields: set[str] = set()
    for slot in flatten_pillbox_slots(slots_data).values():
        fields.update(k for k in slot if k not in SLOT_META_FIELDS)
    return fields

def flatten_pillbox_slots(slots_data: dict) -> dict[str, dict]:
    slots: dict[str, dict] = {}
    if not isinstance(slots_data, dict):
        return slots

    for pillbox_name, pillbox in sorted(slots_data.items()):
        if not isinstance(pillbox, dict):
            continue
        pillbox_slots = pillbox.get("slots", {})
        if not isinstance(pillbox_slots, dict):
            continue
        for slot_name, slot in sorted(
            pillbox_slots.items(),
            key=lambda kv: kv[1].get("order", 0) if isinstance(kv[1], dict) else 0,
        ):
            if not isinstance(slot, dict):
                continue
            slots[slot_name] = {
                **slot,
                "pillbox": pillbox_name,
                "pillbox_label": pillbox.get("label", pillbox_name),
                "stack": pillbox_name,
            }
    return slots

def build_empty_schedule_pillboxes(slots_data: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not isinstance(slots_data, dict):
        return out

    for pillbox_name, pillbox in slots_data.items():
        if not isinstance(pillbox, dict):
            continue
        out[pillbox_name] = {
            "label": pillbox.get("label", pillbox_name),
            "slots": {},
        }
        pillbox_slots = pillbox.get("slots", {})
        if not isinstance(pillbox_slots, dict):
            continue
        for slot_name, slot in sorted(
            pillbox_slots.items(),
            key=lambda kv: kv[1].get("order", 0) if isinstance(kv[1], dict) else 0,
        ):
            if not isinstance(slot, dict):
                continue
            out[pillbox_name]["slots"][slot_name] = {
                "label": slot.get("label", slot_name),
                "products": [],
                "substances": [],
            }
    return out

def check_pillbox_slot_ids(slots_data: dict, slots_path: Path) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    if not isinstance(slots_data, dict):
        return errors
    for pillbox_name, pillbox in slots_data.items():
        if not isinstance(pillbox, dict):
            continue
        pillbox_slots = pillbox.get("slots", {})
        if not isinstance(pillbox_slots, dict):
            continue
        for slot_name in pillbox_slots:
            previous_pillbox = seen.get(slot_name)
            if previous_pillbox is not None:
                errors.append(
                    f"{slots_path}: slot id '{slot_name}' is used in both "
                    f"'{previous_pillbox}' and '{pillbox_name}'; slot ids must be "
                    "unique across pillboxes"
                )
            else:
                seen[slot_name] = pillbox_name
    return errors

