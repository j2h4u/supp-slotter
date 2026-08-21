"""Compact vertical acceptance scenarios for the cutover decision."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from shutil import copytree
from typing import cast

import yaml

from planner.cards.product import format_product_name, load_product_registry
from planner.engine import cmd_plan
from planner.paths import Paths

from tests.helpers import ontology_bundle
from tests.planner_fixture import PlannerFixtureInput, fixture_id, plan_in_temp_dir, write_minimal_planner_fixture


ROOT = Path(__file__).resolve().parents[1]


def _schedule_products(schedule: dict[str, object], pillbox: str) -> list[str]:
    pillboxes = cast(dict[str, object], schedule["pillboxes"])
    entries = cast(dict[str, dict[str, object]], cast(dict[str, object], pillboxes[pillbox])["slots"])
    return [product for entry in entries.values() for product in cast(list[str], entry["products"])]


def test_real_shelf_daily_episodic_and_training_products_are_complete(tmp_path: Path) -> None:
    """The real shelf is complete without asserting a particular balanced slot."""
    copytree(ROOT / "data", tmp_path / "data")
    result = cmd_plan(data_root=tmp_path)

    assert result.exit_code == 0, result.errors
    schedule = cast(dict[str, object], yaml.safe_load((tmp_path / "schedule.yaml").read_text(encoding="utf-8")))
    paths = Paths.from_root(tmp_path)
    products = load_product_registry(paths, ontology_bundle())
    stacks = cast(dict[str, list[str]], yaml.safe_load(paths.stacks_file.read_text(encoding="utf-8")))

    expected_by_stack = {
        stack: {format_product_name(products[product_id]) for product_id in stacks[stack]}
        for stack in ("daily", "training")
    }
    actual_by_stack = {stack: set(_schedule_products(schedule, stack)) for stack in ("daily", "training")}
    assert actual_by_stack == expected_by_stack
    assert Counter(_schedule_products(schedule, "daily") + _schedule_products(schedule, "training")) == Counter(
        name for names in expected_by_stack.values() for name in names
    )

    summary = cast(dict[str, object], schedule["summary"])
    usage_groups = cast(dict[str, list[str]], summary["usage_groups"])
    episodic = {
        format_product_name(products[product_id])
        for product_id in stacks["daily"]
        if products[product_id].use_pattern == "not_every_day"
    }
    assert set(usage_groups["not_every_day"]) == episodic
    assert episodic <= actual_by_stack["daily"]


def test_multicomponent_vertical_explanation_preserves_conflicting_votes_and_neutrality(
    tmp_path: Path,
) -> None:
    food_components = [(f"food_{index}", ["intake:food_preferred"]) for index in range(5)]
    empty_components = [(f"empty_{index}", ["intake:empty_preferred"]) for index in range(2)]
    unknown_component = [("unknown", [])]
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={"multi": {"stack": "daily"}},
            products={"multi": food_components + empty_components + unknown_component},
            traits={
                "intake:food_preferred": {
                    "label": "Food preferred",
                    "description": "Food fixture",
                    "applies_when": "Fixture",
                    "effects": [{"match": {"food": True}, "level": "prefer"}],
                },
                "intake:empty_preferred": {
                    "label": "Empty preferred",
                    "description": "Empty fixture",
                    "applies_when": "Fixture",
                    "effects": [
                        {"match": {"food": False}, "level": "prefer"},
                        {"match": {"food": True}, "level": "avoid"},
                    ],
                },
            },
        ),
    )
    pillboxes_path = tmp_path / "data/pillboxes.yaml"
    pillboxes = cast(dict[str, object], yaml.safe_load(pillboxes_path.read_text(encoding="utf-8")))
    daily = cast(dict[str, object], pillboxes["daily"])
    daily_slots = cast(dict[str, dict[str, object]], daily["slots"])
    daily_slots["day_empty"]["food"] = True
    pillboxes_path.write_text(yaml.safe_dump(pillboxes, sort_keys=False), encoding="utf-8")

    schedule = cast(dict[str, object], plan_in_temp_dir(tmp_path))
    explanation = cast(dict[str, object], cast(dict[str, object], schedule["explanations"])["Multi"])
    contributions = {
        row["policy_id"]: row for row in cast(list[dict[str, object]], explanation["policy_contributions"])
    }

    assert contributions["intake:food_preferred"]["vote_count"] == 5
    assert contributions["intake:food_preferred"]["score_contribution"] == 10
    assert contributions["intake:empty_preferred"]["vote_count"] == 2
    assert contributions["intake:empty_preferred"]["score_contribution"] == -4
    neutral = cast(list[dict[str, object]], explanation["neutral_components"])
    assert neutral == [
        {
            "substance_id": fixture_id("sub", "unknown"),
            "substance": "Unknown",
            "status": "no-scheduling-fact",
            "reason": "no-scheduling-fact",
            "assessment_states": {"activity": "unassessed", "intake": "unassessed", "timing": "unassessed"},
        }
    ]
    why_here = cast(list[str], explanation["why_here"])
    assert any("intake:food_preferred" in reason for reason in why_here)
    assert any("intake:empty_preferred" in reason for reason in why_here)
