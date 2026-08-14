"""Review-only knowledge must not become a scheduling input."""

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from tests.planner_fixture import PlannerFixtureInput, plan_in_temp_dir, write_minimal_planner_fixture


def _scheduled_slot(schedule: dict[str, object], product_name: str) -> str:
    pillboxes = schedule["pillboxes"]
    assert isinstance(pillboxes, dict)
    for pillbox in pillboxes.values():
        assert isinstance(pillbox, dict)
        slots = pillbox["slots"]
        assert isinstance(slots, dict)
        for slot_id, entry in cast(Mapping[str, object], slots).items():
            assert isinstance(entry, dict)
            products = cast(list[str], entry["products"])
            if product_name in products:
                return str(slot_id)
    raise AssertionError(f"product {product_name!r} was not scheduled")


def test_reviewer_only_knowledge_does_not_change_slot_assignment(tmp_path: Path) -> None:
    base = tmp_path / "base"
    reviewer = tmp_path / "reviewer"
    fixture = PlannerFixtureInput(
        stack_items={"product": {"stack": "daily"}, "active_product": {"stack": "daily"}},
        products={
            "product": [("component", ["intake:food_preferred"])],
            "active_product": [
                ("epa_component", ["risk:bleeding_med_interaction", "effect:platelet_aggregation_modulation"])
            ],
        },
        traits={
            "intake:food_preferred": {"label": "Food preferred", "description": "Fixture", "applies_when": "Fixture"},
            "risk:bleeding_med_interaction": {
                "label": "Bleeding medication interaction",
                "description": "Fixture",
                "applies_when": "Fixture",
            },
            "effect:platelet_aggregation_modulation": {
                "label": "Platelet aggregation modulation",
                "description": "Fixture",
                "applies_when": "Fixture",
            },
        },
    )
    write_minimal_planner_fixture(base, fixture)
    write_minimal_planner_fixture(
        reviewer,
        PlannerFixtureInput(
            stack_items=fixture.stack_items,
            products={
                "product": [("component", ["intake:food_preferred", "risk:manual_review"])],
                "active_product": fixture.products["active_product"],
            },
            traits={
                **fixture.traits,
                "risk:manual_review": {"label": "Review only", "description": "Fixture", "applies_when": "Fixture"},
            },
        ),
    )
    base_slot = _scheduled_slot(plan_in_temp_dir(base), "Product")
    reviewer_schedule = plan_in_temp_dir(reviewer)
    reviewer_slot = _scheduled_slot(reviewer_schedule, "Product")
    assert base_slot == reviewer_slot
    active_fact_index = cast(list[dict[str, object]], reviewer_schedule["active_fact_index"])
    assert [(entry["namespace"], entry["fact"]) for entry in active_fact_index] == [
        ("effect", "platelet_aggregation_modulation")
    ]
