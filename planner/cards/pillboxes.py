"""Pillbox slot loading, flattening, and id-uniqueness validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

from planner.cards._common import load_card_mapping
from planner.contracts import (
    CardLoadError,
    Pillbox,
    Slot,
)
from planner.ontology.artifacts import OntologyBundle
from planner.schema_validation import schema_errors


@dataclass(frozen=True, slots=True)
class _SlotLoadContext:
    path: Path
    pillbox_name: str
    pillbox_label: str
    stack: str


def load_pillboxes(path: Path, bundle: OntologyBundle) -> dict[str, Pillbox]:
    """Load the closed logical slot topology.

    Topology validation is intentionally independent of the generated legacy
    ``near``/``food`` card schema.
    """
    data = load_card_mapping(path, "pillboxes")
    if not data:
        raise CardLoadError(path, f"{path}: pillboxes must contain at least one pillbox")
    errors = schema_errors(data, "pillboxes", path, bundle)
    if errors:
        raise CardLoadError(path, errors[0])
    dimensions = bundle.runtime_program.canonical_scheduling.pressure_values_by_dimension
    loaded = {
        pillbox_name: _load_pillbox(path, pillbox_name, pillbox, dimensions)
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
    dimensions: Mapping[str, frozenset[str]],
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
        _load_slot(_SlotLoadContext(path, pillbox_name, pillbox_label, stack), slot_id, raw_slot, dimensions)
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
    dimensions: Mapping[str, frozenset[str]],
) -> Slot:
    """Project one schema-validated logical slot into its runtime record."""
    path = context.path
    slot = cast(dict[str, object], raw_slot)
    label = cast(str, slot["label"])
    if not label.strip():
        raise CardLoadError(path, f"{path}: slot {slot_id!r} requires a non-empty label")
    anchors = {key: cast(str | None, slot.get(key)) for key in sorted(dimensions)}
    return Slot(
        slot_id,
        label,
        cast(int, slot["order"]),
        context.pillbox_name,
        context.pillbox_label,
        context.stack,
        MappingProxyType(cast(dict[str, str | None], anchors)),
    )


def flatten_pillbox_slots(pillboxes: dict[str, Pillbox]) -> dict[str, Slot]:
    slots: dict[str, Slot] = {}
    for pillbox in sorted(pillboxes.values(), key=lambda p: p.name):
        for slot in sorted(pillbox.slots.values(), key=lambda s: s.order):
            slots[slot.slot_id] = slot
    return slots


def check_pillbox_slot_anchors(
    pillboxes: dict[str, Pillbox],
    slots_path: Path,
    bundle: OntologyBundle,
) -> list[str]:
    """Validate generic immutable topology anchors against runtime metadata."""
    errors: list[str] = []
    dimensions = bundle.runtime_program.canonical_scheduling.pressure_values_by_dimension
    for pillbox_name, pillbox in pillboxes.items():
        for slot_id, slot in pillbox.slots.items():
            if set(slot.anchors) != set(dimensions) or any(
                value is not None and value not in dimensions.get(key, frozenset())
                for key, value in slot.anchors.items()
            ):
                errors.append(f"{slots_path}: pillbox '{pillbox_name}' slot '{slot_id}' has invalid runtime anchors")
    return errors
