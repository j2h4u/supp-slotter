"""Acceptance for the generic compiler-emitted scheduling fact projection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import RuntimeCanonicalSchedulingFact, decode_runtime_program
from scripts.ontology_compiler import compile_ontology

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"


def _payload() -> dict[str, object]:
    return cast(dict[str, object], json.loads(compile_ontology(ONTOLOGY)[Path("runtime-program.json")]))


def test_compiler_emits_one_generic_scheduling_projection_without_retired_catalog_keys() -> None:
    projection = cast(dict[str, object], _payload()["projection"])
    scheduling = cast(dict[str, object], projection["canonical_scheduling"])

    assert set(scheduling) == {"dimensions", "families", "evidence_sources", "facts", "laws"}
    assert "canonical_fact_catalog" not in projection
    assert all("effects" not in key for key in scheduling)
    assert len(cast(list[object], scheduling["facts"])) == 6


def test_decoder_types_facts_once_with_family_as_data() -> None:
    scheduling = decode_runtime_program(_payload()).canonical_scheduling

    assert all(isinstance(fact, RuntimeCanonicalSchedulingFact) for fact in scheduling.facts)
    assert {fact.family for fact in scheduling.facts} <= set(scheduling.families_by_id)
    assert {fact.value for fact in scheduling.facts} <= {
        value for family in scheduling.families for value in family.fact_values
    }


@pytest.mark.parametrize("mutation", ("unknown_family", "unadmitted_value", "duplicate_id"))
def test_decoder_rejects_malformed_generic_fact_rows(mutation: str) -> None:
    payload = _payload()
    projection = cast(dict[str, object], payload["projection"])
    scheduling = cast(dict[str, object], projection["canonical_scheduling"])
    facts = cast(list[dict[str, object]], scheduling["facts"])
    if mutation == "unknown_family":
        facts[0]["family"] = "Unknown"
    elif mutation == "unadmitted_value":
        facts[0]["value"] = "unknown"
    else:
        facts.append(dict(facts[0]))

    with pytest.raises(OntologyInfrastructureError):
        decode_runtime_program(payload)
