"""Dashboard membership and review-output semantics."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml
from planner.cards.dashboards import build_dashboard_review
from planner.contracts import Product, ProductComponent, StackEntry, Substance


def _benefit_members(review: dict[str, object]) -> list[dict[str, object]]:
    benefits = cast(list[dict[str, object]], review["benefits"])
    return cast(list[dict[str, object]], benefits[0]["members"])


def test_selector_resolution_is_union_or(tmp_path: Path) -> None:
    sub_a = Substance(id="sub_aaaaaaaaaa", name="SubA", context=("foo",))
    sub_b = Substance(id="sub_bbbbbbbbbb", name="SubB", kind=("bar",))
    sub_c = Substance(id="sub_cccccccccc", name="SubC")

    substances = {
        "sub_aaaaaaaaaa": sub_a,
        "sub_bbbbbbbbbb": sub_b,
        "sub_cccccccccc": sub_c,
    }
    products = {
        "prd_aaaaaaaaaa": Product(
            id="prd_aaaaaaaaaa",
            name="Product A",
            components=(ProductComponent(substance=sub_a.id),),
        ),
        "prd_bbbbbbbbbb": Product(
            id="prd_bbbbbbbbbb",
            name="Product B",
            components=(ProductComponent(substance=sub_b.id),),
        ),
    }
    stack_entries: dict[str, StackEntry] = {
        "prd_aaaaaaaaaa": {"product": "prd_aaaaaaaaaa", "stack": "daily"},
        "prd_bbbbbbbbbb": {"product": "prd_bbbbbbbbbb", "stack": "daily"},
    }
    dashboard = tmp_path / "test_or_dashboard.yaml"
    dashboard.write_text(
        yaml.safe_dump(
            {
                "id": "test_or_dashboard",
                "name": "Test OR Dashboard",
                "description": "Tests OR semantics",
                "benefit": {"description": "Test benefit"},
                "selectors": [{"category": "context", "term": "foo"}, {"category": "kind", "term": "bar"}],
            },
            sort_keys=False,
        )
    )

    result = cast(
        dict[str, object],
        build_dashboard_review(
            dashboard_files=[dashboard],
            products=products,
            stack_entries=stack_entries,
            substances=substances,
        ),
    )

    member_names = {cast(str, member["substance"]) for member in _benefit_members(result)}
    assert "SubA" in member_names, f"SubA not in members: {member_names}"
    assert "SubB" in member_names, f"SubB not in members: {member_names}"
    assert "SubC" not in member_names, f"SubC should not be a member: {member_names}"


def test_dashboard_review_separates_product_tracking_from_usage(
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
    products = {
        "prd_aaaaaaaaaa": Product(
            id="prd_aaaaaaaaaa",
            name="Active Product",
            components=(ProductComponent(substance=active.id),),
        ),
        "prd_bbbbbbbbbb": Product(
            id="prd_bbbbbbbbbb",
            name="Inactive Product",
            components=(ProductComponent(substance=inactive.id),),
        ),
    }
    stack_entries: dict[str, StackEntry] = {
        "prd_aaaaaaaaaa": {"product": "prd_aaaaaaaaaa", "stack": "daily"},
        "prd_bbbbbbbbbb": {"product": "prd_bbbbbbbbbb", "stack": "inactive"},
    }
    dashboard = tmp_path / "test_product_scoped_dashboard.yaml"
    dashboard.write_text(
        yaml.safe_dump(
            {
                "id": "test_product_scoped_dashboard",
                "name": "Product Scoped Dashboard",
                "description": "Tests normalized dashboard member output",
                "benefit": {"description": "Test benefit"},
                "selectors": [{"category": "context", "term": "foo"}],
            },
            sort_keys=False,
        )
    )

    result = cast(
        dict[str, object],
        build_dashboard_review(
            dashboard_files=[dashboard],
            products=products,
            stack_entries=stack_entries,
            substances=substances,
        ),
    )

    entry = cast(dict[str, object], cast(list[dict[str, object]], result["benefits"])[0])
    members = {cast(str, member["substance"]): member for member in _benefit_members(result)}
    assert cast(dict[str, object], members["Active"]["usage"])["state"] == "current"
    assert cast(dict[str, object], members["Active"]["product_tracking"])["state"] == "tracked_product"
    assert cast(dict[str, object], members["Inactive"]["usage"])["state"] == "on_shelf"
    assert cast(dict[str, object], members["Inactive"]["product_tracking"])["state"] == "tracked_product"
    assert cast(dict[str, object], members["Orphan"]["usage"])["state"] == "not_current"
    assert cast(dict[str, object], members["Orphan"]["product_tracking"])["state"] == "no_tracked_product"
    assert "covered" not in entry
    assert "missing" not in entry
