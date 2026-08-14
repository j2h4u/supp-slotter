"""Executable v2 policy and audit contract matrix."""

from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ROOT / "ontology/policies.yaml"
RUNTIME = ROOT / "ontology/generated/runtime-vocabulary.yaml"


def _runtime() -> dict[str, object]:
    return cast(dict[str, object], yaml.safe_load(RUNTIME.read_text(encoding="utf-8")))


def test_runtime_policy_effects_are_direct_and_exact() -> None:
    policies = cast(dict[str, dict[str, object]], _runtime()["scheduling_policies"])
    assert policies
    assert all(
        set(record) <= {"term", "label", "description", "applies_when", "effects", "warning", "action"}
        for record in policies.values()
    )
    assert all(policy_id.split(":", maxsplit=1)[1] == record["term"] for policy_id, record in policies.items())
    assert any(cast(list[object], record["effects"]) for record in policies.values())


def test_every_accepted_schedule_term_has_exactly_one_policy() -> None:
    vocabulary = cast(
        dict[str, object], yaml.safe_load((ROOT / "ontology/vocabulary.yaml").read_text(encoding="utf-8"))
    )
    categories = cast(dict[str, dict[str, object]], vocabulary["semantic_categories"])
    runtime_policy = cast(
        dict[str, object], yaml.safe_load((ROOT / "ontology/runtime-policy.yaml").read_text(encoding="utf-8"))
    )
    axes = {str(record["axis"]) for record in cast(list[dict[str, object]], runtime_policy["assignment_axes"])}
    terms = cast(list[dict[str, object]], vocabulary["terms"])
    accepted: set[str] = set()
    for term in terms:
        category = str(term["semantic_category"])
        predicates = cast(list[object], categories[category]["allowed_predicates"])
        if any(f"schedule.{axis}" in predicates for axis in axes):
            accepted.add(f"{category}:{term['slug']}")
    policies = cast(dict[str, dict[str, object]], _runtime()["scheduling_policies"])
    scheduled_policy_ids = {policy_id for policy_id in policies if policy_id.split(":", maxsplit=1)[0] in axes}
    assert scheduled_policy_ids == accepted


def test_policy_effects_have_authored_match_and_level_shapes() -> None:
    policies = cast(dict[str, dict[str, object]], _runtime()["scheduling_policies"])
    for policy in policies.values():
        effects = cast(list[dict[str, object]], policy["effects"])
        for effect in effects:
            assert set(effect) == {"match", "level"}
            assert isinstance(effect["level"], str) and effect["level"]


def test_authored_policy_catalog_is_central_and_minimal() -> None:
    authored = cast(dict[str, object], yaml.safe_load(POLICIES.read_text(encoding="utf-8")))
    assert set(authored) == {"scheduling_policies", "schedule_presentation"}
    runtime = _runtime()
    assert "scheduling_policies" in runtime
    assert "schedule_presentation" in runtime
