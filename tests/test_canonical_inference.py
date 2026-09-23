"""V-right acceptance for canonical law execution and pressure normalization."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from functools import cache
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from planner.ontology.canonical_inference import (
    CompositionApplicabilityPath,
    Conflict,
    Success,
    UnaryPressureIdentity,
    execute_canonical_inference,
)
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import (
    IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY,
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

from tests.compiled_ontology import compiled_runtime_payload

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
    compiled = decode_runtime_program(
        cast(dict[str, Any], json.loads((ONTOLOGY / "generated/runtime-program.json").read_text(encoding="utf-8")))
    ).canonical_scheduling
    return RuntimeCanonicalScheduling(
        compiled.dimensions,
        compiled.families,
        (SOURCE, RuntimeEvidenceSource("src_other")),
        facts,
        compiled.laws,
    )


def _fact(
    family: str,
    value: str,
    *,
    subject: RuntimeFactSubject | None = None,
    applicability: RuntimeFactApplicability | None = None,
    fact_id: str = "fact_demo",
) -> RuntimeCanonicalSchedulingFact:
    if family == "ProductFoodInstruction":
        subject = RuntimeFactSubject(None, None, "prd_demo")
        applicability = RuntimeFactApplicability(None, None, "prd_demo")
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
    *,
    roles: tuple[RuntimeCompositionRole, ...] = (ROLE,),
) -> Success | Conflict:
    return execute_canonical_inference(
        catalog,
        selected_items,  # type: ignore[arg-type]
        applicability_expansion_strategy=IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY,
        composition_roles=roles,
        known_products={role.product for role in roles},
    )


def test_every_admitted_value_maps_to_one_pressure() -> None:
    """Execute the authored/compiled law table and reject generated drift."""

    authored = cast(dict[str, object], yaml.safe_load((ONTOLOGY / "canonical-laws.yaml").read_text(encoding="utf-8")))
    compiled_payload = cast(dict[str, Any], compiled_runtime_payload())
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
    assert len(runtime_laws) == len(compiled_laws) == 10
    for law in runtime_laws:
        result = _execute(_catalog(_fact(law.family, law.fact_value)), ("prd_demo",))
        assert isinstance(result, Success)
        assert result.pressures[0].identity == UnaryPressureIdentity("prd_demo", law.dimension, law.pressure_value)
        assert result.pressures[0].derivations[0].family == law.family
        assert result.pressures[0].derivations[0].fact.value == law.fact_value  # type: ignore[attr-defined]
        proof = result.pressures[0].derivations[0]
        assert proof.value == law.fact_value
        if law.family == "ProductFoodInstruction":
            assert proof.path == CompositionApplicabilityPath("product", "prd_demo", None, "prd_demo", "")


def test_wrong_or_unselected_applicability_does_not_emit_pressure() -> None:
    law = _primary_law()
    wrong_subject = _fact(
        law.family,
        law.fact_value,
        subject=RuntimeFactSubject("sub_other", None),
        applicability=RuntimeFactApplicability("sub_other", None),
        fact_id="fact_wrong_subject",
    )
    result = _execute(_catalog(wrong_subject), ("prd_other",), roles=(OTHER_ROLE,))
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
    result = _execute(_catalog(fact), ("prd_demo",))
    assert isinstance(result, Success)
    proof = result.pressures[0].derivations[0]
    assert proof.law.id == law.id
    assert proof.fact.id == "fact_demo"
    assert proof.subject == fact.subject  # type: ignore[attr-defined]
    assert proof.path.role_id == ROLE.id
    assert (proof.path.target_kind, proof.path.target_id) == ("substance", "sub_demo")
    assert proof.path.product == ROLE.product
    assert proof.path.substance == ROLE.substance
    assert proof.provenance == PROVENANCE


def test_product_scoped_proof_retains_subject_and_provenance() -> None:
    law = next(law for law in _laws() if law.family == "ProductFoodInstruction")
    fact = _fact(law.family, law.fact_value)
    result = _execute(_catalog(fact), ("prd_demo",))
    assert isinstance(result, Success)
    proof = result.pressures[0].derivations[0]
    assert proof.subject == fact.subject
    assert proof.provenance == PROVENANCE


def test_product_scoped_fact_for_unselected_product_is_ignored() -> None:
    law = next(law for law in _laws() if law.family == "ProductFoodInstruction")
    fact = _fact(law.family, law.fact_value)
    result = _execute(_catalog(fact), ("prd_other",), roles=(OTHER_ROLE,))
    assert isinstance(result, Success)
    assert result.pressures == ()


def test_duplicate_witnesses_facts_components_and_paths_normalize_to_one_pressure() -> None:
    law = _primary_law()
    duplicate = replace(
        _fact(law.family, law.fact_value),
        id="fact_duplicate",  # type: ignore[call-arg]
        provenance=PROVENANCE + PROVENANCE,  # type: ignore[arg-type]
    )
    result = _execute(_catalog(_fact(law.family, law.fact_value), duplicate), ("prd_demo",))
    assert isinstance(result, Success)
    assert len(result.pressures) == 1
    assert len(result.pressures[0].derivations) == 2
    assert result.pressures[0].derivations[1].provenance == PROVENANCE


def test_same_law_derivations_are_sorted_by_fact_id() -> None:
    law = _primary_law()
    result = _execute(
        _catalog(
            _fact(law.family, law.fact_value, fact_id="z_fact"),
            _fact(law.family, law.fact_value, fact_id="a_fact"),
        ),
        ("prd_demo",),
    )
    assert isinstance(result, Success)
    assert tuple(derivation.fact.id for derivation in result.pressures[0].derivations) == ("a_fact", "z_fact")


def test_same_pressure_derivations_are_sorted_by_law_id_before_fact_id() -> None:
    onset = next(law for law in _laws() if law.family == "AcuteSleepEffect" and law.pressure_value == "sleep")
    continuity = next(
        law
        for law in _laws()
        if law.family == "AcuteSleepEffect" and law.pressure_value == "sleep" and law.id != onset.id
    )
    result = _execute(
        _catalog(
            _fact(continuity.family, continuity.fact_value, fact_id="z_fact"),
            _fact(onset.family, onset.fact_value, fact_id="a_fact"),
        ),
        ("prd_demo",),
    )
    assert isinstance(result, Success)
    assert tuple(derivation.law.id for derivation in result.pressures[0].derivations) == tuple(
        sorted((onset.id, continuity.id))
    )


def test_one_fact_with_multiple_roles_has_stable_path_order() -> None:
    law = _primary_law()
    role_a = RuntimeCompositionRole("cmp_a", "prd_demo", "sub_demo")
    role_b = RuntimeCompositionRole("cmp_b", "prd_demo", "sub_demo")
    result = _execute(_catalog(_fact(law.family, law.fact_value)), ("prd_demo",), roles=(role_b, role_a))
    assert isinstance(result, Success)
    assert tuple(derivation.path.role_id for derivation in result.pressures[0].derivations) == ("cmp_a", "cmp_b")


def test_substance_fact_with_unselected_role_still_reaches_selected_role() -> None:
    law = _primary_law()
    result = _execute(
        _catalog(_fact(law.family, law.fact_value)),
        {"item_other": OTHER_ROLE.product},
        roles=(ROLE, OTHER_ROLE),
    )
    assert isinstance(result, Success)
    assert tuple(pressure.item_id for pressure in result.pressures) == ("item_other",)


def test_same_dimension_values_are_layout_free_conflict() -> None:
    first, second = _conflicting_laws()
    result = _execute(
        _catalog(
            _fact(first.family, first.fact_value),
            _fact(second.family, second.fact_value, fact_id="fact_other"),
        ),
        ("prd_demo",),
    )
    assert isinstance(result, Conflict)
    assert result.conflicts[0].item_id == "prd_demo"
    assert result.conflicts[0].dimension == first.dimension
    assert result.conflicts[0].values == tuple(sorted({first.pressure_value, second.pressure_value}))
    assert {derivation.fact.id for derivation in result.conflicts[0].derivations} == {"fact_demo", "fact_other"}


def test_cross_dimension_pressures_coexist() -> None:
    first, second = _cross_dimension_laws()
    result = _execute(
        _catalog(
            _fact(first.family, first.fact_value),
            _fact(second.family, second.fact_value, fact_id="fact_alert"),
        ),
        ("prd_demo",),
    )
    assert isinstance(result, Success)
    assert {(pressure.dimension, pressure.value) for pressure in result.pressures} == {
        (first.dimension, first.pressure_value),
        (second.dimension, second.pressure_value),
    }


def test_incomplete_law_graph_fails_closed_at_runtime_catalog_boundary() -> None:
    law = _primary_law()
    catalog = _catalog(_fact(law.family, law.fact_value))
    with pytest.raises(OntologyInfrastructureError, match="exact admissible coverage"):
        RuntimeCanonicalScheduling(
            catalog.dimensions,
            catalog.families,
            catalog.evidence_sources,
            catalog.facts,
            tuple(candidate for candidate in catalog.laws if candidate.id != law.id),
        )


def test_inference_rejects_duck_typed_runtime_programs() -> None:
    with pytest.raises(TypeError, match=r"^canonical inference requires RuntimeCanonicalScheduling$"):
        execute_canonical_inference(  # type: ignore[arg-type]
            object(),
            ("prd_demo",),
            applicability_expansion_strategy=IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY,
            composition_roles=(ROLE,),
        )


@pytest.mark.parametrize(
    ("selected", "message"),
    (
        (("",), "canonical inference selected items must contain non-empty strings"),
        ((42,), "canonical inference selected items must contain non-empty strings"),
        ({"item": ""}, "canonical inference selected item mapping must contain non-empty strings"),
        ({"": "prd_demo"}, "canonical inference selected item mapping must contain non-empty strings"),
        (("prd_unknown",), "canonical inference selected unknown products: prd_unknown"),
    ),
)
def test_malformed_or_unknown_selected_items_fail_closed(selected: object, message: str) -> None:
    with pytest.raises(OntologyInfrastructureError, match=f"^{re.escape(message)}$"):
        _execute(_catalog(), selected)


def test_valid_neutral_product_yields_no_pressures() -> None:
    result = execute_canonical_inference(
        _catalog(),
        ("prd_neutral",),
        applicability_expansion_strategy=IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY,
        known_products=("prd_neutral",),
    )
    assert isinstance(result, Success)
    assert result.pressures == ()


def test_provenance_sort_is_deterministic_for_optional_quotations() -> None:
    law = _primary_law()
    provenance = (
        RuntimeEvidenceProvenance("src_demo", "z-locator", "quoted"),
        RuntimeEvidenceProvenance("src_demo", "paper#demo", None),
        RuntimeEvidenceProvenance("src_other", "a-locator", "other"),
    )
    fact = replace(_fact(law.family, law.fact_value), provenance=provenance)
    result = _execute(_catalog(fact), ("prd_demo",))
    assert isinstance(result, Success)
    assert result.pressures[0].derivations[0].provenance == (provenance[1], provenance[0], provenance[2])


def test_provenance_sort_handles_same_locator_with_and_without_quotation() -> None:
    law = _primary_law()
    provenance = (
        RuntimeEvidenceProvenance("src_demo", "same-locator", "z-quoted"),
        RuntimeEvidenceProvenance("src_demo", "same-locator", "a-quoted"),
        RuntimeEvidenceProvenance("src_demo", "same-locator", None),
    )
    fact = replace(_fact(law.family, law.fact_value), provenance=provenance)
    result = _execute(_catalog(fact), ("prd_demo",))
    assert isinstance(result, Success)
    assert result.pressures[0].derivations[0].provenance == (provenance[2], provenance[1], provenance[0])


def test_unknown_composition_role_is_ignored() -> None:
    law = _primary_law()
    fact = _fact(
        law.family,
        law.fact_value,
        subject=RuntimeFactSubject(None, "cmp_missing"),
        applicability=RuntimeFactApplicability(None, "cmp_missing"),
    )
    result = _execute(_catalog(fact), ("prd_demo",))
    assert isinstance(result, Success)
    assert result.pressures == ()


def test_invalid_composition_role_is_rejected() -> None:
    with pytest.raises(
        OntologyInfrastructureError,
        match=r"^canonical inference composition roles must be complete runtime roles$",
    ):
        execute_canonical_inference(
            _catalog(),
            ("prd_demo",),
            applicability_expansion_strategy=IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY,
            composition_roles=(RuntimeCompositionRole("cmp_bad", "prd_demo", ""),),
        )


def test_non_runtime_composition_role_is_rejected() -> None:
    with pytest.raises(
        OntologyInfrastructureError,
        match=r"^canonical inference composition roles must be complete runtime roles$",
    ):
        execute_canonical_inference(
            _catalog(),
            ("prd_demo",),
            applicability_expansion_strategy=IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY,
            composition_roles=(object(),),  # type: ignore[arg-type]
        )


def test_known_products_must_be_non_empty_strings() -> None:
    with pytest.raises(
        OntologyInfrastructureError,
        match=r"^canonical inference known products must be non-empty strings$",
    ):
        execute_canonical_inference(
            _catalog(),
            ("prd_demo",),
            applicability_expansion_strategy=IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY,
            known_products=(42,),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "role",
    (
        RuntimeCompositionRole("", "prd_demo", "sub_demo"),
        RuntimeCompositionRole("cmp_bad", "", "sub_demo"),
    ),
)
def test_composition_role_identity_and_product_are_required(role: RuntimeCompositionRole) -> None:
    with pytest.raises(
        OntologyInfrastructureError,
        match=r"^canonical inference composition roles must be complete runtime roles$",
    ):
        execute_canonical_inference(
            _catalog(),
            ("prd_demo",),
            applicability_expansion_strategy=IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY,
            composition_roles=(role,),
        )


def test_unknown_product_error_lists_all_products_in_order() -> None:
    with pytest.raises(
        OntologyInfrastructureError,
        match=r"^canonical inference selected unknown products: prd_missing_a, prd_missing_b$",
    ):
        execute_canonical_inference(
            _catalog(),
            {"item_b": "prd_missing_b", "item_a": "prd_missing_a"},
            applicability_expansion_strategy=IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY,
            known_products=("prd_demo",),
        )
