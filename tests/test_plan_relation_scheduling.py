from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.cards.product import format_product_name, load_product
from planner.contracts import RelationSelector, SchedulingConstraint, Substance
from planner.engine._plan_blocking import (
    _approved_block_constraints,
    _matching_constraints,
    _SchedulingConstraintContext,
    blocking_constraint_diagnostics,
    slot_is_blocked,
)
from planner.engine._plan_types import BlockingContext
from planner.schedule_types import ScheduleData, ScheduleSlotEntry

from tests.planner_fixture import (
    PlannerFixtureInput,
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
    )

    schedule = cast(ScheduleData, plan_in_temp_dir(tmp_path))
    alpha_name = "Alpha Product"
    beta_name = "Beta Product"
    scheduled_items = {item for slot_entry in _schedule_slots(schedule).values() for item in slot_entry["products"]}
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
    )

    schedule = cast(ScheduleData, plan_in_temp_dir(tmp_path))
    products_dir = tmp_path / "data" / "products"
    zinc_id = fixture_id("prd", "zinc_product")
    copper_id = fixture_id("prd", "copper_product")
    zinc_name = format_product_name(load_product(next(products_dir.glob(f"*{zinc_id}*"))))
    copper_name = format_product_name(load_product(next(products_dir.glob(f"*{copper_id}*"))))
    scheduled_items = {item for slot_entry in _schedule_slots(schedule).values() for item in slot_entry["products"]}
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
    )

    schedule = cast(ScheduleData, plan_in_temp_dir(tmp_path))
    conflict_warnings = [
        warning
        for warning in schedule["warnings"]
        if warning.get("category") == "Component conflict inside one product"
    ]

    assert conflict_warnings == []


def test_matching_constraints_deduplicates_rules_and_ignores_empty_context() -> None:
    constraint = SchedulingConstraint(
        id="sc",
        source_selector=RelationSelector(entity_id="a"),
        target_selector=RelationSelector(entity_id="b"),
        effect="separate_slots",
        enforcement="block",
        status="approved",
        evidence=("e",),
    )
    context = _SchedulingConstraintContext(
        slot_items={"slot": ["existing", "existing"]},
        active_components={"item": ["a"], "existing": ["b"]},
        substances={"a": Substance("a", "A"), "b": Substance("b", "B")},
        constraints=(constraint,),
    )
    assert _matching_constraints("item", "slot", context) == (constraint,)
    assert _matching_constraints("item", "missing", context) == ()
    assert _matching_constraints("item", "slot", context._replace(constraints=())) == ()


def test_blocking_entry_points_filter_unapproved_and_non_block_constraints() -> None:
    approved = SchedulingConstraint(
        id="approved",
        source_selector=RelationSelector(entity_id="a"),
        target_selector=RelationSelector(entity_id="b"),
        effect="separate_slots",
        enforcement="block",
        status="approved",
        evidence=("e",),
        action="split",
        rationale="r",
        semantic_note="n",
        scope=(("x", "y"),),
        owner="o",
        review_by="d",
        assertion_type="direct",
        legacy_preserved=True,
        legacy_relation_id="old",
    )
    rejected = approved.__class__(
        id="rejected",
        source_selector=approved.source_selector,
        target_selector=approved.target_selector,
        effect="separate_slots",
        enforcement="block",
        status="review_pending",
        evidence=("e",),
    )
    advisory = approved.__class__(
        id="advisory",
        source_selector=approved.source_selector,
        target_selector=approved.target_selector,
        effect="separate_slots",
        enforcement="advisory",
        status="approved",
        evidence=("e",),
    )
    assert _approved_block_constraints((approved, rejected, advisory)) == (approved,)
    blocking = BlockingContext(
        {"item": ["a"], "existing": ["b"]},
        {"a": Substance("a", "A"), "b": Substance("b", "B")},
        (approved, rejected, advisory),
    )
    assert slot_is_blocked("item", "slot", {"slot": ["existing"]}, blocking)
    diagnostics = blocking_constraint_diagnostics("item", "slot", {"slot": ["existing"]}, blocking)
    assert diagnostics[0].id == "approved"
    assert diagnostics[0].metadata["legacy_relation_id"] == "old"
