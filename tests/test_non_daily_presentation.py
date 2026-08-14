"""Presentation-only use-pattern contracts."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from planner.cards.product import load_product
from planner.cards.schedule import build_schedule_summary
from planner.contracts import CardLoadError, Product, ProductComponent

from tests.helpers import ontology_bundle
from tests.planner_fixture import (
    PlannerFixtureInput,
    plan_in_temp_dir,
    write_minimal_planner_fixture,
    write_yaml,
)


def _product(product_id: str, name: str, use_pattern: str | None = None) -> Product:
    return Product(
        id=product_id,
        name=name,
        components=(ProductComponent("sub_aaaaaaaaaa"),),
        use_pattern=use_pattern,
    )


def _schedule() -> dict[str, object]:
    return {
        "pillboxes": {
            "daily": {
                "slots": {
                    "morning": {"label": "Morning", "products": ["Daily base", "Occasional"]},
                }
            },
            "training": {
                "slots": {
                    "pre": {"label": "Pre-workout", "products": ["Training"]},
                }
            },
        }
    }


def test_summary_separates_presentation_groups_without_changing_take() -> None:
    products = {
        "prd_daily00001": _product("prd_daily00001", "Daily base"),
        "prd_occasion01": _product("prd_occasion01", "Occasional", "not_every_day"),
        "prd_training01": _product("prd_training01", "Training"),
    }
    stack_entries = {
        product_id: {"product": product_id, "stack": stack}
        for product_id, stack in (
            ("prd_daily00001", "daily"),
            ("prd_occasion01", "daily"),
            ("prd_training01", "training"),
        )
    }

    summary = build_schedule_summary(_schedule(), products, stack_entries)

    assert summary["take"] == {
        "daily": ["Morning: Daily base, Occasional"],
        "training": ["Pre-workout: Training"],
    }
    assert summary["usage_groups"] == {
        "daily_base": ["Daily base"],
        "not_every_day": ["Occasional"],
    }


def test_inactive_marker_is_not_presented() -> None:
    products = {"prd_inactive01": _product("prd_inactive01", "Inactive", "not_every_day")}
    stack_entries = {"prd_inactive01": {"product": "prd_inactive01", "stack": "inactive"}}

    summary = build_schedule_summary(_schedule(), products, stack_entries)

    assert summary["usage_groups"] == {"daily_base": [], "not_every_day": []}


def test_product_loader_accepts_closed_use_pattern(tmp_path: Path) -> None:
    path = tmp_path / "product.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "id": "prd_aaaaaaaaaa",
                "name": "Occasional",
                "use_pattern": "not_every_day",
                "components": [{"substance": "sub_aaaaaaaaaa"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    assert load_product(path, ontology_bundle()).use_pattern == "not_every_day"


def test_product_loader_rejects_invalid_use_pattern(tmp_path: Path) -> None:
    path = tmp_path / "product.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "id": "prd_aaaaaaaaaa",
                "name": "Invalid",
                "use_pattern": "weekly",
                "components": [{"substance": "sub_aaaaaaaaaa"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(CardLoadError, match="use_pattern"):
        load_product(path, ontology_bundle())


def test_marked_daily_product_remains_in_physical_daily_schedule(tmp_path: Path) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={"marked": {"stack": "daily"}},
            products={"marked": [("sub_marked", [])]},
            traits={},
        ),
    )
    product_path = next((tmp_path / "data/products").glob("*.yaml"))
    card = yaml.safe_load(product_path.read_text(encoding="utf-8"))
    assert isinstance(card, dict)
    card["use_pattern"] = "not_every_day"
    write_yaml(product_path, card)

    schedule = plan_in_temp_dir(tmp_path)
    summary = schedule["summary"]
    assert isinstance(summary, dict)
    assert summary["usage_groups"]["not_every_day"] == ["Marked"]
    assert any("Marked" in line for lines in summary["take"].values() for line in lines)
    assert any(
        "Marked" in slot["products"] for pillbox in schedule["pillboxes"].values() for slot in pillbox["slots"].values()
    )
