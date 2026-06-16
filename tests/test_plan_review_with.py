from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.schedule_types import ScheduleData
from tests.planner_fixture import (
    PlannerFixtureInput,
    fixture_id,
    plan_in_temp_dir,
    write_minimal_planner_fixture,
    write_yaml,
)


def test_review_with_warning_fires_and_severity_flows_through(
    tmp_path: Path,
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={
                "vit_e_product": {"stack": "daily"},
                "vit_k2_product": {"stack": "daily"},
            },
            products={
                "vit_e_product": [("vit_e_substance", [])],
                "vit_k2_product": [("vit_k2_substance", [])],
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
    vit_e_id = fixture_id("sub", "vit_e_substance")
    vit_k2_id = fixture_id("sub", "vit_k2_substance")
    write_yaml(
        tmp_path / "data/relations.yaml",
        {
            "balance": [],
            "supports": [],
            "competes": [],
            "review_with": [
                {
                    "source_substance": vit_e_id,
                    "target_substance": vit_k2_id,
                    "severity": "medium",
                    "reason": ("High-dose vitamin E can antagonize vitamin K-dependent clotting factors."),
                }
            ],
        },
    )

    schedule = cast(ScheduleData, plan_in_temp_dir(tmp_path))
    review_warnings = [
        warning for warning in schedule["warnings"] if warning.get("category") == "Active review pairing"
    ]

    assert len(review_warnings) == 1
    warning = review_warnings[0]
    assert warning.get("category") == "Active review pairing"
    assert warning.get("severity") == "medium"
    assert warning.get("action") == (
        "Review this active pairing; the planner surfaces it for operator review and does not separate it by slot."
    )
