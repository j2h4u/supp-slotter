"""Compact vertical acceptance scenarios for the cutover decision."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from shutil import copytree
from typing import cast

import planner.engine.plan as plan_module
import yaml
from planner.cards.product import format_product_name, load_product_registry
from planner.engine import cmd_plan
from planner.paths import Paths

from tests.helpers import ontology_bundle

ROOT = Path(__file__).resolve().parents[1]


def _schedule_products(schedule: dict[str, object], pillbox: str) -> list[str]:
    pillboxes = cast(dict[str, object], schedule["pillboxes"])
    entries = cast(dict[str, dict[str, object]], cast(dict[str, object], pillboxes[pillbox])["slots"])
    return [product for entry in entries.values() for product in cast(list[str], entry["products"])]


def test_real_shelf_daily_episodic_and_training_products_are_complete(monkeypatch, tmp_path: Path) -> None:
    """The real shelf is complete without asserting a particular balanced slot."""
    copytree(ROOT / "data", tmp_path / "data")
    check_calls = 0
    original_check = plan_module._cmd_check_inner

    def counted_check(*args, **kwargs):
        nonlocal check_calls
        check_calls += 1
        return original_check(*args, **kwargs)

    monkeypatch.setattr(plan_module, "_cmd_check_inner", counted_check)
    result = cmd_plan(data_root=tmp_path)

    assert result.exit_code == 0, result.errors
    assert check_calls == 1
    schedule = cast(dict[str, object], yaml.safe_load((tmp_path / "schedule.yaml").read_text(encoding="utf-8")))
    assert schedule["status"] == "Optimal"
    paths = Paths.from_root(tmp_path)
    products = load_product_registry(paths, ontology_bundle())
    stacks = cast(dict[str, list[str]], yaml.safe_load(paths.stacks_file.read_text(encoding="utf-8")))

    expected_by_stack = {
        stack: {format_product_name(products[product_id]) for product_id in stacks[stack]}
        for stack in ("daily", "training")
    }
    actual_by_stack = {stack: set(_schedule_products(schedule, stack)) for stack in ("daily", "training")}
    assert actual_by_stack == expected_by_stack
    assert Counter(_schedule_products(schedule, "daily") + _schedule_products(schedule, "training")) == Counter(
        name for names in expected_by_stack.values() for name in names
    )

    summary = cast(dict[str, object], schedule["summary"])
    placement_groups = cast(dict[str, list[str]], summary["placement_groups"])
    episodic = {
        format_product_name(products[product_id])
        for product_id in stacks["daily"]
        if products[product_id].use_pattern == "not_every_day"
    }
    assert set(placement_groups["episodic"]) == episodic
    assert episodic <= actual_by_stack["daily"]

    assignments = cast(dict[str, str], schedule["assignments"])
    pressure_matches = cast(list[dict[str, object]], schedule["pressure_matches"])
    assert all(match["satisfied"] is True for match in pressure_matches)
    assert all(
        bool(match["fact_ids"]) and bool(match["law_ids"]) and bool(match["applicability_role_ids"])
        for match in pressure_matches
    )
    objective = cast(dict[str, object], schedule["objective"])
    assert objective["satisfied_pressures"] == len(pressure_matches)
    assert set(assignments) == {product_id for stack in ("daily", "training") for product_id in stacks[stack]}
