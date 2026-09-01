"""Acceptance for generic source-derived facts-to-pressure laws."""

from __future__ import annotations

from typing import cast

import pytest
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import decode_runtime_program

from tests.compiled_ontology import compiled_runtime_payload


def _payload() -> dict[str, object]:
    return compiled_runtime_payload()


def test_every_annotated_family_value_has_exactly_one_generic_law() -> None:
    scheduling = decode_runtime_program(_payload()).canonical_scheduling
    expected = {(family.id, value) for family in scheduling.families for value in family.fact_values}

    assert {(law.family, law.fact_value) for law in scheduling.laws} == expected
    assert {law.dimension for law in scheduling.laws} == set(scheduling.pressure_values_by_dimension)
    assert all(law.pressure_value in scheduling.pressure_values_by_dimension[law.dimension] for law in scheduling.laws)


@pytest.mark.parametrize("field", ("family", "fact_value", "dimension", "pressure_value"))
def test_decoder_rejects_generic_law_drift(field: str) -> None:
    payload = _payload()
    projection = cast(dict[str, object], payload["projection"])
    scheduling = cast(dict[str, object], projection["canonical_scheduling"])
    law = cast(list[dict[str, object]], scheduling["laws"])[0]
    law[field] = "unknown"

    with pytest.raises(OntologyInfrastructureError):
        decode_runtime_program(payload)
