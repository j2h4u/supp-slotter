"""Pillbox slot loading, flattening, and id-uniqueness validation."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping
from planner.contracts import CardLoadError, Pillbox, Slot, SlotNear
from planner.io import SLOT_META_FIELDS


def load_pillboxes(path: Path) -> dict[str, Pillbox]:
    """Load pillboxes.yaml into a name -> Pillbox map with flattened Slots.

    Raises CardLoadError on missing file, parse error, or non-mapping top-level.
    """
    data = load_card_mapping(path, "pillboxes")
    out: dict[str, Pillbox] = {}
    for pillbox_name, pillbox in sorted(data.items()):
        if not isinstance(pillbox, dict):
            continue
        pillbox_label = str(pillbox.get("label") or pillbox_name)
        pillbox_slots_raw = pillbox.get("slots", {})
        if not isinstance(pillbox_slots_raw, dict):
            pillbox_slots_raw = {}
        slots_dict: dict[str, Slot] = {}
        for slot_id, slot in sorted(
            pillbox_slots_raw.items(),
            key=lambda kv: kv[1].get("order", 0) if isinstance(kv[1], dict) else 0,
        ):
            if not isinstance(slot, dict):
                continue
            try:
                slots_dict[slot_id] = Slot(
                    slot_id=slot_id,
                    label=str(slot.get("label") or slot_id),
                    order=int(slot.get("order") or 0),
                    near=cast(SlotNear, slot["near"]),
                    food=bool(slot["food"]),
                    pillbox=pillbox_name,
                    pillbox_label=pillbox_label,
                    stack=pillbox_name,
                )
            except KeyError as e:
                raise CardLoadError(
                    path, f"{path}: slot '{slot_id}' missing required field {e}"
                ) from e
        out[pillbox_name] = Pillbox(
            name=pillbox_name,
            label=pillbox_label,
            slots=slots_dict,
        )
    return out


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
