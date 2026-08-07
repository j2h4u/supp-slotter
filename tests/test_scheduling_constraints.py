"""Contract for authored hard scheduling constraints."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_constraint_dispositions_and_mineral_category_retirement() -> None:
    source = cast(object, yaml.safe_load((ROOT / "ontology/scheduling-constraints.yaml").read_text(encoding="utf-8")))
    assert isinstance(source, dict)
    source_mapping = cast(dict[str, object], source)
    constraints = source_mapping.get("scheduling_constraints")
    assert isinstance(constraints, dict)
    constraint = cast(dict[str, object], constraints).get("sc_mineral_fat_soluble_separate_slots")
    assert isinstance(constraint, dict)

    assert constraint["assertion_type"] == "clinical_scheduling_constraint"
    assert constraint["operation"] == "separate_products_same_slot"
    assert constraint["status"] == "retired"
    assert constraint["enforcement"] == "review"
    assert constraint["source_selector"] == {"category": "kind", "term": "mineral"}
    assert constraint["target_selector"] == {"category": "quality", "term": "fat_soluble"}
    assert "not biochemical conflict or category disjointness" in constraint["semantic_note"]
