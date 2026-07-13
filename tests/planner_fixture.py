"""Fixture builders for planner integration tests."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import yaml
from planner.engine import CheckResult, cmd_check, cmd_plan


@dataclass(frozen=True, slots=True)
class PlannerFixtureInput:
    stack_items: dict[str, dict[str, object]]
    products: dict[str, list[tuple[str, list[str]]]]
    traits: dict[str, dict[str, object]]


@dataclass(frozen=True, slots=True)
class PlannerFixtureOptions:
    substance_prefer_with: dict[str, list[str]] = field(default_factory=dict)
    substance_relations: dict[str, list[dict[str, object]]] = field(default_factory=dict)


_DEFAULT_PLANNER_OPTIONS = PlannerFixtureOptions()


def fixture_id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:10]}"


def write_yaml(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _load_yaml_dict(path: Path) -> dict[str, object]:
    loaded = cast(object, yaml.safe_load(path.read_text(encoding="utf-8")))
    assert isinstance(loaded, dict)
    return cast(dict[str, object], loaded)


def plan_in_temp_dir(tmp_path: Path) -> dict[str, object]:
    result = cmd_plan(data_root=tmp_path)
    assert result.exit_code == 0, "\n".join(result.errors)
    return _load_yaml_dict(tmp_path / "schedule.yaml")


def check_in_temp_dir(tmp_path: Path) -> CheckResult:
    return cmd_check(data_root=tmp_path)


def flatten_stack_items(stacks: dict[str, list[str]]) -> dict[str, dict[str, str]]:
    return {
        product_id: {"product": product_id, "stack": stack} for stack, items in stacks.items() for product_id in items
    }


def group_trait_ids(trait_ids: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for trait_id in trait_ids:
        if ":" not in trait_id:
            continue
        namespace, slug = trait_id.split(":", 1)
        # Test callers historically used arbitrary trait identifiers backed by
        # fixture-local `data/traits`.  The canonical cutover deliberately has
        # no such runtime registry: scheduler behaviour comes from ontology
        # policies.  Keep the fixture call sites readable while projecting their
        # old shorthand onto the nearest canonical policy/term.
        namespace, slug = _canonical_fixture_term(namespace, slug)
        groups.setdefault(namespace, []).append(slug)
    return groups


def _canonical_fixture_term(namespace: str, slug: str) -> tuple[str, str]:
    aliases = {
        ("is", "mineral"): ("kind", "mineral"),
        ("is", "fat_soluble"): ("quality", "fat_soluble"),
        ("timing", "wake"): ("timing", "energy_like"),
        ("timing", "neutral"): ("timing", "energy_like"),
        ("activity", "workout"): ("activity", "any_workout"),
        ("activity", "workout_before"): ("activity", "pre_workout"),
        ("activity", "workout_after"): ("activity", "post_workout"),
        ("intake", "with_food"): ("intake", "food_preferred"),
        ("intake", "empty_stomach"): ("intake", "empty_preferred"),
    }
    return aliases.get((namespace, slug), (namespace, slug))


def group_policies(traits: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for trait_id, trait in traits.items():
        namespace, short_name = trait_id.split(":", 1)
        grouped.setdefault(namespace, {})[short_name] = trait
    return grouped


def group_items_by_stack(stack_items: dict[str, dict[str, object]]) -> dict[str, list[str]]:
    stacks: dict[str, list[str]] = {"daily": [], "training": [], "inactive": []}
    for item_id, entry in stack_items.items():
        stack = cast(str, entry["stack"])
        stacks[stack].append(item_id)
    return stacks


def flatten_policies(traits_data: dict[str, dict[str, object]]) -> dict[str, object]:
    return {
        f"{namespace}:{name}": trait for namespace, entries in traits_data.items() for name, trait in entries.items()
    }


def flatten_schedule_slots(schedule: dict[str, object]) -> dict[str, dict[str, object]]:
    pillboxes = cast(dict[str, dict[str, object]], schedule["pillboxes"])
    return {
        slot_name: slot_entry
        for pillbox in pillboxes.values()
        for slot_name, slot_entry in cast(dict[str, dict[str, object]], pillbox["slots"]).items()
    }


def find_card_path_by_id(directory: Path, card_id: str) -> Path:
    matches = [path for path in sorted(directory.glob("*.yaml")) if _load_yaml_dict(path).get("id") == card_id]
    assert len(matches) == 1
    return matches[0]


def write_minimal_planner_fixture(
    tmp_path: Path,
    fixture_input: PlannerFixtureInput,
    options: PlannerFixtureOptions = _DEFAULT_PLANNER_OPTIONS,
) -> None:
    stack_items = fixture_input.stack_items
    products = fixture_input.products
    traits = fixture_input.traits
    substance_prefer_with = options.substance_prefer_with
    substance_relations = options.substance_relations

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
    normalized_stack_items: dict[str, dict[str, object]] = {}
    for item_id, entry in stack_items.items():
        source_product = cast(str, entry.get("product", item_id))
        normalized_stack_items[product_ids.get(item_id, item_id)] = {
            **entry,
            "product": product_ids.get(source_product, source_product),
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
            "training": {
                "label": "Training",
                "slots": {
                    "pre_workout": {
                        "label": "Pre-workout",
                        "order": 1,
                        "near": "workout_before",
                        "food": False,
                    },
                    "post_workout": {
                        "label": "Post-workout",
                        "order": 2,
                        "near": "workout_after",
                        "food": False,
                    },
                },
            },
        },
    )
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
    substance_relations: dict[str, list[dict[str, object]]],
) -> None:
    relation_entries: list[dict[str, object]] = []
    for source_id, relations in substance_relations.items():
        for relation in relations:
            relation_type = cast(str, relation["type"])
            if relation_type not in {"balance", "supports", "competes", "review_with"}:
                continue
            for target in cast(list[str], relation.get("substances", [])):
                relation_entries.append({
                    "id": f"rel_fixture_{len(relation_entries)}",
                    "type": relation_type,
                    "source_selector": {"entity": {"id": substance_ids[source_id]}},
                    "target_selector": {"entity": {"id": substance_ids.get(target, target)}},
                    "reason": cast(str, relation["reason"]),
                })
    write_yaml(tmp_path / "data/relations.yaml", {"relations": relation_entries})


def _write_substance_cards(
    tmp_path: Path,
    products: dict[str, list[tuple[str, list[str]]]],
    substance_ids: dict[str, str],
    substance_prefer_with: dict[str, list[str]],
) -> None:
    substance_components: dict[str, list[str]] = {
        component_id: trait_ids for component_ids in products.values() for component_id, trait_ids in component_ids
    }
    schedule_namespaces = {"intake", "timing", "activity"}
    knowledge_namespaces = {"kind", "role", "quality", "effect", "risk", "context", "pathway"}
    for substance_id, trait_ids in substance_components.items():
        normalized_substance_id = substance_ids[substance_id]
        substance: dict[str, object] = {
            "id": normalized_substance_id,
            "name": substance_id.replace("_", " ").title(),
        }
        grouped = group_trait_ids(trait_ids)
        schedule: dict[str, list[str]] = {ns: slugs for ns, slugs in grouped.items() if ns in schedule_namespaces}
        knowledge: dict[str, list[str]] = {ns: slugs for ns, slugs in grouped.items() if ns in knowledge_namespaces}
        if substance_id in substance_prefer_with:
            schedule["prefer_with"] = [
                substance_ids.get(target, target) for target in substance_prefer_with[substance_id]
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
                    {"substance": substance_ids[component_id]} for component_id, _trait_ids in component_ids
                ],
            },
        )
