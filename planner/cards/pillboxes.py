"""Pillbox slot loading, flattening, and id-uniqueness validation."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping
from planner.contracts import CardLoadError, Pillbox, Slot, SlotNear


def _slot_order(slot: object) -> int:
    if not isinstance(slot, dict):
        return 0
    slot_data = cast(dict[str, object], slot)
    order_raw = slot_data.get("order", 0)
    if isinstance(order_raw, (int, float, str, bool)):
        return int(order_raw)
    return 0


def load_pillboxes(path: Path) -> dict[str, Pillbox]:
    """Load pillboxes.yaml into a name -> Pillbox map with flattened Slots.

    Raises CardLoadError on missing file, parse error, or non-mapping top-level.
    """
    data = load_card_mapping(path, "pillboxes")
    out: dict[str, Pillbox] = {}
    for pillbox_name, pillbox in sorted(data.items()):
        if not isinstance(pillbox, dict):
            continue
        pillbox_dict = cast(dict[str, object], pillbox)
        pillbox_label = str(pillbox_dict.get("label") or pillbox_name)
        pillbox_slots_raw = pillbox_dict.get("slots", {})
        if not isinstance(pillbox_slots_raw, dict):
            pillbox_slots_raw = {}
        pillbox_slots_dict = cast(dict[str, object], pillbox_slots_raw)
        slots_dict: dict[str, Slot] = {}
        for slot_id, slot in sorted(
            pillbox_slots_dict.items(),
            key=lambda kv: _slot_order(kv[1]),
        ):
            if not isinstance(slot, dict):
                continue
            slot_dict = cast(dict[str, object], slot)
            try:
                order_raw = slot_dict.get("order")
                slots_dict[slot_id] = Slot(
                    slot_id=slot_id,
                    label=str(slot_dict.get("label") or slot_id),
                    order=int(order_raw) if isinstance(order_raw, (int, float, str, bool)) else 0,
                    near=cast(SlotNear, slot_dict["near"]),
                    food=bool(slot_dict["food"]),
                    pillbox=pillbox_name,
                    pillbox_label=pillbox_label,
                    stack=pillbox_name,
                )
            except KeyError as e:
                raise CardLoadError(path, f"{path}: slot '{slot_id}' missing required field {e}") from e
        out[pillbox_name] = Pillbox(
            name=pillbox_name,
            label=pillbox_label,
            slots=slots_dict,
        )
    return out


def flatten_pillbox_slots(pillboxes: dict[str, Pillbox]) -> dict[str, Slot]:
    slots: dict[str, Slot] = {}
    for pillbox in sorted(pillboxes.values(), key=lambda p: p.name):
        for slot in sorted(pillbox.slots.values(), key=lambda s: s.order):
            slots[slot.slot_id] = slot
    return slots


def build_empty_schedule_pillboxes(
    pillboxes: dict[str, Pillbox],
) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for pillbox in pillboxes.values():
        slot_entries: dict[str, dict[str, object]] = {}
        for slot in sorted(pillbox.slots.values(), key=lambda s: s.order):
            slot_entries[slot.slot_id] = {
                "label": slot.label,
                "products": [],
                "substances": [],
            }
        out[pillbox.name] = {"label": pillbox.label, "slots": slot_entries}
    return out


def check_pillbox_slot_ids(pillboxes: dict[str, Pillbox], slots_path: Path) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    for pillbox_name, pillbox in pillboxes.items():
        for slot_id in pillbox.slots:
            previous_pillbox = seen.get(slot_id)
            if previous_pillbox is not None:
                errors.append(
                    f"{slots_path}: slot id '{slot_id}' is used in both "
                    f"'{previous_pillbox}' and '{pillbox_name}'; slot ids must be "
                    "unique across pillboxes"
                )
            else:
                seen[slot_id] = pillbox_name
    return errors
