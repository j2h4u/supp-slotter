from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def copy_data_tree(tmp_path: Path) -> Path:
    temp_data = tmp_path / "data"
    shutil.copytree(ROOT / "data", temp_data)
    return temp_data


def copy_planner_runtime(tmp_path: Path) -> None:
    shutil.copy2(ROOT / "planner.py", tmp_path / "planner.py")
    shutil.copytree(ROOT / "schema", tmp_path / "schema")


def write_yaml(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def run_temp_plan(tmp_path: Path) -> dict:
    result = subprocess.run(
        ["uv", "run", "planner.py", "plan"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    return yaml.safe_load((tmp_path / "schedule.yaml").read_text())


def write_split_model_fixture(
    tmp_path: Path,
    *,
    inventory: dict,
    products: dict[str, list[tuple[str, list[str]]]],
    traits: dict,
) -> None:
    copy_planner_runtime(tmp_path)
    write_yaml(
        tmp_path / "data/slots.yaml",
        {
            "version": 1,
            "slots": {
                "morning_empty": {
                    "label": "Morning empty",
                    "order": 1,
                    "stack": "daily",
                    "near": "wake",
                    "food": False,
                },
                "day_empty": {
                    "label": "Day empty",
                    "order": 2,
                    "stack": "daily",
                    "near": "day_meal",
                    "food": False,
                },
            },
        },
    )
    write_yaml(tmp_path / "data/traits.yaml", {"version": 1, "traits": traits})
    write_yaml(tmp_path / "data/inventory.yaml", {"version": 1, "supplements": inventory})
    for substance_id, trait_ids in {
        component_id: trait_ids
        for component_ids in products.values()
        for component_id, trait_ids in component_ids
    }.items():
        write_yaml(
            tmp_path / "data/substances" / f"{substance_id}.yaml",
            {
                "id": substance_id,
                "name": substance_id.replace("_", " ").title(),
                "traits": trait_ids,
            },
        )
    for product_id, component_ids in products.items():
        write_yaml(
            tmp_path / "data/products" / f"{product_id}.yaml",
            {
                "id": product_id,
                "name": product_id.replace("_", " ").title(),
                "components": [
                    {"substance": component_id}
                    for component_id, _trait_ids in component_ids
                ],
            },
        )


def test_refresh_adds_missing_product_formula_to_temp_inventory(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    copy_planner_runtime(tmp_path)
    probe_path = temp_data / "products" / "__refresh_probe__.yaml"
    probe_path.write_text(
        yaml.safe_dump(
            {
                "id": "__refresh_probe__",
                "name": "Refresh Probe",
                "components": [{"substance": "nattokinase"}],
            },
            sort_keys=False,
        )
    )

    result = subprocess.run(
        ["uv", "run", "planner.py", "refresh"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    inventory = yaml.safe_load((temp_data / "inventory.yaml").read_text())
    assert inventory["supplements"]["__refresh_probe__"] == {
        "product": "__refresh_probe__",
        "stack": "inactive",
    }
    assert not (ROOT / "data/products/__refresh_probe__.yaml").exists()
    assert "__refresh_probe__" not in (ROOT / "data/inventory.yaml").read_text()


def test_intra_product_separate_from_conflict_warns_without_splitting(
    tmp_path: Path,
) -> None:
    write_split_model_fixture(
        tmp_path,
        inventory={
            "combo_item": {"product": "combo_item", "stack": "daily"},
        },
        products={
            "combo_item": [
                ("alpha_substance", ["effect:alpha"]),
                ("beta_substance", ["effect:beta"]),
            ],
        },
        traits={
            "effect:alpha": {
                "label": "Alpha",
                "description": "Alpha trait",
                "applies_when": "Fixture",
                "separate_from": ["effect:beta"],
            },
            "effect:beta": {
                "label": "Beta",
                "description": "Beta trait",
                "applies_when": "Fixture",
            },
        },
    )

    schedule = run_temp_plan(tmp_path)
    scheduled_items = {
        item for slot_items in schedule["slots"].values() for item in slot_items
    }
    conflict_warnings = [
        warning
        for warning in schedule["warnings"]
        if warning.get("type") == "intra_product_trait_conflict"
    ]

    assert scheduled_items == {"combo_item"}
    assert schedule["explanations"]["combo_item"]["product"] == "combo_item"
    assert schedule["explanations"]["combo_item"]["components"] == [
        "alpha_substance",
        "beta_substance",
    ]
    assert conflict_warnings == [
        {
            "type": "intra_product_trait_conflict",
            "item": "combo_item",
            "product": "combo_item",
            "trait": "effect:alpha",
            "conflicts_with": "effect:beta",
            "substances": ["alpha_substance"],
            "conflicting_substances": ["beta_substance"],
            "message": (
                "Component traits conflict inside one physical product; "
                "scheduling keeps the product together and emits this warning"
            ),
        }
    ]


def test_inter_product_separate_from_conflict_still_blocks_colocation(
    tmp_path: Path,
) -> None:
    write_split_model_fixture(
        tmp_path,
        inventory={
            "alpha_item": {"product": "alpha_product", "stack": "daily"},
            "beta_item": {"product": "beta_product", "stack": "daily"},
        },
        products={
            "alpha_product": [("alpha_substance", ["effect:alpha"])],
            "beta_product": [("beta_substance", ["effect:beta"])],
        },
        traits={
            "effect:alpha": {
                "label": "Alpha",
                "description": "Alpha trait",
                "applies_when": "Fixture",
                "separate_from": ["effect:beta"],
                "effects": [
                    {"match": {"near": "wake"}, "level": "prefer_strong"},
                ],
            },
            "effect:beta": {
                "label": "Beta",
                "description": "Beta trait",
                "applies_when": "Fixture",
                "effects": [
                    {"match": {"near": "wake"}, "level": "prefer_strong"},
                ],
            },
        },
    )

    schedule = run_temp_plan(tmp_path)
    colocated_pairs = [
        set(slot_items)
        for slot_items in schedule["slots"].values()
        if {"alpha_item", "beta_item"}.issubset(slot_items)
    ]

    assert colocated_pairs == []
    assert {item for items in schedule["slots"].values() for item in items} == {
        "alpha_item",
        "beta_item",
    }
