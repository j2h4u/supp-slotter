"""Focused acceptance for the compact normalized-pressure publication trace."""

from __future__ import annotations

from pathlib import Path
from shutil import copytree
from typing import cast

import yaml
from planner.engine import cmd_plan

ROOT = Path(__file__).resolve().parents[1]


def _fresh_schedule(tmp_path: Path) -> dict[str, object]:
    copytree(ROOT / "data", tmp_path / "data")
    result = cmd_plan(data_root=tmp_path)
    assert result.exit_code == 0, result.errors
    return cast(dict[str, object], yaml.safe_load((tmp_path / "schedule.yaml").read_text(encoding="utf-8")))


def test_real_shelf_pressure_trace_retains_normalized_identity_and_proof(tmp_path: Path) -> None:
    schedule = _fresh_schedule(tmp_path)
    matches = cast(list[dict[str, object]], schedule["pressure_matches"])

    assert len(matches) == 10
    assert all(
        {
            "item_id",
            "dimension",
            "value",
            "satisfied",
            "fact_ids",
            "law_ids",
            "applicability_role_ids",
            "applicability_product_ids",
            "provenance_refs",
        }
        <= set(match)
        for match in matches
    )
    assert all(match["satisfied"] is True for match in matches)
    assert all(cast(list[object], match["fact_ids"]) for match in matches)
    assert all(cast(list[object], match["law_ids"]) for match in matches)
    assert all(
        cast(list[object], match["applicability_role_ids"]) or cast(list[object], match["applicability_product_ids"])
        for match in matches
    )
    assert all(cast(list[object], match["applicability_product_ids"]) for match in matches)
    assert all(cast(list[object], match["provenance_refs"]) for match in matches)

    krill = [match for match in matches if match["item_id"] == "prd_w2s970gps4"]
    assert len(krill) == 1
    assert len(cast(list[object], krill[0]["fact_ids"])) == 2
    assert len(cast(list[object], krill[0]["applicability_role_ids"])) == 2

    product_only = [
        match for match in matches if match["item_id"] in {"prd_932319251f", "prd_8eff2491b7", "prd_vitamealc8"}
    ]
    assert {match["item_id"] for match in product_only} == {
        "prd_932319251f",
        "prd_8eff2491b7",
        "prd_vitamealc8",
    }
    assert all(match["applicability_role_ids"] == [] for match in product_only)
    assert all(match["applicability_product_ids"] == [match["item_id"]] for match in product_only)


def test_real_shelf_recovery_objective_and_balance_only_count(tmp_path: Path) -> None:
    schedule = _fresh_schedule(tmp_path)
    objective = cast(dict[str, object], schedule["objective"])
    explanations = cast(dict[str, dict[str, object]], schedule["canonical_explanations"])

    assert schedule["status"] == "Optimal"
    assert objective["satisfied_pressures"] == 10
    assert objective["squared_load"] == 62
    assert (
        sum(explanation["placement_basis"] == "balance_and_tie_break_only" for explanation in explanations.values())
        == 8
    )


def test_recovery_has_only_pressure_explained_placement_changes(tmp_path: Path) -> None:
    schedule = _fresh_schedule(tmp_path)
    assignments = cast(dict[str, str], schedule["assignments"])

    assert {
        item_id: assignments[item_id]
        for item_id in ("prd_9d0fca3201", "prd_d0u8k66ypy", "prd_e5cc3b4e7c", "prd_w2s970gps4")
    } == {
        "prd_9d0fca3201": "evening_empty",
        "prd_d0u8k66ypy": "evening_empty",
        "prd_e5cc3b4e7c": "morning_food",
        "prd_w2s970gps4": "day_food",
    }


def test_recovery_difference_witness_is_strict_and_complete() -> None:
    witness = cast(
        dict[str, object],
        yaml.safe_load(
            (ROOT / "docs/evidence/actionable-scheduling-recovery-difference-20260831.yaml").read_text(encoding="utf-8")
        ),
    )
    current = cast(dict[str, object], witness["current"])
    acceptance = cast(dict[str, object], witness["acceptance"])

    assert current["status"] == "Optimal"
    assert current["normalized_pressures"] == 8
    assert current["squared_load"] == 58
    assert current["balance_only_placements"] == 10
    assert acceptance["changed_placement_count"] == 4
    assert acceptance["no_unexplained_placement_change"] is True
