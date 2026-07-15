"""Executable v2 policy and audit governance matrix."""

from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ROOT / "ontology/policies.yaml"
RUNTIME = ROOT / "ontology/generated/runtime-vocabulary.yaml"
REQUIRED_LIVE_SOURCES = {
    "intake.E01",
    "intake.E02",
    "intake.E03",
    "intake.E04",
    "intake.E05",
    "intake.E06",
    "intake.E07",
    "intake.E09",
    "intake.E10",
    "intake.E14",
    "intake.E16",
    "intake.E17",
    "intake.E18",
    "intake.E19",
    "intake.E20",
    "intake.E21",
    "enzyme.E1",
    "enzyme.E2",
    "enzyme.E3",
    "enzyme.E4",
    "enzyme.E5",
    "enzyme.E6",
    "enzyme.E8",
    "enzyme.E9",
    "circadian.caffeine_sleep_meta",
    "circadian.melatonin",
    "circadian.glycine",
    "circadian.magnesium_glycinate",
    "workout.creatine",
    "workout.lclt",
    "workout.citrulline",
    "workout.betaine_nitrate",
}


def _runtime() -> dict[str, object]:
    return cast(dict[str, object], yaml.safe_load(RUNTIME.read_text(encoding="utf-8")))


def test_runtime_v2_policy_matrix_is_exact() -> None:
    policies = cast(dict[str, dict[str, object]], _runtime()["scheduling_policies"])
    expected = {
        "intake:empty_preferred": ("approved", "preference"),
        "intake:fat_meal_required": ("retired", "none"),
        "intake:food_neutral": ("approved", "none"),
        "intake:food_preferred": ("approved", "preference"),
        "intake:food_required": ("approved", "block"),
        "timing:energy_like": ("approved", "preference"),
        "timing:sleep_disruptive": ("retired", "none"),
        "timing:sleep_support": ("approved", "preference"),
        "activity:any_workout": ("approved", "preference"),
        "activity:pre_workout": ("approved", "preference"),
        "activity:post_workout": ("review_pending", "preference"),
    }
    assert {k: (v["status"], v["enforcement"]) for k, v in policies.items() if k in expected} == expected
    assert policies["intake:fat_meal_required"]["effects"] == []
    assert policies["timing:sleep_disruptive"]["effects"] == []
    assert all(
        set(record) >= {"status", "enforcement", "scope", "evidence", "owner", "review_by"}
        for record in policies.values()
    )


def test_policy_enforcement_matches_effect_projection() -> None:
    policies = cast(dict[str, dict[str, object]], _runtime()["scheduling_policies"])
    for policy in policies.values():
        effects = cast(list[dict[str, object]], policy["effects"])
        expected = (
            "block"
            if any(effect.get("block") is True for effect in effects)
            else ("preference" if effects else ("advisory" if policy.get("warning") else "none"))
        )
        assert policy["enforcement"] == expected


def test_audit_rules_have_lifecycle_and_no_retired_effects() -> None:
    rules = cast(list[dict[str, object]], _runtime()["audit_review_rules"])
    assert rules
    for rule in rules:
        assert set(rule) >= {"status", "enforcement", "scope", "evidence", "owner", "review_by"}
        if rule["status"] == "retired":
            assert rule["enforcement"] == "none"
            assert rule["accepted_intake"] == []


def test_authored_policy_catalog_is_central_and_exactly_referenced() -> None:
    authored = cast(dict[str, object], yaml.safe_load(POLICIES.read_text(encoding="utf-8")))
    catalog = cast(dict[str, object], authored["slot_policy_evidence"])
    assert catalog
    for record_obj in catalog.values():
        record = cast(dict[str, object], record_obj)
        assert set(record) == {"kind", "title", "supports", "limitations", ("url" if "url" in record else "ref")}
    runtime = _runtime()
    assert runtime["slot_policy_evidence"] == catalog


def test_amendment_4_exact_live_source_key_set_is_available() -> None:
    catalog = cast(dict[str, object], _runtime()["slot_policy_evidence"])
    assert set(catalog) >= REQUIRED_LIVE_SOURCES
    assert len(REQUIRED_LIVE_SOURCES) == 32
    assert not {f"intake.E{index}" for index in range(1, 10)} & set(catalog)
    assert len(catalog) == 34  # 32 live sources plus two operational policy-contract sources.
