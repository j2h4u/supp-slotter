from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.cards.product import format_product_name, load_product
from planner.schedule_types import ScheduleData, ScheduleSlotEntry

from tests.planner_fixture import (
    PlannerFixtureInput,
    PlannerFixtureOptions,
    fixture_id,
    flatten_schedule_slots,
    plan_in_temp_dir,
    write_minimal_planner_fixture,
)


def _schedule_slots(schedule: ScheduleData) -> dict[str, ScheduleSlotEntry]:
    return cast(dict[str, ScheduleSlotEntry], flatten_schedule_slots(cast(dict[str, object], schedule)))


def test_legacy_relation_does_not_create_an_intra_product_constraint(
    tmp_path: Path,
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={
                "combo_item": {"product": "combo_item", "stack": "daily"},
            },
            products={
                "combo_item": [
                    ("alpha_substance", []),
                    ("beta_substance", []),
                ],
            },
            traits={
                "intake:alpha": {
                    "label": "Alpha",
                    "description": "Alpha trait",
                    "applies_when": "Fixture",
                },
            },
        ),
        options=PlannerFixtureOptions(
            substance_relations={
                "alpha_substance": [
                    {
                        "type": "competes",
                        "substances": ["beta_substance"],
                        "reason": "Fixture intra-product competing components.",
                    }
                ],
                "beta_substance": [
                    {
                        "type": "competes",
                        "substances": ["alpha_substance"],
                        "reason": "Fixture intra-product competing components.",
                    }
                ],
            },
        ),
    )

    schedule = cast(ScheduleData, plan_in_temp_dir(tmp_path))
    combo_name = "Combo Item"
    slots = _schedule_slots(schedule)
    scheduled_items = {item for slot_entry in slots.values() for item in slot_entry["products"]}
    conflict_warnings = [
        warning
        for warning in schedule["warnings"]
        if warning.get("category") == "Component conflict inside one product"
    ]

    assert scheduled_items == {combo_name}
    assert schedule["explanations"][combo_name]["components"] == [
        "Alpha Substance",
        "Beta Substance",
    ]
    assert conflict_warnings == []


def test_legacy_relation_does_not_block_inter_product_colocation(
    tmp_path: Path,
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={
                "alpha_product": {"stack": "daily"},
                "beta_product": {"stack": "daily"},
            },
            products={
                "alpha_product": [("alpha_substance", ["intake:alpha"])],
                "beta_product": [("beta_substance", ["intake:beta"])],
            },
            traits={
                "intake:alpha": {
                    "label": "Alpha",
                    "description": "Alpha trait",
                    "applies_when": "Fixture",
                    "effects": [
                        {"match": {"near": "wake"}, "level": "prefer_strong"},
                    ],
                },
                "intake:beta": {
                    "label": "Beta",
                    "description": "Beta trait",
                    "applies_when": "Fixture",
                    "effects": [
                        {"match": {"near": "wake"}, "level": "prefer_strong"},
                    ],
                },
            },
        ),
        options=PlannerFixtureOptions(
            substance_relations={
                "alpha_substance": [
                    {
                        "type": "competes",
                        "substances": ["beta_substance"],
                        "reason": "Fixture: competes relation.",
                    }
                ],
                "beta_substance": [
                    {
                        "type": "competes",
                        "substances": ["alpha_substance"],
                        "reason": "Fixture: competes relation.",
                    }
                ],
            },
        ),
    )

    schedule = cast(ScheduleData, plan_in_temp_dir(tmp_path))
    alpha_name = "Alpha Product"
    beta_name = "Beta Product"
    scheduled_items = {
        item for slot_entry in _schedule_slots(schedule).values() for item in slot_entry["products"]
    }
    assert scheduled_items == {alpha_name, beta_name}


def test_legacy_absorption_relation_does_not_block_colocation(
    tmp_path: Path,
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={
                "zinc_product": {"stack": "daily"},
                "copper_product": {"stack": "daily"},
            },
            products={
                "zinc_product": [("zinc_substance", ["timing:wake"])],
                "copper_product": [("copper_substance", ["timing:wake"])],
            },
            traits={
                "timing:wake": {
                    "label": "Wake",
                    "description": "Wake preference",
                    "applies_when": "Fixture",
                    "effects": [
                        {"match": {"near": "wake"}, "level": "prefer_strong"},
                    ],
                },
            },
        ),
        options=PlannerFixtureOptions(
            substance_relations={
                "zinc_substance": [
                    {
                        "type": "competes",
                        "substances": ["copper_substance"],
                        "reason": "Fixture absorption conflict.",
                    }
                ],
                "copper_substance": [
                    {
                        "type": "competes",
                        "substances": ["zinc_substance"],
                        "reason": "Fixture absorption conflict.",
                    }
                ],
            },
        ),
    )

    schedule = cast(ScheduleData, plan_in_temp_dir(tmp_path))
    products_dir = tmp_path / "data" / "products"
    zinc_id = fixture_id("prd", "zinc_product")
    copper_id = fixture_id("prd", "copper_product")
    zinc_name = format_product_name(load_product(next(products_dir.glob(f"*{zinc_id}*"))))
    copper_name = format_product_name(load_product(next(products_dir.glob(f"*{copper_id}*"))))
    scheduled_items = {
        item for slot_entry in _schedule_slots(schedule).values() for item in slot_entry["products"]
    }
    assert scheduled_items == {zinc_name, copper_name}


def test_legacy_absorption_relation_does_not_emit_constraint_warning(
    tmp_path: Path,
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={
                "trace_product": {"product": "trace_product", "stack": "daily"},
            },
            products={
                "trace_product": [
                    ("zinc_substance", []),
                    ("copper_substance", []),
                ],
            },
            traits={
                "timing:neutral": {
                    "label": "Neutral",
                    "description": "Fixture neutral trait",
                    "applies_when": "Fixture",
                },
            },
        ),
        options=PlannerFixtureOptions(
            substance_relations={
                "zinc_substance": [
                    {
                        "type": "competes",
                        "substances": ["copper_substance"],
                        "reason": "Fixture absorption conflict.",
                    }
                ],
                "copper_substance": [
                    {
                        "type": "competes",
                        "substances": ["zinc_substance"],
                        "reason": "Fixture absorption conflict.",
                    }
                ],
            },
        ),
    )

    schedule = cast(ScheduleData, plan_in_temp_dir(tmp_path))
    conflict_warnings = [
        warning
        for warning in schedule["warnings"]
        if warning.get("category") == "Component conflict inside one product"
    ]

    assert conflict_warnings == []
