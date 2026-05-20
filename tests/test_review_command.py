"""Tests for cmd_review (Phase 9: Planner/Reviewer ontology split)."""

from __future__ import annotations

import contextlib
import io
import tempfile
from pathlib import Path

from planner.engine import cmd_audit, cmd_review
from planner.engine.results import ReviewResult

# ---------------------------------------------------------------------------
# Minimal data-root fixture
# ---------------------------------------------------------------------------

def _write_minimal_data_root(tmp: Path) -> None:
    """Write the minimum YAML fixture needed for cmd_review to run end-to-end."""
    substances_dir = tmp / "data" / "substances"
    substances_dir.mkdir(parents=True)
    products_dir = tmp / "data" / "products"
    products_dir.mkdir(parents=True)
    dashboards_dir = tmp / "data" / "dashboards"
    dashboards_dir.mkdir(parents=True)

    # One substance carrying knowledge.risk: [manual_review]
    # ID pattern: ^sub_[a-z0-9]{10}$ — 'aabbccdd01' = 10 chars
    (substances_dir / "test_risk__sub_aabbccdd01.yaml").write_text(
        "id: sub_aabbccdd01\n"
        "name: Test Risk Sub\n"
        "schedule: {}\n"
        "knowledge:\n"
        "  risk:\n"
        "  - manual_review\n"
    )

    # One product wrapping the substance above
    # ID pattern: ^prd_[a-z0-9]{10}$ — 'aabbccdd02' = 10 chars
    (products_dir / "test_risk_prod__prd_aabbccdd02.yaml").write_text(
        "id: prd_aabbccdd02\n"
        "name: Test Risk Product\n"
        "components:\n"
        "- substance: sub_aabbccdd01\n"
        "  label: Test Risk Sub\n"
        "  amount: 100 mg\n"
    )

    # Minimal stacks.yaml — product in daily stack (plain string format)
    (tmp / "data" / "stacks.yaml").write_text(
        "daily:\n"
        "- prd_aabbccdd02\n"
        "training: []\n"
        "inactive: []\n"
    )

    # Minimal pillboxes.yaml — one slot in daily pillbox
    (tmp / "data" / "pillboxes.yaml").write_text(
        "daily:\n"
        "  label: Daily\n"
        "  slots:\n"
        "    morning_food:\n"
        "      label: Morning / with breakfast\n"
        "      order: 1\n"
        "      near: breakfast\n"
        "      food: true\n"
    )

    traits_dir = tmp / "data" / "traits"
    traits_dir.mkdir()
    # Minimal trait registry — just enough for check_substances to parse
    (traits_dir / "fixture.yaml").write_text(
        "intake:\n"
        "  food_preferred:\n"
        "    label: Food preferred\n"
        "    description: Take with food for best absorption.\n"
        "    applies_when: always\n"
    )

    # relations.yaml — empty competes block (load_global_relations handles missing file too)
    (tmp / "data" / "relations.yaml").write_text("competes: []\n")


# ---------------------------------------------------------------------------
# Tests against live data (no args)
# ---------------------------------------------------------------------------

def test_cmd_review_exits_zero() -> None:
    """cmd_review() on the live data returns ReviewResult with exit_code == 0."""
    result = cmd_review()
    assert isinstance(result, ReviewResult)
    assert result.exit_code == 0


def test_cmd_review_output_has_section_headers() -> None:
    """cmd_review() output contains all expected section headers."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_review()
    output = buf.getvalue()
    assert "Risk flags" in output, f"missing 'Risk flags' in: {output[:300]}"
    assert "Pathway memberships" in output, f"missing 'Pathway memberships' in: {output[:300]}"
    assert "Relations (" in output, f"missing 'Relations (' in: {output[:300]}"
    assert "Dashboard summary" in output, f"missing 'Dashboard summary' in: {output[:300]}"


def test_cmd_audit_does_not_emit_concerns_or_relations() -> None:
    """cmd_audit() output does NOT include the Concerns or Relations section headers."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_audit()
    output = buf.getvalue()
    assert "Safety (" not in output, f"audit still emits Safety header: {output[:300]}"
    assert "Relations (" not in output, f"audit still emits Relations header: {output[:300]}"


def test_cmd_audit_labels_reference_only_substances_without_cleanup_framing() -> None:
    """Reference-only substance cards are valid KB entries, not deletion prompts."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_audit()
    output = buf.getvalue()
    assert "Audit diagnostics" in output
    assert "Reference-only substances" in output
    assert "Substances unused" not in output
    assert "Cleanup candidates" not in output


def test_cmd_review_does_not_emit_cleanup_candidates() -> None:
    """cmd_review() output does NOT include the Cleanup candidates section."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_review()
    output = buf.getvalue()
    assert "Cleanup candidates" not in output, (
        f"review should not emit Cleanup candidates: {output[:300]}"
    )


# ---------------------------------------------------------------------------
# Test against minimal temp data root
# ---------------------------------------------------------------------------

def test_cmd_review_surfaces_risk_manual_review() -> None:
    """cmd_review surfaces a substance's name under manual_review in Risk flags section."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        _write_minimal_data_root(tmp)
        result = cmd_review(data_root=tmp)
        assert result.exit_code == 0, f"cmd_review failed: {result.stderr}"
        assert "manual_review" in result.output, (
            f"Risk flags section missing manual_review group: {result.output}"
        )
        assert "Test Risk Sub" in result.output, (
            f"Risk flags section missing substance name: {result.output}"
        )


def test_cmd_review_refuses_on_invalid_relations() -> None:
    """cmd_review exits non-zero when relations.yaml has reference-integrity errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        _write_minimal_data_root(tmp)
        # Overwrite minimal relations.yaml with an entry that references an
        # unregistered is: class — passes JSON Schema, fails check_global_relations.
        (tmp / "data" / "relations.yaml").write_text(
            "competes:\n"
            "- source_class: minearl\n"
            "  target_class: fat_soluble\n"
            "  reason: Fixture relation with misspelled class slug.\n"
        )
        result = cmd_review(data_root=tmp)
        assert result.exit_code != 0
        assert "source_class 'minearl' is not a registered is: trait" in result.stderr
        assert "refusing" in result.stderr
