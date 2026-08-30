"""Pillbox slot loading, flattening, and id-uniqueness validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping
from planner.contracts import (
    CardLoadError,
    CircadianAnchor,
    ExerciseAnchor,
    MealContext,
    Pillbox,
    Slot,
)
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.runtime_program import RuntimeProgram
from planner.schema_validation import schema_errors

_TOPOLOGY_FIELDS = frozenset({"meal_context", "circadian_anchor", "exercise_anchor"})
_TECHNICAL_FIELDS = frozenset({"label", "order"})
_MEAL_CONTEXTS = frozenset({"with_food", "without_food"})
_CIRCADIAN_ANCHORS = frozenset({"wake", "sleep"})
_EXERCISE_ANCHORS = frozenset({"before", "after"})


@dataclass(frozen=True, slots=True)
class _SlotLoadContext:
    path: Path
    pillbox_name: str
    pillbox_label: str
    stack: str


def load_pillboxes(path: Path, bundle: OntologyBundle | RuntimeProgram) -> dict[str, Pillbox]:
    """Load the closed logical slot topology.

    ``bundle`` remains part of the loader boundary for callers during the
    runtime cutover, but topology validation is intentionally independent of
    the generated legacy ``near``/``food`` card schema.
    """
    data = load_card_mapping(path, "pillboxes")
    if not data:
        raise CardLoadError(path, f"{path}: pillboxes must contain at least one pillbox")
    if isinstance(bundle, OntologyBundle):
        errors = schema_errors(data, "pillboxes", path, bundle)
        if errors:
            raise CardLoadError(path, errors[0])
    loaded = {
        pillbox_name: _load_pillbox(path, pillbox_name, pillbox)
        for pillbox_name, pillbox in sorted(data.items(), key=lambda item: str(item[0]))
    }
    seen_ids: set[str] = set()
    seen_stacks: set[str] = set()
    for pillbox in loaded.values():
        if pillbox.stack in seen_stacks:
            raise CardLoadError(path, f"{path}: duplicate pillbox stack reference {pillbox.stack!r}")
        seen_stacks.add(pillbox.stack)
        seen_orders: set[int] = set()
        for slot in pillbox.slots.values():
            if slot.slot_id in seen_ids:
                raise CardLoadError(path, f"{path}: duplicate global slot id {slot.slot_id!r}")
            seen_ids.add(slot.slot_id)
            if slot.order in seen_orders:
                raise CardLoadError(
                    path,
                    f"{path}: pillbox {pillbox.name!r} has duplicate slot order {slot.order}",
                )
            seen_orders.add(slot.order)
    return loaded


def _load_pillbox(
    path: Path,
    pillbox_name: object,
    raw_pillbox: object,
) -> Pillbox:
    if not isinstance(pillbox_name, str) or not pillbox_name.strip():
        raise CardLoadError(path, f"{path}: pillbox ids must be non-empty strings")
    if not isinstance(raw_pillbox, dict):
        raise CardLoadError(path, f"{path}: pillbox {pillbox_name!r} must be a mapping")
    pillbox_dict = cast(dict[str, object], raw_pillbox)
    unknown_pillbox_fields = set(pillbox_dict) - {"label", "stack", "slots"}
    if unknown_pillbox_fields:
        raise CardLoadError(
            path,
            f"{path}: pillbox {pillbox_name!r} has unknown fields: {', '.join(sorted(map(str, unknown_pillbox_fields)))}",
        )
    pillbox_label = pillbox_dict.get("label")
    stack = pillbox_dict.get("stack")
    pillbox_slots_raw = pillbox_dict.get("slots")
    if not isinstance(pillbox_label, str) or not pillbox_label.strip():
        raise CardLoadError(path, f"{path}: pillbox {pillbox_name!r} requires a non-empty label")
    if not isinstance(stack, str) or not stack.strip():
        raise CardLoadError(path, f"{path}: pillbox {pillbox_name!r} requires a non-empty stack reference")
    if not isinstance(pillbox_slots_raw, dict) or not pillbox_slots_raw:
        raise CardLoadError(path, f"{path}: pillbox {pillbox_name!r} requires a non-empty slots mapping")
    slots = [
        _load_slot(_SlotLoadContext(path, pillbox_name, pillbox_label, stack), slot_id, raw_slot)
        for slot_id, raw_slot in cast(dict[object, object], pillbox_slots_raw).items()
    ]
    return Pillbox(
        name=pillbox_name,
        label=pillbox_label,
        stack=stack,
        slots={slot.slot_id: slot for slot in sorted(slots, key=lambda item: (item.order, item.slot_id))},
    )


def _load_slot(
    context: _SlotLoadContext,
    slot_id: object,
    raw_slot: object,
) -> Slot:
    path = context.path
    if not isinstance(slot_id, str) or not slot_id.strip():
        raise CardLoadError(path, f"{path}: slot ids must be non-empty strings")
    if not isinstance(raw_slot, dict):
        raise CardLoadError(path, f"{path}: slot {slot_id!r} must be a mapping")
    slot = cast(dict[str, object], raw_slot)
    unknown = set(slot) - _TECHNICAL_FIELDS - _TOPOLOGY_FIELDS
    if unknown:
        raise CardLoadError(
            path, f"{path}: slot {slot_id!r} has unknown fields: {', '.join(sorted(map(str, unknown)))}"
        )
    missing = _TECHNICAL_FIELDS - set(slot)
    if missing:
        raise CardLoadError(path, f"{path}: slot {slot_id!r} missing required fields: {', '.join(sorted(missing))}")
    label = slot["label"]
    order = slot["order"]
    if not isinstance(label, str) or not label.strip():
        raise CardLoadError(path, f"{path}: slot {slot_id!r} requires a non-empty label")
    if isinstance(order, bool) or not isinstance(order, int) or order < 1:
        raise CardLoadError(path, f"{path}: slot {slot_id!r} order must be a positive integer")
    topology: dict[str, str | None] = {}
    for field, allowed in (
        ("meal_context", _MEAL_CONTEXTS),
        ("circadian_anchor", _CIRCADIAN_ANCHORS),
        ("exercise_anchor", _EXERCISE_ANCHORS),
    ):
        if field not in slot:
            topology[field] = None
            continue
        value = slot[field]
        if not isinstance(value, str) or value not in allowed:
            expected = ", ".join(sorted(allowed))
            raise CardLoadError(path, f"{path}: slot {slot_id!r} {field} must be one of: {expected}")
        topology[field] = value
    return Slot(
        slot_id,
        label,
        order,
        context.pillbox_name,
        context.pillbox_label,
        context.stack,
        cast(MealContext | None, topology["meal_context"]),
        cast(CircadianAnchor | None, topology["circadian_anchor"]),
        cast(ExerciseAnchor | None, topology["exercise_anchor"]),
    )


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


def check_pillbox_slot_anchors(
    pillboxes: dict[str, Pillbox],
    slots_path: Path,
    bundle: OntologyBundle | RuntimeProgram,
) -> list[str]:
    """Validate the closed, optional logical topology axes."""
    errors: list[str] = []
    for pillbox_name, pillbox in pillboxes.items():
        for slot_id, slot in pillbox.slots.items():
            for field, value, allowed in (
                ("meal_context", slot.meal_context, _MEAL_CONTEXTS),
                ("circadian_anchor", slot.circadian_anchor, _CIRCADIAN_ANCHORS),
                ("exercise_anchor", slot.exercise_anchor, _EXERCISE_ANCHORS),
            ):
                if value is not None and value not in allowed:
                    errors.append(
                        f"{slots_path}: pillbox '{pillbox_name}' slot '{slot_id}' has invalid "
                        f"{field} {value!r}; expected one of {sorted(allowed)!r}"
                    )
    return errors
