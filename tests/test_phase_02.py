from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any, cast

import yaml

from planner.cards.product import format_product_name, load_product
from planner.engine import CheckResult, cmd_check, cmd_plan
from tests.helpers import ROOT, run_planner


def fixture_id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:10]}"


def copy_data_tree(tmp_path: Path) -> Path:
    temp_data = tmp_path / "data"
    shutil.copytree(ROOT / "data", temp_data)
    return temp_data


def write_yaml(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def plan_in_temp_dir(tmp_path: Path) -> dict[str, Any]:
    result = cmd_plan(data_root=tmp_path)
    assert result.exit_code == 0, "\n".join(result.errors)
    schedule = yaml.safe_load((tmp_path / "schedule.yaml").read_text())
    assert isinstance(schedule, dict)
    return cast(dict[str, Any], schedule)


def check_in_temp_dir(tmp_path: Path) -> CheckResult:
    return cmd_check(data_root=tmp_path)


def flatten_stack_items(stacks: dict[str, Any]) -> dict[str, Any]:
    return {
        product_id: {"product": product_id, "stack": stack}
        for stack, items in stacks.items()
        for product_id in items
    }


def group_trait_ids(trait_ids: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for tid in trait_ids:
        if ":" in tid:
            ns, slug = tid.split(":", 1)
            groups.setdefault(ns, []).append(slug)
    return groups


def group_trait_defs(traits: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    for trait_id, trait in traits.items():
        namespace, short_name = trait_id.split(":", 1)
        grouped.setdefault(namespace, {})[short_name] = trait
    return grouped


def group_items_by_stack(stack_items: dict[str, Any]) -> dict[str, Any]:
    stacks: dict[str, Any] = {"daily": [], "training": [], "inactive": []}
    for item_id, entry in stack_items.items():
        stacks[entry["stack"]].append(item_id)
    return stacks


def flatten_trait_defs(traits_data: dict[str, Any]) -> dict[str, Any]:
    return {
        f"{namespace}:{name}": trait
        for namespace, entries in traits_data.items()
        if isinstance(entries, dict)
        for name, trait in cast(dict[str, Any], entries).items()
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


def write_minimal_planner_fixture(
    tmp_path: Path,
    *,
    stack_items: dict[str, Any],
    products: dict[str, list[tuple[str, list[str]]]],
    traits: dict[str, Any],
    substance_prefer_with: dict[str, list[str]] | None = None,
    substance_relations: dict[str, list[dict[str, Any]]] | None = None,
) -> None:
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
    normalized_stack_items: dict[str, Any] = {
        product_ids.get(item_id, item_id): {
            **entry,
            "product": product_ids.get(entry.get("product", item_id), entry.get("product", item_id)),
        }
        for item_id, entry in stack_items.items()
    }
    write_yaml(
        tmp_path / "data/pillboxes.yaml",
        {
            "daily": {
                "label": "Daily",
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
    )
    write_yaml(tmp_path / "data/traits.yaml", group_trait_defs(traits))
    write_yaml(tmp_path / "data/stacks.yaml", group_items_by_stack(normalized_stack_items))
    relation_groups: dict[str, Any] = {
        "balance": [],
        "supports": [],
        "competes": [],
        "antagonizes": [],
    }
    substance_relations_dict = substance_relations or {}
    for source_id, relations in substance_relations_dict.items():
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
    substance_components: dict[str, list[str]] = {
        component_id: trait_ids
        for component_ids in products.values()
        for component_id, trait_ids in component_ids
    }
    _SCHEDULE_NS = {"intake", "timing", "activity"}
    _KNOWLEDGE_NS = {"is", "effect", "risk", "context", "pathway"}
    for substance_id, trait_ids in substance_components.items():
        normalized_substance_id = substance_ids[substance_id]
        substance: dict[str, Any] = {
            "id": normalized_substance_id,
            "name": substance_id.replace("_", " ").title(),
        }
        grouped = group_trait_ids(trait_ids)
        sched: dict[str, Any] = {ns: slugs for ns, slugs in grouped.items() if ns in _SCHEDULE_NS}
        know: dict[str, Any] = {ns: slugs for ns, slugs in grouped.items() if ns in _KNOWLEDGE_NS}
        if substance_prefer_with and substance_id in substance_prefer_with:
            sched["prefer_with"] = [
                substance_ids.get(target, target)
                for target in substance_prefer_with[substance_id]
            ]
        if sched:
            substance["schedule"] = sched
        if know:
            substance["knowledge"] = know
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


def test_cli_help_exposes_simple_agent_commands() -> None:
    result = run_planner("--help")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "{check,audit,find,review,review-substance}" in result.stdout
    assert "refresh" not in result.stdout
    assert "normalize" not in result.stdout
    assert "orphans" not in result.stdout


def test_product_formula_ref_validator_rejects_missing_substance(
    tmp_path: Path,
) -> None:
    temp_data = copy_data_tree(tmp_path)
    product_path = find_card_path_by_id(
        temp_data / "products",
        "prd_83dffd67bf",
    )
    product = yaml.safe_load(product_path.read_text())
    product["components"][0]["substance"] = "bogus_substance_xyz"
    write_yaml(product_path, product)

    result = check_in_temp_dir(tmp_path)

    assert result.exit_code != 0
    combined_output = "\n".join(result.errors + result.info)
    assert "bogus_substance_xyz" in combined_output
    assert "references unknown substance" in combined_output


def test_product_schema_accepts_description_urls(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    product_path = find_card_path_by_id(
        temp_data / "products",
        "prd_83dffd67bf",
    )
    product = yaml.safe_load(product_path.read_text())
    product["urls"] = ["https://example.com/minami-sub_877c24aad4"]
    write_yaml(product_path, product)

    result = check_in_temp_dir(tmp_path)

    assert result.exit_code == 0, "\n".join(result.errors + result.info)


def test_malformed_stack_entry_reports_schema_error(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    stacks_path = temp_data / "stacks.yaml"
    stack_items = yaml.safe_load(stacks_path.read_text())
    stack_items["daily"][0] = {"product": "sub_2476bf9d4b"}
    write_yaml(stacks_path, stack_items)

    result = check_in_temp_dir(tmp_path)

    assert result.exit_code != 0
    combined_output = "\n".join(result.errors + result.info)
    assert "stacks" in combined_output
    assert "sub_2476bf9d4b" in combined_output
    assert "AttributeError" not in combined_output
    assert "Traceback" not in combined_output


def test_intra_product_competes_conflict_warns_without_splitting(
    tmp_path: Path,
) -> None:
    # Formerly tested separate_from: trait field; retired in Phase 9 plan 01.
    # Now tests the equivalent intra-product competes substance relation scenario.
    write_minimal_planner_fixture(
        tmp_path,
        stack_items={
            "combo_item": {"product": "combo_item", "stack": "daily"},
        },
        products={
            "combo_item": [
                ("alpha_substance", []),
                ("beta_substance", []),
            ],
        },
        traits={
            "intake:alpha": {
                "label": "Alpha",
                "description": "Alpha trait",
                "applies_when": "Fixture",
            },
        },
        substance_relations={
            "alpha_substance": [
                {
                    "type": "competes",
                    "substances": ["beta_substance"],
                    "reason": "Fixture intra-product competing components.",
                }
            ],
            "beta_substance": [
                {
                    "type": "competes",
                    "substances": ["alpha_substance"],
                    "reason": "Fixture intra-product competing components.",
                }
            ],
        },
    )

    schedule = plan_in_temp_dir(tmp_path)
    combo_name = "Combo Item"
    scheduled_items = {
        item
        for slot_entry in flatten_schedule_slots(schedule).values()
        for item in slot_entry["products"]
    }
    conflict_warnings = [
        warning
        for warning in schedule["warnings"]
        if warning.get("category") == "Component conflict inside one product"
    ]

    assert scheduled_items == {combo_name}
    assert schedule["explanations"][combo_name]["components"] == [
        "Alpha Substance",
        "Beta Substance",
    ]
    assert conflict_warnings == [
        {
            "category": "Component conflict inside one product",
            "product": combo_name,
            "source": "Alpha Substance",
            "target": "Beta Substance",
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


def test_inter_product_separate_from_conflict_still_blocks_colocation(
    tmp_path: Path,
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        stack_items={
            "alpha_product": {"stack": "daily"},
            "beta_product": {"stack": "daily"},
        },
        products={
            "alpha_product": [("alpha_substance", ["intake:alpha"])],
            "beta_product": [("beta_substance", ["intake:beta"])],
        },
        traits={
            "intake:alpha": {
                "label": "Alpha",
                "description": "Alpha trait",
                "applies_when": "Fixture",
                "effects": [
                    {"match": {"near": "wake"}, "level": "prefer_strong"},
                ],
            },
            "intake:beta": {
                "label": "Beta",
                "description": "Beta trait",
                "applies_when": "Fixture",
                "effects": [
                    {"match": {"near": "wake"}, "level": "prefer_strong"},
                ],
            },
        },
        substance_relations={
            "alpha_substance": [
                {
                    "type": "competes",
                    "substances": ["beta_substance"],
                    "reason": "Fixture: separate_from retired; using competes relation.",
                }
            ],
            "beta_substance": [
                {
                    "type": "competes",
                    "substances": ["alpha_substance"],
                    "reason": "Fixture: separate_from retired; using competes relation.",
                }
            ],
        },
    )

    schedule = plan_in_temp_dir(tmp_path)
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
    write_minimal_planner_fixture(
        tmp_path,
        stack_items={
            "zinc_product": {"stack": "daily"},
            "copper_product": {"stack": "daily"},
        },
        products={
            "zinc_product": [("zinc_substance", ["timing:wake"])],
            "copper_product": [("copper_substance", ["timing:wake"])],
        },
        traits={
            "timing:wake": {
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

    schedule = plan_in_temp_dir(tmp_path)
    products_dir = tmp_path / "data" / "products"
    zinc_id = fixture_id("prd", "zinc_product")
    copper_id = fixture_id("prd", "copper_product")
    zinc_name = format_product_name(load_product(next(products_dir.glob(f"*{zinc_id}*"))))
    copper_name = format_product_name(load_product(next(products_dir.glob(f"*{copper_id}*"))))
    colocated_pairs = [
        set(slot_entry["products"])
        for slot_entry in flatten_schedule_slots(schedule).values()
        if {zinc_name, copper_name}.issubset(slot_entry["products"])
    ]

    assert colocated_pairs == []


def test_intra_product_absorption_relation_warns_without_splitting(
    tmp_path: Path,
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        stack_items={
            "trace_product": {"product": "trace_product", "stack": "daily"},
        },
        products={
            "trace_product": [
                ("zinc_substance", []),
                ("copper_substance", []),
            ],
        },
        traits={
            "timing:neutral": {
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

    schedule = plan_in_temp_dir(tmp_path)
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
    write_minimal_planner_fixture(
        tmp_path,
        stack_items={
            "sub_9c0908e7f7": {"stack": "daily"},
            "sub_3918fe347e": {"stack": "daily"},
        },
        products={
            "sub_9c0908e7f7": [("sub_9c0908e7f7", ["timing:wake"])],
            "sub_3918fe347e": [("sub_3918fe347e", ["timing:wake"])],
        },
        traits={
            "timing:wake": {
                "label": "Wake",
                "description": "Wake preference",
                "applies_when": "Fixture",
                "effects": [{"match": {"near": "wake"}, "level": "prefer_strong"}],
            },
        },
        substance_prefer_with={"sub_9c0908e7f7": ["sub_3918fe347e"]},
    )

    schedule = plan_in_temp_dir(tmp_path)
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
    write_minimal_planner_fixture(
        tmp_path,
        stack_items={
            "sub_9c0908e7f7": {"stack": "daily"},
            "citrulline_a": {"stack": "daily"},
            "citrulline_b": {"stack": "daily"},
        },
        products={
            "sub_9c0908e7f7": [("sub_9c0908e7f7", ["timing:wake"])],
            "citrulline_a": [("sub_3918fe347e", ["timing:wake"])],
            "citrulline_b": [("sub_3918fe347e", ["timing:wake"])],
        },
        traits={
            "timing:wake": {
                "label": "Wake",
                "description": "Wake preference",
                "applies_when": "Fixture",
                "effects": [{"match": {"near": "wake"}, "level": "prefer_strong"}],
            },
        },
        substance_prefer_with={"sub_9c0908e7f7": ["sub_3918fe347e"]},
    )

    schedule = plan_in_temp_dir(tmp_path)
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
                    "prefer_with target maps to multiple active stack items; "
                "no bonus awarded"
            ),
            "action": "Choose the intended companion product before relying on co-location.",
        }
    ]


def test_antagonizes_warning_fires_and_severity_flows_through(
    tmp_path: Path,
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        stack_items={
            "vit_e_product": {"stack": "daily"},
            "vit_k2_product": {"stack": "daily"},
        },
        products={
            "vit_e_product": [("vit_e_substance", [])],
            "vit_k2_product": [("vit_k2_substance", [])],
        },
        traits={
            "timing:neutral": {
                "label": "Neutral",
                "description": "Fixture neutral trait",
                "applies_when": "Fixture",
            },
        },
    )
    # Overwrite the fixture relations.yaml with an antagonizes entry that carries severity.
    # write_minimal_planner_fixture does not forward severity through substance_relations,
    # so we write the file directly using the computed substance IDs.
    vit_e_id = fixture_id("sub", "vit_e_substance")
    vit_k2_id = fixture_id("sub", "vit_k2_substance")
    write_yaml(
        tmp_path / "data/relations.yaml",
        {
            "balance": [],
            "supports": [],
            "competes": [],
            "antagonizes": [
                {
                    "source_substance": vit_e_id,
                    "target_substance": vit_k2_id,
                    "severity": "medium",
                    "reason": "High-dose vitamin E can antagonize vitamin K-dependent clotting factors.",
                }
            ],
        },
    )

    schedule = plan_in_temp_dir(tmp_path)
    antagonist_warnings = [
        warning
        for warning in schedule["warnings"]
        if warning.get("category") == "Active antagonist pairing"
    ]

    assert len(antagonist_warnings) == 1
    warning = antagonist_warnings[0]
    assert warning["category"] == "Active antagonist pairing"
    assert warning["severity"] == "medium"
    assert warning["action"] == (
        "Review this antagonist pairing; the planner does not separate antagonizes pairs by slot."
    )


def test_schedule_contains_active_fact_index(tmp_path: Path) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        stack_items={
            "omega_product": {"stack": "daily"},
            "b6_product": {"stack": "daily"},
        },
        products={
            "omega_product": [
                (
                    "epa_component",
                    [
                        "risk:bleeding_med_interaction",
                        "pathway:omega3_eicosanoid",
                        "effect:omega3_source",
                    ],
                )
            ],
            "b6_product": [
                (
                    "b6_component",
                    [
                        "risk:b6_neuropathy_long_term",
                    ],
                )
            ],
        },
        traits={
            "risk:bleeding_med_interaction": {
                "label": "Bleeding medication interaction",
                "description": "Fixture bleeding context",
                "applies_when": "Fixture",
                "warning": True,
            },
            "risk:b6_neuropathy_long_term": {
                "label": "B6 neuropathy long-term",
                "description": "Fixture B6 context",
                "applies_when": "Fixture",
                "warning": True,
            },
            "pathway:omega3_eicosanoid": {
                "label": "Omega-3 / eicosanoid",
                "description": "Fixture omega-3 pathway",
                "applies_when": "Fixture",
            },
        },
    )

    schedule = plan_in_temp_dir(tmp_path)
    fact_index = schedule["active_fact_index"]

    bleeding = next(
        entry for entry in fact_index
        if entry["namespace"] == "risk" and entry["fact"] == "bleeding_med_interaction"
    )
    assert bleeding["label"] == "Bleeding medication interaction"
    assert bleeding["product_count"] == 1
    assert bleeding["products"] == ["Omega Product"]

    omega_source = next(
        entry for entry in fact_index
        if entry["namespace"] == "effect" and entry["fact"] == "omega3_source"
    )
    assert omega_source["label"] == "Omega3 Source"

    assert all(entry["namespace"] != "is" for entry in fact_index)
