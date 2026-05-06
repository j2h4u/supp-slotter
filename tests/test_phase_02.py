from __future__ import annotations

import shutil
import subprocess
import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]

B_COMPLEX_SUBSTANCES = {
    "sub_230c5c820e",
    "sub_67fc2be8aa",
    "sub_e9e80d003a",
    "sub_7628e4f478",
    "sub_799419116d",
    "sub_fd899525d3",
    "sub_d0034bd130",
    "sub_157418854b",
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


def fixture_id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:10]}"


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


def stack_inventory(inventory: dict) -> dict:
    stacks = {"daily": [], "training": [], "inactive": []}
    for item_id, entry in inventory.items():
        stacks[entry["stack"]].append(item_id)
    return {"version": 1, "stacks": stacks}


def flatten_inventory_stacks(inventory: dict) -> dict:
    return {
        product_id: {"product": product_id, "stack": stack}
        for stack, items in inventory["stacks"].items()
        for product_id in items
    }


def load_cards(directory: str) -> dict[str, dict]:
    cards: dict[str, dict] = {}
    for path in sorted((ROOT / directory).glob("*.yaml")):
        card = yaml.safe_load(path.read_text())
        cards[card["id"]] = card
    return cards


def find_card_path_by_id(directory: Path, card_id: str) -> Path:
    matches = [
        path
        for path in sorted(directory.glob("*.yaml"))
        if yaml.safe_load(path.read_text()).get("id") == card_id
    ]
    assert len(matches) == 1
    return matches[0]


def write_split_model_fixture(
    tmp_path: Path,
    *,
    inventory: dict,
    products: dict[str, list[tuple[str, list[str]]]],
    traits: dict,
    substance_prefer_with: dict[str, list[str]] | None = None,
) -> None:
    copy_planner_runtime(tmp_path)
    substance_ids = {
        component_id: component_id
        if component_id.startswith("sub_") and len(component_id) == 14
        else fixture_id("sub", component_id)
        for component_ids in products.values()
        for component_id, _trait_ids in component_ids
    }
    product_ids = {
        product_id: product_id
        if product_id.startswith("prd_") and len(product_id) == 14
        else fixture_id("prd", product_id)
        for product_id in products
    }
    normalized_inventory = {
        product_ids.get(item_id, item_id): {
            **entry,
            "product": product_ids.get(entry.get("product", item_id), entry.get("product", item_id)),
        }
        for item_id, entry in inventory.items()
    }
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
    write_yaml(tmp_path / "data/inventory.yaml", stack_inventory(normalized_inventory))
    for substance_id, trait_ids in {
        component_id: trait_ids
        for component_ids in products.values()
        for component_id, trait_ids in component_ids
    }.items():
        normalized_substance_id = substance_ids[substance_id]
        substance = {
            "id": normalized_substance_id,
            "name": substance_id.replace("_", " ").title(),
            "traits": trait_ids,
        }
        if substance_prefer_with and substance_id in substance_prefer_with:
            substance["prefer_with"] = [
                substance_ids.get(target, target)
                for target in substance_prefer_with[substance_id]
            ]
        write_yaml(
            tmp_path / "data/substances" / f"{substance_id}__{normalized_substance_id}.yaml",
            substance,
        )
    for product_id, component_ids in products.items():
        normalized_product_id = product_ids[product_id]
        write_yaml(
            tmp_path / "data/products" / f"unknown__{product_id}__{normalized_product_id}.yaml",
            {
                "id": normalized_product_id,
                "name": product_id.replace("_", " ").title(),
                "components": [
                    {"substance": substance_ids[component_id]}
                    for component_id, _trait_ids in component_ids
                ],
            },
        )


def test_substance_product_inventory_split_data_shape() -> None:
    substances_dir = ROOT / "data/substances"
    substances = load_cards("data/substances")
    products = load_cards("data/products")
    inventory_data = load_yaml("data/inventory.yaml")
    inventory = flatten_inventory_stacks(inventory_data)
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
        assert "brand" not in entry
        assert "dose" not in entry
        assert entry["product"] in products

    assert {slot["near"] for slot in slots.values()} == SLOT_NEAR_VALUES
    for slot in slots.values():
        assert set(slot) == SLOT_FIELDS

    for trait in traits.values():
        for effect in trait.get("effects") or []:
            assert "time" not in effect.get("match", {})
            assert "activity" not in effect.get("match", {})

    assert substances["sub_9c0908e7f7"]["prefer_with"] == ["sub_3918fe347e"]
    assert substances["sub_d997f98e03"]["aliases"] == ["NAC"]
    assert substances["sub_66b783576c"]["aliases"] == ["EPA"]
    assert {
        component["substance"]
        for component in products[
            "prd_bb212cffc2"
        ]["components"]
    } == B_COMPLEX_SUBSTANCES
    for substance_id in B_COMPLEX_SUBSTANCES:
        substance_traits = substances[substance_id]["traits"]
        assert "effect:energy_like" not in substance_traits
    assert "class:b_vitamin" not in traits


def test_cli_help_exposes_simple_agent_commands(tmp_path: Path) -> None:
    copy_planner_runtime(tmp_path)

    result = subprocess.run(
        ["uv", "run", "planner.py", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "{check,plan,doctor}" in result.stdout
    assert "refresh" not in result.stdout
    assert "normalize" not in result.stdout
    assert "orphans" not in result.stdout


def test_product_formula_ref_validator_rejects_missing_substance(
    tmp_path: Path,
) -> None:
    temp_data = copy_data_tree(tmp_path)
    copy_planner_runtime(tmp_path)
    product_path = find_card_path_by_id(
        temp_data / "products",
        "prd_83dffd67bf",
    )
    product = yaml.safe_load(product_path.read_text())
    product["components"][0]["substance"] = "bogus_substance_xyz"
    write_yaml(product_path, product)

    result = run_temp_check(tmp_path)

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "bogus_substance_xyz" in combined_output
    assert "references unknown substance" in combined_output


def test_product_schema_accepts_description_urls(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    copy_planner_runtime(tmp_path)
    product_path = find_card_path_by_id(
        temp_data / "products",
        "prd_83dffd67bf",
    )
    product = yaml.safe_load(product_path.read_text())
    product["urls"] = ["https://example.com/minami-sub_877c24aad4"]
    write_yaml(product_path, product)

    result = run_temp_check(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr


def test_creatine_target_substance_check_accepts_registry_prefer_with() -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "planner.py",
            "check",
            str(find_card_path_by_id(ROOT / "data/substances", "sub_9c0908e7f7")),
        ],
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
    inventory["stacks"]["daily"][0] = {"product": "sub_2476bf9d4b"}
    write_yaml(inventory_path, inventory)

    result = run_temp_check(tmp_path)

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "stacks" in combined_output
    assert "sub_2476bf9d4b" in combined_output
    assert "AttributeError" not in combined_output
    assert "Traceback" not in combined_output


def test_sub_877c24aad4_formula_schedules_as_one_product_item() -> None:
    product = yaml.safe_load(
        find_card_path_by_id(
            ROOT / "data/products",
            "prd_83dffd67bf",
        ).read_text()
    )
    substance = yaml.safe_load(
        find_card_path_by_id(ROOT / "data/substances", "sub_877c24aad4").read_text()
    )
    inventory = flatten_inventory_stacks(load_yaml("data/inventory.yaml"))
    schedule = run_repo_plan_preserving_schedule()

    assert {component["substance"] for component in product["components"]} == {
        "sub_877c24aad4",
        "sub_66b783576c",
        "sub_45587454c0",
        "sub_c36e075c09",
        "sub_844a87d72b",
        "sub_e9e80d003a",
        "sub_230c5c820e",
        "sub_a873e428ee",
        "sub_157418854b",
    }
    assert "intake:empty_preferred" in substance["traits"]
    assert "mechanism:fibrinolytic" in substance["traits"]
    assert "risk:fibrinolytic_bleeding" in substance["traits"]

    scheduled_items = {
        item
        for slot_entry in schedule["slots"].values()
        for item in slot_entry["products"]
    }
    assert "prd_83dffd67bf" in scheduled_items
    assert (
        schedule["explanations"]["prd_83dffd67bf"]["product"]
        == "prd_83dffd67bf"
    )
    assert schedule["explanations"]["prd_83dffd67bf"][
        "components"
    ] == [
        "sub_877c24aad4",
        "sub_66b783576c",
        "sub_45587454c0",
        "sub_c36e075c09",
        "sub_844a87d72b",
        "sub_e9e80d003a",
        "sub_230c5c820e",
        "sub_a873e428ee",
        "sub_157418854b",
    ]
    for component_id in (
        "sub_66b783576c",
        "sub_45587454c0",
        "sub_c36e075c09",
        "sub_844a87d72b",
        "sub_e9e80d003a",
        "sub_230c5c820e",
        "sub_a873e428ee",
        "sub_157418854b",
    ):
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
    combo_item = fixture_id("prd", "combo_item")
    alpha_substance = fixture_id("sub", "alpha_substance")
    beta_substance = fixture_id("sub", "beta_substance")
    scheduled_items = {
        item
        for slot_entry in schedule["slots"].values()
        for item in slot_entry["products"]
    }
    conflict_warnings = [
        warning
        for warning in schedule["warnings"]
        if warning.get("type") == "intra_product_trait_conflict"
    ]

    assert scheduled_items == {combo_item}
    assert schedule["explanations"][combo_item]["product"] == combo_item
    assert schedule["explanations"][combo_item]["components"] == [
        alpha_substance,
        beta_substance,
    ]
    assert conflict_warnings == [
        {
            "type": "intra_product_trait_conflict",
            "item": combo_item,
            "product": combo_item,
            "trait": "effect:alpha",
            "conflicts_with": "effect:beta",
            "substances": [alpha_substance],
            "conflicting_substances": [beta_substance],
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
            "alpha_product": {"stack": "daily"},
            "beta_product": {"stack": "daily"},
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
    alpha_product = fixture_id("prd", "alpha_product")
    beta_product = fixture_id("prd", "beta_product")
    colocated_pairs = [
        set(slot_entry["products"])
        for slot_entry in schedule["slots"].values()
        if {alpha_product, beta_product}.issubset(slot_entry["products"])
    ]

    assert colocated_pairs == []
    assert {
        item
        for slot_entry in schedule["slots"].values()
        for item in slot_entry["products"]
    } == {
        alpha_product,
        beta_product,
    }


def test_substance_level_prefer_with_awards_colocation_bonus(
    tmp_path: Path,
) -> None:
    write_split_model_fixture(
        tmp_path,
        inventory={
            "sub_9c0908e7f7": {"stack": "daily"},
            "sub_3918fe347e": {"stack": "daily"},
        },
        products={
            "sub_9c0908e7f7": [("sub_9c0908e7f7", ["effect:wake"])],
            "sub_3918fe347e": [("sub_3918fe347e", ["effect:wake"])],
        },
        traits={
            "effect:wake": {
                "label": "Wake",
                "description": "Wake preference",
                "applies_when": "Fixture",
                "effects": [{"match": {"near": "wake"}, "level": "prefer_strong"}],
            },
        },
        substance_prefer_with={"sub_9c0908e7f7": ["sub_3918fe347e"]},
    )

    schedule = run_temp_plan(tmp_path)
    creatine_product = fixture_id("prd", "sub_9c0908e7f7")
    citrulline_product = fixture_id("prd", "sub_3918fe347e")

    assert schedule["prefer_with_bonus"] == 3
    assert schedule["prefer_with_pairs"] == [
        {
            "pair": sorted([citrulline_product, creatine_product]),
            "co_located": True,
            "slot": schedule["explanations"][creatine_product]["slot"],
        }
    ]
    assert (
        schedule["explanations"][creatine_product]["slot"]
        == schedule["explanations"][citrulline_product]["slot"]
    )


def test_ambiguous_substance_level_prefer_with_awards_no_bonus(
    tmp_path: Path,
) -> None:
    write_split_model_fixture(
        tmp_path,
        inventory={
            "sub_9c0908e7f7": {"stack": "daily"},
            "citrulline_a": {"stack": "daily"},
            "citrulline_b": {"stack": "daily"},
        },
        products={
            "sub_9c0908e7f7": [("sub_9c0908e7f7", ["effect:wake"])],
            "citrulline_a": [("sub_3918fe347e", ["effect:wake"])],
            "citrulline_b": [("sub_3918fe347e", ["effect:wake"])],
        },
        traits={
            "effect:wake": {
                "label": "Wake",
                "description": "Wake preference",
                "applies_when": "Fixture",
                "effects": [{"match": {"near": "wake"}, "level": "prefer_strong"}],
            },
        },
        substance_prefer_with={"sub_9c0908e7f7": ["sub_3918fe347e"]},
    )

    schedule = run_temp_plan(tmp_path)
    creatine_product = fixture_id("prd", "sub_9c0908e7f7")
    citrulline_a = fixture_id("prd", "citrulline_a")
    citrulline_b = fixture_id("prd", "citrulline_b")
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
            "item": creatine_product,
            "product": creatine_product,
            "source_substance": "sub_9c0908e7f7",
            "target_substance": "sub_3918fe347e",
            "candidate_items": sorted([citrulline_a, citrulline_b]),
            "message": (
                "prefer_with target maps to multiple active inventory items; "
                "no bonus awarded"
            ),
        }
    ]
