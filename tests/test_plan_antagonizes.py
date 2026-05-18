from __future__ import annotations

from pathlib import Path

from tests.planner_fixture import (
    fixture_id,
    plan_in_temp_dir,
    write_minimal_planner_fixture,
    write_yaml,
)


def test_antagonizes_warning_fires_and_severity_flows_through(
    tmp_path: Path,
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
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
    )
    vit_e_id = fixture_id("sub", "vit_e_substance")
    vit_k2_id = fixture_id("sub", "vit_k2_substance")
    write_yaml(
        tmp_path / "data/relations.yaml",
        {
            "balance": [],
            "supports": [],
            "competes": [],
            "antagonizes": [
                {
                    "source_substance": vit_e_id,
                    "target_substance": vit_k2_id,
                    "severity": "medium",
                    "reason": (
                        "High-dose vitamin E can antagonize vitamin "
                        "K-dependent clotting factors."
                    ),
                }
            ],
        },
    )

    schedule = plan_in_temp_dir(tmp_path)
    antagonist_warnings = [
        warning
        for warning in schedule["warnings"]
        if warning.get("category") == "Active antagonist pairing"
    ]

    assert len(antagonist_warnings) == 1
    warning = antagonist_warnings[0]
    assert warning["category"] == "Active antagonist pairing"
    assert warning["severity"] == "medium"
    assert warning["action"] == (
        "Review this antagonist pairing; the planner does not separate antagonizes pairs by slot."
    )
