"""Focused acceptance for the closed, portable online runtime contract."""

from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from functools import cache
from pathlib import Path
from typing import cast

import pytest
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import (
    IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY,
    IMPLEMENTED_DOMAIN_FEASIBILITY,
    IMPLEMENTED_ENGINE_CONTRACT_PROTOCOL,
    IMPLEMENTED_PRESSURE_IDENTITY,
    IMPLEMENTED_PRESSURE_SATISFACTION_STRATEGY,
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


def _blank_first_canonical_fact_id(payload: dict[str, object]) -> None:
    projection = cast(dict[str, object], payload["projection"])
    scheduling = cast(dict[str, object], projection["canonical_scheduling"])
    facts = cast(list[dict[str, object]], scheduling["facts"])
    facts[0]["id"] = "   "


def _pad_first_canonical_fact_id(payload: dict[str, object]) -> None:
    projection = cast(dict[str, object], payload["projection"])
    scheduling = cast(dict[str, object], projection["canonical_scheduling"])
    facts = cast(list[dict[str, object]], scheduling["facts"])
    facts[0]["id"] = f" {facts[0]['id']}"


def test_v2_contract_decodes_exactly_and_excludes_retired_objective_inputs() -> None:
    payload = _payload()
    runtime = decode_runtime_program(payload)
    contract = runtime.engine_contract

    assert contract.protocol_version == IMPLEMENTED_ENGINE_CONTRACT_PROTOCOL
    assert contract.pressure_identity == IMPLEMENTED_PRESSURE_IDENTITY
    assert contract.applicability_expansion_strategy == IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY
    assert contract.pressure_satisfaction_strategy == IMPLEMENTED_PRESSURE_SATISFACTION_STRATEGY
    assert contract.domain_feasibility == IMPLEMENTED_DOMAIN_FEASIBILITY
    assert contract.primary_objective == IMPLEMENTED_PRIMARY_OBJECTIVE
    assert contract.secondary_objective == IMPLEMENTED_SECONDARY_OBJECTIVE
    assert contract.tie_break == IMPLEMENTED_TIE_BREAK
    assert contract.publication_statuses == IMPLEMENTED_PUBLICATION_STATUSES
    projection = cast(dict[str, object], payload["projection"])
    assert "effect_scoring" not in projection
    assert "constraint_execution_policies" not in projection


def test_authored_stack_partition_is_closed_and_reproduces_active_membership() -> None:
    payload = _payload()
    runtime = decode_runtime_program(payload)
    partition = runtime.glue_contract.stack_partition

    assert partition.routable_stack_names == ("daily", "training")
    assert partition.excluded_stack_names == ("inactive",)
    assert partition.tracked_unassigned_partition_name == "tracked_unassigned"
    assert not (set(partition.routable_stack_names) & set(partition.excluded_stack_names))

    projection = cast(dict[str, object], payload["projection"])
    glue = cast(dict[str, object], projection["glue_contract"])
    partition_payload = cast(dict[str, object], glue["stack_partition"])
    partition_payload["excluded_stack_names"] = ["daily"]
    with pytest.raises(OntologyInfrastructureError, match="disjoint"):
        decode_runtime_program(payload)


def test_v1_contract_is_rejected_without_compatibility_fallback() -> None:
    payload = _payload()
    projection = cast(dict[str, object], payload["projection"])
    contract = cast(dict[str, object], projection["engine_contract"])
    contract["protocol_version"] = "supp-slotter.engine-contract/v1"

    with pytest.raises(OntologyInfrastructureError, match="not implemented"):
        decode_runtime_program(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("applicability_expansion_strategy", "all_roles"),
        ("pressure_satisfaction_strategy", "anchor_contains_value"),
    ),
)
def test_engine_semantic_strategies_are_closed_exact_values(field: str, value: str) -> None:
    payload = _payload()
    projection = cast(dict[str, object], payload["projection"])
    contract = cast(dict[str, object], projection["engine_contract"])
    contract[field] = value

    with pytest.raises(OntologyInfrastructureError, match="not an admitted value"):
        decode_runtime_program(payload)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda payload: cast(dict[str, object], payload["provenance"]).__setitem__("source", "runtime-policy.yaml"),
        lambda payload: cast(dict[str, object], payload["provenance"]).__setitem__("source_sha256", "A" * 64),
        lambda payload: cast(dict[str, object], payload["provenance"]).__setitem__("manifest_schema_version", "3"),
        lambda payload: payload.__setitem__("source_hash", " "),
        _blank_first_canonical_fact_id,
        _pad_first_canonical_fact_id,
    ),
)
def test_runtime_envelope_and_canonical_ids_fail_closed(mutate: Callable[[dict[str, object]], None]) -> None:
    payload = _payload()
    mutate(payload)

    with pytest.raises(OntologyInfrastructureError):
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
