from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.contracts import TraitDef
from planner.engine._plan_output import _append_trait_warnings
from planner.engine._plan_types import ActiveIndex
from planner.schedule_types import ScheduleData

from tests.planner_fixture import PlannerFixtureInput, plan_in_temp_dir, write_minimal_planner_fixture


def test_schedule_contains_active_fact_index(tmp_path: Path) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={
                "omega_product": {"stack": "daily"},
                "b6_product": {"stack": "daily"},
            },
            products={
                "omega_product": [
                    (
                        "epa_component",
                        [
                            "risk:bleeding_med_interaction",
                            "pathway:omega3_eicosanoid",
                            "effect:platelet_aggregation_modulation",
                        ],
                    )
                ],
                "b6_product": [
                    (
                        "b6_component",
                        [
                            "risk:b6_neuropathy_long_term",
                        ],
                    )
                ],
            },
            traits={
                "risk:bleeding_med_interaction": {
                    "label": "Bleeding medication interaction",
                    "description": "Fixture bleeding context",
                    "applies_when": "Fixture",
                    "warning": True,
                },
                "risk:b6_neuropathy_long_term": {
                    "label": "B6 neuropathy long-term",
                    "description": "Fixture B6 context",
                    "applies_when": "Fixture",
                    "warning": True,
                },
                "pathway:omega3_eicosanoid": {
                    "label": "Omega-3 / eicosanoid",
                    "description": "Fixture omega-3 pathway",
                    "applies_when": "Fixture",
                },
                "effect:platelet_aggregation_modulation": {
                    "label": "Platelet aggregation modulation",
                    "description": "Fixture platelet context",
                    "applies_when": "Fixture",
                },
            },
        ),
    )

    schedule = cast(ScheduleData, plan_in_temp_dir(tmp_path))
    fact_index = schedule["active_fact_index"]

    bleeding = next(
        entry for entry in fact_index if entry["namespace"] == "risk" and entry["fact"] == "bleeding_med_interaction"
    )
    assert bleeding["label"] == "Bleeding medication interaction"
    assert bleeding["product_count"] == 1
    assert bleeding["products"] == ["Omega Product"]

    platelet_effect = next(
        entry
        for entry in fact_index
        if entry["namespace"] == "effect" and entry["fact"] == "platelet_aggregation_modulation"
    )
    assert platelet_effect["label"] == "Platelet aggregation modulation"

    assert all(entry["namespace"] != "is" for entry in fact_index)


def test_append_trait_warnings_uses_sources_and_fallback_message() -> None:
    schedule = cast(ScheduleData, {"warnings": []})
    active = ActiveIndex(
        item_traits={
            "item_known": {"risk:known", "risk:not_warning"},
            "item_unknown": {"risk:unknown"},
            "item_missing": {"risk:missing"},
        },
        secondary_traits_by_item={},
        item_products={
            "item_known": "prd_known",
            "item_unknown": "prd_unknown",
            "item_missing": "prd_missing",
        },
        active_components={},
        trait_sources_by_item={
            "item_known": {"risk:known": ["sub_a", "sub_b"]},
            "item_unknown": {"risk:unknown": []},
            "item_missing": {},
        },
        intra_product_relation_conflicts_by_item={},
        item_stacks={},
    )
    trait_defs = {
        "risk:known": TraitDef(
            id="risk:known",
            namespace="risk",
            short_name="known",
            label="Known risk",
            description="Known warning.",
            applies_when="Fixture",
            warning=True,
            action="Review known risk.",
        ),
        "risk:unknown": TraitDef(
            id="risk:unknown",
            namespace="risk",
            short_name="unknown",
            label="Unknown risk",
            description="",
            applies_when="Fixture",
            warning=True,
        ),
        "risk:not_warning": TraitDef(
            id="risk:not_warning",
            namespace="risk",
            short_name="not_warning",
            label="Not warning",
            description="Ignored.",
            applies_when="Fixture",
        ),
    }

    _append_trait_warnings(schedule, active, trait_defs)

    assert schedule["warnings"] == [
        {
            "item": "item_known",
            "product": "prd_known",
            "substance": "sub_a",
            "trait": "risk:known",
            "message": "Known warning.",
            "action": "Review known risk.",
        },
        {
            "item": "item_known",
            "product": "prd_known",
            "substance": "sub_b",
            "trait": "risk:known",
            "message": "Known warning.",
            "action": "Review known risk.",
        },
        {
            "item": "item_unknown",
            "product": "prd_unknown",
            "substance": "unknown",
            "trait": "risk:unknown",
            "message": "Manual review required.",
            "action": "",
        },
    ]
