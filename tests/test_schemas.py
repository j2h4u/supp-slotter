"""CI-friendly check: every YAML data file in the repo conforms to its schema.

Direct counterpart of `planner.validate_schemas()` against the live `data/`
tree. Failure here is a hard signal that the repo state is structurally broken
— before any cross-reference logic, planner output, or downstream tests run.

Also includes Stage 1 unit tests for the new grouped-trait schema shapes,
from_traits resolution semantics, and reference-integrity checks.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import yaml

from planner.cards.dashboards import build_dashboard_review, check_dashboards
from planner.cards.substance import check_substances
from planner.cards.traits import load_traits
from planner.contracts import Substance
from planner.engine._scheduling import effective_stack_item_traits
from planner.io import ROOT, schema_errors, validate_schemas

DATA_DIR = ROOT / "data"


def test_repo_passes_schema_validation() -> None:
    assert validate_schemas() == 0, (
        "schema validation failed for files in data/; see stderr for details"
    )


# ---------------------------------------------------------------------------
# Substance schema — grouped form accepted / flat form rejected
# ---------------------------------------------------------------------------

def _make_substance_card(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"id": "sub_zz0000zzzz", "name": "Test Substance"}
    base.update(extra)
    return base


def test_substance_schema_accepts_grouped_form() -> None:
    card = _make_substance_card(**{"is": ["antioxidant"], "intake": ["food_preferred"]})
    errors = schema_errors(card, "substance", Path("test"))
    assert errors == [], f"Expected no errors, got: {errors}"


def test_substance_schema_rejects_flat_traits_form() -> None:
    card = _make_substance_card(traits=["class:antioxidant"])
    errors = schema_errors(card, "substance", Path("test"))
    assert errors, "Expected schema to reject flat traits: form"


def test_substance_schema_enforces_intake_maxitems() -> None:
    card = _make_substance_card(**{"intake": ["empty_preferred", "food_required"]})
    errors = schema_errors(card, "substance", Path("test"))
    assert errors, "Expected schema to reject intake with >1 item"


def test_substance_schema_enforces_closed_keys() -> None:
    # "note" (singular) is not a defined property — schema has "notes"
    card = _make_substance_card(**{"note": []})
    errors = schema_errors(card, "substance", Path("test"))
    assert errors, "Expected schema to reject unknown top-level key"


# ---------------------------------------------------------------------------
# Dashboard schema — from_traits form accepted
# ---------------------------------------------------------------------------

def _make_dashboard_card(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "Test Dashboard",
        "description": "Test description",
        "benefit": {"description": "Test benefit"},
        "from_traits": {"dashboard": ["connective_tissue_support"]},
    }
    base.update(extra)
    return base


def test_from_traits_dashboard_schema_accepts_grouped_form() -> None:
    card = _make_dashboard_card(
        from_traits={"dashboard": ["connective_tissue_support"]}
    )
    errors = schema_errors(card, "dashboard", Path("test"))
    assert errors == [], f"Expected no errors, got: {errors}"


# ---------------------------------------------------------------------------
# Reference-integrity: check_substances and check_dashboards
# ---------------------------------------------------------------------------

def _load_trait_ids() -> set[str]:
    trait_defs = load_traits(DATA_DIR / "traits.yaml")
    return set(trait_defs)


def test_check_substances_rejects_unknown_namespace_slug() -> None:
    trait_ids = _load_trait_ids()
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        prefix="unknown_test_substance__sub_zz0000zzzz",
        dir="/tmp",
        delete=False,
    ) as f:
        yaml.dump({"id": "sub_zz0000zzzz", "name": "Unknown Test Substance", "is": ["unknown_slug"]}, f)
        tmp_path = Path(f.name)

    try:
        errors, _info, _seen = check_substances([tmp_path], trait_ids)
        assert any("unknown_slug" in e for e in errors), f"Slug not caught: {errors}"
        assert any("register it in data/traits.yaml" in e for e in errors), f"Register msg missing: {errors}"
    finally:
        tmp_path.unlink(missing_ok=True)


def test_check_dashboards_rejects_unknown_from_traits_slug() -> None:
    trait_ids = _load_trait_ids()
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        prefix="test_dashboard_",
        dir="/tmp",
        delete=False,
    ) as f:
        yaml.dump({
            "name": "Test Dashboard",
            "description": "Test",
            "benefit": {"description": "Test benefit"},
            "from_traits": {"dashboard": ["unknown_slug_xyz789"]},
        }, f)
        tmp_path = Path(f.name)

    try:
        errors = check_dashboards([tmp_path], {}, {}, trait_ids)
        assert any("unknown_slug_xyz789" in e for e in errors), f"Slug not caught: {errors}"
        assert any("create data/dashboards/" in e for e in errors), f"Create msg missing: {errors}"
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# from_traits resolution: union (OR) across namespace groups
# ---------------------------------------------------------------------------

def test_from_traits_resolution_is_union_or() -> None:
    """Verify OR-across-namespaces semantics in build_dashboard_review().

    3 substances:
      A: dashboard: [foo]
      B: is: [bar]
      C: neither

    Dashboard from_traits: {dashboard: [foo], is: [bar]}
    Expected members: A and B (NOT A∩B, NOT empty — union/OR semantics).
    """
    sub_a = Substance(id="sub_aaaaaaaaaa", name="SubA", dashboard=("foo",))
    sub_b = Substance(id="sub_bbbbbbbbbb", name="SubB", is_=("bar",))
    sub_c = Substance(id="sub_cccccccccc", name="SubC")

    substances = {
        "sub_aaaaaaaaaa": sub_a,
        "sub_bbbbbbbbbb": sub_b,
        "sub_cccccccccc": sub_c,
    }

    # Write a temporary dashboard YAML
    dash_data = {
        "name": "Test OR Dashboard",
        "description": "Tests OR semantics",
        "benefit": {"description": "Test benefit"},
        "from_traits": {"dashboard": ["foo"], "is": ["bar"]},
    }

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        prefix="test_or_dashboard_",
        dir="/tmp",
        delete=False,
    ) as f:
        yaml.dump(dash_data, f)
        tmp_path = Path(f.name)

    try:
        result = build_dashboard_review(
            dashboard_files=[tmp_path],
            active_substances={"sub_aaaaaaaaaa", "sub_bbbbbbbbbb", "sub_cccccccccc"},
            inactive_substances=set(),
            substances=substances,
        )
        covered_names = set(result["benefits"][0].get("covered", []))
        # Both SubA and SubB must be members (OR semantics)
        assert "SubA" in covered_names, f"SubA not in covered: {covered_names}"
        assert "SubB" in covered_names, f"SubB not in covered: {covered_names}"
        # SubC must NOT be a member
        assert "SubC" not in covered_names, f"SubC should not be covered: {covered_names}"
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Scheduling traits: dashboard: namespace excluded from slot scoring
# ---------------------------------------------------------------------------

def test_dashboard_excluded_from_scheduling_traits() -> None:
    """dashboard: slugs must not appear in effective scheduling traits."""
    from planner.contracts import Product, ProductComponent, TraitDef

    substance = Substance(
        id="sub_zz0000zzzz",
        name="Test Substance",
        dashboard=("sleep_recovery",),
        is_=("nootropic",),
    )
    substances = {"sub_zz0000zzzz": substance}

    product = Product(
        id="prd_test",
        name="Test Product",
        components=(ProductComponent(substance="sub_zz0000zzzz"),),
    )

    # Minimal trait_defs with both traits
    trait_defs = {
        "dashboard:sleep_recovery": TraitDef(
            id="dashboard:sleep_recovery",
            namespace="dashboard",
            short_name="sleep_recovery",
            label="Sleep Recovery",
            description="",
            applies_when="",
        ),
        "is:nootropic": TraitDef(
            id="is:nootropic",
            namespace="is",
            short_name="nootropic",
            label="Nootropic",
            description="",
            applies_when="",
        ),
    }

    effective, _primary, _secondary_only, _trait_sources, _conflicts = effective_stack_item_traits(
        product, substances, trait_defs
    )

    assert "dashboard:sleep_recovery" not in effective, (
        "dashboard: slugs must be excluded from scheduling traits"
    )
    assert "is:nootropic" in effective, (
        "is: slugs must be included in scheduling traits"
    )
