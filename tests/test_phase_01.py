from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]

TRAINING_SUBSTANCES = {
    "l_citrulline_malate",
    "creatine",
    "electrolyte_caps",
    "l_carnitine_l_tartrate",
}

DAILY_SUBSTANCES = {
    "vitamin_d3",
    "vitamin_b5",
    "coenzyme_b_complex",
    "magnesium_glycinate",
    "trace_minerals",
    "potassium_citrate",
    "lions_mane_b6_complex",
    "acetyl_l_carnitine",
    "astaxanthin",
    "nattokinase",
    "tadalafil",
}

INACTIVE_SUBSTANCES = {
    "lions_mane",
    "picamilon",
    "se_methyl_l_selenocysteine",
    "dihydroquercetin_complex",
    "copper",
    "n_acetyl_cysteine",
    "krill_oil",
    "glycine",
}

EXPECTED_ACTIVITY_TRAITS = {
    "l_citrulline_malate": "activity:pre_workout",
    "creatine": "activity:any_workout",
    "electrolyte_caps": "activity:any_workout",
    "l_carnitine_l_tartrate": "activity:any_workout",
}


def load_yaml(path: str) -> object:
    return yaml.safe_load((ROOT / path).read_text())


def run_planner(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "planner.py", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_phase_01_check_passes() -> None:
    result = run_planner("check")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "All checks passed." in result.stdout
    assert "ERROR:" not in result.stderr


def test_training_slots_and_activity_traits() -> None:
    slots = load_yaml("data/slots.yaml")["slots"]
    traits = load_yaml("data/traits.yaml")["traits"]

    assert set(slots) == {
        "morning_empty",
        "morning_food",
        "day_food",
        "evening_empty",
        "pre_workout",
        "post_workout",
    }
    assert all(
        slots[name]["stack"] == "daily"
        for name in ("morning_empty", "morning_food", "day_food", "evening_empty")
    )
    assert slots["pre_workout"]["stack"] == "training"
    assert slots["pre_workout"]["activity"] == "pre_workout"
    assert slots["post_workout"]["stack"] == "training"
    assert slots["post_workout"]["activity"] == "post_workout"

    assert traits["activity:pre_workout"]["effects"] == [
        {"match": {"activity": "pre_workout"}, "level": "prefer_strong"}
    ]
    assert traits["activity:post_workout"]["effects"] == [
        {"match": {"activity": "post_workout"}, "level": "prefer_strong"}
    ]
    assert traits["activity:any_workout"]["effects"] == [
        {"match": {"activity": "pre_workout"}, "level": "prefer"},
        {"match": {"activity": "post_workout"}, "level": "prefer"},
    ]


def test_inventory_stack_partition() -> None:
    inventory = load_yaml("data/inventory.yaml")["supplements"]

    assert len(inventory) == 23
    assert not any("active" in entry for entry in inventory.values())
    assert Counter(entry["stack"] for entry in inventory.values()) == {
        "daily": 11,
        "training": 4,
        "inactive": 8,
    }
    assert inventory["l_carnitine_l_tartrate"]["stack"] == "training"


def test_training_products_have_expected_activity_traits() -> None:
    for substance, activity_trait in EXPECTED_ACTIVITY_TRAITS.items():
        product = load_yaml(f"data/products/{substance}.yaml")

        assert activity_trait in product["traits"]
        assert "goals" not in product


def test_goal_cards_have_expected_members() -> None:
    vascular = load_yaml("data/goals/vascular_health.yaml")
    mitochondrial = load_yaml("data/goals/mitochondrial_health.yaml")

    assert len(vascular["members"]) == 4
    assert all(member["status"] == "taking" for member in vascular["members"])
    assert {member["substance"] for member in vascular["members"]} == {
        "l_citrulline_malate",
        "nattokinase",
        "tadalafil",
        "vitamin_b5",
    }

    takers = [
        member for member in mitochondrial["members"] if member["status"] == "taking"
    ]
    candidates = [
        member
        for member in mitochondrial["members"]
        if member["status"] == "candidate"
    ]
    assert len(takers) == 1
    assert takers[0]["substance"] == "acetyl_l_carnitine"
    assert len(candidates) == 2
    assert all("name" in candidate for candidate in candidates)
    assert all("substance" not in candidate for candidate in candidates)


def test_plan_generates_stack_partitioned_schedule() -> None:
    result = run_planner("plan")
    assert result.returncode == 0, result.stdout + result.stderr

    schedule = load_yaml("schedule.yaml")
    slots = schedule["slots"]
    scheduled_training = set(slots["pre_workout"]) | set(slots["post_workout"])
    scheduled_daily = (
        set(slots["morning_empty"])
        | set(slots["morning_food"])
        | set(slots["day_food"])
        | set(slots["evening_empty"])
    )
    all_scheduled = scheduled_training | scheduled_daily

    assert scheduled_training == TRAINING_SUBSTANCES
    assert scheduled_daily == DAILY_SUBSTANCES
    assert all_scheduled.isdisjoint(INACTIVE_SUBSTANCES)


def test_goal_ref_validator_rejects_missing_product_and_restores_file() -> None:
    goal_path = ROOT / "data/goals/vascular_health.yaml"
    original = goal_path.read_bytes()

    try:
        corrupted = original.replace(
            b"substance: l_citrulline_malate",
            b"substance: bogus_substance_xyz",
            1,
        )
        assert corrupted != original
        goal_path.write_bytes(corrupted)

        result = run_planner("check")

        assert result.returncode != 0
        combined_output = result.stdout + result.stderr
        assert "bogus_substance_xyz" in combined_output
        assert "no matching product card" in combined_output
    finally:
        goal_path.write_bytes(original)

    restored = run_planner("check")
    assert restored.returncode == 0, restored.stdout + restored.stderr
