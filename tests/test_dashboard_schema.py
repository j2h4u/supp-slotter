"""Dashboard schema checks."""

from __future__ import annotations

from pathlib import Path

import pytest
from planner.schema_validation import schema_errors
from planner.yaml_io import YamlValue

from tests.helpers import ontology_bundle


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


@pytest.mark.parametrize(
    ("category", "term"),
    [
        ("context", "connective_tissue_support"),
        ("pathway", "methylation_cycle"),
        ("effect", "cholinergic_support"),
    ],
)
def test_selector_dashboard_schema_accepts_selector(category: str, term: str) -> None:
    card = _make_dashboard_card(selectors=[{"category": category, "term": term}])
    errors = schema_errors(card, "dashboard", Path("test"), ontology_bundle())
    assert errors == [], f"Expected no errors, got: {errors}"


def test_dashboard_schema_rejects_schedule_axis_selector() -> None:
    card = _make_dashboard_card(selectors=[{"category": "intake", "term": "food_preferred"}])
    errors = schema_errors(card, "dashboard", Path("test"), ontology_bundle())
    assert any("intake" in error for error in errors)


def test_dashboard_schema_rejects_removed_started_field() -> None:
    errors = schema_errors(_make_dashboard_card(started="2026-01-01"), "dashboard", Path("test"), ontology_bundle())
    assert any("started" in error for error in errors)
