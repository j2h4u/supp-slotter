from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.schedule_types import ScheduleData

from tests.planner_fixture import (
    PlannerFixtureInput,
    PlannerFixtureOptions,
    plan_in_temp_dir,
    write_minimal_planner_fixture,
)


def _journal(
    tmp_path: Path, fixture: PlannerFixtureInput, options: PlannerFixtureOptions | None = None
) -> list[dict[str, object]]:
    if options is None:
        write_minimal_planner_fixture(tmp_path, fixture)
    else:
        write_minimal_planner_fixture(tmp_path, fixture, options=options)
    schedule = cast(ScheduleData, plan_in_temp_dir(tmp_path))
    return cast(list[dict[str, object]], schedule["pairwise_journal"])


def test_prefer_with_journal_resolves_creatine_citrulline_endpoints(tmp_path: Path) -> None:
    rows = _journal(
        tmp_path,
        PlannerFixtureInput(
            stack_items={"creatine": {"stack": "daily"}, "citrulline": {"stack": "daily"}},
            products={
                "creatine": [("sub_9c0908e7f7", ["timing:energy_like"])],
                "citrulline": [("sub_3918fe347e", ["timing:energy_like"])],
            },
            traits={
                "timing:energy_like": {
                    "label": "Energy-like",
                    "description": "Energy-like preference",
                    "applies_when": "Fixture",
                    "effects": [{"match": {"near": "wake"}, "level": "prefer_strong"}],
                }
            },
        ),
        PlannerFixtureOptions(substance_prefer_with={"sub_9c0908e7f7": ["sub_3918fe347e"]}),
    )
    row = next(item for item in rows if item["kind"] == "prefer_together")
    assert row["state"] == "together"
    assert row["satisfied"] is True
    assert row["bonus_contribution"] == 3
    assert row["rule_id"] == "prefer_with_policy"
    assert len(cast(list[object], row["endpoints"])) == 2


def test_hard_separation_journal_retains_rationale_after_rejected_candidate(tmp_path: Path) -> None:
    rows = _journal(
        tmp_path,
        PlannerFixtureInput(
            stack_items={"zinc": {"stack": "daily"}, "copper": {"stack": "daily"}},
            products={
                "zinc": [("zinc", ["timing:energy_like"])],
                "copper": [("copper", ["timing:energy_like"])],
            },
            traits={
                "timing:energy_like": {
                    "label": "Energy-like",
                    "description": "Energy-like preference",
                    "applies_when": "Fixture",
                    "effects": [{"match": {"near": "wake"}, "level": "prefer_strong"}],
                }
            },
        ),
    )
    row = next(item for item in rows if item["constraint_id"] == "sc_zinc_copper_separate_slots")
    assert row["kind"] == "separate_constraint"
    assert row["disposition"] == "hard"
    assert row["state"] == "apart"
    assert row["satisfied"] is True
    assert row["rationale"]
    assert row["action"]


def test_advisory_calcium_iron_journal_is_visible_when_co_located(tmp_path: Path) -> None:
    rows = _journal(
        tmp_path,
        PlannerFixtureInput(
            stack_items={"calcium": {"stack": "daily"}, "iron": {"stack": "daily"}},
            products={
                "calcium": [("calcium", ["timing:energy_like"])],
                "iron": [("iron", ["timing:energy_like"])],
            },
            traits={
                "timing:energy_like": {
                    "label": "Energy-like",
                    "description": "Energy-like preference",
                    "applies_when": "Fixture",
                    "effects": [{"match": {"near": "wake"}, "level": "prefer_strong"}],
                }
            },
        ),
    )
    row = next(item for item in rows if item["constraint_id"] == "sc_calcium_iron_separate_slots")
    assert row["disposition"] == "advisory"
    assert row["state"] in {"apart", "together"}
    assert row["rationale"]
    assert row["action"]


def test_intra_product_conflict_is_journaled_as_unresolvable(tmp_path: Path) -> None:
    rows = _journal(
        tmp_path,
        PlannerFixtureInput(
            stack_items={"mixed": {"stack": "daily"}},
            products={
                "mixed": [("calcium", ["timing:energy_like"]), ("zinc", ["timing:energy_like"])],
            },
            traits={
                "timing:energy_like": {
                    "label": "Energy-like",
                    "description": "Energy-like preference",
                    "applies_when": "Fixture",
                    "effects": [{"match": {"near": "wake"}, "level": "prefer_strong"}],
                }
            },
        ),
    )
    row = next(item for item in rows if item["kind"] == "intra_product_conflict")
    assert row["state"] == "unresolvable"
    assert row["satisfied"] is False
    assert row["disposition"] == "hard"
    assert row["constraint_id"] == "sc_calcium_zinc_separate_slots"
