"""Cluster 3 V-right tests for the isolated exact optimizer kernel."""

from __future__ import annotations

import random

import pytest
from planner.contracts import Slot
from planner.engine._canonical_optimizer import (
    CanonicalOptimizerInput,
    Indeterminate,
    Optimal,
    optimize_canonical_layout,
)
from planner.ontology.canonical_inference import UnaryPressureIdentity

from tests.oracles.exhaustive_layout import exhaustive_layout


def _slot(  # noqa: PLR0913
    slot_id: str,
    order: int,
    domain: str = "daily",
    *,
    meal: str | None = None,
    circadian: str | None = None,
    exercise: str | None = None,
) -> Slot:
    return Slot(slot_id, slot_id, order, domain, domain, domain, meal, circadian, exercise)


def test_pressure_maximum_precedes_balance_and_keeps_only_maximum_slots() -> None:
    slots = {
        slot.slot_id: slot
        for slot in (
            _slot("meal", 1, meal="with_food"),
            _slot("wake", 2, circadian="wake"),
            _slot("both", 3, meal="with_food", circadian="wake"),
        )
    }
    result = optimize_canonical_layout(
        {"item": "daily"},
        slots,
        (
            UnaryPressureIdentity("item", "meal_context", "with_food"),
            UnaryPressureIdentity("item", "circadian_anchor", "wake"),
        ),
    )
    assert isinstance(result, Optimal)
    assert result.assignments == {"item": "both"}
    assert result.objective == (result.objective.__class__(2, 1, ((3, "both"),)))


def test_exact_squared_load_balance_is_unbounded_and_stable_by_item_id() -> None:
    slots = {slot.slot_id: slot for slot in (_slot("early", 1), _slot("late", 2))}
    result = optimize_canonical_layout({"d": "daily", "c": "daily", "b": "daily", "a": "daily"}, slots, ())
    assert isinstance(result, Optimal)
    assert result.assignments == {"a": "early", "b": "early", "c": "late", "d": "late"}
    assert result.objective.satisfied_pressures == 0
    assert result.objective.squared_load == 8
    assert result.objective.assignment_key == ((1, "early"), (1, "early"), (2, "late"), (2, "late"))


def test_tie_break_uses_slot_id_after_order_and_is_domain_independent() -> None:
    slots = {
        slot.slot_id: slot
        for slot in (
            _slot("z", 1, "one"),
            _slot("a", 1, "one"),
            _slot("other", 5, "two"),
        )
    }
    result = optimize_canonical_layout(
        CanonicalOptimizerInput({"item-z": "one", "item-a": "one", "item-b": "two"}, slots, ())
    )
    assert isinstance(result, Optimal)
    assert result.assignments == {"item-a": "a", "item-b": "other", "item-z": "z"}


def test_none_anchor_never_satisfies_a_pressure() -> None:
    slots = {slot.slot_id: slot for slot in (_slot("unspecified", 1), _slot("wake", 2, circadian="wake"))}
    result = optimize_canonical_layout(
        {"item": "daily"}, slots, (UnaryPressureIdentity("item", "circadian_anchor", "wake"),)
    )
    assert isinstance(result, Optimal)
    assert result.assignments == {"item": "wake"}


def test_conflicts_and_invalid_inputs_are_layout_free_indeterminate() -> None:
    slots = {"slot": _slot("slot", 1)}
    result = optimize_canonical_layout(
        {"item": "daily"},
        slots,
        (
            UnaryPressureIdentity("item", "meal_context", "with_food"),
            UnaryPressureIdentity("item", "meal_context", "without_food"),
        ),
    )
    assert isinstance(result, Indeterminate)
    assert result.diagnostic.code == "contradiction"
    assert isinstance(
        optimize_canonical_layout({}, slots, (UnaryPressureIdentity("item", "meal_context", "with_food"),)),
        Indeterminate,
    )


def test_empty_item_selection_is_an_exact_empty_optimal_layout() -> None:
    result = optimize_canonical_layout({}, {}, ())
    assert isinstance(result, Optimal)
    assert result.assignments == {}
    assert result.objective.satisfied_pressures == 0
    assert result.objective.squared_load == 0
    assert result.objective.assignment_key == ()


def test_deadline_interruption_and_state_bound_never_publish_incumbents() -> None:
    slots = {slot.slot_id: slot for slot in (_slot("a", 1), _slot("b", 2))}
    expired = optimize_canonical_layout({"item": "daily"}, slots, (), deadline_monotonic_ns=0, monotonic_ns=lambda: 1)
    interrupted = optimize_canonical_layout({"item": "daily"}, slots, (), interruption=lambda: True)
    bounded = optimize_canonical_layout({"a": "daily", "b": "daily", "c": "daily"}, slots, (), state_bound=1)
    for result in (expired, interrupted, bounded):
        assert isinstance(result, Indeterminate)

    assert expired.diagnostic.code == "timeout"
    assert interrupted.diagnostic.code == "interrupted"
    assert bounded.diagnostic.code == "resource_exhausted"


@pytest.mark.parametrize(
    ("state_bound", "deadline_monotonic_ns", "message"),
    [
        (True, None, "invalid state bound"),
        (None, True, "invalid deadline"),
    ],
)
def test_invalid_proof_limits_fail_closed(
    state_bound: int | None, deadline_monotonic_ns: int | None, message: str
) -> None:
    result = optimize_canonical_layout(
        {"item": "daily"},
        {"slot": _slot("slot", 1)},
        (),
        state_bound=state_bound,
        deadline_monotonic_ns=deadline_monotonic_ns,
    )

    assert isinstance(result, Indeterminate)
    assert result.diagnostic.code == "invalid_input"
    assert result.diagnostic.message == message


def test_abort_during_final_expansion_or_pre_return_cannot_publish() -> None:
    slots = {slot.slot_id: slot for slot in (_slot("a", 1), _slot("b", 2))}
    calls = 0

    def interrupt_after_final_expansion() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 8

    result = optimize_canonical_layout(
        {"a": "daily", "b": "daily"},
        slots,
        (),
        interruption=interrupt_after_final_expansion,
    )
    assert isinstance(result, Indeterminate)

    clock_calls = 0

    def advancing_clock() -> int:
        nonlocal clock_calls
        clock_calls += 1
        return clock_calls

    result = optimize_canonical_layout(
        {"item": "daily"},
        slots,
        (),
        deadline_monotonic_ns=9,
        monotonic_ns=advancing_clock,
    )
    assert isinstance(result, Indeterminate)


def test_duplicate_pressure_input_is_equivalent_to_one_identity() -> None:
    slots = {slot.slot_id: slot for slot in (_slot("a", 1, meal="with_food"), _slot("b", 2))}
    pressure = UnaryPressureIdentity("item", "meal_context", "with_food")
    one = optimize_canonical_layout({"item": "daily"}, slots, (pressure,))
    duplicate = optimize_canonical_layout({"item": "daily"}, slots, (pressure, pressure))
    assert isinstance(duplicate, Optimal)
    assert isinstance(one, Optimal)
    assert duplicate.assignments == one.assignments
    assert duplicate.objective == one.objective
    oracle_one = exhaustive_layout({"item": "daily"}, slots, (pressure,))
    oracle_duplicate = exhaustive_layout({"item": "daily"}, slots, (pressure, pressure))
    assert oracle_duplicate == oracle_one


def test_bounded_randomized_results_match_independent_cartesian_oracle() -> None:
    rng = random.Random(20260830)
    anchor_values = {
        "meal_context": (None, "with_food", "without_food"),
        "circadian_anchor": (None, "wake", "sleep"),
        "exercise_anchor": (None, "before", "after"),
    }
    for _ in range(80):
        item_count = rng.randint(1, 6)
        slot_count = rng.randint(1, 3)
        item_domains = {f"item-{index}": "daily" for index in range(item_count)}
        slots = {
            f"slot-{index}": _slot(
                f"slot-{index}",
                index,
                meal=rng.choice(anchor_values["meal_context"]),
                circadian=rng.choice(anchor_values["circadian_anchor"]),
                exercise=rng.choice(anchor_values["exercise_anchor"]),
            )
            for index in range(slot_count)
        }
        pressures = tuple(
            UnaryPressureIdentity(
                item_id,
                dimension,
                rng.choice(values[1:]),
            )
            for item_id in item_domains
            for dimension, values in anchor_values.items()
            if rng.random() < 0.35
        )
        actual = optimize_canonical_layout(item_domains, slots, pressures)
        expected = exhaustive_layout(item_domains, slots, pressures)
        if expected.status == "Optimal":
            assert isinstance(actual, Optimal)
            assert actual.assignments == expected.layout
            assert actual.objective.satisfied_pressures == expected.pressure_count
            assert actual.objective.squared_load == expected.squared_load
            assert actual.objective.assignment_key == expected.assignment_key
        else:
            assert isinstance(actual, Indeterminate)
