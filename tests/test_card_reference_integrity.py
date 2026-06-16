"""Reference-integrity checks for substance and dashboard cards."""

from __future__ import annotations

from pathlib import Path

import yaml

from planner.cards.dashboard_validation import check_dashboards
from planner.cards.substance_validation import check_substances
from planner.cards.traits import load_traits
from planner.paths import ROOT, Paths

DATA_DIR = ROOT / "data"


def _load_trait_ids() -> set[str]:
    trait_defs = load_traits(DATA_DIR / "traits")
    return set(trait_defs)


def test_check_substances_rejects_unknown_namespace_slug(tmp_path: Path) -> None:
    trait_ids = _load_trait_ids()
    probe = tmp_path / "unknown_test_substance__sub_zz0000zzzz.yaml"
    probe.write_text(
        yaml.safe_dump(
            {
                "id": "sub_zz0000zzzz",
                "name": "Unknown Test Substance",
                "schedule": {"intake": ["unknown_slug"]},
            },
            sort_keys=False,
        )
    )

    errors, _info, _seen = check_substances([probe], trait_ids, Paths.default())

    assert any("unknown_slug" in e for e in errors), f"Slug not caught: {errors}"
    assert any("register it in data/traits/" in e for e in errors), f"Register msg missing: {errors}"


def test_check_substances_rejects_unknown_review_trait_slug(tmp_path: Path) -> None:
    trait_ids = _load_trait_ids()
    probe = tmp_path / "unknown_review_test__sub_zz0000zzzz.yaml"
    probe.write_text(
        yaml.safe_dump(
            {
                "id": "sub_zz0000zzzz",
                "name": "Unknown Review Test",
                "knowledge": {
                    "effect": ["unknown_effect_slug"],
                    "risk": ["unknown_risk_slug"],
                    "pathway": ["unknown_pathway_slug"],
                },
            },
            sort_keys=False,
        )
    )

    errors, _info, _seen = check_substances([probe], trait_ids, Paths.default())

    assert any("unknown_effect_slug" in e for e in errors), errors
    assert any("unknown_risk_slug" in e for e in errors), errors
    assert any("unknown_pathway_slug" in e for e in errors), errors
    assert all("register it in data/traits/" in e for e in errors), errors


def test_check_dashboards_rejects_unknown_from_traits_slug(tmp_path: Path) -> None:
    trait_ids = _load_trait_ids()
    probe = tmp_path / "test_dashboard.yaml"
    probe.write_text(
        yaml.safe_dump(
            {
                "name": "Test Dashboard",
                "description": "Test",
                "benefit": {"description": "Test benefit"},
                "from_traits": {"context": ["unknown_slug_xyz789"]},
            },
            sort_keys=False,
        )
    )

    errors = check_dashboards([probe], trait_ids, Paths.default())

    assert any("unknown_slug_xyz789" in e for e in errors), f"Slug not caught: {errors}"
    assert any("create data/dashboards/" in e for e in errors), f"Create msg missing: {errors}"


def test_check_dashboards_rejects_unknown_effect_projection(tmp_path: Path) -> None:
    trait_ids = _load_trait_ids()
    probe = tmp_path / "test_dashboard.yaml"
    probe.write_text(
        yaml.safe_dump(
            {
                "name": "Test Dashboard",
                "description": "Test",
                "benefit": {"description": "Test benefit"},
                "from_traits": {"effect": ["unknown_effect_slug"]},
            },
            sort_keys=False,
        )
    )

    errors = check_dashboards([probe], trait_ids, Paths.default())

    assert any("unknown_effect_slug" in e for e in errors), f"Slug not caught: {errors}"
    assert any("register it in data/traits/" in e for e in errors), f"Register msg missing: {errors}"


def test_check_dashboards_accepts_registered_effect_projection(
    tmp_path: Path,
) -> None:
    trait_ids = _load_trait_ids()
    probe = tmp_path / "test_dashboard.yaml"
    probe.write_text(
        yaml.safe_dump(
            {
                "name": "Test Dashboard",
                "description": "Test",
                "benefit": {"description": "Test benefit"},
                "from_traits": {"effect": ["cholinergic_support"]},
            },
            sort_keys=False,
        )
    )

    errors = check_dashboards([probe], trait_ids, Paths.default())

    assert errors == [], f"Expected no errors, got: {errors}"
