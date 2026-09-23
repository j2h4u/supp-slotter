"""Presentation-only use-pattern contracts."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.cards.product import load_product
from planner.contracts import CardLoadError

from tests.helpers import ontology_bundle, run_planner
from tests.planner_fixture import (
    PlannerFixtureInput,
    find_card_path_by_id,
    fixture_id,
    plan_in_temp_dir,
    write_minimal_planner_fixture,
    write_yaml,
)


def test_product_loader_accepts_closed_use_pattern(tmp_path: Path) -> None:
    path = tmp_path / "product.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "id": "prd_aaaaaaaaaa",
                "name": "Occasional",
                "use_pattern": "not_every_day",
                "components": [{"id": "cmp_prd_aaaaaaaaaa__sub_aaaaaaaaaa", "substance": "sub_aaaaaaaaaa"}],
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
                "components": [{"id": "cmp_prd_aaaaaaaaaa__sub_aaaaaaaaaa", "substance": "sub_aaaaaaaaaa"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(CardLoadError, match="use_pattern"):
        load_product(path, ontology_bundle())


def test_marked_daily_product_is_an_episodic_current_plan_placement(tmp_path: Path) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={"marked": {"stack": "daily"}},
            products={"marked": [("sub_marked", [])]},
            traits={},
        ),
    )
    product_path = find_card_path_by_id(tmp_path / "data/products", fixture_id("prd", "marked"))
    card = yaml.safe_load(product_path.read_text(encoding="utf-8"))
    assert isinstance(card, dict)
    card["use_pattern"] = "not_every_day"
    write_yaml(product_path, card)

    schedule = plan_in_temp_dir(tmp_path)
    summary = cast(dict[str, object], schedule["summary"])
    assert isinstance(summary, dict)
    assert summary["placement_groups"] == {"routine": [], "episodic": [fixture_id("prd", "marked")]}
    pillboxes = cast(dict[str, dict[str, object]], schedule["pillboxes"])
    assert any(
        any(product["label"] == "Marked" for product in cast(list[dict[str, object]], slot["products"]))
        for pillbox in pillboxes.values()
        for slot in cast(dict[str, dict[str, object]], pillbox["slots"]).values()
    )

    shown = run_planner(root=tmp_path)

    assert shown.returncode == 0, shown.stderr
    assert "Current plan:" in shown.stdout
    assert "Episodic placements" in shown.stdout
    assert "Marked" in shown.stdout
    assert "[balance-only]" in shown.stdout
    assert "today" not in shown.stdout.casefold()
    assert "take" not in shown.stdout.casefold()
