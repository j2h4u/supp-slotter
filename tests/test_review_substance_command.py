from __future__ import annotations

import shutil
from pathlib import Path

from planner.engine import cmd_review_substance
from tests.helpers import ROOT, run_planner
from tests.planner_fixture import copy_data_tree, find_card_path_by_id


def test_review_substance_prints_grouped_trait_checklist() -> None:
    substance_path = find_card_path_by_id(
        ROOT / "data/substances",
        "sub_3918fe347e",
    )

    result = cmd_review_substance(str(substance_path), data_root=ROOT)

    assert result.exit_code == 0, result.output + result.stderr
    assert "Substance review: L-Citrulline (malate)" in result.output
    assert "\nintake\n" in result.output
    assert "  [x] empty_preferred - Prefers empty stomach" in result.output
    assert "Works or absorbs better away from food" in result.output
    assert "Applies when: Use for amino acids" in result.output
    assert "Slot effects: prefer_strong when food=False; avoid when food=True" in result.output
    assert "mechanism" not in result.output
    assert "no_precursor" not in result.output
    assert "Output: schedule warning" in result.output
    assert "Concerns" in result.output


def test_review_substance_prints_central_relation_matches() -> None:
    substance_path = find_card_path_by_id(
        ROOT / "data/substances",
        "sub_a873e428ee",
    )

    result = cmd_review_substance(str(substance_path), data_root=ROOT)

    assert result.exit_code == 0, result.output + result.stderr
    assert "Central relations from data/relations.yaml (read-only)" in result.output
    assert "Edit these in data/relations.yaml, not in this substance card." in result.output
    assert "Matches this substance by id: sub_a873e428ee" in result.output
    assert "Matches this substance by exact name: Vitamin B6" in result.output
    assert "antagonizes" in result.output
    assert "Vitamin B6 (pyridoxine HCl) -> Levodopa" in result.output
    assert "matched by: source exact id" in result.output


def test_cli_review_substance_prints_result_output() -> None:
    substance_path = find_card_path_by_id(
        ROOT / "data/substances",
        "sub_a873e428ee",
    )

    result = run_planner("review-substance", str(substance_path), root=ROOT)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Substance review: Vitamin B6 (pyridoxine HCl)" in result.stdout
    assert "Central relations from data/relations.yaml (read-only)" in result.stdout


def test_review_substance_rejects_missing_file(tmp_path: Path) -> None:
    copy_data_tree(tmp_path)
    nonexistent = tmp_path / "data" / "substances" / "probe__sub_0000000099.yaml"

    result = run_planner("review-substance", str(nonexistent), root=tmp_path)

    assert result.returncode == 1
    assert "file not found" in result.stderr


def test_review_substance_rejects_path_outside_substances_dir(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    product_path = next((temp_data / "products").glob("*.yaml"))

    result = run_planner("review-substance", str(product_path), root=tmp_path)

    assert result.returncode == 1
    assert "review-substance only accepts paths inside" in result.stderr


def test_review_substance_rejects_non_yaml_suffix(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    probe = temp_data / "substances" / "probe__sub_0000000099.txt"
    probe.write_text("name: Probe\ntraits: []\n")

    result = run_planner("review-substance", str(probe), root=tmp_path)

    assert result.returncode == 1
    assert "review-substance only accepts .yaml files" in result.stderr


def test_review_substance_rejects_empty_traits_file(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    shutil.rmtree(temp_data / "traits")
    traits_dir = temp_data / "traits"
    traits_dir.mkdir()
    (traits_dir / "empty.yaml").write_text("{}\n", encoding="utf-8")
    substance_path = next((temp_data / "substances").glob("*.yaml"))

    result = run_planner("review-substance", str(substance_path), root=tmp_path)

    assert result.returncode == 1
    assert "no traits found" in result.stderr or "data/traits" in result.stderr
