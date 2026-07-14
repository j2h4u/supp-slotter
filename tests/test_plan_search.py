"""Branch-and-bound plan-search invariants."""

from __future__ import annotations

from planner.contracts import RelationSelector, SchedulingConstraint, Slot, Substance
from planner.engine._plan_search import PlanSearchInput, _PlanSearch, run_plan_search


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
        PlanSearchInput(
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
            scheduling_constraints=(),
        )
    )

    assert metrics is not None
    assert assignment == {"item_a": "morning", "item_b": "evening"}


def test_plan_search_returns_none_when_hard_constraint_blocks_all_assignments() -> None:
    slots = {"morning": _slot("morning", 1)}
    feasible_slots: dict[str, list[tuple[str, int, list[str]]]] = {
        "item_a": [("morning", 0, [])],
        "item_b": [("morning", 0, [])],
    }
    constraints = (
        SchedulingConstraint(
            id="sc_test",
            source_selector=RelationSelector(entity_id="sub_a"),
            target_selector=RelationSelector(entity_id="sub_b"),
            effect="separate_slots",
            enforcement="block",
            status="approved",
            evidence=("https://example.test/evidence",),
        ),
    )

    assignment, metrics = run_plan_search(
        PlanSearchInput(
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
            scheduling_constraints=constraints,
        )
    )

    assert assignment is None
    assert metrics is None


def test_advisory_penalty_prefers_separate_slot() -> None:
    constraints = (_advisory("advisory", "sub_a", "sub_b"),)
    assignment, metrics = run_plan_search(
        _search_input(
            {"item_a": [("morning", 0, []), ("evening", 0, [])], "item_b": [("morning", 0, []), ("evening", 0, [])]},
            constraints,
        )
    )
    assert metrics is not None and metrics[1] == 0
    assert assignment in ({"item_a": "morning", "item_b": "evening"}, {"item_a": "evening", "item_b": "morning"})


def test_review_enforcement_does_not_change_search_layout_or_score() -> None:
    feasible: dict[str, list[tuple[str, int, list[str]]]] = {
        "item_a": [("morning", 0, []), ("evening", 0, [])],
        "item_b": [("morning", 0, []), ("evening", 0, [])],
    }
    review = SchedulingConstraint(
        id="review_only",
        source_selector=RelationSelector(entity_id="sub_a"),
        target_selector=RelationSelector(entity_id="sub_b"),
        effect="separate_slots",
        enforcement="review",
        status="review_pending",
        evidence=("https://example.test/evidence",),
    )

    baseline = run_plan_search(_search_input(feasible, ()))
    with_review = run_plan_search(_search_input(feasible, (review,)))

    assert with_review == baseline


def test_advisory_penalty_tie_keeps_original_slot_order() -> None:
    constraints = (_advisory("advisory", "sub_a", "sub_b"),)
    search = _PlanSearch(
        _search_input(
            {"item_a": [("morning", 0, []), ("evening", 0, [])], "item_b": [("morning", 1, []), ("evening", 0, [])]},
            constraints,
        )
    )
    candidates = search.ordered_candidates("item_b", {"morning": ["item_a"]})
    assert [(name, score) for name, score, _reasons, _ids in candidates] == [("morning", 0), ("evening", 0)]


def test_base_score_four_stays_ahead_of_two_advisory_penalties() -> None:
    rules = (_advisory("advisory_a", "sub_a", "sub_b"), _advisory("advisory_b", "sub_a", "sub_b"))
    search = _PlanSearch(
        _search_input(
            {"item_a": [("morning", 0, []), ("evening", 0, [])], "item_b": [("morning", 4, []), ("evening", 0, [])]},
            rules,
        )
    )
    candidates = search.ordered_candidates("item_b", {"morning": ["item_a"]})
    assert candidates[0][1] == 2
    assert candidates[1][1] == 0


def _advisory(rule_id: str, source: str, target: str) -> SchedulingConstraint:
    return SchedulingConstraint(
        id=rule_id,
        source_selector=RelationSelector(entity_id=source),
        target_selector=RelationSelector(entity_id=target),
        effect="separate_slots",
        enforcement="advisory",
        status="approved",
        evidence=("https://example.test/evidence",),
    )


def _search_input(
    feasible_slots: dict[str, list[tuple[str, int, list[str]]]],
    constraints: tuple[SchedulingConstraint, ...],
) -> PlanSearchInput:
    return PlanSearchInput(
        slots={"morning": _slot("morning", 1), "evening": _slot("evening", 2)},
        items_by_scheduling_priority=["item_a", "item_b"],
        item_id_sequence=["item_a", "item_b"],
        item_traits={"item_a": set(), "item_b": set()},
        item_stacks={"item_a": "daily", "item_b": "daily"},
        feasible_slots_by_item=feasible_slots,
        remaining_score_upper_bound=[1, 1, 0],
        prefer_pairs=set(),
        active_components={"item_a": ["sub_a"], "item_b": ["sub_b"]},
        substances=_substances(),
        scheduling_constraints=constraints,
    )


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
