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

SLOT_FIELDS = {"label", "order", "near", "food"}
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
    return {"stacks": stacks}


def flatten_inventory_stacks(inventory: dict) -> dict:
    return {
        product_id: {"product": product_id, "stack": stack}
        for stack, items in inventory["stacks"].items()
        for product_id in items
    }


def flatten_schedule_slots(schedule: dict) -> dict:
    return {
        slot_name: slot_entry
        for pillbox in schedule["pillboxes"].values()
        for slot_name, slot_entry in pillbox["slots"].items()
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


def format_product_name(product: dict) -> str:
    brand = product.get("brand")
    name = product["name"]
    return f"{brand} - {name}" if brand and brand != "unknown" else name


def write_split_model_fixture(
    tmp_path: Path,
    *,
    inventory: dict,
    products: dict[str, list[tuple[str, list[str]]]],
    traits: dict,
    substance_prefer_with: dict[str, list[str]] | None = None,
    substance_relations: dict[str, list[dict]] | None = None,
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
        tmp_path / "data/pillboxes.yaml",
        {
            "pillboxes": {
                "daily_pillbox": {
                    "label": "Daily pillbox",
                    "inventory_stack": "daily",
                    "slots": {
                        "morning_empty": {
                            "label": "Morning empty",
                            "order": 1,
                            "near": "wake",
                            "food": False,
                        },
                        "day_empty": {
                            "label": "Day empty",
                            "order": 2,
                            "near": "day_meal",
                            "food": False,
                        },
                    },
                },
            },
        },
    )
    write_yaml(tmp_path / "data/traits.yaml", {"traits": traits})
    write_yaml(tmp_path / "data/inventory.yaml", stack_inventory(normalized_inventory))
    relation_groups = {
        "balance": [],
        "supports": [],
        "competes": [],
        "antagonizes": [],
    }
    for source_id, relations in (substance_relations or {}).items():
        for relation in relations:
            relation_type = relation["type"]
            if relation_type not in relation_groups:
                continue
            for target in relation.get("substances", []):
                relation_groups[relation_type].append(
                    {
                        "source_substance": substance_ids[source_id],
                        "target_substance": substance_ids.get(target, target),
                        "reason": relation["reason"],
                    }
                )
    write_yaml(tmp_path / "data/relations.yaml", relation_groups)
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
    pillboxes = load_yaml("data/pillboxes.yaml")["pillboxes"]
    slots = {
        slot_name: slot_entry
        for pillbox in pillboxes.values()
        for slot_name, slot_entry in pillbox["slots"].items()
    }
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
    assert not any(trait_id.startswith("competition:") for trait_id in traits)
    assert not any(
        trait_id.startswith("competition:")
        for substance in substances.values()
        for trait_id in substance.get("traits", [])
    )


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
    assert "{check,plan,doctor,find,review-substance}" in result.stdout
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
    product_name = format_product_name(product)

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
    bleeding_load = load_yaml("data/goals/bleeding_load.yaml")
    assert "sub_877c24aad4" in {
        member["substance"] for member in bleeding_load["members"]
    }

    scheduled_items = {
        item
        for slot_entry in flatten_schedule_slots(schedule).values()
        for item in slot_entry["products"]
    }
    assert product_name in scheduled_items
    assert schedule["explanations"][product_name][
        "components"
    ] == [
        "Nattokinase",
        "Eicosapentaenoic acid",
        "Ginkgo biloba",
        "Red yeast rice",
        "Vitamin E (tocopherol)",
        "Vitamin B3 (niacin)",
        "Vitamin B1 (thiamine)",
        "Vitamin B6 (pyridoxine HCl)",
        "Vitamin B12 (methylcobalamin)",
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
    combo_name = "Combo Item"
    scheduled_items = {
        item
        for slot_entry in flatten_schedule_slots(schedule).values()
        for item in slot_entry["products"]
    }
    conflict_warnings = [
        warning
        for warning in schedule["warnings"]
        if warning.get("category") == "Timing conflict inside one product"
    ]

    assert scheduled_items == {combo_name}
    assert schedule["explanations"][combo_name]["components"] == [
        "Alpha Substance",
        "Beta Substance",
    ]
    assert conflict_warnings == [
        {
            "category": "Timing conflict inside one product",
            "product": combo_name,
            "concern": "alpha",
            "note": (
                "Component traits conflict inside one physical product; "
                "scheduling keeps the product together and emits this warning"
            ),
            "action": "Review this product manually; its components have conflicting timing preferences.",
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
    alpha_name = "Alpha Product"
    beta_name = "Beta Product"
    colocated_pairs = [
        set(slot_entry["products"])
        for slot_entry in flatten_schedule_slots(schedule).values()
        if {alpha_name, beta_name}.issubset(slot_entry["products"])
    ]

    assert colocated_pairs == []
    assert {
        item
        for slot_entry in flatten_schedule_slots(schedule).values()
        for item in slot_entry["products"]
    } == {
        alpha_name,
        beta_name,
    }


def test_inter_product_absorption_relation_blocks_colocation(
    tmp_path: Path,
) -> None:
    write_split_model_fixture(
        tmp_path,
        inventory={
            "zinc_product": {"stack": "daily"},
            "copper_product": {"stack": "daily"},
        },
        products={
            "zinc_product": [("zinc_substance", ["effect:wake"])],
            "copper_product": [("copper_substance", ["effect:wake"])],
        },
        traits={
            "effect:wake": {
                "label": "Wake",
                "description": "Wake preference",
                "applies_when": "Fixture",
                "effects": [
                    {"match": {"near": "wake"}, "level": "prefer_strong"},
                ],
            },
        },
        substance_relations={
            "zinc_substance": [
                {
                    "type": "competes",
                    "substances": ["copper_substance"],
                    "reason": "Fixture absorption conflict.",
                }
            ],
            "copper_substance": [
                {
                    "type": "competes",
                    "substances": ["zinc_substance"],
                    "reason": "Fixture absorption conflict.",
                }
            ],
        },
    )

    schedule = run_temp_plan(tmp_path)
    zinc_product = fixture_id("prd", "zinc_product")
    copper_product = fixture_id("prd", "copper_product")
    colocated_pairs = [
        set(slot_entry["products"])
        for slot_entry in flatten_schedule_slots(schedule).values()
        if {zinc_product, copper_product}.issubset(slot_entry["products"])
    ]

    assert colocated_pairs == []


def test_intra_product_absorption_relation_warns_without_splitting(
    tmp_path: Path,
) -> None:
    write_split_model_fixture(
        tmp_path,
        inventory={
            "trace_product": {"product": "trace_product", "stack": "daily"},
        },
        products={
            "trace_product": [
                ("zinc_substance", []),
                ("copper_substance", []),
            ],
        },
        traits={
            "effect:neutral": {
                "label": "Neutral",
                "description": "Fixture neutral trait",
                "applies_when": "Fixture",
            },
        },
        substance_relations={
            "zinc_substance": [
                {
                    "type": "competes",
                    "substances": ["copper_substance"],
                    "reason": "Fixture absorption conflict.",
                }
            ],
            "copper_substance": [
                {
                    "type": "competes",
                    "substances": ["zinc_substance"],
                    "reason": "Fixture absorption conflict.",
                }
            ],
        },
    )

    schedule = run_temp_plan(tmp_path)
    trace_product = fixture_id("prd", "trace_product")
    zinc_substance = fixture_id("sub", "zinc_substance")
    copper_substance = fixture_id("sub", "copper_substance")
    conflict_warnings = [
        warning
        for warning in schedule["warnings"]
        if warning.get("category") == "Component conflict inside one product"
    ]

    assert conflict_warnings == [
        {
            "category": "Component conflict inside one product",
            "product": "Trace Product",
            "source": "Zinc Substance",
            "target": "Copper Substance",
            "concern": "competes",
            "note": (
                "Component relation conflicts inside one physical product; "
                "scheduling keeps the product together and emits this warning"
            ),
            "action": (
                "Review this product manually; competing components are inside one "
                "physical product and cannot be separated by scheduling."
            ),
        }
    ]


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
    creatine_product = "Sub 9C0908E7F7"
    citrulline_product = "Sub 3918Fe347E"

    assert schedule["kept_together"] == [
        {
            "pair": sorted([citrulline_product, creatine_product], key=str.casefold),
            "together": True,
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
        if warning.get("category") == "Companion product is ambiguous"
    ]

    assert schedule["kept_together"] == []
    assert ambiguous_warnings == [
        {
            "category": "Companion product is ambiguous",
            "product": "Sub 9C0908E7F7",
            "source": "Sub 9C0908E7F7",
            "target": "Sub 3918Fe347E",
            "concern": "ambiguous prefer with",
            "note": (
                "prefer_with target maps to multiple active inventory items; "
                "no bonus awarded"
            ),
            "action": "Choose the intended companion product before relying on co-location.",
        }
    ]
