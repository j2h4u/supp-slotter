"""Tests for planner review and audit output boundaries."""

from __future__ import annotations

from pathlib import Path

from planner.engine import cmd_review

ROOT = Path(__file__).resolve().parents[1]

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
        "id: sub_aabbccdd01\nname: Test Risk Sub\nschedule: {}\nknowledge:\n  risk:\n  - manual_review\n"
    )
    (substances_dir / "review_with_source__sub_aabbccdd08.yaml").write_text(
        "id: sub_aabbccdd08\nname: L-Citrulline (malate)\nknowledge:\n  effect:\n  - nitric_oxide_support\n"
    )
    (substances_dir / "review_with_target__sub_aabbccdd09.yaml").write_text(
        "id: sub_aabbccdd09\nname: Tadalafil\nknowledge:\n  effect:\n  - pde5_inhibition\n"
    )

    # One product wrapping the substance above
    # ID pattern: ^prd_[a-z0-9]{10}$ — 'aabbccdd02' = 10 chars
    (products_dir / "test_risk_prod__prd_aabbccdd02.yaml").write_text(
        "id: prd_aabbccdd02\n"
        "name: Test Risk Product\n"
        "components:\n"
        "- substance: sub_aabbccdd01\n"
        "- substance: sub_aabbccdd08\n"
        "- substance: sub_aabbccdd09\n"
    )

    # Minimal stacks.yaml — product in daily stack (plain string format)
    (tmp / "data" / "stacks.yaml").write_text("daily:\n- prd_aabbccdd02\ntraining: []\ninactive: []\n")

    # Minimal pillboxes.yaml — one slot in daily pillbox
    (tmp / "data" / "pillboxes.yaml").write_text(
        "daily:\n"
        "  label: Daily\n"
        "  stack: daily\n"
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
        "effect:\n"
        "  nitric_oxide_support:\n"
        "    label: Nitric Oxide Support\n"
        "    description: Fixture source endpoint for review_with matching.\n"
        "    applies_when: Fixture only.\n"
        "  pde5_inhibition:\n"
        "    label: PDE5 Inhibition\n"
        "    description: Fixture target endpoint for review_with matching.\n"
        "    applies_when: Fixture only.\n"
    )

    # Canonical typed selector relation for concrete endpoint matching.
    (tmp / "data" / "relations.yaml").write_text(
        "relations:\n"
        "- id: rel_fixture_review_with\n"
        "  relation_type: review_with\n"
        "  assertion_kind: clinical_review_signal\n"
        "  semantic_family: clinical_review_signal\n"
        "  source_selector: {category: effect, term: nitric_oxide_support}\n"
        "  target_selector: {category: effect, term: pde5_inhibition}\n"
        "  reason: Fixture review_with relation.\n"
    )


# ---------------------------------------------------------------------------
# Tests against synthetic temp data root
# ---------------------------------------------------------------------------


def test_cmd_review_accepts_canonical_typed_selector_relation(tmp_path: Path) -> None:
    """Review consumes the canonical selector relation without alias decoding."""
    _write_minimal_data_root(tmp_path)
    result = cmd_review(data_root=tmp_path)
    output = result.output

    assert result.exit_code == 0
    assert "Actionable relation warnings (" in output


def test_cmd_review_renders_canonical_balance_metadata() -> None:
    result = cmd_review(data_root=ROOT)

    assert result.exit_code == 0, result.stderr
    relation_section = result.output.split("Actionable relation warnings", maxsplit=1)[1]
    assert "warning:" in relation_section
    assert "Vitamin E" in relation_section


def test_cmd_review_does_not_emit_audit_diagnostics(tmp_path: Path) -> None:
    """cmd_review() output does NOT include the audit diagnostics section."""
    _write_minimal_data_root(tmp_path)
    output = cmd_review(data_root=tmp_path).output
    assert "Audit diagnostics" not in output, f"review should not emit audit diagnostics: {output[:300]}"


# ---------------------------------------------------------------------------
# Test against minimal temp data root
# ---------------------------------------------------------------------------


def test_cmd_review_refuses_on_invalid_relations(tmp_path: Path) -> None:
    """cmd_review exits non-zero when relations.yaml has reference-integrity errors."""
    _write_minimal_data_root(tmp_path)
    # Overwrite minimal relations.yaml with an entry that references an
    # unknown canonical selector term — passes shape validation, fails vocabulary validation.
    (tmp_path / "data" / "relations.yaml").write_text(
        "relations:\n"
        "- id: rel_invalid_term\n"
        "  relation_type: supports\n"
        "  assertion_kind: ontology_assertion\n"
        "  semantic_family: biochemical_mechanism_assertion\n"
        "  source_selector: {category: kind, term: minearl}\n"
        "  target_selector: {category: quality, term: fat_soluble}\n"
        "  reason: Fixture relation with misspelled class slug.\n"
    )
    result = cmd_review(data_root=tmp_path)
    assert result.exit_code != 0
    assert "source_selector term 'kind:minearl' is not in canonical ontology vocabulary" in result.stderr
    assert "refusing" in result.stderr


def test_cmd_review_refuses_on_unknown_dashboard_selector(tmp_path: Path) -> None:
    _write_minimal_data_root(tmp_path)
    (tmp_path / "data" / "dashboards" / "unknown.yaml").write_text(
        "id: unknown_dashboard\n"
        "name: Unknown dashboard\n"
        "description: Fixture\n"
        "benefit:\n"
        "  description: Fixture benefit\n"
        "selectors:\n"
        "- category: context\n"
        "  term: not_a_canonical_term\n"
    )

    result = cmd_review(data_root=tmp_path)

    assert result.exit_code != 0
    assert "dashboard selectors[0] term 'context:not_a_canonical_term'" in result.stderr
    assert "canonical ontology vocabulary" in result.stderr
