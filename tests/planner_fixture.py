"""Fixture builders for planner integration tests."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from shutil import copy2
from typing import cast

import yaml
from planner.card_ids import composition_role_id
from planner.engine import CheckResult, cmd_check, cmd_plan
from planner.ontology.glue_capabilities import ONTOLOGY_COMPOSITE_KEY_SEPARATOR


@dataclass(frozen=True, slots=True)
class PlannerFixtureInput:
    stack_items: dict[str, dict[str, object]]
    products: dict[str, list[tuple[str, list[str]]]]
    traits: dict[str, dict[str, object]]


@dataclass(frozen=True, slots=True)
class PlannerFixtureOptions:
    substance_relations: dict[str, list[dict[str, object]]] = field(default_factory=dict)


_DEFAULT_PLANNER_OPTIONS = PlannerFixtureOptions()
_ONTOLOGY_ROOT = Path(__file__).resolve().parents[1] / "ontology"


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
        groups.setdefault(namespace, []).append(slug)
    return groups


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
        f"{namespace}{ONTOLOGY_COMPOSITE_KEY_SEPARATOR}{name}": trait
        for namespace, entries in traits_data.items()
        for name, trait in entries.items()
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
                "stack": "daily",
                "slots": {
                    "morning_empty": {
                        "label": "Morning empty",
                        "order": 1,
                        "meal_context": "without_food",
                        "circadian_anchor": "wake",
                    },
                    "day_empty": {
                        "label": "Day empty",
                        "order": 2,
                        "meal_context": "without_food",
                    },
                },
            },
            "training": {
                "label": "Training",
                "stack": "training",
                "slots": {
                    "pre_workout": {
                        "label": "Pre-workout",
                        "order": 1,
                        "meal_context": "without_food",
                        "exercise_anchor": "before",
                    },
                    "post_workout": {
                        "label": "Post-workout",
                        "order": 2,
                        "meal_context": "without_food",
                        "exercise_anchor": "after",
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
    )
    _write_product_cards(tmp_path, products, substance_ids, product_ids)
    _write_complete_canonical_catalog_fixture_cards(tmp_path)
    _track_fixture_dependency_products(tmp_path)


def _write_complete_canonical_catalog_fixture_cards(tmp_path: Path) -> None:
    """Make every temporary planner corpus satisfy the production fact catalog.

    The canonical catalog is validated against the complete loaded corpus
    before plan scoping.  Synthetic products may coexist with it, but cannot
    replace its referenced product/substance forms.  Copy just the catalog's
    real product forms and their components, preserving any fixture card that
    already provides the same stable substance ID.
    """
    catalog = _load_yaml_dict(_ONTOLOGY_ROOT / "canonical-facts.yaml")
    facts = [
        fact
        for family in (
            "food_effects",
            "acute_alertness_effects",
            "acute_sleep_effects",
            "pre_exercise_performance_effects",
            "post_exercise_recovery_effects",
        )
        for fact in cast(list[dict[str, object]], catalog[family])
    ]
    substance_ids = {
        cast(str, target["substance"])
        for fact in facts
        for target in (cast(dict[str, object], fact["subject"]), cast(dict[str, object], fact["applicability"]))
        if isinstance(target.get("substance"), str)
    }
    role_ids = {
        cast(str, target["composition_role"])
        for fact in facts
        for target in (cast(dict[str, object], fact["subject"]), cast(dict[str, object], fact["applicability"]))
        if isinstance(target.get("composition_role"), str)
    }
    product_ids = {role_id.removeprefix("cmp_").split("__", 1)[0] for role_id in role_ids}
    substance_ids.update(role_id.split("__", 1)[1] for role_id in role_ids)
    source_products = _ONTOLOGY_ROOT.parents[0] / "data/products"
    source_substances = _ONTOLOGY_ROOT.parents[0] / "data/substances"

    for product_id in product_ids:
        source = _card_path_for_id(source_products, product_id)
        product = _load_yaml_dict(source)
        components = cast(list[dict[str, object]], product["components"])
        substance_ids.update(cast(str, component["substance"]) for component in components)
        destination = tmp_path / "data/products" / source.name
        if not destination.exists():
            copy2(source, destination)

    fixture_substances = tmp_path / "data/substances"
    existing_ids = {_load_yaml_dict(path).get("id") for path in fixture_substances.glob("*.yaml")}
    for substance_id in substance_ids:
        if substance_id in existing_ids:
            continue
        source = _card_path_for_id(source_substances, substance_id)
        copy2(source, fixture_substances / source.name)


def _track_fixture_dependency_products(tmp_path: Path) -> None:
    """Give copied canonical catalog products explicit fixture-only ownership."""
    stacks_path = tmp_path / "data/stacks.yaml"
    stacks = _load_yaml_dict(stacks_path)
    assigned = {
        product_id
        for stack in ("daily", "training", "inactive")
        for product_id in cast(list[str], stacks.get(stack, []))
    }
    tracked = stacks.setdefault("tracked_unassigned", [])
    assert isinstance(tracked, list)
    for entry in tracked:
        if isinstance(entry, dict) and isinstance(entry.get("product"), str):
            assigned.add(entry["product"])
    product_ids = {
        card_id
        for path in (tmp_path / "data/products").glob("*.yaml")
        if isinstance((card_id := _load_yaml_dict(path).get("id")), str)
    }
    tracked.extend(
        {"product": product_id, "reason": "Fixture-only canonical catalog dependency."}
        for product_id in sorted(product_ids - assigned)
    )
    write_yaml(stacks_path, stacks)


def _card_path_for_id(directory: Path, card_id: str) -> Path:
    matches = [path for path in directory.glob("*.yaml") if _load_yaml_dict(path).get("id") == card_id]
    assert len(matches) == 1, f"expected exactly one canonical card for {card_id!r}"
    return matches[0]


def _write_relation_groups(
    tmp_path: Path,
    substance_ids: dict[str, str],
    substance_relations: dict[str, list[dict[str, object]]],
) -> None:
    relation_entries: list[dict[str, object]] = []
    for source_id, relations in substance_relations.items():
        for relation in relations:
            relation_type = cast(str, relation["relation_type"])
            if relation_type not in {"balance", "supports", "co_use_context"}:
                continue
            for target in cast(list[str], relation.get("substances", [])):
                relation_entries.append({
                    "id": f"rel_fixture_{len(relation_entries)}",
                    "relation_type": relation_type,
                    "assertion_kind": "ontology_assertion",
                    "semantic_family": "biochemical_mechanism_assertion",
                    "research_state": "unassessed",
                    "sources": [],
                    "source_selector": {"entity": {"entity_id": substance_ids[source_id]}},
                    "target_selector": {"entity": {"entity_id": substance_ids.get(target, target)}},
                    "reason": cast(str, relation["reason"]),
                })
    write_yaml(tmp_path / "data/relations.yaml", {"relations": relation_entries})


def _write_substance_cards(
    tmp_path: Path,
    products: dict[str, list[tuple[str, list[str]]]],
    substance_ids: dict[str, str],
) -> None:
    substance_components: dict[str, list[str]] = {
        component_id: trait_ids for component_ids in products.values() for component_id, trait_ids in component_ids
    }
    knowledge_namespaces = _fixture_knowledge_namespaces()
    for substance_id, trait_ids in substance_components.items():
        normalized_substance_id = substance_ids[substance_id]
        substance: dict[str, object] = {
            "id": normalized_substance_id,
            "name": substance_id.replace("_", " ").title(),
        }
        grouped = group_trait_ids(trait_ids)
        knowledge: dict[str, list[dict[str, object]]] = {}
        for namespace, slugs in grouped.items():
            records = [{"value": slug, "research_state": "unassessed", "sources": []} for slug in slugs]
            if namespace in knowledge_namespaces:
                knowledge[namespace] = records
            else:
                knowledge[namespace] = records
        # Preserve unknown namespaces in the card.  The generated schema is
        # the normal validation boundary and must reject them explicitly.
        if knowledge:
            substance["knowledge"] = knowledge
        write_yaml(
            tmp_path / "data/substances" / f"{substance_id}__{normalized_substance_id}.yaml",
            substance,
        )


def _fixture_knowledge_namespaces() -> set[str]:
    """Read fixture card containers from authored ontology catalogs.

    The helper intentionally has no fallback vocabulary.  An unknown fixture
    namespace is written into the knowledge envelope so normal generated
    schema validation reports it instead of silently translating or dropping
    the term.
    """

    vocabulary = cast(dict[str, object], yaml.safe_load((_ONTOLOGY_ROOT / "vocabulary.yaml").read_text()))
    categories = vocabulary.get("semantic_categories", {})
    knowledge: set[str] = set()
    if isinstance(categories, dict):
        for raw in categories.values():
            if not isinstance(raw, dict) or not isinstance(raw.get("allowed_predicates"), list):
                continue
            for predicate in cast(list[object], raw["allowed_predicates"]):
                if isinstance(predicate, str) and predicate.startswith("knowledge."):
                    knowledge.add(predicate.removeprefix("knowledge."))
    return knowledge


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
                    {
                        "id": composition_role_id(normalized_product_id, substance_ids[component_id]),
                        "substance": substance_ids[component_id],
                    }
                    for component_id, _trait_ids in component_ids
                ],
            },
        )
