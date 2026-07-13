"""Parity contract for relocated legacy hard scheduling constraints."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml
from scripts.ontology_inventory import DEFAULT_BASELINE, account

ROOT = Path(__file__).resolve().parents[1]


def test_all_legacy_competes_records_are_relocated_as_first_class_constraints() -> None:
    result = account(DEFAULT_BASELINE)

    assert result["relations"] == 36
    assert result["ontology_relations"] == 28
    assert result["scheduling_constraints"] == 8


def test_mineral_fat_soluble_rule_is_a_hard_planner_constraint_not_a_category_claim() -> None:
    source = cast(object, yaml.safe_load((ROOT / "ontology/scheduling-constraints.yaml").read_text(encoding="utf-8")))
    assert isinstance(source, dict)
    source_mapping = cast(dict[str, object], source)
    constraints = source_mapping.get("scheduling_constraints")
    assert isinstance(constraints, dict)
    constraint = cast(dict[str, object], constraints).get("sc_mineral_fat_soluble_separate_slots")
    assert isinstance(constraint, dict)

    assert constraint["legacy_relation_id"] == "rel_competes_007"
    assert constraint["assertion_type"] == "clinical_scheduling_constraint"
    assert constraint["effect"] == "separate_slots"
    assert constraint["enforcement"] == "block"
    assert constraint["source_selector"] == {"category": "kind", "term": "mineral"}
    assert constraint["target_selector"] == {"category": "quality", "term": "fat_soluble"}
    assert "not biochemical incompatibility or category disjointness" in constraint["semantic_note"]
