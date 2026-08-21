"""Dashboard membership and review-output semantics."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.cards.dashboards import build_dashboard_review
from planner.contracts import KnowledgeAssertion, Product, ProductComponent, RelationSelector, StackEntry, Substance
from planner.engine import review_model
from planner.engine.review_model import _dashboard_summary
from planner.ontology.selector import resolve_dashboard_selector, resolve_selector
from planner.paths import Paths

from tests.helpers import ontology_bundle


def test_dashboard_review_rejects_product_in_active_and_inactive_stacks(tmp_path: Path) -> None:
    substance = Substance(
        id="sub_aaaaaaaaaa",
        name="Duplicate stack substance",
        knowledge_assertions=(KnowledgeAssertion("context", "vascular_health"),),
    )
    product = Product(
        id="prd_aaaaaaaaaa",
        name="Duplicate stack product",
        components=(ProductComponent(substance=substance.id),),
    )
    dashboard = tmp_path / "duplicate_stack_dashboard.yaml"
    dashboard.write_text(
        yaml.safe_dump(
            {
                "id": "duplicate_stack_dashboard",
                "name": "Duplicate stack dashboard",
                "description": "duplicate stack regression",
                "benefit": {"description": "benefit"},
                "selectors": [{"category": "context", "term": "vascular_health"}],
            },
            sort_keys=False,
        )
    )

    with pytest.raises(ValueError, match=r"prd_aaaaaaaaaa.*multiple stacks"):
        build_dashboard_review(
            dashboard_files=[dashboard],
            products={product.id: product},
            stack_entries={
                "daily": {"product": product.id, "stack": "daily"},
                "inactive": {"product": product.id, "stack": "inactive"},
            },
            substances={substance.id: substance},
            bundle=ontology_bundle(),
        )


def _benefit_members(review: dict[str, object]) -> list[dict[str, object]]:
    benefits = cast(list[dict[str, object]], review["benefits"])
    return cast(list[dict[str, object]], benefits[0]["members"])


def test_selector_resolution_distinguishes_unknown_from_valid_empty() -> None:
    bundle = ontology_bundle()

    valid_empty = resolve_selector(
        RelationSelector(category="context", term="vascular_health"),
        {},
        bundle,
    )
    unknown = resolve_selector(
        RelationSelector(category="context", term="not_a_canonical_term"),
        {},
        bundle,
    )

    assert valid_empty.outcome == "empty"
    assert unknown.outcome == "unsupported_selector"


def test_dashboard_selector_resolution_rejects_schedule_axes() -> None:
    result = resolve_dashboard_selector(
        RelationSelector(category="intake", term="food_preferred"),
        {},
        ontology_bundle(),
    )
    assert result.outcome == "unsupported_selector"


def test_selector_resolution_is_union_or(tmp_path: Path) -> None:
    sub_a = Substance(
        id="sub_aaaaaaaaaa",
        name="SubA",
        knowledge_assertions=(KnowledgeAssertion("context", "vascular_health"),),
    )
    sub_b = Substance(
        id="sub_bbbbbbbbbb",
        name="SubB",
        knowledge_assertions=(KnowledgeAssertion("kind", "mineral"),),
    )
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
                "selectors": [
                    {"category": "context", "term": "vascular_health"},
                    {"category": "kind", "term": "mineral"},
                ],
            },
            sort_keys=False,
        )
    )

    result = cast(
        dict[str, object],
        build_dashboard_review(
            dashboard_files=[dashboard],
            bundle=ontology_bundle(),
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
    context_assertion = (KnowledgeAssertion("context", "vascular_health"),)
    active = Substance(id="sub_aaaaaaaaaa", name="Active", knowledge_assertions=context_assertion)
    inactive = Substance(id="sub_bbbbbbbbbb", name="Inactive", knowledge_assertions=context_assertion)
    orphan = Substance(id="sub_cccccccccc", name="Orphan", knowledge_assertions=context_assertion)
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
                "selectors": [{"category": "context", "term": "vascular_health"}],
            },
            sort_keys=False,
        )
    )

    result = cast(
        dict[str, object],
        build_dashboard_review(
            dashboard_files=[dashboard],
            bundle=ontology_bundle(),
            products=products,
            stack_entries=stack_entries,
            substances=substances,
        ),
    )

    entry = cast(dict[str, object], cast(list[dict[str, object]], result["benefits"])[0])
    assert entry["id"] == "test_product_scoped_dashboard"
    assert entry["declares_context"] == []
    assert entry["declares_context_labels"] == []
    members = {cast(str, member["substance"]): member for member in _benefit_members(result)}
    assert cast(dict[str, object], members["Active"]["usage"])["state"] == "current"
    assert cast(dict[str, object], members["Active"]["product_tracking"])["state"] == "tracked_product"
    assert cast(dict[str, object], members["Inactive"]["usage"])["state"] == "on_shelf"
    assert cast(dict[str, object], members["Inactive"]["product_tracking"])["state"] == "tracked_product"
    assert cast(dict[str, object], members["Orphan"]["usage"])["state"] == "not_current"
    assert cast(dict[str, object], members["Orphan"]["product_tracking"])["state"] == "no_tracked_product"
    assert "covered" not in entry
    assert "missing" not in entry


def test_dashboard_review_retains_union_of_active_and_inactive_stacks(
    tmp_path: Path,
) -> None:
    substance = Substance(
        id="sub_aaaaaaaaaa",
        name="Both stacks",
        knowledge_assertions=(KnowledgeAssertion("context", "vascular_health"),),
    )
    products = {
        "prd_aaaaaaaaaa": Product(
            id="prd_aaaaaaaaaa",
            name="Daily product",
            components=(ProductComponent(substance=substance.id),),
        ),
        "prd_bbbbbbbbbb": Product(
            id="prd_bbbbbbbbbb",
            name="Inactive product",
            components=(ProductComponent(substance=substance.id),),
        ),
    }
    stack_entries: dict[str, StackEntry] = {
        "prd_aaaaaaaaaa": {"product": "prd_aaaaaaaaaa", "stack": "daily"},
        "prd_bbbbbbbbbb": {"product": "prd_bbbbbbbbbb", "stack": "inactive"},
    }
    dashboard = tmp_path / "both_stacks_dashboard.yaml"
    dashboard.write_text(
        yaml.safe_dump(
            {
                "id": "both_stacks_dashboard",
                "name": "Both stacks dashboard",
                "description": "Tests union stack provenance",
                "benefit": {"description": "Test benefit"},
                "selectors": [{"category": "context", "term": "vascular_health"}],
            },
            sort_keys=False,
        )
    )

    bundle = ontology_bundle()
    result = cast(
        dict[str, object],
        build_dashboard_review(
            dashboard_files=[dashboard],
            bundle=bundle,
            products=products,
            stack_entries=stack_entries,
            substances={substance.id: substance},
        ),
    )

    member = _benefit_members(result)[0]
    usage = cast(dict[str, object], member["usage"])
    expected_state = bundle.runtime_program.dashboard_state_catalog.usage_state_for(
        active_stack_membership=True,
        inactive_stack_membership=True,
        tracked_product_presence=True,
    )
    assert usage == {"state": expected_state.state, "stacks": ["daily", "inactive"]}


def test_dashboard_summary_preserves_same_name_dashboards_with_distinct_ids(
    tmp_path: Path,
    monkeypatch,
) -> None:
    review_data = {
        "benefits": [
            {
                "id": "dashboard_first",
                "name": "Shared dashboard name",
                "declares_context": [],
                "declares_context_labels": [],
            },
            {
                "id": "dashboard_second",
                "name": "Shared dashboard name",
                "declares_context": [],
                "declares_context_labels": [],
            },
        ],
        "risks": [],
        "warnings": [],
    }
    monkeypatch.setattr(review_model, "build_dashboard_review", lambda **_: review_data)

    summary = _dashboard_summary(Paths.from_root(tmp_path), {}, {}, {}, ontology_bundle())

    assert set(summary) == {"dashboard_first", "dashboard_second"}
