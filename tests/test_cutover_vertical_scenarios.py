"""Compact vertical acceptance scenarios for the cutover decision."""

from __future__ import annotations

from pathlib import Path
from shutil import copytree
from typing import cast

import planner.engine.plan as plan_module
import yaml
from planner.cards.pillboxes import flatten_pillbox_slots, load_pillboxes
from planner.engine import cmd_plan
from planner.paths import Paths

from tests.helpers import ontology_bundle

ROOT = Path(__file__).resolve().parents[1]


def _assert_current_shelf_proof(schedule: dict[str, object], stacks: dict[str, object], paths: Paths) -> None:
    assignments = cast(dict[str, str], schedule["assignments"])
    pressure_matches = cast(list[dict[str, object]], schedule["pressure_matches"])
    active_by_stack = {stack: set(cast(list[str], stacks[stack])) for stack in ("daily", "training")}
    active_products = set().union(*active_by_stack.values())

    assert set(assignments) == active_products
    assert not set(assignments) & set(cast(list[str], stacks["inactive"]))
    assert not set(assignments) & {
        cast(str, entry["product"]) for entry in cast(list[dict[str, object]], stacks["tracked_unassigned"])
    }

    slots = flatten_pillbox_slots(load_pillboxes(paths.data / "pillboxes.yaml", ontology_bundle()))
    product_domains = {
        product_id: stack for stack, product_ids in active_by_stack.items() for product_id in product_ids
    }
    assert all(slots[slot_id].stack == product_domains[product_id] for product_id, slot_id in assignments.items())
    assert all(
        match["item_id"] in assignments
        and match["slot_id"] == assignments[match["item_id"]]
        and match["slot_anchor"] == slots[match["slot_id"]].anchors[match["dimension"]]
        and bool(match["fact_ids"])
        and bool(match["law_ids"])
        and bool(match["provenance_refs"])
        for match in pressure_matches
    )

    objective = cast(dict[str, object], schedule["objective"])
    assert objective["satisfied_pressures"] == sum(bool(match["satisfied"]) for match in pressure_matches)
    domain_loads = cast(dict[str, dict[str, object]], schedule["domain_loads"])
    assert set(domain_loads) == set(product_domains.values())
    assert objective["squared_load"] == sum(cast(int, domain["squared_load"]) for domain in domain_loads.values())
    for domain, proof in domain_loads.items():
        slot_loads = cast(dict[str, int], proof["slot_loads"])
        assert set(slot_loads) == {slot_id for slot_id, slot in slots.items() if slot.stack == domain}
        assert slot_loads == {
            slot_id: sum(assigned_slot == slot_id for assigned_slot in assignments.values()) for slot_id in slot_loads
        }
        assert proof["squared_load"] == sum(load**2 for load in slot_loads.values())

    explanations = cast(dict[str, dict[str, object]], schedule["canonical_explanations"])
    assert set(explanations) == set(assignments)
    for item_id, explanation in explanations.items():
        item_matches = [match for match in pressure_matches if match["item_id"] == item_id]
        assert explanation["item_id"] == item_id
        assert explanation["slot_id"] == assignments[item_id]
        assert explanation["pressure_matches"] == item_matches
        assert explanation["placement_basis"] == (
            "pressure_evidence" if any(match["satisfied"] for match in item_matches) else "balance_and_tie_break_only"
        )


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
    stacks = cast(dict[str, object], yaml.safe_load(paths.stacks_file.read_text(encoding="utf-8")))

    _assert_current_shelf_proof(schedule, stacks, paths)
