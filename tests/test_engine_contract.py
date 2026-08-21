"""Focused conformance checks for the versioned scheduler engine contract."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import cast

import pytest
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import decode_runtime_program

ROOT = Path(__file__).resolve().parents[1]


def _payload() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((ROOT / "ontology/generated/runtime-program.json").read_text(encoding="utf-8")),
    )


def test_engine_contract_is_versioned_and_covers_observable_semantics() -> None:
    runtime = decode_runtime_program(_payload())

    assert runtime.engine_contract.protocol_version == "supp-slotter.engine-contract/v1"
    assert runtime.engine_contract.result_mode == "exact_assignment"
    semantics = {item.id for item in runtime.engine_contract.semantics}
    assert semantics == {
        "selector_resolution",
        "component_vote_aggregation",
        "stack_partition",
        "episodic_presentation",
        "constraint_pair_evaluation",
        "prefer_with_resolution",
        "candidate_feasibility",
        "objective_and_tie_break",
        "relation_warning_truth",
    }
    assert {item.semantic for item in runtime.engine_contract.conformance_scenarios} == semantics


def test_engine_contract_rejects_scenarios_for_undeclared_semantics() -> None:
    payload = copy.deepcopy(_payload())
    projection = cast(dict[str, object], payload["projection"])
    contract = cast(dict[str, object], projection["engine_contract"])
    scenarios = cast(list[dict[str, object]], contract["conformance_scenarios"])
    scenarios[0]["semantic"] = "not_declared"

    with pytest.raises(OntologyInfrastructureError, match="unknown semantics"):
        decode_runtime_program(payload)
