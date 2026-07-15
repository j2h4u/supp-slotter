from __future__ import annotations

import os
from pathlib import Path
from typing import NotRequired, TypedDict, cast

import pytest
import yaml
from planner.engine import cmd_check, cmd_plan
from planner.engine.plan import _failed_search_plan_result

from tests.planner_fixture import PlannerFixtureInput, find_card_path_by_id, write_minimal_planner_fixture


class _ProductComponent(TypedDict):
    substance: str


class _ProductCard(TypedDict):
    components: list[_ProductComponent]
    name: NotRequired[str]


class _PillboxSlot(TypedDict):
    label: str
    order: int
    near: str
    food: bool


class _Pillbox(TypedDict):
    slots: dict[str, _PillboxSlot]


StackItem = str | dict[str, str]
Stacks = dict[str, list[StackItem]]


def _write_phase_fixture(tmp_path: Path) -> Path:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={
                "prd_aaa0000001": {"stack": "daily"},
                "prd_bbb0000002": {"stack": "training"},
            },
            products={
                "prd_aaa0000001": [("sub_aaa0000001", ["timing:wake"])],
                "prd_bbb0000002": [("sub_bbb0000002", ["activity:workout"])],
            },
            traits={
                "timing:wake": {
                    "label": "Wake",
                    "description": "Fixture wake timing.",
                    "applies_when": "Fixture only.",
                    "effects": [{"match": {"near": "wake"}, "level": "prefer"}],
                },
                "activity:workout": {
                    "label": "Workout",
                    "description": "Fixture workout activity.",
                    "applies_when": "Fixture only.",
                    "effects": [{"match": {"near": "workout_before"}, "level": "prefer"}],
                },
            },
        ),
    )
    return tmp_path / "data"


def test_check_auto_renames_files_when_names_change(tmp_path: Path) -> None:
    temp_data = _write_phase_fixture(tmp_path)
    product_path = find_card_path_by_id(temp_data / "products", "prd_aaa0000001")
    substance_path = find_card_path_by_id(temp_data / "substances", "sub_aaa0000001")

    product = cast(_ProductCard, yaml.safe_load(product_path.read_text()))
    product["name"] = "Daily Probe Updated"
    product_path.write_text(yaml.safe_dump(product, sort_keys=False))

    substance = cast(dict[str, object], yaml.safe_load(substance_path.read_text()))
    substance["form"] = "updated form"
    substance_path.write_text(yaml.safe_dump(substance, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code == 0, "\n".join(result.errors)
    assert find_card_path_by_id(temp_data / "products", "prd_aaa0000001").name == (
        "unknown__daily_probe_updated__prd_aaa0000001.yaml"
    )
    assert find_card_path_by_id(temp_data / "substances", "sub_aaa0000001").name == (
        "sub_aaa0000001_updated_form__sub_aaa0000001.yaml"
    )
    stacks = cast(Stacks, yaml.safe_load((temp_data / "stacks.yaml").read_text()))
    assert "prd_aaa0000001" in stacks["daily"]


def test_check_warns_about_products_without_stack_entry(tmp_path: Path) -> None:
    temp_data = _write_phase_fixture(tmp_path)
    probe_path = temp_data / "products" / ("unknown__unlisted_probe__prd_0000000002.yaml")
    probe_path.write_text(
        yaml.safe_dump(
            {
                "id": "prd_0000000002",
                "name": "Unlisted Probe",
                "components": [{"substance": "sub_aaa0000001"}],
            },
            sort_keys=False,
        )
    )

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code == 0, "\n".join(result.errors)
    assert "product 'prd_0000000002' has no stack entry" in "\n".join(result.info)
    assert "Add it to `inactive` if it is still on the shelf" in "\n".join(result.info)
    assert "outside stacks intentionally" in "\n".join(result.info)


def test_duplicate_stack_item_across_stacks_is_rejected(tmp_path: Path) -> None:
    temp_data = _write_phase_fixture(tmp_path)
    stacks_path = temp_data / "stacks.yaml"
    stacks = cast(Stacks, yaml.safe_load(stacks_path.read_text()))
    stacks["training"].append("prd_aaa0000001")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    combined_output = "\n".join(result.errors + result.info)
    assert "prd_aaa0000001" in combined_output
    assert "multiple stacks" in combined_output


def test_auto_maintenance_lock_only_blocks_mutations(tmp_path: Path) -> None:
    temp_data = _write_phase_fixture(tmp_path)
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


def test_workout_activity_is_inert_without_workout_slots(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    temp_data = _write_phase_fixture(tmp_path)
    stacks_path = temp_data / "stacks.yaml"
    stacks = cast(Stacks, yaml.safe_load(stacks_path.read_text()))
    stacks["training"].remove("prd_bbb0000002")
    stacks["daily"].append("prd_bbb0000002")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    result = cmd_plan(data_root=tmp_path)
    captured = capsys.readouterr()

    assert result.exit_code == 0, "\n".join(result.errors)
    assert result.schedule_written is True
    assert result.errors == []
    assert result.warnings == []
    assert result.slot_loads == {
        "daily.morning_empty": 1,
        "daily.day_empty": 1,
        "training.pre_workout": 0,
        "training.post_workout": 0,
    }
    assert (
        captured.err.count(
            "plan: stack item 'prd_bbb0000002' activity activity:any_workout "
            "inactive_by_capability (stack 'daily' has no workout slots)."
        )
        == 1
    )

    schedule = yaml.safe_load((tmp_path / "schedule.yaml").read_text())
    daily_products = {
        product
        for slot in schedule["pillboxes"]["daily"]["slots"].values()
        for product in slot["products"]
    }
    training_products = {
        product
        for slot in schedule["pillboxes"]["training"]["slots"].values()
        for product in slot["products"]
    }
    assert "Prd Bbb0000002" in daily_products
    assert "Prd Bbb0000002" not in training_products


def test_duplicate_slot_ids_across_pillboxes_are_rejected(tmp_path: Path) -> None:
    temp_data = _write_phase_fixture(tmp_path)
    pillboxes_path = temp_data / "pillboxes.yaml"
    pillboxes_data = cast(dict[str, _Pillbox], yaml.safe_load(pillboxes_path.read_text()))
    pillboxes_data["training"]["slots"]["morning_empty"] = {
        "label": "Duplicate morning food",
        "order": 3,
        "near": "workout_before",
        "food": False,
    }
    pillboxes_path.write_text(yaml.safe_dump(pillboxes_data, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    combined_output = "\n".join(result.errors + result.info)
    assert "slot id 'morning_empty'" in combined_output
    assert "unique across pillboxes" in combined_output


def test_failed_search_plan_result_lists_tight_items(capsys: pytest.CaptureFixture[str]) -> None:
    errors: list[str] = []

    result = _failed_search_plan_result(
        errors,
        {
            "blocked_item": [],
            "tight_item": [("morning_empty", 10, ["fixture reason"])],
            "flexible_item": [
                ("morning_empty", 10, ["fixture reason"]),
                ("breakfast", 5, ["fixture reason"]),
            ],
        },
    )

    captured = capsys.readouterr()
    assert result.exit_code == 1
    assert result.errors == errors
    assert "plan: items with" in captured.err
    assert "blocked_item: (none)" in captured.err
    assert "tight_item: morning_empty" in captured.err
    assert "flexible_item" not in captured.err
    assert "no valid global assignment" in captured.err
