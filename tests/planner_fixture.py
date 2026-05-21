"""Fixture builders for planner integration tests."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any, cast

import yaml

from planner.engine import CheckResult, cmd_check, cmd_plan
from tests.helpers import ROOT


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
    for trait_id in trait_ids:
        if ":" not in trait_id:
            continue
        namespace, slug = trait_id.split(":", 1)
        groups.setdefault(namespace, []).append(slug)
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
    write_yaml(tmp_path / "data/traits/fixture.yaml", group_trait_defs(traits))
    write_yaml(tmp_path / "data/stacks.yaml", group_items_by_stack(normalized_stack_items))
    _write_relation_groups(tmp_path, substance_ids, substance_relations or {})
    _write_substance_cards(
        tmp_path,
        products,
        substance_ids,
        substance_prefer_with or {},
    )
    _write_product_cards(tmp_path, products, substance_ids, product_ids)


def _write_relation_groups(
    tmp_path: Path,
    substance_ids: dict[str, str],
    substance_relations: dict[str, list[dict[str, Any]]],
) -> None:
    relation_groups: dict[str, Any] = {
        "balance": [],
        "supports": [],
        "competes": [],
        "review_with": [],
    }
    for source_id, relations in substance_relations.items():
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


def _write_substance_cards(
    tmp_path: Path,
    products: dict[str, list[tuple[str, list[str]]]],
    substance_ids: dict[str, str],
    substance_prefer_with: dict[str, list[str]],
) -> None:
    substance_components: dict[str, list[str]] = {
        component_id: trait_ids
        for component_ids in products.values()
        for component_id, trait_ids in component_ids
    }
    schedule_namespaces = {"intake", "timing", "activity"}
    knowledge_namespaces = {"is", "effect", "risk", "context", "pathway"}
    for substance_id, trait_ids in substance_components.items():
        normalized_substance_id = substance_ids[substance_id]
        substance: dict[str, Any] = {
            "id": normalized_substance_id,
            "name": substance_id.replace("_", " ").title(),
        }
        grouped = group_trait_ids(trait_ids)
        schedule: dict[str, Any] = {
            ns: slugs for ns, slugs in grouped.items() if ns in schedule_namespaces
        }
        knowledge: dict[str, Any] = {
            ns: slugs for ns, slugs in grouped.items() if ns in knowledge_namespaces
        }
        if substance_id in substance_prefer_with:
            schedule["prefer_with"] = [
                substance_ids.get(target, target)
                for target in substance_prefer_with[substance_id]
            ]
        if schedule:
            substance["schedule"] = schedule
        if knowledge:
            substance["knowledge"] = knowledge
        write_yaml(
            tmp_path / "data/substances" / f"{substance_id}__{normalized_substance_id}.yaml",
            substance,
        )


def _write_product_cards(
    tmp_path: Path,
    products: dict[str, list[tuple[str, list[str]]]],
    substance_ids: dict[str, str],
    product_ids: dict[str, str],
) -> None:
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
