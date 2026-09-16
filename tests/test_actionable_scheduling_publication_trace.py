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


def test_real_shelf_pressure_trace_retains_normalized_shape_and_proof(tmp_path: Path) -> None:
    schedule = _fresh_schedule(tmp_path)
    matches = cast(list[dict[str, object]], schedule["pressure_matches"])

    identities = [(match["item_id"], match["dimension"], match["value"]) for match in matches]
    assert identities == sorted(identities)
    assert len(identities) == len(set(identities))
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
    assert all(match["item_id"] in match["applicability_product_ids"] for match in matches)
    for match in matches:
        provenance = cast(list[dict[str, str | None]], match["provenance_refs"])
        assert provenance == sorted(
            provenance,
            key=lambda ref: (ref["source"], ref["locator"], ref["quotation"] is not None, ref["quotation"] or ""),
        )
        assert len(provenance) == len({(ref["source"], ref["locator"], ref["quotation"]) for ref in provenance})


def test_real_shelf_publication_trace_is_self_consistent(tmp_path: Path) -> None:
    schedule = _fresh_schedule(tmp_path)
    objective = cast(dict[str, object], schedule["objective"])
    assignments = cast(dict[str, str], schedule["assignments"])
    matches = cast(list[dict[str, object]], schedule["pressure_matches"])
    explanations = cast(dict[str, dict[str, object]], schedule["canonical_explanations"])

    assert schedule["status"] == "Optimal"
    assert objective["satisfied_pressures"] == sum(match["satisfied"] for match in matches)
    assert set(explanations) == set(assignments)
    for item_id, explanation in explanations.items():
        item_matches = [match for match in matches if match["item_id"] == item_id]
        assert explanation["item_id"] == item_id
        assert explanation["slot_id"] == assignments[item_id]
        assert explanation["pressure_matches"] == item_matches
        assert explanation["placement_basis"] == (
            "pressure_evidence" if any(match["satisfied"] for match in item_matches) else "balance_and_tie_break_only"
        )
