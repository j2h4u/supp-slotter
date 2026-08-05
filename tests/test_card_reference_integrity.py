"""Reference-integrity checks for substance and dashboard cards."""

from __future__ import annotations

from pathlib import Path

import yaml
from planner.cards.dashboard_validation import check_dashboards
from planner.cards.substance_validation import check_substances
from planner.paths import Paths

from tests.helpers import ontology_bundle


def _trait_ids() -> set[str]:
    return set()


def test_check_substances_uses_explicit_ontology_bundle(tmp_path: Path) -> None:
    paths = Paths.from_root(tmp_path)
    substance_files: list[Path] = []
    for index in range(3):
        substance_id = f"sub_zz{index:06d}zzzz"
        path = tmp_path / f"test_substance_{index}__{substance_id}.yaml"
        path.write_text(yaml.safe_dump({"id": substance_id, "name": f"Test Substance {index}"}, sort_keys=False))
        substance_files.append(path)

    errors, info, seen = check_substances(substance_files, _trait_ids(), paths, ontology_bundle())

    assert errors == []
    assert info == []
    assert set(seen) == {f"sub_zz{index:06d}zzzz" for index in range(3)}


def test_check_substances_accepts_empty_batch(tmp_path: Path) -> None:
    result = check_substances([], _trait_ids(), Paths.from_root(tmp_path), ontology_bundle())

    assert result == ([], [], {})


def test_check_substances_preserves_load_errors(tmp_path: Path) -> None:
    missing_first = tmp_path / "missing-first.yaml"
    missing_second = tmp_path / "missing-second.yaml"

    errors, info, seen = check_substances(
        [missing_first, missing_second],
        _trait_ids(),
        Paths.from_root(tmp_path),
        ontology_bundle(),
    )

    assert errors == [
        f"{missing_first}: file does not exist",
        f"{missing_second}: file does not exist",
    ]
    assert info == []
    assert seen == {}


def test_check_substances_rejects_unknown_namespace_slug(tmp_path: Path) -> None:
    trait_ids = _trait_ids()
    paths = Paths.from_root(tmp_path)
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

    errors, _info, _seen = check_substances([probe], trait_ids, paths, ontology_bundle())

    assert any("unknown_slug" in e for e in errors), f"Slug not caught: {errors}"
    assert any("canonical ontology vocabulary" in e for e in errors), f"Vocabulary msg missing: {errors}"


def test_check_substances_rejects_unknown_review_trait_slug(tmp_path: Path) -> None:
    trait_ids = _trait_ids()
    paths = Paths.from_root(tmp_path)
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

    errors, _info, _seen = check_substances([probe], trait_ids, paths, ontology_bundle())

    assert any("unknown_effect_slug" in e for e in errors), errors
    assert any("unknown_risk_slug" in e for e in errors), errors
    assert any("unknown_pathway_slug" in e for e in errors), errors
    assert all("canonical ontology vocabulary" in e for e in errors), errors


def test_check_dashboards_rejects_unknown_selector_slug(tmp_path: Path) -> None:
    trait_ids = _trait_ids()
    paths = Paths.from_root(tmp_path)
    probe = tmp_path / "test_dashboard.yaml"
    probe.write_text(
        yaml.safe_dump(
            {
                "id": "test_dashboard",
                "name": "Test Dashboard",
                "description": "Test",
                "benefit": {"description": "Test benefit"},
                "selectors": [{"category": "context", "term": "unknown_slug_xyz789"}],
            },
            sort_keys=False,
        )
    )

    errors = check_dashboards([probe], trait_ids, paths, ontology_bundle())

    assert any("unknown_slug_xyz789" in e for e in errors), f"Slug not caught: {errors}"
    assert any("canonical ontology vocabulary" in e for e in errors), f"Vocabulary msg missing: {errors}"


def test_check_dashboards_rejects_unknown_effect_projection(tmp_path: Path) -> None:
    trait_ids = _trait_ids()
    paths = Paths.from_root(tmp_path)
    probe = tmp_path / "test_dashboard.yaml"
    probe.write_text(
        yaml.safe_dump(
            {
                "id": "test_dashboard",
                "name": "Test Dashboard",
                "description": "Test",
                "benefit": {"description": "Test benefit"},
                "selectors": [{"category": "effect", "term": "unknown_effect_slug"}],
            },
            sort_keys=False,
        )
    )

    errors = check_dashboards([probe], trait_ids, paths, ontology_bundle())

    assert any("unknown_effect_slug" in e for e in errors), f"Slug not caught: {errors}"
    assert any("canonical ontology vocabulary" in e for e in errors), f"Vocabulary msg missing: {errors}"


def test_check_dashboards_accepts_registered_effect_projection(
    tmp_path: Path,
) -> None:
    trait_ids = _trait_ids()
    paths = Paths.from_root(tmp_path)
    probe = tmp_path / "test_dashboard.yaml"
    probe.write_text(
        yaml.safe_dump(
            {
                "id": "test_dashboard",
                "name": "Test Dashboard",
                "description": "Test",
                "benefit": {"description": "Test benefit"},
                "selectors": [{"category": "effect", "term": "cholinergic_support"}],
            },
            sort_keys=False,
        )
    )

    errors = check_dashboards([probe], trait_ids, paths, ontology_bundle())

    assert errors == [], f"Expected no errors, got: {errors}"
