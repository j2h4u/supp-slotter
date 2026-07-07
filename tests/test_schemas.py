"""Substance schema checks."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from planner.cards.substance import load_substance
from planner.contracts import CardLoadError
from planner.schema_validation import schema_errors
from planner.yaml_io import YamlValue


def _make_substance_card(**extra: YamlValue) -> dict[str, YamlValue]:
    base: dict[str, YamlValue] = {"id": "sub_zz0000zzzz", "name": "Test Substance"}
    base.update(extra)
    return base


def test_substance_schema_accepts_nested_form() -> None:
    card = _make_substance_card(
        schedule={"intake": ["food_preferred"], "timing": ["sleep_support"]},
        knowledge={"is": ["amino"], "risk": ["manual_review"]},
    )
    errors = schema_errors(card, "substance", Path("test"))
    assert errors == [], f"Expected no errors, got: {errors}"


def test_substance_schema_rejects_top_level_schedule_namespace_key() -> None:
    card = _make_substance_card(intake=["food_preferred"])
    errors = schema_errors(card, "substance", Path("test"))
    assert errors, "Expected schema to reject top-level schedule namespace key"


def test_substance_schema_rejects_top_level_trait_namespace_keys() -> None:
    namespace_keys: dict[str, YamlValue] = {
        "is": ["antioxidant"],
        "intake": ["food_preferred"],
        "effect": ["energy_like"],
        "risk": ["manual_review"],
        "activity": ["pre_workout"],
        "context": ["cardiovascular"],
        "prefer_with": ["sub_aabbccdd01"],
    }
    for key, value in namespace_keys.items():
        card = _make_substance_card(**{key: value})
        errors = schema_errors(card, "substance", Path("test"))
        assert errors, f"Expected schema to reject top-level namespace key '{key}:'"


def test_substance_schema_rejects_top_level_traits_key() -> None:
    card = _make_substance_card(traits=["class:antioxidant"])
    errors = schema_errors(card, "substance", Path("test"))
    assert errors, "Expected schema to reject unknown top-level traits key"


def test_substance_schema_enforces_intake_maxitems() -> None:
    card = _make_substance_card(schedule={"intake": ["empty_preferred", "food_required"]})
    errors = schema_errors(card, "substance", Path("test"))
    assert errors, "Expected schema to reject intake with >1 item"


def test_substance_schema_enforces_closed_keys() -> None:
    card = _make_substance_card(note=[])
    errors = schema_errors(card, "substance", Path("test"))
    assert errors, "Expected schema to reject unknown top-level key"


def test_substance_schema_rejects_unknown_key_inside_schedule() -> None:
    card = _make_substance_card(schedule={"foo": []})
    errors = schema_errors(card, "substance", Path("test"))
    assert errors, "Expected schema to reject unknown key inside schedule:"


def test_substance_schema_rejects_unknown_key_inside_knowledge() -> None:
    card = _make_substance_card(knowledge={"bar": []})
    errors = schema_errors(card, "substance", Path("test"))
    assert errors, "Expected schema to reject unknown key inside knowledge:"


def test_substance_schema_rejects_unknown_top_level_namespace_key_with_schedule() -> None:
    card = _make_substance_card(
        schedule={"timing": ["sleep_support"]},
        intake=["food_preferred"],
    )
    errors = schema_errors(card, "substance", Path("test"))
    assert errors, "Expected schema to reject unknown top-level namespace key"


def test_load_substance_rejects_unknown_top_level_namespace_key(tmp_path: Path) -> None:
    card = {
        "id": "sub_zz0000zzzz",
        "name": "Ambiguous Test",
        "intake": ["food_preferred"],
        "schedule": {"timing": ["sleep_support"]},
    }
    probe = tmp_path / "ambiguous__sub_zz0000zzzz.yaml"
    probe.write_text(yaml.safe_dump(card, sort_keys=False))

    with pytest.raises(CardLoadError) as exc_info:
        load_substance(probe)

    assert str(exc_info.value)
