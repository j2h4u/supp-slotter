from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml


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
    "prd_955ea0c9e6": "Doctor's Best (NAC Detox Regulators)",
    "prd_83dffd67bf": "Minami Healthy Foods",
    "prd_7ae9a92d3b": "Farmstandart",
    "prd_97fc03c4c0": "Now",
    "prd_91a71b69f0": "Life Extension",
    "prd_33f3450f29": "Tadalista",
    "prd_932319251f": "Life Extension",
    "prd_8eff2491b7": "BioGrace",
    "prd_eb6337a6dc": "Futurebiotics",
}

EXPECTED_DOSE_TEXT = {
    "prd_27f7b85aa6": "1000 mg",
    "prd_e5cc3b4e7c": "6 mg",
    "prd_55d65df796": "2 mg (Albion bisglycinate)",
    "prd_2ca842627a": "5 g",
    "prd_20bf2df267": "1 g/cap",
    "prd_17f2788c3f": "1 g",
    "prd_7f04daf970": "1 g",
    "prd_0e92bc1674": "530 mg",
    "prd_cfce0b36b6": "5 g",
    "prd_c81eb18069": "150 mg Lion's Mane + 1 mg B6",
    "prd_955ea0c9e6": "600 mg",
    "prd_83dffd67bf": "13000 FU",
    "prd_7ae9a92d3b": "50 mg",
    "prd_97fc03c4c0": "99 mg elemental K",
    "prd_91a71b69f0": "200 mcg",
    "prd_8eff2491b7": "15 mg",
    "prd_eb6337a6dc": "10000 IU",
}

EXPECTED_STACKS = {
    "daily": {
        "prd_eb6337a6dc",
        "prd_8eff2491b7",
        "prd_bb212cffc2",
        "prd_9d0fca3201",
        "prd_932319251f",
        "prd_97fc03c4c0",
        "prd_c81eb18069",
        "prd_27f7b85aa6",
        "prd_e5cc3b4e7c",
        "prd_83dffd67bf",
        "prd_33f3450f29",
    },
    "training": {
        "prd_20bf2df267",
        "prd_cfce0b36b6",
        "prd_2ca842627a",
        "prd_0e92bc1674",
    },
    "inactive": {
        "prd_a6342d7725",
        "prd_7ae9a92d3b",
        "prd_91a71b69f0",
        "prd_7a4ee33852",
        "prd_55d65df796",
        "prd_955ea0c9e6",
        "prd_7f04daf970",
        "prd_17f2788c3f",
    },
}

EXPECTED_PRODUCT_FILENAMES = {
    "prd_27f7b85aa6": "best_naturals__acetyl_l_carnitine_alcar__prd_27f7b85aa6.yaml",
    "prd_e5cc3b4e7c": "harmony_aqua__astaxanthin__prd_e5cc3b4e7c.yaml",
    "prd_bb212cffc2": "country_life__coenzyme_b_complex_active_coenzymated_b_vitamins__prd_bb212cffc2.yaml",
    "prd_55d65df796": "swanson__copper_bisglycinate__prd_55d65df796.yaml",
    "prd_2ca842627a": "do4a__creatine_monohydrate__prd_2ca842627a.yaml",
    "prd_7a4ee33852": "eqville__dihydroquercetin_taxifolin_with_vitamins_a_c_e__prd_7a4ee33852.yaml",
    "prd_20bf2df267": "tim__electrolyte_caps_multi_electrolyte__prd_20bf2df267.yaml",
    "prd_17f2788c3f": "geneticlab_nutrition__glycine__prd_17f2788c3f.yaml",
    "prd_7f04daf970": "unknown__krill_oil__prd_7f04daf970.yaml",
    "prd_0e92bc1674": "primecraft__l_carnitine_l_tartrate_lclt__prd_0e92bc1674.yaml",
    "prd_cfce0b36b6": "unknown__l_citrulline_malate__prd_cfce0b36b6.yaml",
    "prd_a6342d7725": "unknown__lions_mane_hericium_erinaceus__prd_a6342d7725.yaml",
    "prd_c81eb18069": "vitamir__lions_mane_b6_complex_vitamir__prd_c81eb18069.yaml",
    "prd_9d0fca3201": "vitamir__magnesium_glycinate__prd_9d0fca3201.yaml",
    "prd_955ea0c9e6": "doctors_best_nac_detox_regulators__n_acetyl_cysteine_nac__prd_955ea0c9e6.yaml",
    "prd_83dffd67bf": "minami_healthy_foods__nattokinase_13000fu__prd_83dffd67bf.yaml",
    "prd_7ae9a92d3b": "farmstandart__picamilon__prd_7ae9a92d3b.yaml",
    "prd_97fc03c4c0": "now__potassium_citrate__prd_97fc03c4c0.yaml",
    "prd_91a71b69f0": "life_extension__se_methyl_l_selenocysteine__prd_91a71b69f0.yaml",
    "prd_33f3450f29": "tadalista__tadalafil__prd_33f3450f29.yaml",
    "prd_932319251f": "life_extension__only_trace_minerals_multi_trace_mineral_complex__prd_932319251f.yaml",
    "prd_8eff2491b7": "biograce__vitamin_b5_pantothenic_acid__prd_8eff2491b7.yaml",
    "prd_eb6337a6dc": "futurebiotics__vitamin_d3_cholecalciferol__prd_eb6337a6dc.yaml",
}

EXPECTED_SCHEDULE_SLOTS = {
    "morning_empty": ["prd_8eff2491b7", "prd_27f7b85aa6"],
    "morning_food": [
        "prd_eb6337a6dc",
        "prd_bb212cffc2",
        "prd_932319251f",
        "prd_97fc03c4c0",
    ],
    "day_food": [
        "prd_c81eb18069",
        "prd_e5cc3b4e7c",
        "prd_83dffd67bf",
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


def load_yaml(path: str) -> object:
    return yaml.safe_load((ROOT / path).read_text())


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


def test_product_files_use_brand_product_names() -> None:
    actual: dict[str, str] = {}
    for path in sorted((ROOT / "data/products").glob("*.yaml")):
        product = yaml.safe_load(path.read_text())
        actual[product["id"]] = path.name

    assert actual == EXPECTED_PRODUCT_FILENAMES
    assert all("__" in filename for filename in actual.values())


def test_check_auto_renames_files_when_names_change(tmp_path: Path) -> None:
    temp_data = copy_planner_runtime(tmp_path)
    product_path = find_card_path_by_id(temp_data / "products", "prd_83dffd67bf")
    substance_path = find_card_path_by_id(temp_data / "substances", "sub_7e02eab0d1")

    product = yaml.safe_load(product_path.read_text())
    product["name"] = "Nattokinase 13000FU Updated"
    product_path.write_text(yaml.safe_dump(product, sort_keys=False))

    substance = yaml.safe_load(substance_path.read_text())
    substance["form"] = "glycinate chelate"
    substance_path.write_text(yaml.safe_dump(substance, sort_keys=False))

    result = subprocess.run(
        ["uv", "run", "planner.py", "check"],
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
    inventory = yaml.safe_load((temp_data / "inventory.yaml").read_text())
    assert "prd_83dffd67bf" in inventory["stacks"]["daily"]


def test_inventory_contains_no_dose_or_notes() -> None:
    products = load_cards("data/products")

    for product_id, dose in EXPECTED_DOSE_TEXT.items():
        assert dose in product_text(products[product_id])

    inventory = load_yaml("data/inventory.yaml")
    all_inventory_text = product_text(inventory)
    assert "notes" not in all_inventory_text
    assert "dose" not in all_inventory_text


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


def test_inventory_is_stack_oriented_and_contains_no_product_facts() -> None:
    inventory = load_yaml("data/inventory.yaml")

    assert "supplements" not in inventory
    assert set(inventory["stacks"]) == {"daily", "training", "inactive"}
    assert {
        stack: set(items)
        for stack, items in inventory["stacks"].items()
    } == EXPECTED_STACKS

    for items in inventory["stacks"].values():
        assert all(isinstance(item, str) for item in items)
        for item in items:
            assert item == item.strip()


def test_check_warns_about_products_without_inventory_entry(tmp_path: Path) -> None:
    temp_data = copy_planner_runtime(tmp_path)
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
        ["uv", "run", "planner.py", "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "product 'prd_0000000002' has no inventory entry" in result.stdout
    assert "Add it to stacks.* if it is on the shelf" in result.stdout
    assert "refresh" not in result.stdout


def test_duplicate_inventory_item_across_stacks_is_rejected(tmp_path: Path) -> None:
    temp_data = copy_planner_runtime(tmp_path)
    inventory_path = temp_data / "inventory.yaml"
    inventory = yaml.safe_load(inventory_path.read_text())
    inventory["stacks"]["training"].append("prd_eb6337a6dc")
    inventory_path.write_text(yaml.safe_dump(inventory, sort_keys=False))

    result = subprocess.run(
        ["uv", "run", "planner.py", "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "prd_eb6337a6dc" in combined_output
    assert "multiple stacks" in combined_output


def test_orphans_command_lists_cleanup_candidates(tmp_path: Path) -> None:
    temp_data = copy_planner_runtime(tmp_path)

    orphan_substance = {
        "id": "sub_0000000003",
        "name": "Orphan Substance",
        "traits": [],
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
    traits["traits"]["risk:orphan_trait"] = {
        "label": "Orphan Trait",
        "description": "Unused fixture trait.",
        "applies_when": "Fixture only.",
    }
    traits_path.write_text(yaml.safe_dump(traits, sort_keys=False))

    inventory_path = temp_data / "inventory.yaml"
    inventory = yaml.safe_load(inventory_path.read_text())
    inventory["stacks"]["parking"] = []
    inventory_path.write_text(yaml.safe_dump(inventory, sort_keys=False))

    result = subprocess.run(
        ["uv", "run", "planner.py", "doctor"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Doctor / cleanup candidates" in result.stdout
    assert "substances.unused" in result.stdout
    assert "  - sub_0000000003" in result.stdout
    assert "products.without_inventory" in result.stdout
    assert "  - prd_0000000004" in result.stdout
    assert "traits.unused" in result.stdout
    assert "  - risk:orphan_trait" in result.stdout
    assert "stacks.empty (1)\n  - parking" in result.stdout
    assert "stacks.without_slots (1)\n  - parking" in result.stdout


def test_concrete_b6_forms_are_distinct_without_unused_taxonomy() -> None:
    substances = load_cards("data/substances")
    traits = load_yaml("data/traits.yaml")["traits"]

    assert "sub_799419116d" in substances
    assert "sub_a873e428ee" in substances
    assert "vitamin_b6" not in substances
    assert substances["sub_799419116d"]["traits"] == []
    assert substances["sub_a873e428ee"]["traits"] == []
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

    assert substances["sub_f78ea75282"]["relations"] == [
        {
            "type": "balance",
            "substances": ["sub_844a0cc551"],
            "reason": (
                "Long-term high-dose zinc supplementation can depress copper status."
            ),
        },
        {
            "type": "competes_absorption",
            "substances": ["sub_844a0cc551"],
            "reason": "Zinc and copper can compete for absorption when co-administered.",
        }
    ]
    assert substances["sub_844a0cc551"]["relations"] == [
        {
            "type": "balance",
            "substances": ["sub_f78ea75282"],
            "reason": (
                "Copper and zinc status should be reviewed together in long-term stacks."
            ),
        },
        {
            "type": "competes_absorption",
            "substances": ["sub_f78ea75282"],
            "reason": "Copper and zinc can compete for absorption when co-administered.",
        }
    ]


def test_balance_relation_warns_when_related_substance_missing(tmp_path: Path) -> None:
    temp_data = copy_planner_runtime(tmp_path)
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
        ["uv", "run", "planner.py", "doctor"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert "relations.balance_missing (1)" in doctor.stdout
    assert (
        "sub_f78ea75282 (Zinc) -> sub_844a0cc551 (Copper (bisglycinate))"
        in doctor.stdout
    )

    plan = subprocess.run(
        ["uv", "run", "planner.py", "plan"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    schedule = yaml.safe_load((tmp_path / "schedule.yaml").read_text())
    balance_warnings = [
        warning
        for warning in schedule["warnings"]
        if warning.get("type") == "missing_balance_substance"
    ]

    assert plan.returncode == 0, plan.stdout + plan.stderr
    assert balance_warnings == [
        {
            "type": "missing_balance_substance",
            "source_substance": "sub_f78ea75282",
            "source_name": "Zinc",
            "target_substance": "sub_844a0cc551",
            "target_name": "Copper (bisglycinate)",
            "reason": (
                "Long-term high-dose zinc supplementation can depress copper status."
            ),
        }
    ]


def test_nac_detox_regulators_product_has_label_components_and_urls() -> None:
    substances = load_cards("data/substances")
    products = load_cards("data/products")
    product = products["prd_955ea0c9e6"]

    assert product["urls"] == [
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
    assert substances["sub_59bza5s7h0"]["relations"] == [
        {
            "type": "supports",
            "substances": ["sub_d997f98e03"],
            "reason": (
                "Selenium is required for glutathione peroxidases; "
                "NAC supplies cysteine for glutathione synthesis."
            ),
        }
    ]
    assert substances["sub_86uvfl7jeo"]["relations"] == [
        {
            "type": "supports",
            "substances": ["sub_d997f98e03"],
            "reason": (
                "Molybdenum cofactor enzymes metabolize sulfur-containing "
                "amino acids; NAC is a cysteine derivative."
            ),
        }
    ]
    assert substances["sub_d997f98e03"]["relations"] == [
        {
            "type": "supported_by",
            "substances": ["sub_59bza5s7h0", "sub_86uvfl7jeo"],
            "reason": (
                "Selenium supports glutathione peroxidases; molybdenum supports "
                "sulfur-amino-acid metabolism. Doctor's Best pairs both with NAC."
            ),
        }
    ]


def test_relation_mirror_validation_requires_supported_by(tmp_path: Path) -> None:
    temp_data = copy_planner_runtime(tmp_path)
    nac_path = find_card_path_by_id(temp_data / "substances", "sub_d997f98e03")
    nac = yaml.safe_load(nac_path.read_text())
    nac.pop("relations")
    nac_path.write_text(yaml.safe_dump(nac, sort_keys=False))

    result = subprocess.run(
        ["uv", "run", "planner.py", "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "must be mirrored as 'supported_by'" in result.stderr


def test_support_relation_warns_when_supporter_missing(tmp_path: Path) -> None:
    temp_data = copy_planner_runtime(tmp_path)
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

    inventory_path = temp_data / "inventory.yaml"
    inventory = yaml.safe_load(inventory_path.read_text())
    inventory["stacks"]["inactive"].remove("prd_955ea0c9e6")
    inventory["stacks"]["daily"].append("prd_955ea0c9e6")
    inventory_path.write_text(yaml.safe_dump(inventory, sort_keys=False))

    doctor = subprocess.run(
        ["uv", "run", "planner.py", "doctor"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert "relations.supports_missing (1)" in doctor.stdout
    assert (
        "sub_59bza5s7h0 (Selenium (SelenoExcell High Selenium Yeast)) -> "
        "sub_d997f98e03 (N-Acetyl Cysteine)"
    ) in doctor.stdout


def test_no_regimen_file_exists() -> None:
    assert not (ROOT / "data/regimen.yaml").exists()
    assert not (ROOT / "regimen.yaml").exists()


def test_schedule_baseline_remains_stable() -> None:
    schedule = load_yaml("schedule.yaml")

    assert schedule["total_score"] == 44.5
    assert schedule["slot_score_total"] == 62
    assert schedule["balance_penalty"] == 20.5
    assert "search" not in schedule
    assert schedule["quality_rating"] == 3
    assert schedule["quality_scale"] == 5
    assert {
        slot_name: {"products": slot_entry["products"]}
        for slot_name, slot_entry in schedule["slots"].items()
    } == EXPECTED_SCHEDULE_SLOT_PRODUCTS
    assert schedule["explanations"][
        "prd_bb212cffc2"
    ]["components"] == [
        "sub_230c5c820e",
        "sub_67fc2be8aa",
        "sub_e9e80d003a",
        "sub_7628e4f478",
        "sub_799419116d",
        "sub_fd899525d3",
        "sub_d0034bd130",
        "sub_157418854b",
    ]
    assert schedule["explanations"]["prd_c81eb18069"]["components"] == [
        "sub_e3af6f78d9",
        "sub_a873e428ee",
    ]
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


def test_schedule_always_includes_product_and_substance_layers() -> None:
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
        schedule = load_yaml("schedule.yaml")
    finally:
        schedule_path.write_bytes(original_schedule)

    assert {
        slot_name: {"products": slot_entry["products"]}
        for slot_name, slot_entry in schedule["slots"].items()
    } == EXPECTED_SCHEDULE_SLOT_PRODUCTS
    day_food = schedule["slots"]["day_food"]["substances"]

    assert day_food == [
        "Lion's Mane",
        "Vitamin B6 (pyridoxine HCl)",
        "Astaxanthin",
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
    assert all(isinstance(entry, str) for entry in day_food)
