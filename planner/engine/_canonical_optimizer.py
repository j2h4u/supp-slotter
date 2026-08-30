"""Exact optimizer for canonical pressure/layout inputs.

The optimizer consumes only normalized unary pressure identities and the
logical slot topology.  It intentionally has no knowledge of authored
schedule assertions, preferences, weights, or presentation text.

For each scheduling domain, the finite dynamic program retains one
lexicographically smallest assignment for every reachable slot-load vector.
Every item first discards slots that satisfy fewer pressures than its own
maximum.  The remaining states are compared by exact integer squared load and
then by the stable ``(slot.order, slot_id)`` assignment key.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from planner.canonical_optimizer_result import (
    CanonicalObjective,
    CanonicalOptimizerResult,
    Diagnostic,
    DiagnosticCode,
    Indeterminate,
    Optimal,
)
from planner.contracts import Slot
from planner.ontology.canonical_inference import NormalizedUnaryPressure, UnaryPressureIdentity

Pressure = UnaryPressureIdentity | NormalizedUnaryPressure
InterruptCheck = Callable[[], bool]
MonotonicNs = Callable[[], int]

_ANCHOR_VALUES: dict[str, frozenset[str]] = {
    "meal_context": frozenset({"with_food", "without_food"}),
    "circadian_anchor": frozenset({"wake", "sleep"}),
    "exercise_anchor": frozenset({"before", "after"}),
}


@dataclass(frozen=True, slots=True)
class CanonicalOptimizerInput:
    """Closed input boundary for exact canonical optimization.

    ``item_domains`` maps scenario item IDs to their independent scheduling
    domain (the current topology uses ``Slot.stack`` for that domain).  Slots
    are keyed by their stable IDs.  Pressures may be either normalized proof
    nodes or their identities; identities are all that affect optimization.
    ``deadline_monotonic_ns`` is an absolute integer deadline in the same clock
    domain as ``monotonic_ns``.  The clock is injectable so deadline and
    interruption boundaries can be tested without sleeping.
    """

    item_domains: Mapping[str, str]
    slots: Mapping[str, Slot]
    pressures: Sequence[Pressure]
    deadline_monotonic_ns: int | None = None
    interruption: InterruptCheck | None = None
    state_bound: int | None = None
    monotonic_ns: MonotonicNs = time.monotonic_ns


@dataclass(frozen=True, slots=True)
class _PreparedItem:
    item_id: str
    domain: str
    candidate_slots: tuple[str, ...]
    maximum_pressure_count: int


@dataclass(frozen=True, slots=True)
class _PreparedInput:
    items: tuple[_PreparedItem, ...]
    slots_by_domain: dict[str, tuple[Slot, ...]]
    pressure_count: int
    pressures: tuple[UnaryPressureIdentity, ...]


class _IndeterminateError(Exception):
    """Internal fail-closed signal carrying a user-facing diagnostic."""

    def __init__(self, code: DiagnosticCode, message: str) -> None:
        super().__init__(message)
        self.diagnostic: Diagnostic = Diagnostic(code, message)


def optimize_canonical_layout(  # noqa: PLR0913
    item_domains: Mapping[str, str] | CanonicalOptimizerInput,
    slots: Mapping[str, Slot] | None = None,
    pressures: Sequence[Pressure] | None = None,
    *,
    deadline_monotonic_ns: int | None = None,
    interruption: InterruptCheck | None = None,
    state_bound: int | None = None,
    monotonic_ns: MonotonicNs = time.monotonic_ns,
) -> CanonicalOptimizerResult:
    """Prove and return the exact canonical layout.

    The first positional argument may be a :class:`CanonicalOptimizerInput`,
    in which case the remaining arguments must be omitted.  Invalid inputs,
    conflicts, interruption, deadline expiry, resource bounds, allocation
    failure, and proof failures all return ``Indeterminate`` with no layout.
    """

    try:
        optimizer_input = _coerce_input(
            item_domains,
            slots,
            pressures,
            deadline_monotonic_ns=deadline_monotonic_ns,
            interruption=interruption,
            state_bound=state_bound,
            monotonic_ns=monotonic_ns,
        )
        prepared = _prepare(optimizer_input)
        _check_abort(optimizer_input)
        assignment: dict[str, str] = {}
        squared_load = 0
        proof_parts: list[str] = []
        for domain in sorted(set(optimizer_input.item_domains.values())):
            domain_items = tuple(item for item in prepared.items if item.domain == domain)
            if not domain_items:
                continue
            domain_assignment, domain_squared, states = _solve_domain(
                domain_items,
                prepared.slots_by_domain[domain],
                optimizer_input,
            )
            assignment.update(domain_assignment)
            squared_load += domain_squared
            proof_parts.append(f"domain={domain!r} reachable_load_vectors={states}")

        _check_abort(optimizer_input)
        if set(assignment) != set(optimizer_input.item_domains):
            raise _IndeterminateError(
                "proof_failed", "proof_incomplete: not every scenario item received an assignment"
            )
        assignment_key = tuple(
            (prepared_slot.order, slot_id)
            for item_id, slot_id in sorted(assignment.items())
            for prepared_slot in (optimizer_input.slots[slot_id],)
        )
        objective = CanonicalObjective(prepared.pressure_count, squared_load, assignment_key)
        _check_abort(optimizer_input)
        _verify_solution(optimizer_input, prepared, assignment, objective)
        _check_abort(optimizer_input)
        result = Optimal(assignment, objective, tuple(proof_parts))
        _check_abort(optimizer_input)
        return result
    except _IndeterminateError as error:
        return Indeterminate(error.diagnostic)
    except MemoryError:
        return Indeterminate(Diagnostic("resource_exhausted", "optimization resource exhausted"))
    except KeyboardInterrupt:
        return Indeterminate(Diagnostic("interrupted", "optimization interrupted"))
    except Exception as error:  # noqa: BLE001
        # The publication boundary is deliberately closed.  An unexpected
        # malformed input or proof error must never leak an incumbent layout.
        return Indeterminate(Diagnostic("infrastructure_failed", f"optimization failed closed: {error}"))


def _coerce_input(  # noqa: PLR0913
    item_domains: Mapping[str, str] | CanonicalOptimizerInput,
    slots: Mapping[str, Slot] | None,
    pressures: Sequence[Pressure] | None,
    *,
    deadline_monotonic_ns: int | None,
    interruption: InterruptCheck | None,
    state_bound: int | None,
    monotonic_ns: MonotonicNs,
) -> CanonicalOptimizerInput:
    if isinstance(item_domains, CanonicalOptimizerInput):
        if (
            slots is not None
            or pressures is not None
            or any(value is not None for value in (deadline_monotonic_ns, interruption, state_bound))
        ):
            raise _IndeterminateError("invalid_input", "optimizer input object cannot be combined with keyword inputs")
        return item_domains
    if slots is None or pressures is None:
        raise _IndeterminateError("invalid_input", "item_domains, slots, and pressures are required")
    return CanonicalOptimizerInput(
        item_domains,
        slots,
        pressures,
        deadline_monotonic_ns=deadline_monotonic_ns,
        interruption=interruption,
        state_bound=state_bound,
        monotonic_ns=monotonic_ns,
    )


def _prepare(optimizer_input: CanonicalOptimizerInput) -> _PreparedInput:
    _validate_run_limits(optimizer_input)
    domains = _validated_item_domains(optimizer_input.item_domains)
    slots_by_domain = _validated_slots_by_domain(optimizer_input.slots)
    pressures = _pressure_identities(optimizer_input.pressures, domains)
    items = _prepared_items(domains, slots_by_domain, pressures)
    return _PreparedInput(
        items,
        slots_by_domain,
        sum(item.maximum_pressure_count for item in items),
        pressures,
    )


def _validate_run_limits(optimizer_input: CanonicalOptimizerInput) -> None:
    if optimizer_input.state_bound is not None and (
        isinstance(optimizer_input.state_bound, bool) or optimizer_input.state_bound < 1
    ):
        raise _IndeterminateError("invalid_input", "invalid state bound")
    if optimizer_input.deadline_monotonic_ns is not None and (
        isinstance(optimizer_input.deadline_monotonic_ns, bool)
        or not isinstance(optimizer_input.deadline_monotonic_ns, int)
        or optimizer_input.deadline_monotonic_ns < 0
    ):
        raise _IndeterminateError("invalid_input", "invalid deadline")
    if not isinstance(optimizer_input.item_domains, Mapping):
        raise _IndeterminateError("invalid_input", "item_domains must be a mapping")
    if not isinstance(optimizer_input.slots, Mapping):
        raise _IndeterminateError("invalid_input", "slots must be a mapping")


def _validated_item_domains(item_domains: Mapping[str, str]) -> dict[str, str]:
    domains: dict[str, str] = {}
    for item_id, domain in item_domains.items():
        if not isinstance(item_id, str) or not item_id or not isinstance(domain, str) or not domain:
            raise _IndeterminateError("invalid_input", "item and domain IDs must be non-empty strings")
        if item_id in domains:
            raise _IndeterminateError("invalid_input", f"duplicate item ID {item_id!r}")
        domains[item_id] = domain
    return domains


def _validated_slots_by_domain(slots: Mapping[str, Slot]) -> dict[str, tuple[Slot, ...]]:
    slots_by_domain: dict[str, list[Slot]] = {}
    for slot_key, slot in slots.items():
        if not isinstance(slot_key, str) or not slot_key or not isinstance(slot, Slot):
            raise _IndeterminateError("invalid_input", "slots must be keyed by non-empty IDs and contain Slot values")
        if slot.slot_id != slot_key or not slot.slot_id or not isinstance(slot.stack, str) or not slot.stack:
            raise _IndeterminateError("invalid_input", f"slot identity/domain is invalid for {slot_key!r}")
        if isinstance(slot.order, bool) or not isinstance(slot.order, int):
            raise _IndeterminateError("invalid_input", f"slot order is invalid for {slot_key!r}")
        for dimension, values in _ANCHOR_VALUES.items():
            value = cast(str | None, getattr(slot, dimension))
            if value is not None and value not in values:
                raise _IndeterminateError("invalid_input", f"slot {slot_key!r} has invalid {dimension} value")
        slots_by_domain.setdefault(slot.stack, []).append(slot)
    return {
        domain: tuple(sorted(rows, key=lambda row: (row.order, row.slot_id)))
        for domain, rows in slots_by_domain.items()
    }


def _prepared_items(
    domains: Mapping[str, str],
    slots_by_domain: Mapping[str, Sequence[Slot]],
    pressures: Sequence[UnaryPressureIdentity],
) -> tuple[_PreparedItem, ...]:
    pressure_by_item: dict[str, list[UnaryPressureIdentity]] = {}
    for pressure in pressures:
        pressure_by_item.setdefault(pressure.item_id, []).append(pressure)
    prepared_items: list[_PreparedItem] = []
    for item_id, domain in sorted(domains.items()):
        domain_slots = slots_by_domain.get(domain)
        if not domain_slots:
            raise _IndeterminateError("invalid_input", f"item {item_id!r} has no slots in domain {domain!r}")
        item_pressures = pressure_by_item.get(item_id, [])
        scores = {slot.slot_id: _satisfied_count(slot, item_pressures) for slot in domain_slots}
        maximum = max(scores.values())
        prepared_items.append(
            _PreparedItem(
                item_id,
                domain,
                tuple(slot_id for slot_id, score in scores.items() if score == maximum),
                maximum,
            )
        )
    return tuple(prepared_items)


def _pressure_identities(
    pressures: Sequence[Pressure], item_domains: Mapping[str, str]
) -> tuple[UnaryPressureIdentity, ...]:
    if not isinstance(pressures, Sequence):
        raise _IndeterminateError("invalid_input", "pressures must be a sequence")
    identities: set[UnaryPressureIdentity] = set()
    for pressure in pressures:
        identity: UnaryPressureIdentity
        if isinstance(pressure, UnaryPressureIdentity):
            identity = pressure
        elif isinstance(pressure, NormalizedUnaryPressure):
            identity = pressure.identity
        else:
            raise _IndeterminateError("invalid_input", "pressures must contain normalized pressure identities")
        _validate_pressure_identity(identity, item_domains)
        identities.add(identity)
    grouped: dict[tuple[str, str], set[str]] = {}
    for identity in identities:
        grouped.setdefault((identity.item_id, identity.dimension), set()).add(identity.value)
    if any(len(values) > 1 for values in grouped.values()):
        raise _IndeterminateError("contradiction", "same-dimension pressure conflict")
    return tuple(sorted(identities, key=lambda row: (row.item_id, row.dimension, row.value)))


def _satisfied_count(slot: Slot, pressures: Sequence[UnaryPressureIdentity]) -> int:
    return sum(1 for pressure in pressures if getattr(slot, pressure.dimension) == pressure.value)


def _solve_domain(
    items: Sequence[_PreparedItem],
    slots: Sequence[Slot],
    optimizer_input: CanonicalOptimizerInput,
) -> tuple[dict[str, str], int, int]:
    slot_ids = tuple(slot.slot_id for slot in slots)
    slot_keys = tuple((slot.order, slot.slot_id) for slot in slots)
    # state -> the lexicographically smallest slot-key prefix reaching it
    states: dict[tuple[int, ...], tuple[int, ...]] = {(0,) * len(slots): ()}
    for item in items:
        _check_abort(optimizer_input)
        next_states: dict[tuple[int, ...], tuple[int, ...]] = {}
        candidate_indexes = tuple(slot_ids.index(slot_id) for slot_id in item.candidate_slots)
        for loads, assignment_indexes in states.items():
            _check_abort(optimizer_input)
            for slot_index in candidate_indexes:
                _check_abort(optimizer_input)
                new_loads = list(loads)
                new_loads[slot_index] += 1
                loads_key = tuple(new_loads)
                new_assignment = (*assignment_indexes, slot_index)
                prior = next_states.get(loads_key)
                if prior is None or _assignment_key(new_assignment, slot_keys) < _assignment_key(prior, slot_keys):
                    next_states[loads_key] = new_assignment
                if optimizer_input.state_bound is not None and len(next_states) > optimizer_input.state_bound:
                    raise _IndeterminateError("resource_exhausted", "state bound exhausted")
        states = next_states
        if not states:
            raise _IndeterminateError("proof_failed", "proof failure: no reachable load vector")
    best_loads, best_assignment = min(
        states.items(),
        key=lambda row: (sum(load * load for load in row[0]), _assignment_key(row[1], slot_keys)),
    )
    assignment = {item.item_id: slot_ids[index] for item, index in zip(items, best_assignment, strict=True)}
    return assignment, sum(load * load for load in best_loads), len(states)


def _assignment_key(indexes: Sequence[int], slot_keys: Sequence[tuple[int, str]]) -> tuple[tuple[int, str], ...]:
    return tuple(slot_keys[index] for index in indexes)


def _verify_solution(
    optimizer_input: CanonicalOptimizerInput,
    prepared: _PreparedInput,
    assignment: Mapping[str, str],
    objective: CanonicalObjective,
) -> None:
    """Independently recompute every published objective component."""

    loads_by_domain = _assignment_loads(optimizer_input, assignment)
    if (
        _satisfied_pressure_count(optimizer_input.slots, assignment, prepared.pressures)
        != objective.satisfied_pressures
    ):
        raise _IndeterminateError("proof_failed", "proof_incomplete: pressure count mismatch")
    if _squared_load(loads_by_domain) != objective.squared_load:
        raise _IndeterminateError("proof_failed", "proof_incomplete: squared load mismatch")
    if _published_assignment_key(optimizer_input.slots, assignment) != objective.assignment_key:
        raise _IndeterminateError("proof_failed", "proof_incomplete: assignment key mismatch")


def _assignment_loads(
    optimizer_input: CanonicalOptimizerInput, assignment: Mapping[str, str]
) -> dict[str, dict[str, int]]:
    expected_items = set(optimizer_input.item_domains)
    if set(assignment) != expected_items:
        raise _IndeterminateError("proof_failed", "proof_incomplete: assignment item set mismatch")
    loads_by_domain: dict[str, dict[str, int]] = {}
    for item_id in sorted(expected_items):
        slot_id = assignment.get(item_id)
        domain = optimizer_input.item_domains[item_id]
        if (
            not isinstance(slot_id, str)
            or slot_id not in optimizer_input.slots
            or optimizer_input.slots[slot_id].stack != domain
        ):
            raise _IndeterminateError("proof_failed", "proof_incomplete: assignment domain mismatch")
        domain_loads = loads_by_domain.setdefault(domain, {})
        domain_loads[slot_id] = domain_loads.get(slot_id, 0) + 1
    return loads_by_domain


def _satisfied_pressure_count(
    slots: Mapping[str, Slot], assignment: Mapping[str, str], pressures: Sequence[UnaryPressureIdentity]
) -> int:
    return sum(
        getattr(slots[assignment[identity.item_id]], identity.dimension) == identity.value for identity in pressures
    )


def _squared_load(loads_by_domain: Mapping[str, Mapping[str, int]]) -> int:
    return sum(load * load for domain_loads in loads_by_domain.values() for load in domain_loads.values())


def _published_assignment_key(slots: Mapping[str, Slot], assignment: Mapping[str, str]) -> tuple[tuple[int, str], ...]:
    return tuple((slots[assignment[item_id]].order, assignment[item_id]) for item_id in sorted(assignment))


def _validate_pressure_identity(identity: UnaryPressureIdentity, item_domains: Mapping[str, str]) -> None:
    if not isinstance(identity.item_id, str) or not identity.item_id or identity.item_id not in item_domains:
        raise _IndeterminateError("invalid_input", "invalid or unselected pressure identity")
    if identity.dimension not in _ANCHOR_VALUES:
        raise _IndeterminateError("invalid_input", "invalid or unselected pressure identity")
    if not isinstance(identity.value, str) or identity.value not in _ANCHOR_VALUES[identity.dimension]:
        raise _IndeterminateError("invalid_input", "invalid or unselected pressure identity")


def _check_abort(optimizer_input: CanonicalOptimizerInput) -> None:
    if (
        optimizer_input.deadline_monotonic_ns is not None
        and optimizer_input.monotonic_ns() >= optimizer_input.deadline_monotonic_ns
    ):
        raise _IndeterminateError("timeout", "deadline expired")
    if optimizer_input.interruption is not None:
        try:
            interrupted = optimizer_input.interruption()
        except KeyboardInterrupt, MemoryError:
            raise
        except Exception as error:
            raise _IndeterminateError("infrastructure_failed", f"interruption check failed: {error}") from error
        if interrupted:
            raise _IndeterminateError("interrupted", "optimization interrupted")


__all__ = [
    "CanonicalObjective",
    "CanonicalOptimizerInput",
    "CanonicalOptimizerResult",
    "Diagnostic",
    "DiagnosticCode",
    "Indeterminate",
    "InterruptCheck",
    "MonotonicNs",
    "Optimal",
    "optimize_canonical_layout",
]
