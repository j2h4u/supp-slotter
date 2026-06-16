from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.engine._types import ScheduleData
from tests.planner_fixture import plan_in_temp_dir, write_minimal_planner_fixture


def test_schedule_contains_active_fact_index(tmp_path: Path) -> None:
    write_minimal_planner_fixture(
        tmp_path,
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
