"""Semantic layout contract using only committed fixtures and isolated outputs."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import cast

import yaml
from planner.engine import cmd_plan

ROOT = Path(__file__).parents[1]
FIX = ROOT / "tests/fixtures/slot_policy"
Placement = dict[str, dict[str, str]]
FrozenPlacement = {
    "prd_175251bd63": {"pillbox": "daily", "slot": "morning_empty"},
    "prd_27f7b85aa6": {"pillbox": "daily", "slot": "morning_empty"},
    "prd_8eff2491b7": {"pillbox": "daily", "slot": "morning_food"},
    "prd_eb6337a6dc": {"pillbox": "daily", "slot": "morning_food"},
    "prd_e5cc3b4e7c": {"pillbox": "daily", "slot": "morning_food"},
    "prd_7f04daf970": {"pillbox": "daily", "slot": "morning_food"},
    "prd_bb212cffc2": {"pillbox": "daily", "slot": "day_food"},
    "prd_932319251f": {"pillbox": "daily", "slot": "day_food"},
    "prd_vitamealc8": {"pillbox": "daily", "slot": "day_food"},
    "prd_c81eb18069": {"pillbox": "daily", "slot": "day_food"},
    "prd_33f3450f29": {"pillbox": "daily", "slot": "evening_empty"},
    "prd_9d0fca3201": {"pillbox": "daily", "slot": "evening_empty"},
    "prd_2ca842627a": {"pillbox": "training", "slot": "pre_workout"},
    "prd_cfce0b36b6": {"pillbox": "training", "slot": "pre_workout"},
    "prd_0e92bc1674": {"pillbox": "training", "slot": "post_workout"},
    "prd_20bf2df267": {"pillbox": "training", "slot": "post_workout"},
}
MovementReasons = {
    "prd_8eff2491b7": "B_VITAMIN_BLANKET",
    "prd_bb212cffc2": "B_VITAMIN_BLANKET",
    "prd_932319251f": "MINERAL_DOSE_FORM_DEPENDENT",
    "prd_c81eb18069": "B_VITAMIN_BLANKET",
    "prd_e5cc3b4e7c": "FAT_PREFERENCE_SUPPORTED",
    "prd_7f04daf970": "FAT_FORM_DEPENDENT",
}


def _mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    raw = cast(dict[object, object], value)
    return {str(k): v for k, v in raw.items()}


def _yaml(path: Path) -> dict[str, object]:
    return _mapping(cast(object, yaml.safe_load(path.read_text())))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _placement(schedule: dict[str, object]) -> Placement:
    result: Placement = {}
    pillboxes = _mapping(schedule["pillboxes"])
    for pillbox, raw in pillboxes.items():
        for slot, slot_raw in _mapping(_mapping(raw)["slots"]).items():
            products = _mapping(slot_raw).get("products", [])
            assert isinstance(products, list)
            for name_raw in products:
                name = str(cast(object, name_raw))
                product_id = name_to_id[name]
                assert product_id not in result
                result[product_id] = {"pillbox": pillbox, "slot": slot}
    return result


def _copy_planner_data(tmp_path: Path) -> Path:
    root = tmp_path / "planner"
    shutil.copytree(ROOT / "data", root / "data")
    return root


name_to_id: dict[str, str] = {}
for product_path in sorted((ROOT / "data/products").glob("*.yaml")):
    card = _yaml(product_path)
    name = str(card["name"])
    brand = card.get("brand")
    name_to_id[f"{brand} - {name}" if brand and brand != "unknown" else name] = str(card["id"])


def test_layout_matches_frozen_baseline_without_root_schedule(tmp_path: Path) -> None:
    inventory = _mapping(cast(object, json.loads((FIX / "pre_migration_inventory.json").read_text())))
    assert _mapping(inventory["normalized_layout"])["algorithm"] == "POSIX relative paths, UTF-8 byte sort"
    root_schedule = ROOT / "schedule.yaml"
    root_before = (
        (root_schedule.stat().st_ino, root_schedule.stat().st_mtime_ns, _sha(root_schedule))
        if root_schedule.exists()
        else None
    )
    root = _copy_planner_data(tmp_path)
    result = cmd_plan(data_root=root)
    assert result.exit_code == 0, "\n".join(result.errors)
    generated = _placement(_yaml(root / "schedule.yaml"))
    movements = {
        product_id: {
            "from": FrozenPlacement[product_id],
            "to": generated[product_id],
            "reason": MovementReasons[product_id],
        }
        for product_id in FrozenPlacement
        if FrozenPlacement[product_id] != generated[product_id]
    }
    assert movements == {
        product_id: {"from": FrozenPlacement[product_id], "to": generated[product_id], "reason": reason}
        for product_id, reason in MovementReasons.items()
    }
    assert all(
        bool(cast(str, item["from"]["pillbox"]) == cast(str, item["to"]["pillbox"])) for item in movements.values()
    )
    ledger = cast(list[object], _yaml(FIX / "v2_migration_ledger.yaml")["rows"])
    reason_codes = {str(_mapping(_mapping(row)["decision"]).get("reason_code")) for row in ledger}
    assert {item["reason"] for item in movements.values()} <= reason_codes
    assert len(generated) == 16
    assert {value["pillbox"] for value in generated.values()} == {"daily", "training"}
    assert (
        len({
            str(substance)
            for pillbox in _mapping(_yaml(root / "schedule.yaml")["pillboxes"]).values()
            for slot in _mapping(_mapping(pillbox)["slots"]).values()
            for substance in cast(list[object], _mapping(slot).get("substances", []))
        })
        == 35
    )
    root_after = (
        (root_schedule.stat().st_ino, root_schedule.stat().st_mtime_ns, _sha(root_schedule))
        if root_schedule.exists()
        else None
    )
    assert root_after == root_before
    assert not (tmp_path / "absent" / "schedule.yaml").exists()


def test_layout_card_and_slot_cardinality() -> None:
    inventory = _mapping(cast(object, json.loads((FIX / "pre_migration_inventory.json").read_text())))
    assert inventory["card_counts"] == {"substances": 253, "products": 59, "dashboards": 27}
    pillboxes = _yaml(ROOT / "data/pillboxes.yaml")
    assert set(pillboxes) == {"daily", "training"}
    assert sum(len(_mapping(_mapping(value)["slots"])) for value in pillboxes.values()) == 6
    stacks = _yaml(ROOT / "data/stacks.yaml")
    active = cast(list[object], stacks["daily"]) + cast(list[object], stacks["training"])
    assert len(active) == 16 and len(set(map(str, active))) == 16
    rows = cast(list[object], inventory["assignments"])
    assert len({str(_mapping(row)["card_id"]) for row in rows if _mapping(row)["axis"] == "intake"}) == 224


def test_daily_only_activity_is_inert(tmp_path: Path) -> None:
    root = _copy_planner_data(tmp_path)
    stacks = _yaml(root / "data/stacks.yaml")
    stacks["training"], stacks["daily"] = [], [*cast(list[object], stacks["daily"]), "prd_2ca842627a"]
    (root / "data/stacks.yaml").write_text(yaml.safe_dump(stacks, sort_keys=False))
    result = cmd_plan(data_root=root)
    assert result.exit_code == 0, "\n".join(result.errors)
    generated = _yaml(root / "schedule.yaml")
    daily = _mapping(_mapping(generated["pillboxes"])["daily"])
    products = [
        str(cast(object, product))
        for slot in _mapping(daily["slots"]).values()
        for product in cast(list[object], _mapping(slot).get("products", []))
    ]
    assert "Do4a - Creatine monohydrate" in products
