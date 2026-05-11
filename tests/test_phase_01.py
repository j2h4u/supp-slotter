from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]

TRAINING_ITEMS = {
    "prd_cfce0b36b6",
    "prd_2ca842627a",
    "prd_20bf2df267",
    "prd_0e92bc1674",
}

DAILY_ITEMS = {
    "prd_eb6337a6dc",
    "prd_8eff2491b7",
    "prd_bb212cffc2",
    "prd_9d0fca3201",
    "prd_932319251f",
    "prd_c81eb18069",
    "prd_27f7b85aa6",
    "prd_e5cc3b4e7c",
    "prd_83dffd67bf",
    "prd_33f3450f29",
    "prd_7f04daf970",
}

INACTIVE_ITEMS = {
    "prd_a6342d7725",
    "prd_7ae9a92d3b",
    "prd_91a71b69f0",
    "prd_7a4ee33852",
    "prd_55d65df796",
    "prd_955ea0c9e6",
    "prd_97fc03c4c0",
    "prd_17f2788c3f",
}

EXPECTED_ACTIVITY_TRAITS = {
    "sub_3918fe347e": "activity:pre_workout",
    "sub_9c0908e7f7": "activity:any_workout",
    "sub_5bd641c116": "activity:any_workout",
}


def load_yaml(path: str) -> dict[str, Any]:
    result = yaml.safe_load((ROOT / path).read_text())
    assert isinstance(result, dict)
    return cast(dict[str, Any], result)


def load_card_by_id(directory: str, card_id: str) -> dict[str, Any]:
    matches = [
        yaml.safe_load(path.read_text())
        for path in sorted((ROOT / directory).glob("*.yaml"))
        if yaml.safe_load(path.read_text()).get("id") == card_id
    ]
    assert len(matches) == 1
    result = matches[0]
    assert isinstance(result, dict)
    return cast(dict[str, Any], result)


def flatten_stack_items(stacks: dict[str, Any]) -> dict[str, Any]:
    return {
        product_id: {"product": product_id, "stack": stack}
        for stack, items in stacks.items()
        for product_id in items
    }


def flatten_trait_defs(traits_data: dict[str, Any]) -> dict[str, Any]:
    return {
        f"{namespace}:{name}": trait
        for namespace, entries in traits_data.items()
        if isinstance(entries, dict)
        for name, trait in cast(dict[str, Any], entries).items()
    }


def product_display_names(product_ids: set[str]) -> set[str]:
    products = {
        card["id"]: card
        for card in (
            yaml.safe_load(path.read_text())
            for path in sorted((ROOT / "data/products").glob("*.yaml"))
        )
    }
    names: set[str] = set()
    for product_id in product_ids:
        product = products[product_id]
        brand = product.get("brand")
        name = product["name"]
        names.add(f"{brand} - {name}" if brand and brand != "unknown" else name)
    return names


def run_planner(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "python", "-m", "planner", *args],
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
    assert str(ROOT) not in result.stdout


def test_training_pillbox_slot_structure() -> None:
    pillboxes = load_yaml("data/pillboxes.yaml")
    daily_slots = pillboxes["daily"]["slots"]
    training_slots = pillboxes["training"]["slots"]

    assert set(pillboxes) == {"daily", "training"}
    assert set(daily_slots) == {
        "morning_empty",
        "morning_food",
        "day_food",
        "evening_empty",
    }
    assert set(training_slots) == {
        "pre_workout",
        "post_workout",
    }
    assert training_slots["pre_workout"]["near"] == "workout_before"
    assert training_slots["post_workout"]["near"] == "workout_after"


def test_activity_trait_effects_match_pillbox_slots() -> None:
    traits = flatten_trait_defs(load_yaml("data/traits.yaml"))

    assert traits["activity:pre_workout"]["effects"] == [
        {"match": {"near": "workout_before"}, "level": "prefer_strong"}
    ]
    assert traits["activity:post_workout"]["effects"] == [
        {"match": {"near": "workout_after"}, "level": "prefer_strong"}
    ]
    assert traits["activity:any_workout"]["effects"] == [
        {"match": {"near": "workout_before"}, "level": "prefer"},
        {"match": {"near": "workout_after"}, "level": "prefer"},
    ]


def test_training_substances_have_expected_activity_traits() -> None:
    for substance, activity_trait in EXPECTED_ACTIVITY_TRAITS.items():
        card = load_card_by_id("data/substances", substance)
        # activity_trait is like "activity:pre_workout" — extract bare slug after ":"
        bare_slug = activity_trait.split(":", 1)[1]
        assert bare_slug in card.get("activity", [])
        assert "goals" not in card
        assert "dashboards" not in card


def test_vascular_dashboard_membership_resolves_to_seven_substances() -> None:
    vascular = load_yaml("data/dashboards/vascular_health.yaml")

    # from_traits.dashboard must reference the vascular_health slug
    assert vascular.get("from_traits", {}).get("dashboard") == ["vascular_health"]

    # Exactly 7 substance cards must carry "vascular_health" in their dashboard: list
    cards_with_vascular = [
        yaml.safe_load(path.read_text())
        for path in sorted((ROOT / "data/substances").glob("*.yaml"))
        if "vascular_health" in (yaml.safe_load(path.read_text()).get("dashboard") or [])
    ]
    assert len(cards_with_vascular) == 7
    assert {card["id"] for card in cards_with_vascular} == {
        "sub_3918fe347e",
        "sub_877c24aad4",
        "sub_a3ec9f9c52",
        "sub_7628e4f478",
        "sub_699a985e61",
        "sub_fmuptat7pw",
        "sub_396c221c31",
    }



def test_plan_generates_stack_partitioned_schedule() -> None:
    schedule_path = ROOT / "schedule.yaml"
    original_schedule = schedule_path.read_bytes()
    try:
        result = run_planner()
        assert result.returncode == 0, result.stdout + result.stderr
        assert "schedule_fit: " not in result.stdout

        schedule = load_yaml("schedule.yaml")
    finally:
        schedule_path.write_bytes(original_schedule)

    pillboxes = schedule["pillboxes"]
    training_slots = pillboxes["training"]["slots"]
    daily_slots = pillboxes["daily"]["slots"]
    scheduled_training = set(training_slots["pre_workout"]["products"]) | set(
        training_slots["post_workout"]["products"]
    )
    scheduled_daily = (
        set(daily_slots["morning_empty"]["products"])
        | set(daily_slots["morning_food"]["products"])
        | set(daily_slots["day_food"]["products"])
        | set(daily_slots["evening_empty"]["products"])
    )
    all_scheduled = scheduled_training | scheduled_daily

    assert scheduled_training == product_display_names(TRAINING_ITEMS)
    assert scheduled_daily == product_display_names(DAILY_ITEMS)
    assert set(schedule["summary"]["take"]) == {"daily", "training"}
    assert all(
        "Pre-workout" not in line and "Post-workout" not in line
        for line in schedule["summary"]["take"]["daily"]
    )
    assert all(
        line.startswith(("Pre-workout", "Post-workout"))
        for line in schedule["summary"]["take"]["training"]
    )
    assert all_scheduled.isdisjoint(product_display_names(INACTIVE_ITEMS))
    assert all(
        key not in schedule
        for key in (
            "schedule_fit",
            "fit_notes",
            "quality",
            "total_score",
            "quality_stars",
            "quality_rating",
            "quality_scale",
            "quality_ratio",
            "quality_max_score",
            "slot_score_total",
            "prefer_with_bonus",
            "balance_penalty",
        )
    )


def test_dashboard_ref_validator_rejects_unknown_from_traits_slug_and_restores_file() -> None:
    dashboard_path = ROOT / "data/dashboards/vascular_health.yaml"
    original = dashboard_path.read_bytes()

    try:
        # Inject an unknown slug into from_traits to trigger ref-integrity check
        corrupted = original.replace(
            b"  - vascular_health",
            b"  - vascular_health\n  - bogus_slug_xyz456",
            1,
        )
        assert corrupted != original
        dashboard_path.write_bytes(corrupted)

        result = run_planner("check")

        assert result.returncode != 0
        combined_output = result.stdout + result.stderr
        assert "bogus_slug_xyz456" in combined_output
        assert "register it in data/traits.yaml" in combined_output
    finally:
        dashboard_path.write_bytes(original)

    restored = run_planner("check")
    assert restored.returncode == 0, restored.stdout + restored.stderr
