from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]

B_COMPLEX_SUBSTANCES = {
    "vitamin_b1",
    "vitamin_b2",
    "vitamin_b3",
    "vitamin_b5",
    "vitamin_b6",
    "vitamin_b7",
    "vitamin_b9",
    "vitamin_b12",
}

SLOT_FIELDS = {"label", "order", "stack", "near", "food"}
SLOT_NEAR_VALUES = {
    "wake",
    "breakfast",
    "day_meal",
    "sleep",
    "workout_before",
    "workout_after",
}


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


def run_temp_check(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "planner.py", "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def run_repo_plan_preserving_schedule() -> dict:
    schedule_path = ROOT / "schedule.yaml"
    original_schedule = schedule_path.read_bytes()
    try:
        result = subprocess.run(
            ["uv", "run", "planner.py", "plan"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return yaml.safe_load(schedule_path.read_text())
    finally:
        schedule_path.write_bytes(original_schedule)


def load_yaml(path: str) -> object:
    return yaml.safe_load((ROOT / path).read_text())


def load_cards(directory: str) -> dict[str, dict]:
    return {
        path.stem: yaml.safe_load(path.read_text())
        for path in sorted((ROOT / directory).glob("*.yaml"))
    }


def write_split_model_fixture(
    tmp_path: Path,
    *,
    inventory: dict,
    products: dict[str, list[tuple[str, list[str]]]],
    traits: dict,
    substance_prefer_with: dict[str, list[str]] | None = None,
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
        substance = {
            "id": substance_id,
            "name": substance_id.replace("_", " ").title(),
            "traits": trait_ids,
        }
        if substance_prefer_with and substance_id in substance_prefer_with:
            substance["prefer_with"] = substance_prefer_with[substance_id]
        write_yaml(
            tmp_path / "data/substances" / f"{substance_id}.yaml",
            substance,
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


def test_substance_product_inventory_split_data_shape() -> None:
    substances_dir = ROOT / "data/substances"
    substances = load_cards("data/substances")
    products = load_cards("data/products")
    inventory = load_yaml("data/inventory.yaml")["supplements"]
    slots = load_yaml("data/slots.yaml")["slots"]
    traits = load_yaml("data/traits.yaml")["traits"]

    assert substances_dir.is_dir()
    assert substances
    assert all(card["id"] == substance_id for substance_id, card in substances.items())

    for product in products.values():
        assert "traits" not in product
        assert "prefer_with" not in product
        assert product["components"]
        for component in product["components"]:
            assert component["substance"] in substances

    for entry in inventory.values():
        assert "product" in entry
        assert "stack" in entry
        assert entry["product"] in products

    assert {slot["near"] for slot in slots.values()} == SLOT_NEAR_VALUES
    for slot in slots.values():
        assert set(slot) == SLOT_FIELDS

    for trait in traits.values():
        for effect in trait.get("effects") or []:
            assert "time" not in effect.get("match", {})
            assert "activity" not in effect.get("match", {})

    assert substances["creatine"]["prefer_with"] == ["l_citrulline_malate"]
    assert {
        component["substance"]
        for component in products["coenzyme_b_complex"]["components"]
    } == B_COMPLEX_SUBSTANCES
    for substance_id in B_COMPLEX_SUBSTANCES:
        substance_traits = substances[substance_id]["traits"]
        assert "class:b_vitamin" in substance_traits
        assert "effect:energy_like" not in substance_traits
    assert inventory["coenzyme_b_complex"]["traits_override"]["add"] == [
        "intake:prefers_food"
    ]


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


def test_product_formula_ref_validator_rejects_missing_substance(
    tmp_path: Path,
) -> None:
    temp_data = copy_data_tree(tmp_path)
    copy_planner_runtime(tmp_path)
    product_path = temp_data / "products" / "nattokinase.yaml"
    product = yaml.safe_load(product_path.read_text())
    product["components"][0]["substance"] = "bogus_substance_xyz"
    write_yaml(product_path, product)

    result = run_temp_check(tmp_path)

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "bogus_substance_xyz" in combined_output
    assert "references unknown substance" in combined_output


def test_creatine_target_substance_check_accepts_registry_prefer_with() -> None:
    result = subprocess.run(
        ["uv", "run", "planner.py", "check", "data/substances/creatine.yaml"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "All checks passed." in result.stdout
    assert "prefer_with target" not in result.stderr


def test_malformed_inventory_entry_reports_schema_error(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    copy_planner_runtime(tmp_path)
    inventory_path = temp_data / "inventory.yaml"
    inventory = yaml.safe_load(inventory_path.read_text())
    inventory["supplements"]["vitamin_d3"] = "not a supplement mapping"
    write_yaml(inventory_path, inventory)

    result = run_temp_check(tmp_path)

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "supplements" in combined_output
    assert "vitamin_d3" in combined_output
    assert "AttributeError" not in combined_output
    assert "Traceback" not in combined_output


def test_nattokinase_formula_schedules_as_one_product_item() -> None:
    product = load_yaml("data/products/nattokinase.yaml")
    substance = load_yaml("data/substances/nattokinase.yaml")
    inventory = load_yaml("data/inventory.yaml")["supplements"]
    schedule = run_repo_plan_preserving_schedule()

    assert {component["substance"] for component in product["components"]} == {
        "nattokinase",
        "vitamin_b6",
        "vitamin_b12",
    }
    assert "intake:prefers_empty_stomach" in substance["traits"]
    assert "mechanism:fibrinolytic" in substance["traits"]
    assert "risk:fibrinolytic_bleeding" in substance["traits"]

    scheduled_items = {
        item for slot_items in schedule["slots"].values() for item in slot_items
    }
    assert "nattokinase" in scheduled_items
    assert schedule["explanations"]["nattokinase"]["product"] == "nattokinase"
    assert schedule["explanations"]["nattokinase"]["components"] == [
        "nattokinase",
        "vitamin_b6",
        "vitamin_b12",
    ]
    for component_id in ("vitamin_b6", "vitamin_b12"):
        standalone_items = [
            item_id
            for item_id, entry in inventory.items()
            if entry["product"] == component_id
        ]
        if standalone_items:
            assert any(item in scheduled_items for item in standalone_items)
        else:
            assert component_id not in scheduled_items


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


def test_substance_level_prefer_with_awards_colocation_bonus(
    tmp_path: Path,
) -> None:
    write_split_model_fixture(
        tmp_path,
        inventory={
            "creatine": {"product": "creatine_product", "stack": "daily"},
            "l_citrulline_malate": {
                "product": "citrulline_product",
                "stack": "daily",
            },
        },
        products={
            "creatine_product": [("creatine", ["effect:wake"])],
            "citrulline_product": [("l_citrulline_malate", ["effect:wake"])],
        },
        traits={
            "effect:wake": {
                "label": "Wake",
                "description": "Wake preference",
                "applies_when": "Fixture",
                "effects": [{"match": {"near": "wake"}, "level": "prefer_strong"}],
            },
        },
        substance_prefer_with={"creatine": ["l_citrulline_malate"]},
    )

    schedule = run_temp_plan(tmp_path)

    assert schedule["prefer_with_bonus"] == 3
    assert schedule["prefer_with_pairs"] == [
        {
            "pair": ["creatine", "l_citrulline_malate"],
            "co_located": True,
            "slot": schedule["explanations"]["creatine"]["slot"],
        }
    ]
    assert (
        schedule["explanations"]["creatine"]["slot"]
        == schedule["explanations"]["l_citrulline_malate"]["slot"]
    )


def test_ambiguous_substance_level_prefer_with_awards_no_bonus(
    tmp_path: Path,
) -> None:
    write_split_model_fixture(
        tmp_path,
        inventory={
            "creatine": {"product": "creatine_product", "stack": "daily"},
            "citrulline_a": {"product": "citrulline_a_product", "stack": "daily"},
            "citrulline_b": {"product": "citrulline_b_product", "stack": "daily"},
        },
        products={
            "creatine_product": [("creatine", ["effect:wake"])],
            "citrulline_a_product": [("l_citrulline_malate", ["effect:wake"])],
            "citrulline_b_product": [("l_citrulline_malate", ["effect:wake"])],
        },
        traits={
            "effect:wake": {
                "label": "Wake",
                "description": "Wake preference",
                "applies_when": "Fixture",
                "effects": [{"match": {"near": "wake"}, "level": "prefer_strong"}],
            },
        },
        substance_prefer_with={"creatine": ["l_citrulline_malate"]},
    )

    schedule = run_temp_plan(tmp_path)
    ambiguous_warnings = [
        warning
        for warning in schedule["warnings"]
        if warning.get("type") == "ambiguous_prefer_with"
    ]

    assert schedule["prefer_with_bonus"] == 0
    assert schedule["prefer_with_pairs"] == []
    assert ambiguous_warnings == [
        {
            "type": "ambiguous_prefer_with",
            "item": "creatine",
            "product": "creatine_product",
            "source_substance": "creatine",
            "target_substance": "l_citrulline_malate",
            "candidate_items": ["citrulline_a", "citrulline_b"],
            "message": (
                "prefer_with target maps to multiple active inventory items; "
                "no bonus awarded"
            ),
        }
    ]
