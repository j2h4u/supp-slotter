"""Ontology-dependent authored-to-runtime vertical acceptance scenario."""

from __future__ import annotations

from pathlib import Path
from shutil import copytree
from typing import cast

import planner.engine.plan as plan_module
import yaml
from planner.ontology.artifacts import load_ontology
from planner.paths import Paths
from scripts.ontology_compiler import compile_ontology, write_artifacts

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ID_SUFFIXES = {
    "food": "vertfood01",
    "empty": "vertempty0",
    "wake": "vertwake01",
    "sleep": "vertsleep0",
    "before": "vertbefore",
    "after": "vertafter1",
}


def _fixture_product_id(key: str) -> str:
    return f"prd_{FIXTURE_ID_SUFFIXES[key]}"


def _fixture_substance_id(key: str) -> str:
    return f"sub_{FIXTURE_ID_SUFFIXES[key]}"


def _fixture_fact(key: str, value: str) -> dict[str, object]:
    product_id, substance_id = _fixture_product_id(key), _fixture_substance_id(key)
    role_id = f"cmp_{product_id}__{substance_id}"
    return {
        "id": f"fact_vertical_{key}",
        "subject": {"composition_role": role_id},
        "applicability": {"composition_role": role_id},
        "provenance": [{"source": "src_vertical_fixture", "locator": f"fixture://{key}"}],
        "value": value,
    }


def _write_authored_vertical_fixture(root: Path) -> None:
    copytree(ROOT / "ontology", root / "ontology")
    data = root / "data"
    (data / "products").mkdir(parents=True)
    (data / "substances").mkdir()
    (data / "dashboards").mkdir()
    (data / "dashboards" / "fixture.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "vertical_fixture",
                "name": "Vertical fixture",
                "description": "Isolated compiler-to-runtime acceptance fixture.",
                "benefit": {"description": "Fixture-only artifact-path coverage."},
                "selectors": [{"category": "effect", "term": "alertness_context"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    products = {
        "food": ("daily", "Fixture with food", "not_every_day"),
        "empty": ("daily", "Fixture without food", None),
        "wake": ("daily", "Fixture wake", None),
        "sleep": ("daily", "Fixture sleep", None),
        "before": ("training", "Fixture before", None),
        "after": ("training", "Fixture after", None),
    }
    for key, (_stack, name, use_pattern) in products.items():
        product_id, substance_id = _fixture_product_id(key), _fixture_substance_id(key)
        product: dict[str, object] = {
            "id": product_id,
            "name": name,
            "components": [{"id": f"cmp_{product_id}__{substance_id}", "substance": substance_id}],
        }
        if use_pattern is not None:
            product["use_pattern"] = use_pattern
        (data / "products" / f"unknown__{name.lower().replace(' ', '_')}__{product_id}.yaml").write_text(
            yaml.safe_dump(product, sort_keys=False), encoding="utf-8"
        )
        (data / "substances" / f"fixture_{key}__{substance_id}.yaml").write_text(
            yaml.safe_dump({"id": substance_id, "name": f"Fixture {key}"}, sort_keys=False), encoding="utf-8"
        )
    relations = {
        "relations": [
            {
                "id": "rel_vertical_review",
                "relation_type": "review_with",
                "assertion_kind": "clinical_review_signal",
                "semantic_family": "nutrient_balance_review_signal",
                "research_state": "unassessed",
                "sources": [],
                "reason": "Fixture reviewer relation.",
                "source_selector": {"entity": {"entity_id": _fixture_substance_id("food")}},
                "target_selector": {"entity": {"entity_id": _fixture_substance_id("empty")}},
            },
            {
                "id": "rel_vertical_support",
                "relation_type": "supports",
                "assertion_kind": "ontology_assertion",
                "semantic_family": "biochemical_mechanism_assertion",
                "research_state": "unassessed",
                "sources": [],
                "reason": "Fixture support relation.",
                "source_selector": {"entity": {"entity_id": _fixture_substance_id("wake")}},
                "target_selector": {"entity": {"entity_id": _fixture_substance_id("sleep")}},
            },
        ]
    }
    (data / "relations.yaml").write_text(yaml.safe_dump(relations, sort_keys=False), encoding="utf-8")
    (data / "stacks.yaml").write_text(
        yaml.safe_dump(
            {
                "daily": [_fixture_product_id(key) for key in ("food", "empty", "wake", "sleep")],
                "training": [_fixture_product_id(key) for key in ("before", "after")],
                "inactive": [],
                "tracked_unassigned": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    pillboxes = {
        "daily": {
            "label": "Daily fixture",
            "stack": "daily",
            "slots": {
                "daily_food": {"label": "Food", "order": 1, "meal_context": "with_food"},
                "daily_empty": {"label": "Empty", "order": 2, "meal_context": "without_food"},
                "daily_wake": {"label": "Wake", "order": 3, "circadian_anchor": "wake"},
                "daily_sleep": {"label": "Sleep", "order": 4, "circadian_anchor": "sleep"},
            },
        },
        "training": {
            "label": "Training fixture",
            "stack": "training",
            "slots": {
                "training_before": {"label": "Before", "order": 1, "exercise_anchor": "before"},
                "training_after": {"label": "After", "order": 2, "exercise_anchor": "after"},
            },
        },
    }
    (data / "pillboxes.yaml").write_text(yaml.safe_dump(pillboxes, sort_keys=False), encoding="utf-8")
    facts = {
        "evidence_sources": [{"id": "src_vertical_fixture"}],
        "food_effects": [
            _fixture_fact("food", "bioavailability_increases"),
            _fixture_fact("empty", "bioavailability_decreases"),
        ],
        "acute_alertness_effects": [_fixture_fact("wake", "acute_alertness_increases")],
        "acute_sleep_effects": [_fixture_fact("sleep", "onset_latency_decreases")],
        "pre_exercise_performance_effects": [_fixture_fact("before", "performance_improves")],
        "post_exercise_recovery_effects": [_fixture_fact("after", "recovery_improves")],
    }
    (root / "ontology" / "canonical-facts.yaml").write_text(yaml.safe_dump(facts, sort_keys=False), encoding="utf-8")


def test_authored_vertical_fixture_compiles_loads_and_routes_all_runtime_anchors(tmp_path: Path) -> None:
    _write_authored_vertical_fixture(tmp_path)
    ontology_root = tmp_path / "ontology"
    write_artifacts(ontology_root, compile_ontology(ontology_root))
    bundle = load_ontology(ontology_root)
    catalog = bundle.runtime_program.canonical_scheduling
    assert {fact.id for fact in catalog.facts} == {f"fact_vertical_{key}" for key in FIXTURE_ID_SUFFIXES}
    result = plan_module._cmd_plan_inner(Paths.from_root(tmp_path), bundle)
    assert result.exit_code == 0, result.errors
    schedule = cast(dict[str, object], yaml.safe_load((tmp_path / "schedule.yaml").read_text(encoding="utf-8")))
    assert schedule["status"] == "Optimal"
    assignments = cast(dict[str, str], schedule["assignments"])
    assert set(assignments) == {_fixture_product_id(key) for key in FIXTURE_ID_SUFFIXES}
    for key, slot_id in {
        "food": "daily_food",
        "empty": "daily_empty",
        "wake": "daily_wake",
        "sleep": "daily_sleep",
        "before": "training_before",
        "after": "training_after",
    }.items():
        assert assignments[_fixture_product_id(key)] == slot_id
    matches = cast(list[dict[str, object]], schedule["pressure_matches"])
    assert {match["fact_ids"][0] for match in matches} == {f"fact_vertical_{key}" for key in FIXTURE_ID_SUFFIXES}
    assert all(match["satisfied"] is True and match["applicability_role_ids"] for match in matches)
    groups = cast(dict[str, list[str]], cast(dict[str, object], schedule["summary"])["placement_groups"])
    assert groups["episodic"] == [_fixture_product_id("food")]
