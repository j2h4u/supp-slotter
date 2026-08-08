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


def test_runtime_policy_effects_are_direct_and_exact() -> None:
    policies = cast(dict[str, dict[str, object]], _runtime()["scheduling_policies"])
    assert policies
    assert all(set(record) <= {"label", "description", "applies_when", "effects", "warning", "action"} for record in policies.values())
    assert any(cast(list[object], record["effects"]) for record in policies.values())


def test_policy_effects_have_authored_match_and_level_shapes() -> None:
    policies = cast(dict[str, dict[str, object]], _runtime()["scheduling_policies"])
    for policy in policies.values():
        effects = cast(list[dict[str, object]], policy["effects"])
        for effect in effects:
            assert set(effect) <= {"match", "level"}


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
    assert len(catalog) == 33  # 32 live sources plus one operational policy-contract source.
