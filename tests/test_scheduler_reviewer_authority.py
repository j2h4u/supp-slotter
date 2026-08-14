from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.engine import cmd_review
from planner.schedule_types import ScheduleData

from tests.planner_fixture import (
    PlannerFixtureInput,
    fixture_id,
    flatten_schedule_slots,
    plan_in_temp_dir,
    write_minimal_planner_fixture,
    write_yaml,
)


def _write_authority_fixture(
    root: Path,
    *,
    product_traits: list[str],
    reviewer_only: bool = False,
) -> None:
    traits: dict[str, dict[str, object]] = {
        "timing:sleep_support": {
            "label": "Sleep support",
            "description": "Fixture timing trait.",
            "applies_when": "Fixture only.",
            "effects": [{"match": {"near": "sleep"}, "level": "prefer_strong"}],
        },
        "effect:vasodilator": {
            "label": "Vasodilator",
            "description": "Fixture reviewer effect.",
            "applies_when": "Fixture only.",
        },
        "risk:manual_review": {
            "label": "Manual review",
            "description": "Fixture reviewer risk.",
            "applies_when": "Fixture only.",
        },
        "pathway:nitric_oxide": {
            "label": "Nitric oxide",
            "description": "Fixture reviewer pathway.",
            "applies_when": "Fixture only.",
        },
    }
    write_minimal_planner_fixture(
        root,
        PlannerFixtureInput(
            stack_items={"review_product": {"stack": "daily"}},
            products={"review_product": [("review_subject", product_traits)]},
            traits=traits,
        ),
    )
    _write_daily_slots_with_sleep_slot(root)
    if reviewer_only:
        _add_context_membership(root)


def _write_daily_slots_with_sleep_slot(root: Path) -> None:
    write_yaml(
        root / "data/pillboxes.yaml",
        {
            "daily": {
                "label": "Daily",
                "slots": {
                    "morning_empty": {
                        "label": "Morning empty",
                        "order": 1,
                        "near": "wake",
                        "food": False,
                    },
                    "sleep_empty": {
                        "label": "Sleep empty",
                        "order": 2,
                        "near": "sleep",
                        "food": False,
                    },
                },
            },
        },
    )


def _add_context_membership(root: Path) -> None:
    subject_id = fixture_id("sub", "review_subject")
    write_yaml(
        root / "data/substances" / f"review_subject__{subject_id}.yaml",
        {
            "id": subject_id,
            "name": "Review Subject",
            "knowledge": {
                "effect": ["vasodilator"],
                "risk": ["manual_review"],
                "context": ["interaction_review"],
                "pathway": ["nitric_oxide"],
            },
        },
    )
    write_yaml(
        root / "data/dashboards/interaction_review.yaml",
        {
            "name": "Interaction Review",
            "description": "Fixture dashboard for reviewer-only context membership.",
            "from_traits": {"context": ["interaction_review"]},
            "risk": {"description": "Fixture interaction review membership."},
        },
    )


def _scheduled_slot(schedule: ScheduleData, product_name: str = "Review Product") -> str:
    slots = cast(dict[str, dict[str, object]], flatten_schedule_slots(cast(dict[str, object], schedule)))
    matches = [slot_id for slot_id, slot in slots.items() if product_name in cast(list[str], slot["products"])]
    assert len(matches) == 1
    return matches[0]


def test_reviewer_only_knowledge_does_not_change_slot_assignment(tmp_path: Path) -> None:
    base_root = tmp_path / "base"
    reviewer_root = tmp_path / "reviewer"
    _write_authority_fixture(base_root, product_traits=[])
    _write_authority_fixture(
        reviewer_root,
        product_traits=["effect:vasodilator", "risk:manual_review", "pathway:nitric_oxide"],
        reviewer_only=True,
    )

    base_slot = _scheduled_slot(cast(ScheduleData, plan_in_temp_dir(base_root)))
    reviewer_schedule = cast(ScheduleData, plan_in_temp_dir(reviewer_root))
    reviewer_slot = _scheduled_slot(reviewer_schedule)
    review_result = cmd_review(data_root=reviewer_root)

    assert reviewer_slot == base_slot
    assert review_result.exit_code == 0, review_result.stderr
    assert "manual_review" in review_result.output
    assert "nitric_oxide" in review_result.output
    risk_members = cast(list[dict[str, object]], reviewer_schedule["risks"][0].get("members"))
    assert risk_members[0]["substance"] == "Review Subject"


def test_explicit_schedule_trait_can_change_slot_assignment(tmp_path: Path) -> None:
    base_root = tmp_path / "base"
    scheduled_root = tmp_path / "scheduled"
    _write_authority_fixture(base_root, product_traits=[])
    _write_authority_fixture(scheduled_root, product_traits=["timing:sleep_support"])

    base_slot = _scheduled_slot(cast(ScheduleData, plan_in_temp_dir(base_root)))
    scheduled_slot = _scheduled_slot(cast(ScheduleData, plan_in_temp_dir(scheduled_root)))

    assert base_slot == "morning_empty"
    assert scheduled_slot == "sleep_empty"
