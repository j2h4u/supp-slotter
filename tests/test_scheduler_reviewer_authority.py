"""Review-only knowledge must not become a scheduling input."""

from pathlib import Path

from tests.planner_fixture import PlannerFixtureInput, plan_in_temp_dir, write_minimal_planner_fixture


def _scheduled_slot(schedule: dict[str, object], product_name: str) -> str:
    pillboxes = schedule["pillboxes"]
    assert isinstance(pillboxes, dict)
    for pillbox in pillboxes.values():
        assert isinstance(pillbox, dict)
        slots = pillbox["slots"]
        assert isinstance(slots, dict)
        for slot_id, entry in slots.items():
            assert isinstance(entry, dict)
            if product_name in entry["products"]:
                return str(slot_id)
    raise AssertionError(f"product {product_name!r} was not scheduled")


def test_reviewer_only_knowledge_does_not_change_slot_assignment(tmp_path: Path) -> None:
    base = tmp_path / "base"
    reviewer = tmp_path / "reviewer"
    fixture = PlannerFixtureInput(
        stack_items={"product": {"stack": "daily"}},
        products={"product": [("component", ["intake:food_preferred"])]},
        traits={"intake:food_preferred": {"label": "Food preferred", "description": "Fixture", "applies_when": "Fixture"}},
    )
    write_minimal_planner_fixture(base, fixture)
    write_minimal_planner_fixture(
        reviewer,
        PlannerFixtureInput(
            stack_items=fixture.stack_items,
            products={"product": [("component", ["intake:food_preferred", "risk:manual_review"])]},
            traits={
                **fixture.traits,
                "risk:manual_review": {"label": "Review only", "description": "Fixture", "applies_when": "Fixture"},
            },
        ),
    )
    base_slot = _scheduled_slot(plan_in_temp_dir(base), "Product")
    reviewer_slot = _scheduled_slot(plan_in_temp_dir(reviewer), "Product")
    assert base_slot == reviewer_slot
