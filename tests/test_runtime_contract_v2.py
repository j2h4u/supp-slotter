"""Focused acceptance for the closed, portable online runtime contract."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import cache
from pathlib import Path
from typing import cast

import pytest
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import (
    IMPLEMENTED_DOMAIN_FEASIBILITY,
    IMPLEMENTED_ENGINE_CONTRACT_PROTOCOL,
    IMPLEMENTED_PRESSURE_IDENTITY,
    IMPLEMENTED_PRIMARY_OBJECTIVE,
    IMPLEMENTED_PUBLICATION_STATUSES,
    IMPLEMENTED_SECONDARY_OBJECTIVE,
    IMPLEMENTED_TIE_BREAK,
    decode_runtime_program,
)
from scripts.ontology_compiler import compile_ontology

ROOT = Path(__file__).resolve().parents[1]


@cache
def _compiled_payload() -> str:
    artifacts = compile_ontology(ROOT / "ontology")
    return artifacts[Path("runtime-program.json")].decode("utf-8")


def _payload() -> dict[str, object]:
    return cast(dict[str, object], json.loads(deepcopy(_compiled_payload())))


def test_v2_contract_decodes_exactly_and_excludes_retired_objective_inputs() -> None:
    payload = _payload()
    runtime = decode_runtime_program(payload)
    contract = runtime.engine_contract

    assert contract.protocol_version == IMPLEMENTED_ENGINE_CONTRACT_PROTOCOL
    assert contract.pressure_identity == IMPLEMENTED_PRESSURE_IDENTITY
    assert contract.domain_feasibility == IMPLEMENTED_DOMAIN_FEASIBILITY
    assert contract.primary_objective == IMPLEMENTED_PRIMARY_OBJECTIVE
    assert contract.secondary_objective == IMPLEMENTED_SECONDARY_OBJECTIVE
    assert contract.tie_break == IMPLEMENTED_TIE_BREAK
    assert contract.publication_statuses == IMPLEMENTED_PUBLICATION_STATUSES
    projection = cast(dict[str, object], payload["projection"])
    assert "effect_scoring" not in projection
    assert "prefer_with_policy" not in projection
    assert "constraint_execution_policies" not in projection


def test_v1_contract_is_rejected_without_compatibility_fallback() -> None:
    payload = _payload()
    projection = cast(dict[str, object], payload["projection"])
    contract = cast(dict[str, object], projection["engine_contract"])
    contract["protocol_version"] = "supp-slotter.engine-contract/v1"

    with pytest.raises(OntologyInfrastructureError, match="not implemented"):
        decode_runtime_program(payload)


@pytest.mark.parametrize(
    "retired_field",
    [
        "highest_maximum_score",
        "float_epsilon",
        "weight",
        "bonus",
        "penalty",
        "advisory",
        "pair_mode",
        "blocks_slots",
        "constraint_execution_policies",
    ],
)
def test_retired_objective_and_pair_fields_are_rejected(retired_field: str) -> None:
    payload = _payload()
    projection = cast(dict[str, object], payload["projection"])
    contract = cast(dict[str, object], projection["engine_contract"])
    contract[retired_field] = False

    with pytest.raises(OntologyInfrastructureError, match="invalid closed shape"):
        decode_runtime_program(payload)


def test_source_policy_review_annotations_remain_source_data() -> None:
    # Removing the online effect scorer must not erase source-facing review
    # annotations, which are compiled into the vocabulary for non-objective UI.
    source = (ROOT / "ontology/policies.yaml").read_text(encoding="utf-8")
    assert "level:" in source
