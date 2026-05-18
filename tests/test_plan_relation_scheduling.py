from __future__ import annotations

from pathlib import Path

from planner.cards.product import format_product_name, load_product
from tests.planner_fixture import (
    fixture_id,
    flatten_schedule_slots,
    plan_in_temp_dir,
    write_minimal_planner_fixture,
)


def test_intra_product_competes_conflict_warns_without_splitting(
    tmp_path: Path,
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
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
    )

    schedule = plan_in_temp_dir(tmp_path)
    combo_name = "Combo Item"
    scheduled_items = {
        item
        for slot_entry in flatten_schedule_slots(schedule).values()
        for item in slot_entry["products"]
    }
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
    assert conflict_warnings == [
        {
            "category": "Component conflict inside one product",
            "product": combo_name,
            "source": "Alpha Substance",
            "target": "Beta Substance",
            "concern": "competes",
            "note": (
                "Component relation conflicts inside one physical product; "
                "scheduling keeps the product together and emits this warning"
            ),
            "action": (
                "Review this product manually; competing components are inside one "
                "physical product and cannot be separated by scheduling."
            ),
        }
    ]


def test_inter_product_competes_relation_blocks_colocation(
    tmp_path: Path,
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
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
    )

    schedule = plan_in_temp_dir(tmp_path)
    alpha_name = "Alpha Product"
    beta_name = "Beta Product"
    colocated_pairs = [
        set(slot_entry["products"])
        for slot_entry in flatten_schedule_slots(schedule).values()
        if {alpha_name, beta_name}.issubset(slot_entry["products"])
    ]

    assert colocated_pairs == []
    assert {
        item
        for slot_entry in flatten_schedule_slots(schedule).values()
        for item in slot_entry["products"]
    } == {
        alpha_name,
        beta_name,
    }


def test_inter_product_absorption_relation_blocks_colocation(
    tmp_path: Path,
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
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
    )

    schedule = plan_in_temp_dir(tmp_path)
    products_dir = tmp_path / "data" / "products"
    zinc_id = fixture_id("prd", "zinc_product")
    copper_id = fixture_id("prd", "copper_product")
    zinc_name = format_product_name(load_product(next(products_dir.glob(f"*{zinc_id}*"))))
    copper_name = format_product_name(load_product(next(products_dir.glob(f"*{copper_id}*"))))
    colocated_pairs = [
        set(slot_entry["products"])
        for slot_entry in flatten_schedule_slots(schedule).values()
        if {zinc_name, copper_name}.issubset(slot_entry["products"])
    ]

    assert colocated_pairs == []


def test_intra_product_absorption_relation_warns_without_splitting(
    tmp_path: Path,
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
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
    )

    schedule = plan_in_temp_dir(tmp_path)
    conflict_warnings = [
        warning
        for warning in schedule["warnings"]
        if warning.get("category") == "Component conflict inside one product"
    ]

    assert conflict_warnings == [
        {
            "category": "Component conflict inside one product",
            "product": "Trace Product",
            "source": "Zinc Substance",
            "target": "Copper Substance",
            "concern": "competes",
            "note": (
                "Component relation conflicts inside one physical product; "
                "scheduling keeps the product together and emits this warning"
            ),
            "action": (
                "Review this product manually; competing components are inside one "
                "physical product and cannot be separated by scheduling."
            ),
        }
    ]
