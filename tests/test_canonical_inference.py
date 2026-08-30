"""V-right acceptance for canonical law execution and pressure normalization."""

from __future__ import annotations

import json
from dataclasses import replace
from functools import cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import yaml
from planner.ontology.canonical_inference import (
    Conflict,
    Success,
    UnaryPressureIdentity,
    execute_canonical_inference,
)
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import (
    RuntimeCanonicalLaw,
    RuntimeCanonicalScheduling,
    RuntimeCanonicalSchedulingFact,
    RuntimeCompositionRole,
    RuntimeEvidenceProvenance,
    RuntimeEvidenceSource,
    RuntimeFactApplicability,
    RuntimeFactSubject,
    decode_runtime_program,
)
from scripts.ontology_compiler import compile_ontology

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"

ROLE = RuntimeCompositionRole("cmp_prd_demo__sub_demo", "prd_demo", "sub_demo")
OTHER_ROLE = RuntimeCompositionRole("cmp_prd_other__sub_demo", "prd_other", "sub_demo")
SOURCE = RuntimeEvidenceSource("src_demo")
PROVENANCE = (RuntimeEvidenceProvenance("src_demo", "paper#demo", "quote"),)


@cache
def _laws() -> tuple[RuntimeCanonicalLaw, ...]:
    payload = cast(
        dict[str, Any], json.loads((ONTOLOGY / "generated/runtime-program.json").read_text(encoding="utf-8"))
    )
    return decode_runtime_program(payload).canonical_scheduling.laws


def _primary_law() -> RuntimeCanonicalLaw:
    return _laws()[0]


def _conflicting_laws() -> tuple[RuntimeCanonicalLaw, RuntimeCanonicalLaw]:
    for law in _laws():
        for other in _laws():
            if law.dimension == other.dimension and law.pressure_value != other.pressure_value:
                return law, other
    raise AssertionError("authored generic scheduling has no conflicting dimension values")


def _cross_dimension_laws() -> tuple[RuntimeCanonicalLaw, RuntimeCanonicalLaw]:
    first = _primary_law()
    for law in _laws():
        if law.dimension != first.dimension:
            return first, law
    raise AssertionError("authored generic scheduling has only one dimension")


def _catalog(*facts: RuntimeCanonicalSchedulingFact) -> RuntimeCanonicalScheduling:
    return RuntimeCanonicalScheduling((), (), (SOURCE,), facts, _laws())


def _fact(
    family: str,
    value: str,
    *,
    subject: RuntimeFactSubject | None = None,
    applicability: RuntimeFactApplicability | None = None,
    fact_id: str = "fact_demo",
) -> RuntimeCanonicalSchedulingFact:
    return RuntimeCanonicalSchedulingFact(
        fact_id,
        family,
        subject or RuntimeFactSubject("sub_demo", None),
        applicability or RuntimeFactApplicability("sub_demo", None),
        PROVENANCE,
        value,
    )


def _execute(
    catalog: RuntimeCanonicalScheduling,
    selected_items: object,
    laws: tuple[RuntimeCanonicalLaw, ...] | None = None,
    *,
    roles: tuple[RuntimeCompositionRole, ...] = (ROLE,),
) -> Success | Conflict:
    return execute_canonical_inference(catalog, selected_items, laws or _laws(), composition_roles=roles)  # type: ignore[arg-type]


def test_every_admitted_value_maps_to_one_pressure() -> None:
    """Execute the authored/compiled law table and reject generated drift."""

    authored = cast(dict[str, object], yaml.safe_load((ONTOLOGY / "canonical-laws.yaml").read_text(encoding="utf-8")))
    compiled_payload = cast(dict[str, Any], json.loads(compile_ontology(ONTOLOGY)[Path("runtime-program.json")]))
    generated_payload = cast(
        dict[str, Any], json.loads((ONTOLOGY / "generated/runtime-program.json").read_text(encoding="utf-8"))
    )
    compiled_laws = cast(dict[str, Any], cast(dict[str, Any], compiled_payload["projection"])["canonical_scheduling"])[
        "laws"
    ]
    generated_laws = cast(
        dict[str, Any], cast(dict[str, Any], generated_payload["projection"])["canonical_scheduling"]
    )["laws"]
    assert compiled_laws == generated_laws
    assert sum(len(cast(list[object], rows)) for rows in authored.values()) == len(compiled_laws)

    runtime_laws = decode_runtime_program(generated_payload).canonical_scheduling.laws
    assert len(runtime_laws) == len(compiled_laws) == 9
    for law in runtime_laws:
        result = _execute(_catalog(_fact(law.family, law.fact_value)), ("prd_demo",), runtime_laws)
        assert isinstance(result, Success)
        assert result.pressures[0].identity == UnaryPressureIdentity("prd_demo", law.dimension, law.pressure_value)
        assert result.pressures[0].derivations[0].family == law.family
        assert result.pressures[0].derivations[0].fact.value == law.fact_value  # type: ignore[attr-defined]


def test_wrong_or_unselected_applicability_does_not_emit_pressure() -> None:
    law = _primary_law()
    fact = _fact(law.family, law.fact_value)
    wrong_subject = _fact(
        law.family,
        law.fact_value,
        subject=RuntimeFactSubject("sub_other", None),
        fact_id="fact_wrong_subject",
    )
    result = _execute(_catalog(fact, wrong_subject), ("prd_other",), _laws())
    assert isinstance(result, Success)
    assert result.pressures == ()


def test_substance_applicability_reaches_each_exact_matching_role() -> None:
    law = _primary_law()
    role_scoped = _fact(
        law.family,
        law.fact_value,
        subject=RuntimeFactSubject(None, ROLE.id),
        applicability=RuntimeFactApplicability(None, ROLE.id),
        fact_id="fact_role_scoped",
    )
    substance_subject = _fact(
        law.family,
        law.fact_value,
        fact_id="fact_substance_subject",
    )

    result = _execute(
        _catalog(role_scoped, substance_subject),
        {"item_primary": ROLE.product, "item_other": OTHER_ROLE.product},
        _laws(),
        roles=(ROLE, OTHER_ROLE),
    )

    assert isinstance(result, Success)
    assert tuple(pressure.identity for pressure in result.pressures) == (
        UnaryPressureIdentity("item_other", law.dimension, law.pressure_value),
        UnaryPressureIdentity("item_primary", law.dimension, law.pressure_value),
    )
    by_item = {pressure.item_id: pressure for pressure in result.pressures}
    assert {derivation.fact.id for derivation in by_item["item_primary"].derivations} == {
        "fact_role_scoped",
        "fact_substance_subject",
    }
    assert {derivation.fact.id for derivation in by_item["item_other"].derivations} == {"fact_substance_subject"}


def test_proof_contains_law_fact_subject_path_and_provenance() -> None:
    law = _primary_law()
    fact = _fact(law.family, law.fact_value)
    result = _execute(_catalog(fact), ("prd_demo",), _laws())
    assert isinstance(result, Success)
    proof = result.pressures[0].derivations[0]
    assert proof.law.id == law.id
    assert proof.fact.id == "fact_demo"
    assert proof.subject == fact.subject  # type: ignore[attr-defined]
    assert proof.path.applicability_role == ROLE.id
    assert (proof.path.target_kind, proof.path.target_id) == ("substance", "sub_demo")
    assert proof.path.product == ROLE.product
    assert proof.provenance == PROVENANCE


def test_duplicate_witnesses_facts_components_and_paths_normalize_to_one_pressure() -> None:
    law = _primary_law()
    duplicate = replace(
        _fact(law.family, law.fact_value),
        id="fact_duplicate",  # type: ignore[call-arg]
        provenance=PROVENANCE + PROVENANCE,  # type: ignore[arg-type]
    )
    result = _execute(_catalog(_fact(law.family, law.fact_value), duplicate), ("prd_demo",), _laws())
    assert isinstance(result, Success)
    assert len(result.pressures) == 1
    assert len(result.pressures[0].derivations) == 2
    assert result.pressures[0].derivations[1].provenance == PROVENANCE


def test_same_dimension_values_are_layout_free_conflict() -> None:
    first, second = _conflicting_laws()
    result = _execute(
        _catalog(
            _fact(first.family, first.fact_value),
            _fact(second.family, second.fact_value, fact_id="fact_other"),
        ),
        ("prd_demo",),
        _laws(),
    )
    assert isinstance(result, Conflict)
    assert result.conflicts[0].item_id == "prd_demo"
    assert result.conflicts[0].dimension == first.dimension
    assert result.conflicts[0].values == tuple(sorted({first.pressure_value, second.pressure_value}))


def test_cross_dimension_pressures_coexist() -> None:
    first, second = _cross_dimension_laws()
    result = _execute(
        _catalog(
            _fact(first.family, first.fact_value),
            _fact(second.family, second.fact_value, fact_id="fact_alert"),
        ),
        ("prd_demo",),
        _laws(),
    )
    assert isinstance(result, Success)
    assert {(pressure.dimension, pressure.value) for pressure in result.pressures} == {
        (first.dimension, first.pressure_value),
        (second.dimension, second.pressure_value),
    }


def test_admitted_fact_without_exact_law_fails_closed() -> None:
    law = _primary_law()
    laws = tuple(candidate for candidate in _laws() if candidate.id != law.id)
    with pytest.raises(OntologyInfrastructureError, match="canonical law missing"):
        _execute(
            _catalog(_fact(law.family, law.fact_value)),
            ("prd_demo",),
            laws,
        )


def test_runtime_program_input_supplies_its_compiler_emitted_laws() -> None:
    law = _primary_law()
    runtime = SimpleNamespace(canonical_scheduling=_catalog(_fact(law.family, law.fact_value)))

    result = execute_canonical_inference(runtime, ("prd_demo",), composition_roles=(ROLE,))

    assert isinstance(result, Success)
    assert result.pressures[0].identity == UnaryPressureIdentity("prd_demo", law.dimension, law.pressure_value)


def test_provenance_sort_is_deterministic_for_optional_quotations() -> None:
    law = _primary_law()
    provenance = (
        RuntimeEvidenceProvenance("src_demo", "paper#demo", "quoted"),
        RuntimeEvidenceProvenance("src_demo", "paper#demo", None),
        RuntimeEvidenceProvenance("src_demo", "paper#demo", "quoted"),
    )
    fact = replace(_fact(law.family, law.fact_value), provenance=provenance)
    result = _execute(_catalog(fact), ("prd_demo",), _laws())
    assert isinstance(result, Success)
    assert result.pressures[0].derivations[0].provenance == (provenance[1], provenance[0])
