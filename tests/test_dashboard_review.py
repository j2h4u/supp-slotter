"""Dashboard membership and review-output semantics."""

from __future__ import annotations

from pathlib import Path

import yaml

from planner.cards.dashboards import build_dashboard_review
from planner.contracts import Product, ProductComponent, StackEntry, Substance


def test_from_traits_resolution_is_union_or(tmp_path: Path) -> None:
    sub_a = Substance(id="sub_aaaaaaaaaa", name="SubA", context=("foo",))
    sub_b = Substance(id="sub_bbbbbbbbbb", name="SubB", is_=("bar",))
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
        products=products,
        stack_entries=stack_entries,
        substances=substances,
    )

    member_names = {member["substance"] for member in result["benefits"][0]["members"]}
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
                "name": "Product Scoped Dashboard",
                "description": "Tests normalized dashboard member output",
                "benefit": {"description": "Test benefit"},
                "from_traits": {"context": ["foo"]},
            },
            sort_keys=False,
        )
    )

    result = build_dashboard_review(
        dashboard_files=[dashboard],
        products=products,
        stack_entries=stack_entries,
        substances=substances,
    )

    entry = result["benefits"][0]
    members = {member["substance"]: member for member in entry["members"]}
    assert members["Active"]["usage"]["state"] == "current"
    assert members["Active"]["product_tracking"]["state"] == "tracked_product"
    assert members["Inactive"]["usage"]["state"] == "on_shelf"
    assert members["Inactive"]["product_tracking"]["state"] == "tracked_product"
    assert members["Orphan"]["usage"]["state"] == "not_current"
    assert members["Orphan"]["product_tracking"]["state"] == "no_tracked_product"
    assert "covered" not in entry
    assert "missing" not in entry
