from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.schedule_types import ScheduleData
from tests.planner_fixture import PlannerFixtureInput, plan_in_temp_dir, write_minimal_planner_fixture


def test_schedule_excludes_reviewer_only_facts_from_active_fact_index(tmp_path: Path) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={"omega_product": {"stack": "daily"}, "b6_product": {"stack": "daily"}},
            products={
                "omega_product": [("epa_component", ["risk:bleeding_med_interaction", "effect:platelet_aggregation_modulation"])],
                "b6_product": [("b6_component", ["risk:b6_neuropathy_long_term"])],
            },
            traits={
                "risk:bleeding_med_interaction": {"label": "Bleeding medication interaction", "description": "Fixture", "applies_when": "Fixture"},
                "risk:b6_neuropathy_long_term": {"label": "B6 neuropathy long-term", "description": "Fixture", "applies_when": "Fixture"},
                "effect:platelet_aggregation_modulation": {"label": "Platelet aggregation modulation", "description": "Fixture", "applies_when": "Fixture"},
            },
        ),
    )
    schedule = cast(ScheduleData, plan_in_temp_dir(tmp_path))
    assert [(entry["namespace"], entry["fact"]) for entry in schedule["active_fact_index"]] == [
        ("effect", "platelet_aggregation_modulation")
    ]
