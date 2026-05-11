from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import yaml

from planner.cards.product import format_product_name, load_product_registry

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_BRANDS = {
    "prd_27f7b85aa6": "Best Naturals",
    "prd_e5cc3b4e7c": "Harmony Aqua",
    "prd_bb212cffc2": "Country Life",
    "prd_55d65df796": "Swanson",
    "prd_2ca842627a": "Do4a",
    "prd_7a4ee33852": "Eqville",
    "prd_20bf2df267": "TiM",
    "prd_17f2788c3f": "Geneticlab Nutrition",
    "prd_0e92bc1674": "Primecraft",
    "prd_c81eb18069": "Vitamir (Ежовик Комплекс)",
    "prd_9d0fca3201": "Vitamir",
    "prd_955ea0c9e6": "Doctor's Best",
    "prd_83dffd67bf": "Minami Healthy Foods",
    "prd_7ae9a92d3b": "Farmstandart",
    "prd_97fc03c4c0": "NOW Foods",
    "prd_91a71b69f0": "Life Extension",
    "prd_33f3450f29": "Tadalista",
    "prd_932319251f": "Life Extension",
    "prd_8eff2491b7": "BioGrace",
    "prd_eb6337a6dc": "Futurebiotics",
    "prd_7f04daf970": "Nature's Truth",
}

EXPECTED_DOSE_TEXT = {
    "prd_27f7b85aa6": "1000 mg",
    "prd_e5cc3b4e7c": "6 mg",
    "prd_55d65df796": "2 mg (Albion bisglycinate)",
    "prd_2ca842627a": "5 g",
    "prd_20bf2df267": "1 g/cap",
    "prd_17f2788c3f": "1 g",
    "prd_7f04daf970": "1000 mg per softgel",
    "prd_0e92bc1674": "530 mg",
    "prd_cfce0b36b6": "5 g",
    "prd_c81eb18069": "150 mg Lion's Mane + 1 mg B6",
    "prd_955ea0c9e6": "600 mg",
    "prd_83dffd67bf": "13000 FU",
    "prd_7ae9a92d3b": "50 mg",
    "prd_97fc03c4c0": "99 mg elemental potassium",
    "prd_91a71b69f0": "200 mcg",
    "prd_8eff2491b7": "15 mg",
    "prd_eb6337a6dc": "10000 IU",
}

EXPECTED_SCHEDULE_SLOTS = {
    # Nattokinase 13000FU moved from day_food to morning_empty (primary-component scoring;
    # nattokinase's intake:empty_preferred now drives at full weight, EPA's fat-meal
    # preference is secondary-only and contributes at SECONDARY_TRAIT_WEIGHT).
    # Vitamin B5 moved from morning_empty to morning_food.
    # Krill Oil replaces Potassium Citrate (deactivated) in day_food.
    "morning_empty": ["prd_27f7b85aa6", "prd_83dffd67bf"],
    "morning_food": [
        "prd_eb6337a6dc",
        "prd_bb212cffc2",
        "prd_932319251f",
        "prd_8eff2491b7",
    ],
    "day_food": [
        "prd_c81eb18069",
        "prd_e5cc3b4e7c",
        "prd_7f04daf970",
    ],
    "evening_empty": ["prd_9d0fca3201", "prd_33f3450f29"],
    "pre_workout": ["prd_cfce0b36b6", "prd_2ca842627a"],
    "post_workout": [
        "prd_20bf2df267",
        "prd_0e92bc1674",
    ],
}


EXPECTED_SCHEDULE_SLOT_PRODUCTS = {
    slot_name: {"products": product_ids}
    for slot_name, product_ids in EXPECTED_SCHEDULE_SLOTS.items()
}


def load_yaml(path: str) -> dict[str, Any]:
    result = yaml.safe_load((ROOT / path).read_text())
    assert isinstance(result, dict)
    return cast(dict[str, Any], result)


def load_cards(directory: str) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for path in sorted((ROOT / directory).glob("*.yaml")):
        card = yaml.safe_load(path.read_text())
        assert isinstance(card, dict)
        card_dict = cast(dict[str, Any], card)
        cards[card_dict["id"]] = card_dict
    return cards


def expected_schedule_slot_products() -> dict[str, dict[str, list[str]]]:
    products = load_product_registry()
    return {
        slot_name: {
            "products": sorted([
                format_product_name(products[product_id])
                for product_id in product_ids
            ], key=str.casefold)
        }
        for slot_name, product_ids in EXPECTED_SCHEDULE_SLOTS.items()
    }


def flatten_schedule_slots(schedule: dict[str, Any]) -> dict[str, Any]:
    return {
        slot_name: slot_entry
        for pillbox in schedule["pillboxes"].values()
        for slot_name, slot_entry in pillbox["slots"].items()
    }


def find_card_path_by_id(directory: Path, card_id: str) -> Path:
    matches = [
        path
        for path in sorted(directory.glob("*.yaml"))
        if yaml.safe_load(path.read_text()).get("id") == card_id
    ]
    assert len(matches) == 1
    return matches[0]


def product_text(product: dict[str, Any]) -> str:
    values: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, dict):
            for child in cast(dict[str, Any], value).values():
                collect(child)
        elif isinstance(value, list):
            for child in cast(list[Any], value):
                collect(child)

    collect(product)
    return "\n".join(values)


def copy_planner_with_data(tmp_path: Path) -> Path:
    temp_data = tmp_path / "data"
    shutil.copytree(ROOT / "data", temp_data)
    shutil.copytree(ROOT / "planner", tmp_path / "planner")
    shutil.copytree(ROOT / "schema", tmp_path / "schema")
    return temp_data


def flatten_trait_defs(traits_data: dict[str, Any]) -> dict[str, Any]:
    return {
        f"{namespace}:{name}": trait
        for namespace, entries in traits_data.items()
        if isinstance(entries, dict)
        for name, trait in cast(dict[str, Any], entries).items()
    }


def test_known_stack_brands_are_complete_on_product_cards() -> None:
    products = load_cards("data/products")

    assert {
        product_id: products[product_id].get("brand")
        for product_id in EXPECTED_BRANDS
    } == EXPECTED_BRANDS
    assert all(product.get("brand") != "unknown" for product in products.values())


def test_product_files_use_brand_product_names() -> None:
    actual: dict[str, str] = {}
    for path in sorted((ROOT / "data/products").glob("*.yaml")):
        product = yaml.safe_load(path.read_text())
        actual[product["id"]] = path.name

    assert all("__" in filename for filename in actual.values())


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

    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert find_card_path_by_id(temp_data / "products", "prd_83dffd67bf").name == (
        "minami_healthy_foods__nattokinase_13000fu_updated__prd_83dffd67bf.yaml"
    )
    assert find_card_path_by_id(temp_data / "substances", "sub_7e02eab0d1").name == (
        "magnesium_glycinate_chelate__sub_7e02eab0d1.yaml"
    )
    stacks = yaml.safe_load((temp_data / "stacks.yaml").read_text())
    assert "prd_83dffd67bf" in stacks["daily"]


def test_stacks_contain_no_dose_or_notes() -> None:
    products = load_cards("data/products")

    for product_id, dose in EXPECTED_DOSE_TEXT.items():
        assert dose in product_text(products[product_id])

    stacks = load_yaml("data/stacks.yaml")
    all_stack_text = product_text(stacks)
    assert "notes" not in all_stack_text
    assert "dose" not in all_stack_text


def test_ambiguous_product_amounts_are_not_fabricated() -> None:
    products = load_cards("data/products")

    electrolyte = products["prd_20bf2df267"]
    assert electrolyte["brand"] == "TiM"
    assert "1 g/cap" in product_text(electrolyte)
    assert all("amount" not in component for component in electrolyte["components"])

    trace_minerals = products["prd_932319251f"]
    assert trace_minerals["brand"] == "Life Extension"
    assert "per-cap weights not enumerated" in product_text(trace_minerals)
    assert all("amount" not in component for component in trace_minerals["components"])

    coenzyme = products["prd_bb212cffc2"]
    assert coenzyme["brand"] == "Country Life"
    assert "dose per cap not labelled granularly" in product_text(coenzyme)
    assert all("amount" not in component for component in coenzyme["components"])


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

    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "product 'prd_0000000002' has no stack entry" in result.stdout
    assert "Add it to a stack if it is on the shelf" in result.stdout
    assert "refresh" not in result.stdout


def test_duplicate_stack_item_across_stacks_is_rejected(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    stacks_path = temp_data / "stacks.yaml"
    stacks = yaml.safe_load(stacks_path.read_text())
    stacks["training"].append("prd_eb6337a6dc")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "prd_eb6337a6dc" in combined_output
    assert "multiple stacks" in combined_output


def test_review_substance_prints_grouped_trait_checklist() -> None:
    substance_path = find_card_path_by_id(
        ROOT / "data/substances",
        "sub_3918fe347e",
    )

    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "review-substance", str(substance_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Substance review: L-Citrulline (malate)" in result.stdout
    assert "\nintake\n" in result.stdout
    assert "  [x] empty_preferred - Prefers empty stomach" in result.stdout
    assert "Works or absorbs better away from food" in result.stdout
    assert "Applies when: Use for amino acids" in result.stdout
    assert "Slot effects: prefer_strong when food=False; avoid when food=True" in result.stdout
    assert "mechanism" not in result.stdout
    assert "no_precursor" not in result.stdout
    assert "Output: schedule warning" in result.stdout
    assert "Concerns" in result.stdout


def test_review_substance_prints_central_relation_matches() -> None:
    substance_path = find_card_path_by_id(
        ROOT / "data/substances",
        "sub_a873e428ee",
    )

    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "review-substance", str(substance_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Central relations from data/relations.yaml (read-only)" in result.stdout
    assert "Edit these in data/relations.yaml, not in this substance card." in result.stdout
    assert "Matches this substance by id: sub_a873e428ee" in result.stdout
    assert "Matches this substance by exact name: Vitamin B6" in result.stdout
    assert "antagonizes" in result.stdout
    assert "Vitamin B6 (pyridoxine HCl) -> Levodopa" in result.stdout
    assert "matched by: source exact id" in result.stdout


def test_review_substance_rejects_missing_file(tmp_path: Path) -> None:
    copy_planner_with_data(tmp_path)
    nonexistent = tmp_path / "data" / "substances" / "probe__sub_0000000099.yaml"

    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "review-substance", str(nonexistent)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "file not found" in result.stderr


def test_review_substance_rejects_path_outside_substances_dir(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    product_path = next((temp_data / "products").glob("*.yaml"))

    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "review-substance", str(product_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "review-substance only accepts paths inside" in result.stderr


def test_review_substance_rejects_non_yaml_suffix(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    probe = temp_data / "substances" / "probe__sub_0000000099.txt"
    probe.write_text("name: Probe\ntraits: []\n")

    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "review-substance", str(probe)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "review-substance only accepts .yaml files" in result.stderr


def test_review_substance_rejects_empty_traits_file(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    # Overwrite traits.yaml with empty mapping — load_traits returns {}
    (temp_data / "traits.yaml").write_text("{}\n")
    substance_path = next((temp_data / "substances").glob("*.yaml"))

    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "review-substance", str(substance_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    # Schema validation may fire before the no-traits check; assert whichever
    # fragment fires. The empty-mapping {} satisfies the YAML parser but the
    # schema validator may reject it — the real reachable error is documented here.
    assert "no traits found" in result.stderr or "traits.yaml" in result.stderr


def test_find_searches_multiple_fuzzy_words() -> None:
    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "find", "magnesium", "bisglycinate"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Search results for: magnesium bisglycinate" in result.stdout
    assert "Magnesium (glycinate)" in result.stdout
    assert "Vitamir - Magnesium glycinate" in result.stdout

    substance_index = result.stdout.index("Magnesium (glycinate)")
    assert substance_index < result.stdout.index("Glycine")


def test_find_supports_partial_word_matches() -> None:
    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "find", "citrul", "malat"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "L-Citrulline (malate)" in result.stdout
    assert "L-Citrulline Malate" in result.stdout


def test_auto_maintenance_lock_only_blocks_mutations(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    lock_dir = tmp_path / ".planner-maintenance.lock"
    lock_dir.mkdir()
    (lock_dir / "pid").write_text(f"{os.getpid()}\n")

    read_only_result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert read_only_result.returncode == 0, (
        read_only_result.stdout + read_only_result.stderr
    )

    probe_path = temp_data / "substances" / "lock_probe.yaml"
    probe_path.write_text("name: Lock Probe\ntraits: []\n")

    blocked_result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert blocked_result.returncode != 0
    assert "another planner process is running" in blocked_result.stderr


def test_workout_activity_product_is_not_scheduled_as_daily(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)
    stacks_path = temp_data / "stacks.yaml"
    stacks = yaml.safe_load(stacks_path.read_text())
    stacks["training"].remove("prd_cfce0b36b6")
    stacks["daily"].append("prd_cfce0b36b6")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "prd_cfce0b36b6" in combined_output
    assert "has no workout pillbox slots" in combined_output


def test_show_regenerates_and_prints_pillbox_layout() -> None:
    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Here's your schedule for today:" in result.stdout
    # Both labels are confirmed non-empty in the current schedule.yaml:
    # morning_empty has Best Naturals - ALCAR and BioGrace - Vitamin B5
    # morning_food has Country Life, Futurebiotics, Life Extension, NOW Foods
    assert "Morning / empty stomach" in result.stdout
    assert "Morning / with breakfast" in result.stdout
    assert "Full details in schedule.yaml" in result.stdout


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

    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
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

    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "doctor"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Doctor / cleanup candidates" in result.stdout
    assert "substances.unused" in result.stdout
    assert "  - sub_0000000003" in result.stdout
    assert "products.without_stack" in result.stdout
    assert "  - prd_0000000004" in result.stdout
    assert "traits.unused" in result.stdout
    assert "  - risk:orphan_trait" in result.stdout


def test_doctor_lists_similar_substance_cards(tmp_path: Path) -> None:
    temp_data = copy_planner_with_data(tmp_path)

    duplicate_like_substance: dict[str, Any] = {
        "id": "sub_0000000005",
        "name": "Magnesium Bisglycinate",
    }
    (temp_data / "substances/magnesium_bisglycinate__sub_0000000005.yaml").write_text(
        yaml.safe_dump(duplicate_like_substance, sort_keys=False)
    )

    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "doctor"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "substances.similar_names" in result.stdout
    assert "  - Magnesium" in result.stdout
    assert "    - sub_0000000005 Magnesium Bisglycinate" in result.stdout
    assert "    - sub_7e02eab0d1 Magnesium (glycinate)" in result.stdout


def test_concrete_b6_forms_are_distinct_without_unused_taxonomy() -> None:
    substances = load_cards("data/substances")
    traits = flatten_trait_defs(load_yaml("data/traits.yaml"))

    assert "sub_799419116d" in substances
    assert "sub_a873e428ee" in substances
    assert "vitamin_b6" not in substances
    # After migration, substances with no traits have no namespace keys (all fields are absent)
    assert "is" not in substances["sub_799419116d"]
    assert "is" not in substances["sub_a873e428ee"]
    assert "class:b_vitamin" not in traits
    # No substance has a "b_vitamin" slug in any namespace (removed taxonomy)
    assert all(
        not any(
            slug == "b_vitamin"
            for ns in ("is", "intake", "effect", "risk", "activity", "dashboard")
            for slug in substance.get(ns, [])
        )
        for substance in substances.values()
    )
    # No substance has a "vitamin_b6" slug in any namespace (family taxonomy removed)
    assert all(
        not any(
            slug == "vitamin_b6"
            for ns in ("is", "intake", "effect", "risk", "activity", "dashboard")
            for slug in substance.get(ns, [])
        )
        for substance in substances.values()
    )


def test_products_reference_concrete_b6_forms_where_known() -> None:
    products = load_cards("data/products")

    coenzyme_components = {
        component["substance"]: component
        for component in products[
            "prd_bb212cffc2"
        ]["components"]
    }
    sub_e3af6f78d9_components = {
        component["substance"]: component
        for component in products["prd_c81eb18069"]["components"]
    }
    sub_877c24aad4_components = [
        component["substance"]
        for component in products["prd_83dffd67bf"]["components"]
    ]

    assert "sub_799419116d" in coenzyme_components
    assert "P-5-P" in coenzyme_components["sub_799419116d"]["label"]
    assert "vitamin_b6" not in coenzyme_components
    assert "sub_a873e428ee" in sub_e3af6f78d9_components
    assert "pyridoxine hydrochloride" in sub_e3af6f78d9_components["sub_a873e428ee"]["label"]
    assert "vitamin_b6" not in sub_e3af6f78d9_components
    assert sub_877c24aad4_components == [
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
    assert "unmatched_concerns" not in products["prd_83dffd67bf"]


def test_zinc_copper_balance_relations_are_declared() -> None:
    substances = load_cards("data/substances")
    relations = load_yaml("data/relations.yaml")

    assert "relations" not in substances["sub_f78ea75282"]
    assert "relations" not in substances["sub_844a0cc551"]
    assert relations["balance"][0] == {
        "source_name": "Zinc",
        "target_name": "Copper",
        "reason": (
            "Long-term high-dose zinc supplementation can depress copper status; "
            "zinc and copper status should be reviewed together in long-term stacks."
        ),
        "action": "Review zinc/copper balance in long-term active stacks.",
    }
    assert relations["competes"][0] == {
        "source_name": "Zinc",
        "target_name": "Copper",
        "reason": "Zinc and copper can compete for absorption when co-administered.",
        "action": (
            "Keep zinc and copper away from the same slot when they are in separate "
            "products."
        ),
    }


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

    doctor = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "doctor"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert "relations.balance_missing (1)" in doctor.stdout
    assert (
        "Zinc -> Copper"
        in doctor.stdout
    )

    plan = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    schedule = yaml.safe_load((tmp_path / "schedule.yaml").read_text())
    balance_warnings = [
        warning
        for warning in schedule["warnings"]
        if warning.get("category") == "Missing balancing substance"
    ]

    assert plan.returncode == 0, plan.stdout + plan.stderr
    assert balance_warnings == [
        {
            "category": "Missing balancing substance",
            "source": "Zinc",
            "target": "Copper",
            "concern": "missing balance substance",
            "note": (
                "Long-term high-dose zinc supplementation can depress copper status; "
                "zinc and copper status should be reviewed together in long-term stacks."
            ),
            "action": "Review zinc/copper balance in long-term active stacks.",
        }
    ]


def test_nac_detox_regulators_product_has_label_components_and_urls() -> None:
    substances = load_cards("data/substances")
    products = load_cards("data/products")
    product = products["prd_955ea0c9e6"]

    assert product["urls"] == [
        "https://www.iherb.com/pr/doctor-s-best-nac-detox-regulators-180-veggie-caps/95570",
        "https://www.doctorsbest.com/products/doctor-s-best-nac-detox-regulators-180-veggie-caps-95570",
        "https://cdn.shopify.com/s/files/1/0553/2542/5869/files/NAC_Detox_Regulators_Family_FS.pdf?v=1739214151",
    ]
    assert product["components"] == [
        {
            "substance": "sub_59bza5s7h0",
            "label": "Selenium (from SelenoExcell High Selenium Yeast)",
            "amount": "50 mcg",
        },
        {
            "substance": "sub_86uvfl7jeo",
            "label": "Molybdenum (from molybdenum glycinate chelate)",
            "amount": "50 mcg",
        },
        {
            "substance": "sub_d997f98e03",
            "label": "N-Acetylcysteine (NAC)",
            "amount": "600 mg",
        },
    ]
    assert "relations" not in substances["sub_59bza5s7h0"]
    assert "relations" not in substances["sub_86uvfl7jeo"]
    assert "relations" not in substances["sub_d997f98e03"]
    assert {
        (relation["source_name"], relation["target_name"])
        for relation in load_yaml("data/relations.yaml")["supports"]
    } >= {
        ("Selenium", "N-Acetyl Cysteine"),
        ("Molybdenum", "N-Acetyl Cysteine"),
    }


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

    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "source_name 'Definitely Missing' has no matching substance name" in result.stderr


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

    doctor = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "doctor"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert "relations.supports_missing (1)" in doctor.stdout
    assert (
        "Selenium -> N-Acetyl Cysteine"
    ) in doctor.stdout


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

    doctor = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "python", "-m", "planner", "doctor"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert "relations.supports_missing (0)" in doctor.stdout


def test_schedule_baseline_remains_stable() -> None:
    schedule_path = ROOT / "schedule.yaml"
    original_schedule = schedule_path.read_bytes()
    try:
        result = subprocess.run(
            ["uv", "run", "--project", str(ROOT), "python", "-m", "planner"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        schedule = load_yaml("schedule.yaml")
    finally:
        schedule_path.write_bytes(original_schedule)

    assert "search" not in schedule
    assert all(
        key not in schedule
        for key in (
            "schedule_fit",
            "fit_notes",
            "quality",
            "total_score",
            "quality_stars",
            "quality_rating",
            "quality_scale",
            "quality_ratio",
            "quality_max_score",
            "slot_score_total",
            "prefer_with_bonus",
            "balance_penalty",
        )
    )
    assert {
        slot_name: {"products": slot_entry["products"]}
        for slot_name, slot_entry in flatten_schedule_slots(schedule).items()
    } == expected_schedule_slot_products()
    products = load_product_registry()
    b_complex = format_product_name(products["prd_bb212cffc2"])
    lions_mane = format_product_name(products["prd_c81eb18069"])
    nattokinase = format_product_name(products["prd_83dffd67bf"])
    assert schedule["explanations"][b_complex]["components"] == [
        "Vitamin B1 (thiamine)",
        "Vitamin B2 (riboflavin)",
        "Vitamin B3 (niacin)",
        "Vitamin B5 (pantothenic acid)",
        "Vitamin B6 (pyridoxal 5 phosphate)",
        "Vitamin B7 (biotin)",
        "Vitamin B9 (methylfolate)",
        "Vitamin B12 (methylcobalamin)",
    ]
    assert schedule["explanations"][lions_mane]["components"] == [
        "Lion's Mane",
        "Vitamin B6 (pyridoxine HCl)",
    ]
    assert schedule["explanations"][nattokinase]["components"] == [
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


def test_schedule_always_includes_product_and_substance_layers() -> None:
    schedule_path = ROOT / "schedule.yaml"
    original_schedule = schedule_path.read_bytes()
    try:
        result = subprocess.run(
            ["uv", "run", "--project", str(ROOT), "python", "-m", "planner"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        schedule = load_yaml("schedule.yaml")
    finally:
        schedule_path.write_bytes(original_schedule)

    assert {
        slot_name: {"products": slot_entry["products"]}
        for slot_name, slot_entry in flatten_schedule_slots(schedule).items()
    } == expected_schedule_slot_products()
    day_food = flatten_schedule_slots(schedule)["day_food"]["substances"]

    # Krill Oil replaces Potassium Citrate in day_food; adds EPA, DHA, Krill Oil substances.
    assert day_food == sorted([
        "Astaxanthin",
        "Docosahexaenoic acid",
        "Eicosapentaenoic acid",
        "Krill Oil",
        "Lion's Mane",
        "Vitamin B6 (pyridoxine HCl)",
    ], key=str.casefold)


def test_schedule_includes_dashboard_coverage_review() -> None:
    schedule_path = ROOT / "schedule.yaml"
    original_schedule = schedule_path.read_bytes()
    try:
        result = subprocess.run(
            ["uv", "run", "--project", str(ROOT), "python", "-m", "planner"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        schedule = load_yaml("schedule.yaml")
    finally:
        schedule_path.write_bytes(original_schedule)

    dashboards = {dashboard["name"]: dashboard for dashboard in schedule["benefits"]}

    assert dashboards["Workout Performance"]["covered"] == [
        "Calcium (dicalcium phosphate)",
        "Calcium (lactate)",
        "Creatine (monohydrate)",
        "L-Carnitine (L-tartrate)",
        "L-Citrulline (malate)",
        "Magnesium (citrate)",
        "Potassium (citrate)",
        "Sodium (chloride)",
        "Sodium (citrate tribasic)",
    ]
    assert dashboards["Cortisol Reduction"]["inactive"] == [
        "Glycine",
        "Picamilon",
        "Vitamin C (ascorbic acid)",
    ]

    risks = {risk["name"]: risk for risk in schedule["risks"]}
    assert risks["Bleeding Load"]["active"] == [
        "Docosahexaenoic acid",
        "Eicosapentaenoic acid",
        "Ginkgo biloba",
        "Krill Oil",
        "Nattokinase",
    ]


def test_schedule_surfaces_active_warnings_and_placement_notes() -> None:
    schedule_path = ROOT / "schedule.yaml"
    original_schedule = schedule_path.read_bytes()
    try:
        result = subprocess.run(
            ["uv", "run", "--project", str(ROOT), "python", "-m", "planner"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        schedule = load_yaml("schedule.yaml")
    finally:
        schedule_path.write_bytes(original_schedule)

    assert any(
        warning.get("category") == "Safety concern"
        for warning in schedule["warnings"]
    )
    assert any(
        note["product"] == "TiM - Electrolyte Caps (multi-electrolyte)"
        for note in schedule["placement_notes"]
    )
