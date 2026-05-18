"""Branch-and-bound plan-search invariants."""

from __future__ import annotations

from planner.contracts import Slot, Substance
from planner.engine._plan_search import run_plan_search


def test_plan_search_uses_item_sequence_as_final_tie_breaker() -> None:
    slots = {
        "morning": _slot("morning", 1),
        "evening": _slot("evening", 2),
    }
    feasible_slots: dict[str, list[tuple[str, int, list[str]]]] = {
        "item_b": [("morning", 0, []), ("evening", 0, [])],
        "item_a": [("morning", 0, []), ("evening", 0, [])],
    }

    assignment, metrics = run_plan_search(
        slots=slots,
        items_by_scheduling_priority=["item_b", "item_a"],
        item_id_sequence=["item_a", "item_b"],
        item_traits={"item_a": set(), "item_b": set()},
        item_stacks={"item_a": "daily", "item_b": "daily"},
        feasible_slots_by_item=feasible_slots,
        remaining_score_upper_bound=[0, 0, 0],
        prefer_pairs=set(),
        active_components={"item_a": ["sub_a"], "item_b": ["sub_b"]},
        substances=_substances(),
        trait_defs={},
        global_relations=[],
        competes_pairs=set(),
    )

    assert metrics is not None
    assert assignment == {"item_a": "morning", "item_b": "evening"}


def test_plan_search_returns_none_when_global_competes_blocks_all_assignments() -> None:
    slots = {"morning": _slot("morning", 1)}
    feasible_slots: dict[str, list[tuple[str, int, list[str]]]] = {
        "item_a": [("morning", 0, [])],
        "item_b": [("morning", 0, [])],
    }
    competes_pairs = {frozenset({"sub_a", "sub_b"})}

    assignment, metrics = run_plan_search(
        slots=slots,
        items_by_scheduling_priority=["item_a", "item_b"],
        item_id_sequence=["item_a", "item_b"],
        item_traits={"item_a": set(), "item_b": set()},
        item_stacks={"item_a": "daily", "item_b": "daily"},
        feasible_slots_by_item=feasible_slots,
        remaining_score_upper_bound=[0, 0, 0],
        prefer_pairs=set(),
        active_components={"item_a": ["sub_a"], "item_b": ["sub_b"]},
        substances=_substances(),
        trait_defs={},
        global_relations=[],
        competes_pairs=competes_pairs,
    )

    assert assignment is None
    assert metrics is None


def _slot(slot_id: str, order: int) -> Slot:
    return Slot(
        slot_id=slot_id,
        label=slot_id.title(),
        order=order,
        near="wake",
        food=False,
        pillbox="daily",
        pillbox_label="Daily",
        stack="daily",
    )


def _substances() -> dict[str, Substance]:
    return {
        "sub_a": Substance(id="sub_a", name="A"),
        "sub_b": Substance(id="sub_b", name="B"),
    }
