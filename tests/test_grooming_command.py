"""Vertical tests for the bounded, read-only enrichment queue."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml
from planner.engine import cmd_grooming_next

from tests.planner_fixture import (
    PlannerFixtureInput,
    find_card_path_by_id,
    plan_in_temp_dir,
    write_minimal_planner_fixture,
)


def _write_grooming_fixture(tmp_path: Path) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={
                "prd_alpha00001": {"stack": "daily"},
                "prd_beta000001": {"stack": "training"},
                "prd_inactive01": {"stack": "inactive"},
            },
            products={
                "prd_alpha00001": [("sub_alpha00001", [])],
                "prd_beta000001": [("sub_beta000001", [])],
                "prd_inactive01": [("sub_inactive01", [])],
            },
            traits={},
        ),
    )
    names = {
        "sub_alpha00001": "zeta",
        "sub_beta000001": "Alpha",
        "sub_inactive01": "Inactive",
    }
    for substance_id, name in names.items():
        path = find_card_path_by_id(tmp_path / "data/substances", substance_id)
        data = cast(dict[str, object], yaml.safe_load(path.read_text()))
        data["name"] = name
        path.write_text(yaml.safe_dump(data, sort_keys=False))
    (tmp_path / "data/substances/orphan__sub_orphan0001.yaml").write_text(
        yaml.safe_dump(
            {"id": "sub_orphan0001", "name": "Orphan registry card"},
            sort_keys=False,
        )
    )


def test_grooming_next_returns_active_unreviewed_in_stable_order(tmp_path: Path) -> None:
    _write_grooming_fixture(tmp_path)

    result = cmd_grooming_next(limit=8, data_root=tmp_path)

    assert result.exit_code == 0
    assert [candidate.name for candidate in result.candidates] == ["Alpha", "zeta"]
    assert all(candidate.id != "sub_inactive01" for candidate in result.candidates)
    assert all(candidate.id != "sub_orphan0001" for candidate in result.candidates)
    assert "Alpha" in result.output and "zeta" in result.output


def test_grooming_next_casefold_ties_use_id_order_and_repeat_exactly(tmp_path: Path) -> None:
    _write_grooming_fixture(tmp_path)
    for substance_id, name in (("sub_alpha00001", "ALPHA"), ("sub_beta000001", "alpha")):
        path = find_card_path_by_id(tmp_path / "data/substances", substance_id)
        data = cast(dict[str, object], yaml.safe_load(path.read_text()))
        data["name"] = name
        path.write_text(yaml.safe_dump(data, sort_keys=False))

    first = cmd_grooming_next(limit=2, data_root=tmp_path)
    second = cmd_grooming_next(limit=2, data_root=tmp_path)

    first_ids = [candidate.id for candidate in first.candidates]
    second_ids = [candidate.id for candidate in second.candidates]
    assert first.exit_code == second.exit_code == 0
    assert len(first_ids) == len(second_ids) == 2
    assert first_ids == second_ids == sorted(first_ids)


def test_grooming_next_excludes_dated_cards_and_applies_positive_limit(tmp_path: Path) -> None:
    _write_grooming_fixture(tmp_path)
    dated_path = find_card_path_by_id(tmp_path / "data/substances", "sub_alpha00001")
    dated = cast(dict[str, object], yaml.safe_load(dated_path.read_text()))
    dated["semantic_enrichment_attempted_on"] = "2026-08-12"
    dated_path.write_text(yaml.safe_dump(dated, sort_keys=False))

    result = cmd_grooming_next(limit=1, data_root=tmp_path)

    assert result.exit_code == 0
    assert [candidate.id for candidate in result.candidates] == ["sub_beta000001"]


def test_grooming_marker_does_not_change_scheduling_output(tmp_path: Path) -> None:
    _write_grooming_fixture(tmp_path)
    before = plan_in_temp_dir(tmp_path)
    dated_path = find_card_path_by_id(tmp_path / "data/substances", "sub_alpha00001")
    dated = cast(dict[str, object], yaml.safe_load(dated_path.read_text()))
    dated["semantic_enrichment_attempted_on"] = "2026-08-12"
    dated_path.write_text(yaml.safe_dump(dated, sort_keys=False))

    after = plan_in_temp_dir(tmp_path)

    assert before == after
