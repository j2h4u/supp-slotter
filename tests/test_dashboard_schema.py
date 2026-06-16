"""Dashboard schema checks."""

from __future__ import annotations

from pathlib import Path

from planner.schema_validation import schema_errors


def _make_dashboard_card(**extra: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "Test Dashboard",
        "description": "Test description",
        "benefit": {"description": "Test benefit"},
        "from_traits": {"context": ["connective_tissue_support"]},
    }
    base.update(extra)
    return base


def test_from_traits_dashboard_schema_accepts_grouped_form() -> None:
    card = _make_dashboard_card(from_traits={"context": ["connective_tissue_support"]})
    errors = schema_errors(card, "dashboard", Path("test"))
    assert errors == [], f"Expected no errors, got: {errors}"


def test_from_traits_dashboard_schema_accepts_pathway_projection() -> None:
    card = _make_dashboard_card(from_traits={"pathway": ["methylation_cycle"]})
    errors = schema_errors(card, "dashboard", Path("test"))
    assert errors == [], f"Expected no errors, got: {errors}"


def test_from_traits_dashboard_schema_accepts_effect_projection() -> None:
    card = _make_dashboard_card(from_traits={"effect": ["cholinergic_support"]})
    errors = schema_errors(card, "dashboard", Path("test"))
    assert errors == [], f"Expected no errors, got: {errors}"
