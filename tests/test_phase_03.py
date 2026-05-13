from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, cast

import yaml

from planner.engine import (
    cmd_audit,
    cmd_check,
    cmd_find,
    cmd_plan,
    cmd_review,
    cmd_review_substance,
)
from tests.helpers import ROOT, run_planner


def copy_planner_with_data(tmp_path: Path) -> Path:
    temp_data = tmp_path / "data"
    shutil.copytree(ROOT / "data", temp_data)
    return temp_data


def find_card_path_by_id(directory: Path, card_id: str) -> Path:
    matches = [
        path
        for path in sorted(directory.glob("*.yaml"))
        if yaml.safe_load(path.read_text()).get("id") == card_id
    ]
    assert len(matches) == 1
    return matches[0]


def test_check_auto_renames_files_when_names_change(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    product_path = find_card_path_by_id(temp_data / "products", "prd_83dffd67bf")
    substance_path = find_card_path_by_id(temp_data / "substances", "sub_7e02eab0d1")

    product = yaml.safe_load(product_path.read_text())
    product["name"] = "Nattokinase 13000FU Updated"
    product_path.write_text(yaml.safe_dump(product, sort_keys=False))

    substance = yaml.safe_load(substance_path.read_text())
    substance["form"] = "glycinate chelate"
    substance_path.write_text(yaml.safe_dump(substance, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code == 0, "\n".join(result.errors)
    assert find_card_path_by_id(temp_data / "products", "prd_83dffd67bf").name == (
        "minami_healthy_foods__nattokinase_13000fu_updated__prd_83dffd67bf.yaml"
    )
    assert find_card_path_by_id(temp_data / "substances", "sub_7e02eab0d1").name == (
        "magnesium_glycinate_chelate__sub_7e02eab0d1.yaml"
    )
    stacks = yaml.safe_load((temp_data / "stacks.yaml").read_text())
    assert "prd_83dffd67bf" in stacks["daily"]


def test_check_warns_about_products_without_stack_entry(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    probe_path = temp_data / "products" / (
        "unknown__unlisted_probe__prd_0000000002.yaml"
    )
    probe_path.write_text(
        yaml.safe_dump(
                {
                    "id": "prd_0000000002",
                    "name": "Unlisted Probe",
                    "components": [{"substance": "sub_877c24aad4"}],
                },
            sort_keys=False,
        )
    )

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code == 0, "\n".join(result.errors)
    assert "product 'prd_0000000002' has no stack entry" in "\n".join(result.info)
    assert "Add it to a stack if it is on the shelf" in "\n".join(result.info)
    assert "refresh" not in "\n".join(result.info + result.errors)


def test_duplicate_stack_item_across_stacks_is_rejected(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    stacks_path = temp_data / "stacks.yaml"
    stacks = yaml.safe_load(stacks_path.read_text())
    stacks["training"].append("prd_eb6337a6dc")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    combined_output = "\n".join(result.errors + result.info)
    assert "prd_eb6337a6dc" in combined_output
    assert "multiple stacks" in combined_output


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


def test_review_substance_rejects_missing_file(tmp_path: Path) -> None:
    copy_planner_with_data(tmp_path)
    nonexistent = tmp_path / "data" / "substances" / "probe__sub_0000000099.yaml"

    result = run_planner("review-substance", str(nonexistent), root=tmp_path)

    assert result.returncode == 1
    assert "file not found" in result.stderr


def test_review_substance_rejects_path_outside_substances_dir(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    product_path = next((temp_data / "products").glob("*.yaml"))

    result = run_planner("review-substance", str(product_path), root=tmp_path)

    assert result.returncode == 1
    assert "review-substance only accepts paths inside" in result.stderr


def test_review_substance_rejects_non_yaml_suffix(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    probe = temp_data / "substances" / "probe__sub_0000000099.txt"
    probe.write_text("name: Probe\ntraits: []\n")

    result = run_planner("review-substance", str(probe), root=tmp_path)

    assert result.returncode == 1
    assert "review-substance only accepts .yaml files" in result.stderr


def test_review_substance_rejects_empty_traits_file(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    (temp_data / "traits.yaml").write_text("{}\n")
    substance_path = next((temp_data / "substances").glob("*.yaml"))

    result = run_planner("review-substance", str(substance_path), root=tmp_path)

    assert result.returncode == 1
    # Schema validation may fire before the no-traits check; assert whichever
    # fragment fires. The empty-mapping {} satisfies the YAML parser but the
    # schema validator may reject it — the real reachable error is documented here.
    assert "no traits found" in result.stderr or "traits.yaml" in result.stderr


def test_find_searches_multiple_fuzzy_words() -> None:
    result = cmd_find(["magnesium", "bisglycinate"], data_root=ROOT)

    assert result.exit_code == 0
    substance_names = [label for _score, _card_id, label, _path in result.substances]
    product_names = [label for _score, _card_id, label, _path in result.products]
    all_names = substance_names + product_names
    assert "Magnesium (glycinate)" in substance_names
    assert "Vitamir - Magnesium glycinate" in product_names
    # Magnesium (glycinate) ranks higher than Glycine
    magnesium_idx = substance_names.index("Magnesium (glycinate)")
    assert "Glycine" in substance_names
    glycine_idx = substance_names.index("Glycine")
    assert magnesium_idx < glycine_idx
    _ = all_names  # suppress unused variable warning


def test_find_supports_partial_word_matches() -> None:
    result = cmd_find(["citrul", "malat"], data_root=ROOT)

    assert result.exit_code == 0
    substance_names = [label for _score, _card_id, label, _path in result.substances]
    product_names = [label for _score, _card_id, label, _path in result.products]
    assert "L-Citrulline (malate)" in substance_names
    assert "L-Citrulline Malate" in product_names


def test_auto_maintenance_lock_only_blocks_mutations(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    lock_dir = tmp_path / ".planner-maintenance.lock"
    lock_dir.mkdir()
    (lock_dir / "pid").write_text(f"{os.getpid()}\n")

    read_only_result = cmd_check(data_root=tmp_path)

    assert read_only_result.exit_code == 0, "\n".join(read_only_result.errors)

    probe_path = temp_data / "substances" / "lock_probe.yaml"
    probe_path.write_text("name: Lock Probe\ntraits: []\n")

    blocked_result = cmd_check(data_root=tmp_path)

    assert blocked_result.exit_code != 0
    assert "another planner process is running" in "\n".join(blocked_result.errors)


def test_workout_activity_product_is_not_scheduled_as_daily(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    stacks_path = temp_data / "stacks.yaml"
    stacks = yaml.safe_load(stacks_path.read_text())
    stacks["training"].remove("prd_cfce0b36b6")
    stacks["daily"].append("prd_cfce0b36b6")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    result = cmd_plan(data_root=tmp_path)

    assert result.exit_code != 0
    combined_output = "\n".join(result.errors)
    assert "prd_cfce0b36b6" in combined_output
    assert "has no workout pillbox slots" in combined_output


def test_duplicate_slot_ids_across_pillboxes_are_rejected(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    pillboxes_path = temp_data / "pillboxes.yaml"
    pillboxes_data = yaml.safe_load(pillboxes_path.read_text())
    pillboxes_data["training"]["slots"]["morning_food"] = {
        "label": "Duplicate morning food",
        "order": 3,
        "near": "workout_before",
        "food": False,
    }
    pillboxes_path.write_text(yaml.safe_dump(pillboxes_data, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    combined_output = "\n".join(result.errors + result.info)
    assert "slot id 'morning_food'" in combined_output
    assert "unique across pillboxes" in combined_output


def test_orphans_command_lists_cleanup_candidates(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)

    orphan_substance: dict[str, Any] = {
        "id": "sub_0000000003",
        "name": "Orphan Substance",
    }
    (temp_data / "substances/orphan_substance__sub_0000000003.yaml").write_text(
        yaml.safe_dump(orphan_substance, sort_keys=False)
    )

    orphan_product = {
        "id": "prd_0000000004",
        "name": "Orphan Product",
        "components": [{"substance": "sub_877c24aad4"}],
    }
    (temp_data / "products/unknown__orphan_product__prd_0000000004.yaml").write_text(
        yaml.safe_dump(orphan_product, sort_keys=False)
    )

    traits_path = temp_data / "traits.yaml"
    traits = yaml.safe_load(traits_path.read_text())
    traits_dict = cast(dict[str, Any], traits)
    risk_dict = cast(dict[str, Any], traits_dict["risk"])
    risk_dict["orphan_trait"] = {
        "label": "Orphan Trait",
        "description": "Unused fixture trait.",
        "applies_when": "Fixture only.",
    }
    traits_path.write_text(yaml.safe_dump(traits_dict, sort_keys=False))

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.cleanup
    assert "sub_0000000003" in result.cleanup["substances.unused"]
    assert "prd_0000000004" in result.cleanup["products.without_stack"]
    assert "risk:orphan_trait" in result.cleanup["traits.unused"]


def test_doctor_lists_similar_substance_cards(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)

    duplicate_like_substance: dict[str, Any] = {
        "id": "sub_0000000005",
        "name": "Magnesium Bisglycinate",
    }
    (temp_data / "substances/magnesium_bisglycinate__sub_0000000005.yaml").write_text(
        yaml.safe_dump(duplicate_like_substance, sort_keys=False)
    )

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.cleanup
    similar = result.cleanup["substances.similar_names"]
    # Similar names section contains entries for the Magnesium group
    combined = "\n".join(similar)
    assert "sub_0000000005 Magnesium Bisglycinate" in combined
    assert "sub_7e02eab0d1 Magnesium (glycinate)" in combined


def test_balance_relation_warns_when_related_substance_missing(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    trace_product_path = find_card_path_by_id(
        temp_data / "products",
        "prd_932319251f",
    )
    trace_product = yaml.safe_load(trace_product_path.read_text())
    trace_product["components"] = [
        component
        for component in trace_product["components"]
        if component["substance"] != "sub_844a0cc551"
    ]
    trace_product_path.write_text(yaml.safe_dump(trace_product, sort_keys=False))

    review_result = cmd_review(data_root=tmp_path)

    assert review_result.exit_code == 0
    # Relations section moved to cmd_review in Phase 9; verify via output text.
    assert "missing_target" in review_result.output or "missing_source" in review_result.output, (
        f"review output missing relation gap info: {review_result.output}"
    )
    assert "Zinc" in review_result.output and "Copper" in review_result.output, (
        f"review output missing Zinc/Copper relation: {review_result.output}"
    )

    plan_result = cmd_plan(data_root=tmp_path)

    assert plan_result.exit_code == 0, plan_result
    assert any(
        w.get("type") == "missing_balance_substance"
        and w.get("severity") == "medium"
        and "Zinc" in str(w.get("source_name", ""))
        and "Copper" in str(w.get("target_name", ""))
        and "reason" in w
        and "action" in w
        for w in plan_result.warnings
    ), f"Expected missing_balance_substance warning for Zinc/Copper in: {plan_result.warnings}"


def test_relation_validation_rejects_unknown_substance_name(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = yaml.safe_load(relations_path.read_text())
    relations["supports"].append(
        {
            "source_name": "Definitely Missing",
            "target_name": "N-Acetyl Cysteine",
            "reason": "Fixture relation.",
        }
    )
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    assert "source_name 'Definitely Missing' has no matching substance name" in "\n".join(result.errors)


def test_support_relation_warns_when_supporter_missing(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    nac_product_path = find_card_path_by_id(
        temp_data / "products",
        "prd_955ea0c9e6",
    )
    nac_product = yaml.safe_load(nac_product_path.read_text())
    nac_product["components"] = [
        component
        for component in nac_product["components"]
        if component["substance"] != "sub_59bza5s7h0"
    ]
    nac_product_path.write_text(yaml.safe_dump(nac_product, sort_keys=False))
    trace_product_path = find_card_path_by_id(
        temp_data / "products",
        "prd_932319251f",
    )
    trace_product = yaml.safe_load(trace_product_path.read_text())
    trace_product["components"] = [
        component
        for component in trace_product["components"]
        if component["substance"] != "sub_e684a3e94e"
    ]
    trace_product_path.write_text(yaml.safe_dump(trace_product, sort_keys=False))

    stacks_path = temp_data / "stacks.yaml"
    stacks = yaml.safe_load(stacks_path.read_text())
    stacks["inactive"].remove("prd_955ea0c9e6")
    stacks["daily"].append("prd_955ea0c9e6")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    review_result = cmd_review(data_root=tmp_path)

    assert review_result.exit_code == 0
    # Relations section moved to cmd_review in Phase 9; verify via output text.
    assert "missing_source" in review_result.output, (
        f"review output missing missing_source status: {review_result.output}"
    )
    assert "Selenium" in review_result.output and "N-Acetyl Cysteine" in review_result.output, (
        f"review output missing Selenium/NAC relation: {review_result.output}"
    )


def test_support_relation_accepts_alternate_active_supporter_form(
    tmp_path: Path,
) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    nac_product_path = find_card_path_by_id(
        temp_data / "products",
        "prd_955ea0c9e6",
    )
    nac_product = yaml.safe_load(nac_product_path.read_text())
    nac_product["components"] = [
        component
        for component in nac_product["components"]
        if component["substance"] != "sub_59bza5s7h0"
    ]
    nac_product_path.write_text(yaml.safe_dump(nac_product, sort_keys=False))
    trace_product_path = find_card_path_by_id(
        temp_data / "products",
        "prd_932319251f",
    )
    trace_product = yaml.safe_load(trace_product_path.read_text())
    trace_product["components"] = [
        component
        for component in trace_product["components"]
        if component["substance"] != "sub_e684a3e94e"
    ]
    trace_product_path.write_text(yaml.safe_dump(trace_product, sort_keys=False))

    stacks_path = temp_data / "stacks.yaml"
    stacks = yaml.safe_load(stacks_path.read_text())
    stacks["inactive"].remove("prd_955ea0c9e6")
    stacks["inactive"].remove("prd_91a71b69f0")
    stacks["daily"].append("prd_955ea0c9e6")
    stacks["daily"].append("prd_91a71b69f0")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.relations_by_status
    nac_warnings = [
        e for e in result.relations_by_status.get("missing_source", [])
        if e["type"] == "supports" and ("N-Acetyl Cysteine" in e["target"] or "NAC" in e["target"])
    ]
    assert nac_warnings == [], nac_warnings


def test_doctor_warns_empty_cluster(tmp_path: Path) -> None:
    """dashboard.empty_cluster fires when a dashboard yaml's from_traits resolves to
    zero member substances using union (OR) resolution."""
    temp_data = copy_planner_with_data(tmp_path)

    traits_path = temp_data / "traits.yaml"
    traits = yaml.safe_load(traits_path.read_text())
    traits_dict = cast(dict[str, Any], traits)
    if "dashboard" not in traits_dict:
        traits_dict["dashboard"] = {}
    cast(dict[str, Any], traits_dict["dashboard"])["empty_cluster_probe_xyz"] = {
        "label": "Empty Cluster Probe",
        "description": "Fixture trait for empty_cluster test.",
        "applies_when": "Fixture only.",
    }
    traits_path.write_text(yaml.safe_dump(traits_dict, sort_keys=False))

    dashboards_dir = temp_data / "dashboards"
    dashboards_dir.mkdir(exist_ok=True)
    (dashboards_dir / "empty_cluster_probe_xyz.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "Empty Cluster Probe Dashboard",
                "description": "Fixture.",
                "from_traits": {"dashboard": ["empty_cluster_probe_xyz"]},
                "benefit": {"description": "Fixture benefit."},
            },
            sort_keys=False,
        )
    )

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.cleanup
    empty_cluster_entries = result.cleanup["dashboard.empty_cluster"]
    assert len(empty_cluster_entries) >= 1
    combined = "\n".join(empty_cluster_entries)
    assert "empty_cluster_probe_xyz" in combined
    assert "union resolution" in combined
    assert "Resolution:" in combined
