"""Parity tests for the manifest-owned planner scheduling-policy contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tests/fixtures/ontology_migration/pre_cutover_baseline.json"
POLICIES = ROOT / "ontology/policies.yaml"
RUNTIME_VOCABULARY = ROOT / "ontology/generated/runtime-vocabulary.yaml"


def test_generated_scheduling_policies_exhaustively_match_immutable_pre_cutover_traits() -> None:
    """Every legacy score/block/warning policy has one canonical replacement."""
    expected = _baseline_policy_contract()
    generated = _generated_policies()

    assert generated == expected
    assert len(generated) == 29
    assert sum(bool(policy["effects"]) for policy in generated.values()) == 10
    assert sum(bool(policy["warning"]) for policy in generated.values()) == 19


def test_schedule_effect_fixtures_preserve_all_score_and_block_rules() -> None:
    """The scheduling subset remains byte-for-value equivalent before cutover."""
    expected = _baseline_policy_contract()
    generated = _generated_policies()
    expected_effects = {key: value["effects"] for key, value in expected.items() if value["effects"]}
    generated_effects = {key: value["effects"] for key, value in generated.items() if value["effects"]}
    assert generated_effects == expected_effects


def _generated_policies() -> dict[str, dict[str, object]]:
    raw = yaml.safe_load(RUNTIME_VOCABULARY.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    policies = raw.get("scheduling_policies")
    assert isinstance(policies, dict)
    return cast(dict[str, dict[str, object]], policies)


def _baseline_policy_contract() -> dict[str, dict[str, object]]:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    documents = baseline.get("documents")
    assert isinstance(documents, list)
    expected: dict[str, dict[str, object]] = {}
    for document in documents:
        if not isinstance(document, dict) or not str(document.get("path", "")).startswith("data/traits/"):
            continue
        normalized = document.get("normalized")
        assert isinstance(normalized, dict)
        source = _restore(cast(dict[str, object], normalized))
        assert isinstance(source, dict)
        for category, entries in source.items():
            assert isinstance(category, str)
            assert isinstance(entries, dict)
            for term, raw_policy in entries.items():
                assert isinstance(term, str)
                assert isinstance(raw_policy, dict)
                if not any(key in raw_policy for key in ("effects", "warning", "action")):
                    continue
                expected[f"{category}:{term}"] = {
                    "label": raw_policy["label"],
                    "description": raw_policy["description"],
                    "applies_when": raw_policy["applies_when"],
                    "effects": raw_policy.get("effects", []),
                    "warning": bool(raw_policy.get("warning", False)),
                    **({"action": raw_policy["action"]} if "action" in raw_policy else {}),
                }
    return dict(sorted(expected.items()))


def _restore(value: dict[str, object]) -> object:
    value_type = value["type"]
    if value_type == "mapping":
        return {
            str(key): _restore(cast(dict[str, object], child))
            for key, child in cast(list[list[object]], value["value"])
        }
    if value_type == "sequence":
        return [_restore(cast(dict[str, object], child)) for child in cast(list[object], value["value"])]
    if value_type == "null":
        return None
    return value.get("value")
