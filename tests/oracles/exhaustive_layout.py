"""Small independent Cartesian oracle for canonical layouts.

This module intentionally does not import the production optimizer or any of
its private helpers.  It is bounded by the caller's fixture size and exists to
test the observable objective, rather than the production search strategy.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import product

from planner.contracts import Slot
from planner.ontology.canonical_inference import NormalizedUnaryPressure, UnaryPressureIdentity


@dataclass(frozen=True, slots=True)
class OracleResult:
    status: str
    layout: dict[str, str] | None
    pressure_count: int | None
    squared_load: int | None
    assignment_key: tuple[tuple[int, str], ...] | None


def exhaustive_layout(  # noqa: C901
    item_domains: Mapping[str, str],
    slots: Mapping[str, Slot],
    pressures: Sequence[UnaryPressureIdentity | NormalizedUnaryPressure],
    *,
    max_layouts: int = 100_000,
) -> OracleResult:
    """Enumerate every assignment and select the exact canonical winner."""

    if isinstance(max_layouts, bool) or max_layouts < 1:
        return OracleResult("Indeterminate", None, None, None, None)
    items = tuple(sorted(item_domains))
    slots_by_domain: dict[str, tuple[Slot, ...]] = {}
    for domain in set(item_domains.values()):
        slots_by_domain[domain] = tuple(
            sorted((slot for slot in slots.values() if slot.stack == domain), key=lambda row: (row.order, row.slot_id))
        )
        if not slots_by_domain[domain]:
            return OracleResult("Indeterminate", None, None, None, None)

    identities = tuple({
        pressure.identity if isinstance(pressure, NormalizedUnaryPressure) else pressure for pressure in pressures
    })
    grouped: dict[tuple[str, str], set[str]] = {}
    for identity in identities:
        grouped.setdefault((identity.item_id, identity.dimension), set()).add(identity.value)
    if any(len(values) > 1 for values in grouped.values()):
        return OracleResult("Indeterminate", None, None, None, None)
    layout_count = 1
    for item in items:
        layout_count *= len(slots_by_domain[item_domains[item]])
        if layout_count > max_layouts:
            return OracleResult("Indeterminate", None, None, None, None)
    item_indexes = {item: index for index, item in enumerate(items)}
    best: tuple[int, int, tuple[tuple[int, str], ...], dict[str, str]] | None = None
    for choices in product(*(slots_by_domain[item_domains[item]] for item in items)):
        layout = {item: slot.slot_id for item, slot in zip(items, choices, strict=True)}
        pressure_count = sum(
            1
            for pressure in identities
            if choices[item_indexes[pressure.item_id]].anchors.get(pressure.dimension) == pressure.value
        )
        loads: dict[str, int] = {}
        for slot_id in layout.values():
            loads[slot_id] = loads.get(slot_id, 0) + 1
        squared_load = sum(load * load for load in loads.values())
        assignment_key = tuple((layout_item.order, layout_item.slot_id) for layout_item in choices)
        candidate = (pressure_count, squared_load, assignment_key, layout)
        if best is None:
            best = candidate
            continue
        # Pressure count is maximized; the two remaining stages are minimized.
        if _is_better(pressure_count, squared_load, assignment_key, best):
            best = candidate
    if best is None:
        return OracleResult("Indeterminate", None, None, None, None)
    return OracleResult("Optimal", best[3], best[0], best[1], best[2])


def _is_better(
    pressure_count: int,
    squared_load: int,
    assignment_key: tuple[tuple[int, str], ...],
    best: tuple[int, int, tuple[tuple[int, str], ...], dict[str, str]],
) -> bool:
    if pressure_count != best[0]:
        return pressure_count > best[0]
    if squared_load != best[1]:
        return squared_load < best[1]
    return assignment_key < best[2]


__all__ = ["OracleResult", "exhaustive_layout"]
