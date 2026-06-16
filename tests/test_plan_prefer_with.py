from __future__ import annotations

from pathlib import Path

from tests.planner_fixture import plan_in_temp_dir, write_minimal_planner_fixture


def test_substance_level_prefer_with_awards_colocation_bonus(
    tmp_path: Path,
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        stack_items={
            "sub_9c0908e7f7": {"stack": "daily"},
            "sub_3918fe347e": {"stack": "daily"},
        },
        products={
            "sub_9c0908e7f7": [("sub_9c0908e7f7", ["timing:wake"])],
            "sub_3918fe347e": [("sub_3918fe347e", ["timing:wake"])],
        },
        traits={
            "timing:wake": {
                "label": "Wake",
                "description": "Wake preference",
                "applies_when": "Fixture",
                "effects": [{"match": {"near": "wake"}, "level": "prefer_strong"}],
            },
        },
        substance_prefer_with={"sub_9c0908e7f7": ["sub_3918fe347e"]},
    )

    schedule = plan_in_temp_dir(tmp_path)
    creatine_product = "Sub 9C0908E7F7"
    citrulline_product = "Sub 3918Fe347E"

    assert schedule["kept_together"] == [
        {
            "pair": sorted([citrulline_product, creatine_product], key=str.casefold),
            "together": True,
            "slot": schedule["explanations"][creatine_product]["slot"],
        }
    ]
    assert schedule["explanations"][creatine_product]["slot"] == schedule["explanations"][citrulline_product]["slot"]


def test_ambiguous_substance_level_prefer_with_awards_no_bonus(
    tmp_path: Path,
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        stack_items={
            "sub_9c0908e7f7": {"stack": "daily"},
            "citrulline_a": {"stack": "daily"},
            "citrulline_b": {"stack": "daily"},
        },
        products={
            "sub_9c0908e7f7": [("sub_9c0908e7f7", ["timing:wake"])],
            "citrulline_a": [("sub_3918fe347e", ["timing:wake"])],
            "citrulline_b": [("sub_3918fe347e", ["timing:wake"])],
        },
        traits={
            "timing:wake": {
                "label": "Wake",
                "description": "Wake preference",
                "applies_when": "Fixture",
                "effects": [{"match": {"near": "wake"}, "level": "prefer_strong"}],
            },
        },
        substance_prefer_with={"sub_9c0908e7f7": ["sub_3918fe347e"]},
    )

    schedule = plan_in_temp_dir(tmp_path)
    ambiguous_warnings = [
        warning for warning in schedule["warnings"] if warning.get("category") == "Companion product is ambiguous"
    ]

    assert schedule["kept_together"] == []
    assert ambiguous_warnings == [
        {
            "category": "Companion product is ambiguous",
            "product": "Sub 9C0908E7F7",
            "source": "Sub 9C0908E7F7",
            "target": "Sub 3918Fe347E",
            "concern": "ambiguous prefer with",
            "note": ("prefer_with target maps to multiple active stack items; no bonus awarded"),
            "action": "Choose the intended companion product before relying on co-location.",
        }
    ]
