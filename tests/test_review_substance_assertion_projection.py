"""Regression coverage for canonical assertion rendering in review-substance."""

from __future__ import annotations

from planner.engine.review import cmd_review_substance


def test_review_substance_renders_resolved_canonical_assertion_endpoints() -> None:
    result = cmd_review_substance(
        "data/substances/vitamin_b6_pyridoxine_hcl__sub_a873e428ee.yaml",
        compact=True,
    )

    assert result.exit_code == 0, result.stderr
    assert "review_with" in result.output
    assert "Vitamin B6 (pyridoxine HCl) -> Levodopa" in result.output
    assert "matched by: source selector" in result.output
