from __future__ import annotations

import os
from pathlib import Path

import yaml

from planner.engine import cmd_check, cmd_plan
from tests.planner_fixture import copy_data_tree, find_card_path_by_id


def test_check_auto_renames_files_when_names_change(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
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
    temp_data = copy_data_tree(tmp_path)
    probe_path = temp_data / "products" / ("unknown__unlisted_probe__prd_0000000002.yaml")
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


def test_duplicate_stack_item_across_stacks_is_rejected(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    stacks_path = temp_data / "stacks.yaml"
    stacks = yaml.safe_load(stacks_path.read_text())
    stacks["training"].append("prd_eb6337a6dc")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    combined_output = "\n".join(result.errors + result.info)
    assert "prd_eb6337a6dc" in combined_output
    assert "multiple stacks" in combined_output


def test_auto_maintenance_lock_only_blocks_mutations(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
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
    temp_data = copy_data_tree(tmp_path)
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
    temp_data = copy_data_tree(tmp_path)
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
