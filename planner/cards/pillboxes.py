"""Pillbox slot loading, flattening, and id-uniqueness validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping
from planner.contracts import CardLoadError, Pillbox, Slot, SlotObservation
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.glue_capabilities import IMPLEMENTED_EFFECT_MATCH_VALUE_HANDLERS
from planner.ontology.runtime_program import RuntimeEffectMatchDimension, RuntimeProgram
from planner.schema_validation import schema_errors


def _runtime(bundle: OntologyBundle | RuntimeProgram) -> RuntimeProgram:
    return bundle.runtime_program if isinstance(bundle, OntologyBundle) else bundle


@dataclass(frozen=True, slots=True)
class _SlotLoadContext:
    path: Path
    pillbox_name: str
    pillbox_label: str
    stack: str
    expected_fields: set[str]
    dimensions: tuple[RuntimeEffectMatchDimension, ...]
    runtime: RuntimeProgram


@dataclass(frozen=True, slots=True)
class _PillboxLoadContext:
    path: Path
    expected_fields: set[str]
    dimensions: tuple[RuntimeEffectMatchDimension, ...]
    runtime: RuntimeProgram


def _observation_dimensions(
    path: Path, bundle: OntologyBundle | RuntimeProgram
) -> tuple[RuntimeEffectMatchDimension, ...]:
    runtime = _runtime(bundle)
    dimensions = runtime.effect_match_dimensions
    if not dimensions:
        raise CardLoadError(path, f"{path}: ontology declares no effect-match slot observations")
    keys: set[str] = set()
    fields: set[str] = set()
    for dimension in dimensions:
        if dimension.key in keys:
            raise CardLoadError(path, f"{path}: ontology repeats effect-match observation key {dimension.key!r}")
        if dimension.slot_field in fields:
            raise CardLoadError(path, f"{path}: ontology repeats slot observation field {dimension.slot_field!r}")
        if dimension.slot_field in {"label", "order"}:
            raise CardLoadError(
                path,
                f"{path}: ontology observation field {dimension.slot_field!r} conflicts with a technical slot field",
            )
        if dimension.value_type not in IMPLEMENTED_EFFECT_MATCH_VALUE_HANDLERS:
            raise CardLoadError(
                path,
                f"{path}: ontology effect-match value type {dimension.value_type!r} has no scalar handler",
            )
        keys.add(dimension.key)
        fields.add(dimension.slot_field)
    return dimensions


def _scalar_observation(
    raw: object,
    dimension: RuntimeEffectMatchDimension,
    runtime: RuntimeProgram,
    path: Path,
    slot_id: str,
) -> str | bool:
    handler = IMPLEMENTED_EFFECT_MATCH_VALUE_HANDLERS[dimension.value_type]
    if handler == "boolean":
        if not isinstance(raw, bool):
            raise CardLoadError(
                path,
                f"{path}: slot {slot_id!r} observation field {dimension.slot_field!r} must be boolean",
            )
        return raw
    if handler == "capability_values":
        if not isinstance(raw, str) or not raw:
            raise CardLoadError(
                path,
                f"{path}: slot {slot_id!r} observation field {dimension.slot_field!r} must be a non-empty string",
            )
        if raw not in runtime.slot_near_values:
            raise CardLoadError(
                path,
                f"{path}: slot {slot_id!r} observation field {dimension.slot_field!r} has unsupported value {raw!r}",
            )
        return raw
    raise CardLoadError(
        path,
        f"{path}: ontology effect-match value handler {handler!r} is not supported",
    )


def load_pillboxes(path: Path, bundle: OntologyBundle | RuntimeProgram) -> dict[str, Pillbox]:
    """Load pillboxes.yaml using the verified authored effect-match projection.

    Technical fields (identity, labels, ordering, and joined pillbox metadata)
    are stable runtime structure.  Every scheduling observation is instead
    selected and typed from ``effect_match_dimensions`` in the compiled
    ontology; malformed input raises ``CardLoadError`` rather than defaulting.
    """
    runtime = _runtime(bundle)
    dimensions = _observation_dimensions(path, runtime)
    data = load_card_mapping(path, "pillboxes")
    if not data:
        raise CardLoadError(path, f"{path}: pillboxes must contain at least one pillbox")
    if isinstance(bundle, OntologyBundle):
        errors = schema_errors(data, "pillboxes", path, bundle)
        if errors:
            raise CardLoadError(path, errors[0])
    expected_slot_fields = {"label", "order", *(dimension.slot_field for dimension in dimensions)}
    context = _PillboxLoadContext(path, expected_slot_fields, dimensions, runtime)
    return {
        pillbox_name: _load_pillbox(context, pillbox_name, pillbox)
        for pillbox_name, pillbox in sorted(data.items(), key=lambda item: str(item[0]))
    }


def _load_pillbox(
    context: _PillboxLoadContext,
    pillbox_name: object,
    raw_pillbox: object,
) -> Pillbox:
    path = context.path
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
    slot_context = _SlotLoadContext(
        path, pillbox_name, pillbox_label, stack, context.expected_fields, context.dimensions, context.runtime
    )
    slots = [
        _load_slot(slot_context, slot_id, raw_slot)
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
    unknown = set(slot) - context.expected_fields
    if unknown:
        raise CardLoadError(
            path, f"{path}: slot {slot_id!r} has unknown fields: {', '.join(sorted(map(str, unknown)))}"
        )
    missing = context.expected_fields - set(slot)
    if missing:
        raise CardLoadError(path, f"{path}: slot {slot_id!r} missing required fields: {', '.join(sorted(missing))}")
    label = slot["label"]
    order = slot["order"]
    if not isinstance(label, str) or not label.strip():
        raise CardLoadError(path, f"{path}: slot {slot_id!r} requires a non-empty label")
    if isinstance(order, bool) or not isinstance(order, int) or order < 1:
        raise CardLoadError(path, f"{path}: slot {slot_id!r} order must be a positive integer")
    observations = tuple(
        SlotObservation(
            dimension.key,
            _scalar_observation(slot[dimension.slot_field], dimension, context.runtime, path, slot_id),
        )
        for dimension in context.dimensions
    )
    return Slot(
        slot_id,
        label,
        order,
        observations,
        context.pillbox_name,
        context.pillbox_label,
        context.stack,
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
    """Validate ontology capability-backed scalar observations generically."""
    runtime = _runtime(bundle)
    dimensions = _observation_dimensions(slots_path, runtime)
    errors: list[str] = []
    for pillbox_name, pillbox in pillboxes.items():
        for slot_id, slot in pillbox.slots.items():
            observations = {item.key: item.value for item in slot.observations}
            if len(observations) != len(slot.observations):
                errors.append(f"{slots_path}: pillbox '{pillbox_name}' slot '{slot_id}' has duplicate observation keys")
                continue
            for dimension in dimensions:
                value = observations.get(dimension.key)
                handler = IMPLEMENTED_EFFECT_MATCH_VALUE_HANDLERS[dimension.value_type]
                if handler == "capability_values" and value not in runtime.slot_near_values:
                    errors.append(
                        f"{slots_path}: pillbox '{pillbox_name}' slot '{slot_id}' has invalid "
                        f"{dimension.key} {value!r}; expected one of {sorted(runtime.slot_near_values)!r}"
                    )
    return errors
