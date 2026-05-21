"""Dashboard membership and review-output semantics."""

from __future__ import annotations

from pathlib import Path

import yaml

from planner.cards.dashboards import build_dashboard_review
from planner.contracts import Substance


def test_from_traits_resolution_is_union_or(tmp_path: Path) -> None:
    sub_a = Substance(id="sub_aaaaaaaaaa", name="SubA", context=("foo",))
    sub_b = Substance(id="sub_bbbbbbbbbb", name="SubB", is_=("bar",))
    sub_c = Substance(id="sub_cccccccccc", name="SubC")

    substances = {
        "sub_aaaaaaaaaa": sub_a,
        "sub_bbbbbbbbbb": sub_b,
        "sub_cccccccccc": sub_c,
    }
    dashboard = tmp_path / "test_or_dashboard.yaml"
    dashboard.write_text(
        yaml.safe_dump(
            {
                "name": "Test OR Dashboard",
                "description": "Tests OR semantics",
                "benefit": {"description": "Test benefit"},
                "from_traits": {"context": ["foo"], "is": ["bar"]},
            },
            sort_keys=False,
        )
    )

    result = build_dashboard_review(
        dashboard_files=[dashboard],
        active_substances={"sub_aaaaaaaaaa", "sub_bbbbbbbbbb", "sub_cccccccccc"},
        inactive_substances=set(),
        substances=substances,
    )

    covered_names = set(result["benefits"][0].get("covered", []))
    assert "SubA" in covered_names, f"SubA not in covered: {covered_names}"
    assert "SubB" in covered_names, f"SubB not in covered: {covered_names}"
    assert "SubC" not in covered_names, f"SubC should not be covered: {covered_names}"


def test_dashboard_review_surfaces_reference_only_substances_separately(
    tmp_path: Path,
) -> None:
    active = Substance(id="sub_aaaaaaaaaa", name="Active", context=("foo",))
    inactive = Substance(id="sub_bbbbbbbbbb", name="Inactive", context=("foo",))
    orphan = Substance(id="sub_cccccccccc", name="Orphan", context=("foo",))
    substances = {
        active.id: active,
        inactive.id: inactive,
        orphan.id: orphan,
    }
    dashboard = tmp_path / "test_product_scoped_dashboard.yaml"
    dashboard.write_text(
        yaml.safe_dump(
            {
                "name": "Product Scoped Dashboard",
                "description": "Tests reference-only dashboard output",
                "benefit": {"description": "Test benefit"},
                "from_traits": {"context": ["foo"]},
            },
            sort_keys=False,
        )
    )

    result = build_dashboard_review(
        dashboard_files=[dashboard],
        active_substances={active.id},
        inactive_substances={inactive.id},
        substances=substances,
    )

    entry = result["benefits"][0]
    assert entry.get("covered") == ["Active"]
    assert entry.get("inactive") == ["Inactive"]
    assert entry.get("reference_only") == ["Orphan"]
    assert "missing" not in entry
