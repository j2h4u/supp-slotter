from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]

OPERATOR_USAGE_NOT_PRODUCT_AMOUNT = {
    "magnesium_glycinate": "200 mg × 2/day (= 400 mg elemental Mg)",
    "tadalafil": "1.25 mg",
}

EXPECTED_BRANDS = {
    "acetyl_l_carnitine": "Best Naturals",
    "astaxanthin": "Harmony Aqua",
    "coenzyme_b_complex": "Country Life",
    "copper": "Swanson",
    "creatine": "Do4a",
    "dihydroquercetin_complex": "Eqville",
    "electrolyte_caps": "TiM",
    "glycine": "Geneticlab Nutrition",
    "l_carnitine_l_tartrate": "Primecraft",
    "lions_mane_b6_complex": "Vitamir (Ежовик Комплекс)",
    "magnesium_glycinate": "Vitamir",
    "n_acetyl_cysteine": "Doctor's Best (NAC Detox Regulators)",
    "nattokinase": "Minami Healthy Foods",
    "picamilon": "Фармстандарт",
    "potassium_citrate": "Now",
    "se_methyl_l_selenocysteine": "Life Extension",
    "tadalafil": "Tadalista",
    "trace_minerals": "Life Extension",
    "vitamin_b5": "BioGrace",
    "vitamin_d3": "Futurebiotics",
}

EXPECTED_DOSE_TEXT = {
    "acetyl_l_carnitine": "1000 mg",
    "astaxanthin": "6 mg",
    "copper": "2 mg (Albion bisglycinate)",
    "creatine": "5 g",
    "electrolyte_caps": "1 g/cap",
    "glycine": "1 g",
    "krill_oil": "1 g",
    "l_carnitine_l_tartrate": "530 mg",
    "l_citrulline_malate": "5 g",
    "lions_mane_b6_complex": "150 mg Lion's Mane + 1 mg B6",
    "n_acetyl_cysteine": "600 mg",
    "nattokinase": "13000 FU",
    "picamilon": "50 mg",
    "potassium_citrate": "99 mg elemental K",
    "se_methyl_l_selenocysteine": "200 mcg",
    "vitamin_b5": "15 mg",
    "vitamin_d3": "10000 IU",
}

EXPECTED_STACKS = {
    "daily": {
        "vitamin_d3",
        "vitamin_b5",
        "coenzyme_b_complex",
        "magnesium_glycinate",
        "trace_minerals",
        "potassium_citrate",
        "lions_mane_b6_complex",
        "acetyl_l_carnitine",
        "astaxanthin",
        "nattokinase",
        "tadalafil",
    },
    "training": {
        "electrolyte_caps",
        "l_citrulline_malate",
        "creatine",
        "l_carnitine_l_tartrate",
    },
    "inactive": {
        "lions_mane",
        "picamilon",
        "se_methyl_l_selenocysteine",
        "dihydroquercetin_complex",
        "copper",
        "n_acetyl_cysteine",
        "krill_oil",
        "glycine",
    },
}

EXPECTED_TRAITS_OVERRIDES = {
    "vitamin_d3": {"add": ["risk:dose_monitoring"]},
    "coenzyme_b_complex": {"add": ["intake:prefers_food"]},
    "electrolyte_caps": {
        "add": ["risk:hyperkalemia_med_interaction", "intake:with_water_or_food"]
    },
    "trace_minerals": {"add": ["risk:narrow_therapeutic_window"]},
}


def load_yaml(path: str) -> object:
    return yaml.safe_load((ROOT / path).read_text())


def load_cards(directory: str) -> dict[str, dict]:
    return {
        path.stem: yaml.safe_load(path.read_text())
        for path in sorted((ROOT / directory).glob("*.yaml"))
    }


def product_text(product: dict) -> str:
    values: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, dict):
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(product)
    return "\n".join(values)


def copy_planner_runtime(tmp_path: Path) -> Path:
    temp_data = tmp_path / "data"
    shutil.copytree(ROOT / "data", temp_data)
    shutil.copy2(ROOT / "planner.py", tmp_path / "planner.py")
    shutil.copytree(ROOT / "schema", tmp_path / "schema")
    return temp_data


def test_known_inventory_brands_are_complete_on_product_cards() -> None:
    products = load_cards("data/products")

    assert {
        product_id: products[product_id].get("brand")
        for product_id in EXPECTED_BRANDS
    } == EXPECTED_BRANDS
    assert all(product.get("brand") != "unknown" for product in products.values())


def test_inventory_dose_and_notes_are_routed_before_strip() -> None:
    products = load_cards("data/products")

    for product_id, dose in EXPECTED_DOSE_TEXT.items():
        assert dose in product_text(products[product_id])

    inventory = load_yaml("data/inventory.yaml")
    all_inventory_text = product_text(inventory)
    for dose in OPERATOR_USAGE_NOT_PRODUCT_AMOUNT.values():
        assert dose in all_inventory_text
        assert all(dose not in product_text(product) for product in products.values())


def test_ambiguous_product_amounts_are_not_fabricated() -> None:
    products = load_cards("data/products")

    electrolyte = products["electrolyte_caps"]
    assert electrolyte["brand"] == "TiM"
    assert "1 g/cap" in product_text(electrolyte)
    assert all("amount" not in component for component in electrolyte["components"])

    trace_minerals = products["trace_minerals"]
    assert trace_minerals["brand"] == "Life Extension"
    assert "per-cap weights not enumerated" in product_text(trace_minerals)
    assert all("amount" not in component for component in trace_minerals["components"])

    coenzyme = products["coenzyme_b_complex"]
    assert coenzyme["brand"] == "Country Life"
    assert "dose per cap not labelled granularly" in product_text(coenzyme)
    assert all("amount" not in component for component in coenzyme["components"])


def test_inventory_is_stack_oriented_and_contains_no_product_facts() -> None:
    inventory = load_yaml("data/inventory.yaml")

    assert "supplements" not in inventory
    assert set(inventory["stacks"]) == {"daily", "training", "inactive"}
    assert {
        stack: set(items)
        for stack, items in inventory["stacks"].items()
    } == EXPECTED_STACKS

    for items in inventory["stacks"].values():
        for entry in items.values():
            assert "product" in entry
            assert "stack" not in entry
            assert "brand" not in entry
            assert "dose" not in entry


def test_stack_inventory_preserves_required_traits_overrides() -> None:
    inventory = load_yaml("data/inventory.yaml")
    flattened = {
        item_id: entry
        for items in inventory["stacks"].values()
        for item_id, entry in items.items()
    }

    assert {
        item_id: flattened[item_id]["traits_override"]
        for item_id in EXPECTED_TRAITS_OVERRIDES
    } == EXPECTED_TRAITS_OVERRIDES


def test_refresh_creates_missing_inactive_stack(tmp_path: Path) -> None:
    temp_data = copy_planner_runtime(tmp_path)
    inventory_path = temp_data / "inventory.yaml"
    inventory = yaml.safe_load(inventory_path.read_text())
    inventory["stacks"].pop("inactive")
    inventory_path.write_text(yaml.safe_dump(inventory, sort_keys=False))
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
    refreshed_inventory = yaml.safe_load(inventory_path.read_text())
    assert refreshed_inventory["stacks"]["inactive"]["__refresh_probe__"] == {
        "product": "__refresh_probe__"
    }
    assert "stacks.inactive" in result.stdout


def test_concrete_b6_forms_are_distinct_without_unused_taxonomy() -> None:
    substances = load_cards("data/substances")
    traits = load_yaml("data/traits.yaml")["traits"]

    assert "b6_pyridoxal_5_phosphate" in substances
    assert "b6_pyridoxine_hcl" in substances
    assert substances["b6_pyridoxal_5_phosphate"]["traits"] == []
    assert substances["b6_pyridoxine_hcl"]["traits"] == []
    assert substances["vitamin_b6"]["traits"] == []
    assert "class:b_vitamin" not in traits
    assert all(
        "class:b_vitamin" not in substance.get("traits", [])
        for substance in substances.values()
    )
    assert all(
        "family:vitamin_b6" not in substance.get("traits", [])
        for substance in substances.values()
    )


def test_products_reference_concrete_b6_forms_where_known() -> None:
    products = load_cards("data/products")

    coenzyme_components = {
        component["substance"]: component
        for component in products["coenzyme_b_complex"]["components"]
    }
    lions_mane_components = {
        component["substance"]: component
        for component in products["lions_mane_b6_complex"]["components"]
    }
    nattokinase_components = [
        component["substance"]
        for component in products["nattokinase"]["components"]
    ]

    assert "b6_pyridoxal_5_phosphate" in coenzyme_components
    assert "P-5-P" in coenzyme_components["b6_pyridoxal_5_phosphate"]["label"]
    assert "vitamin_b6" not in coenzyme_components
    assert "b6_pyridoxine_hcl" in lions_mane_components
    assert "pyridoxine hydrochloride" in lions_mane_components["b6_pyridoxine_hcl"]["label"]
    assert "vitamin_b6" not in lions_mane_components
    assert nattokinase_components == ["nattokinase", "vitamin_b6", "vitamin_b12"]
    assert "unmatched_concerns" in products["nattokinase"]
