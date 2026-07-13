"""Dashboard schema checks."""

from __future__ import annotations

from pathlib import Path

from planner.schema_validation import schema_errors
from planner.yaml_io import YamlValue


def _make_dashboard_card(**extra: YamlValue) -> dict[str, YamlValue]:
    base: dict[str, YamlValue] = {
        "id": "test_dashboard",
        "name": "Test Dashboard",
        "description": "Test description",
        "benefit": {"description": "Test benefit"},
        "selectors": [{"category": "context", "term": "connective_tissue_support"}],
    }
    base.update(extra)
    return base


def test_selector_dashboard_schema_accepts_context_selector() -> None:
    card = _make_dashboard_card(selectors=[{"category": "context", "term": "connective_tissue_support"}])
    errors = schema_errors(card, "dashboard", Path("test"))
    assert errors == [], f"Expected no errors, got: {errors}"


def test_selector_dashboard_schema_accepts_pathway_selector() -> None:
    card = _make_dashboard_card(selectors=[{"category": "pathway", "term": "methylation_cycle"}])
    errors = schema_errors(card, "dashboard", Path("test"))
    assert errors == [], f"Expected no errors, got: {errors}"


def test_selector_dashboard_schema_accepts_effect_selector() -> None:
    card = _make_dashboard_card(selectors=[{"category": "effect", "term": "cholinergic_support"}])
    errors = schema_errors(card, "dashboard", Path("test"))
    assert errors == [], f"Expected no errors, got: {errors}"
