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
from planner.cards.substance import check_substances, load_substance
from planner.cards.traits import load_traits
from planner.contracts import CardLoadError, Substance
from planner.engine._scheduling import effective_stack_item_traits
from planner.io import ROOT, Paths, schema_errors

DATA_DIR = ROOT / "data"


# ---------------------------------------------------------------------------
# Substance schema — v2-only shape (oneOf and $defs.v1_flat removed in plan 05)
# ---------------------------------------------------------------------------

def _make_substance_card(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"id": "sub_zz0000zzzz", "name": "Test Substance"}
    base.update(extra)
    return base


def test_substance_schema_accepts_nested_form() -> None:
    card = _make_substance_card(
        schedule={"intake": ["food_preferred"], "timing": ["sleep_support"]},
        knowledge={"is": ["amino"], "risk": ["manual_review"]},
    )
    errors = schema_errors(card, "substance", Path("test"))
    assert errors == [], f"Expected no errors, got: {errors}"


def test_substance_schema_rejects_flat_form() -> None:
    """v2-only schema rejects a card with a top-level v1 flat namespace key (intake:)."""
    card = _make_substance_card(**{"intake": ["food_preferred"]})
    errors = schema_errors(card, "substance", Path("test"))
    assert errors, "Expected v2-only schema to reject flat intake: key, got no errors"


def test_substance_schema_rejects_flat_is_risk_etc() -> None:
    """v2-only schema rejects each of the seven v1 flat namespace keys at top level."""
    flat_keys: dict[str, Any] = {
        "is": ["antioxidant"],
        "intake": ["food_preferred"],
        "effect": ["energy_like"],
        "risk": ["manual_review"],
        "activity": ["pre_workout"],
        "context": ["cardiovascular"],
        "prefer_with": ["sub_aabbccdd01"],
    }
    for key, value in flat_keys.items():
        card = _make_substance_card(**{key: value})
        errors = schema_errors(card, "substance", Path("test"))
        assert errors, f"Expected schema to reject flat top-level key '{key}:', got no errors"


def test_substance_schema_rejects_flat_traits_form() -> None:
    card = _make_substance_card(traits=["class:antioxidant"])
    errors = schema_errors(card, "substance", Path("test"))
    assert errors, "Expected schema to reject flat traits: form"


def test_substance_schema_enforces_intake_maxitems() -> None:
    card = _make_substance_card(schedule={"intake": ["empty_preferred", "food_required"]})
    errors = schema_errors(card, "substance", Path("test"))
    assert errors, "Expected schema to reject intake with >1 item"


def test_substance_schema_enforces_closed_keys() -> None:
    # "note" (singular) is not a defined property — schema has "notes"
    card = _make_substance_card(**{"note": []})
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


def test_substance_schema_rejects_mixed_form() -> None:
    card = _make_substance_card(
        schedule={"timing": ["sleep_support"]},
        **{"intake": ["food_preferred"]},
    )
    errors = schema_errors(card, "substance", Path("test"))
    assert errors, "Expected schema to reject a card mixing schedule: with flat namespace key"


def test_check_rejects_ambiguous_dual_format() -> None:
    """load_substance raises CardLoadError on a card with flat keys (schema enforces v2-only)."""
    card = {
        "id": "sub_zz0000zzzz",
        "name": "Ambiguous Test",
        "intake": ["food_preferred"],
        "schedule": {"timing": ["sleep_support"]},
    }
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        dir="/tmp",
        delete=False,
    ) as f:
        yaml.dump(card, f)
        tmp = Path(f.name)
    try:
        import pytest
        with pytest.raises(CardLoadError) as exc_info:
            load_substance(tmp)
        msg = str(exc_info.value)
        # Schema now enforces v2-only via additionalProperties: false — message wording
        # may vary (schema error vs. explicit guard); any CardLoadError is correct.
        assert len(msg) > 0
    finally:
        tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Dashboard schema — from_traits form accepted
# ---------------------------------------------------------------------------

def _make_dashboard_card(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "Test Dashboard",
        "description": "Test description",
        "benefit": {"description": "Test benefit"},
        "from_traits": {"context": ["connective_tissue_support"]},
    }
    base.update(extra)
    return base


def test_from_traits_dashboard_schema_accepts_grouped_form() -> None:
    card = _make_dashboard_card(
        from_traits={"context": ["connective_tissue_support"]}
    )
    errors = schema_errors(card, "dashboard", Path("test"))
    assert errors == [], f"Expected no errors, got: {errors}"


def test_from_traits_dashboard_schema_accepts_pathway_projection() -> None:
    card = _make_dashboard_card(
        from_traits={"pathway": ["methylation_cycle"]}
    )
    errors = schema_errors(card, "dashboard", Path("test"))
    assert errors == [], f"Expected no errors, got: {errors}"


def test_from_traits_dashboard_schema_accepts_effect_projection() -> None:
    card = _make_dashboard_card(
        from_traits={"effect": ["cholinergic_support"]}
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
        yaml.dump({"id": "sub_zz0000zzzz", "name": "Unknown Test Substance", "schedule": {"intake": ["unknown_slug"]}}, f)
        tmp_path = Path(f.name)

    try:
        errors, _info, _seen = check_substances([tmp_path], trait_ids, Paths.default())
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
            "from_traits": {"context": ["unknown_slug_xyz789"]},
        }, f)
        tmp_path = Path(f.name)

    try:
        errors = check_dashboards([tmp_path], {}, {}, trait_ids, Paths.default())
        assert any("unknown_slug_xyz789" in e for e in errors), f"Slug not caught: {errors}"
        assert any("create data/dashboards/" in e for e in errors), f"Create msg missing: {errors}"
    finally:
        tmp_path.unlink(missing_ok=True)


def test_check_dashboards_accepts_operator_curated_effect_projection() -> None:
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
            "from_traits": {"effect": ["cholinergic_support"]},
        }, f)
        tmp_path = Path(f.name)

    try:
        errors = check_dashboards([tmp_path], {}, {}, trait_ids, Paths.default())
        assert errors == [], f"Expected no errors, got: {errors}"
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# from_traits resolution: union (OR) across namespace groups
# ---------------------------------------------------------------------------

def test_from_traits_resolution_is_union_or() -> None:
    """Verify OR-across-namespaces semantics in build_dashboard_review().

    3 substances:
      A: context: [foo]
      B: is: [bar]
      C: neither

    Dashboard from_traits: {context: [foo], is: [bar]}
    Expected members: A and B (NOT A∩B, NOT empty — union/OR semantics).
    """
    sub_a = Substance(id="sub_aaaaaaaaaa", name="SubA", context=("foo",))
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
        "from_traits": {"context": ["foo"], "is": ["bar"]},
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


def test_dashboard_review_omits_orphan_reference_substances() -> None:
    """Dashboard review is product-scoped.

    A matching substance that is not active and not in inactive shelf products is
    reference knowledge, not a dashboard "missing product" recommendation.
    """
    active = Substance(id="sub_aaaaaaaaaa", name="Active", context=("foo",))
    inactive = Substance(id="sub_bbbbbbbbbb", name="Inactive", context=("foo",))
    orphan = Substance(id="sub_cccccccccc", name="Orphan", context=("foo",))
    substances = {
        active.id: active,
        inactive.id: inactive,
        orphan.id: orphan,
    }

    dash_data = {
        "name": "Product Scoped Dashboard",
        "description": "Tests product-scoped dashboard output",
        "benefit": {"description": "Test benefit"},
        "from_traits": {"context": ["foo"]},
    }

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        prefix="test_product_scoped_dashboard_",
        dir="/tmp",
        delete=False,
    ) as f:
        yaml.dump(dash_data, f)
        tmp_path = Path(f.name)

    try:
        result = build_dashboard_review(
            dashboard_files=[tmp_path],
            active_substances={active.id},
            inactive_substances={inactive.id},
            substances=substances,
        )
        entry = result["benefits"][0]
        assert entry.get("covered") == ["Active"]
        assert entry.get("inactive") == ["Inactive"]
        assert "missing" not in entry
        assert "Orphan" not in str(entry)
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Scheduling traits: context: namespace excluded from slot scoring
# ---------------------------------------------------------------------------

def test_knowledge_and_context_excluded_from_scheduling_traits() -> None:
    """knowledge: namespace slugs (is, context, effect, risk, pathway) must not appear in
    effective scheduling traits. Only schedule: namespace slugs (intake, timing, activity)
    drive slot assignment."""
    from planner.contracts import Product, ProductComponent, TraitDef

    substance = Substance(
        id="sub_zz0000zzzz",
        name="Test Substance",
        context=("sleep_recovery",),
        is_=("nootropic",),
        intake=("food_preferred",),
        timing=("sleep_support",),
    )
    substances = {"sub_zz0000zzzz": substance}

    product = Product(
        id="prd_test",
        name="Test Product",
        components=(ProductComponent(substance="sub_zz0000zzzz"),),
    )

    # Minimal trait_defs
    trait_defs = {
        "context:sleep_recovery": TraitDef(
            id="context:sleep_recovery",
            namespace="context",
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
        "intake:food_preferred": TraitDef(
            id="intake:food_preferred",
            namespace="intake",
            short_name="food_preferred",
            label="Food preferred",
            description="",
            applies_when="",
        ),
        "timing:sleep_support": TraitDef(
            id="timing:sleep_support",
            namespace="timing",
            short_name="sleep_support",
            label="Sleep support",
            description="",
            applies_when="",
        ),
    }

    effective, _primary, _secondary_only, _trait_sources, _conflicts = effective_stack_item_traits(
        product, substances, trait_defs
    )

    # knowledge: fields are excluded from scheduling
    assert "context:sleep_recovery" not in effective, (
        "context: slugs must be excluded from scheduling traits"
    )
    assert "is:nootropic" not in effective, (
        "is: slugs must be excluded from scheduling traits (knowledge: field, Reviewer-only)"
    )
    # schedule: fields are included
    assert "intake:food_preferred" in effective, (
        "intake: slugs must be included in scheduling traits"
    )
    assert "timing:sleep_support" in effective, (
        "timing: slugs must be included in scheduling traits"
    )
