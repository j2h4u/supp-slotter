"""Focused cross-card and plan-input integration checks for canonical facts."""

from __future__ import annotations

import json
from dataclasses import replace
from functools import cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import planner.engine._plan_inputs as plan_inputs_module
import planner.engine.check as check_module
import pytest
from planner.contracts import CardLoadError, Product, ProductComponent, Substance
from planner.engine._plan_types import PlanInputs
from planner.ontology.canonical_facts import validate_canonical_scheduling
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import (
    RuntimeCanonicalScheduling,
    RuntimeCanonicalSchedulingFact,
    RuntimeEvidenceProvenance,
    RuntimeFactApplicability,
    RuntimeFactSubject,
    decode_runtime_program,
)
from planner.paths import Paths

ROOT = Path(__file__).resolve().parents[1]


@cache
def _basis() -> RuntimeCanonicalScheduling:
    return decode_runtime_program(
        cast(dict[str, Any], json.loads((ROOT / "ontology/generated/runtime-program.json").read_text(encoding="utf-8")))
    ).canonical_scheduling


def _catalog() -> RuntimeCanonicalScheduling:
    basis = _basis()
    return RuntimeCanonicalScheduling(
        basis.dimensions,
        basis.families,
        basis.evidence_sources,
        (
            RuntimeCanonicalSchedulingFact(
                "fact_food",
                "FoodEffect",
                RuntimeFactSubject("sub_demo", None),
                RuntimeFactApplicability("sub_demo", None),
                (RuntimeEvidenceProvenance(basis.evidence_sources[0].id, "paper#food", None),),
                "bioavailability_increases",
            ),
        ),
        basis.laws,
    )


def _cards() -> tuple[dict[str, Substance], dict[str, Product]]:
    substances = {"sub_demo": Substance("sub_demo", "Demo substance")}
    products = {
        "prd_demo": Product(
            "prd_demo",
            "Demo product",
            components=(ProductComponent("sub_demo", id="cmp_prd_demo__sub_demo"),),
        ),
    }
    return substances, products


def test_canonical_reference_validator_accepts_empty_catalog() -> None:
    validate_canonical_scheduling(
        RuntimeCanonicalScheduling((), (), (), (), ()),
        {},
        {},
    )


def test_canonical_reference_validator_accepts_matching_role_and_fact() -> None:
    substances, products = _cards()
    validate_canonical_scheduling(_catalog(), substances, products)


def test_canonical_reference_validator_accepts_matching_composition_role_fact() -> None:
    substances, products = _cards()
    catalog = _catalog()
    role_id = "cmp_prd_demo__sub_demo"
    fact = replace(
        catalog.facts[0],
        subject=RuntimeFactSubject(None, role_id),
        applicability=RuntimeFactApplicability(None, role_id),
    )

    validate_canonical_scheduling(replace(catalog, facts=(fact,)), substances, products)


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_subject",
        "unknown_applicability",
        "mismatched_subject",
        "mismatched_role_target",
        "unknown_source",
        "mismatched_subject_role",
    ],
)
def test_canonical_reference_validator_rejects_dangling_or_inconsistent_references(
    mutation: str,
) -> None:
    substances, products = _cards()
    catalog = _catalog()
    if mutation == "unknown_subject":
        fact = replace(catalog.facts[0], subject=RuntimeFactSubject("sub_missing", None))
        catalog = replace(catalog, facts=(fact,))
    elif mutation == "unknown_applicability":
        fact = replace(catalog.facts[0], applicability=RuntimeFactApplicability(None, "cmp_missing"))
        catalog = replace(catalog, facts=(fact,))
    elif mutation == "mismatched_subject":
        substances["sub_other"] = Substance("sub_other", "Other substance")
        fact = replace(catalog.facts[0], subject=RuntimeFactSubject("sub_other", None))
        catalog = replace(catalog, facts=(fact,))
    elif mutation == "mismatched_role_target":
        fact = replace(
            catalog.facts[0],
            applicability=RuntimeFactApplicability(None, "cmp_prd_demo__sub_demo"),
        )
        catalog = replace(catalog, facts=(fact,))
    elif mutation == "unknown_source":
        fact = replace(
            catalog.facts[0],
            provenance=(RuntimeEvidenceProvenance("src_missing", "paper#food", None),),
        )
        with pytest.raises(OntologyInfrastructureError, match="unknown family, value, or evidence source"):
            replace(catalog, facts=(fact,))
        return
    elif mutation == "mismatched_subject_role":
        catalog = replace(
            catalog,
            facts=(
                replace(
                    catalog.facts[0],
                    subject=RuntimeFactSubject(None, "cmp_prd_demo__sub_demo"),
                    applicability=RuntimeFactApplicability("sub_demo", None),
                ),
            ),
        )

    with pytest.raises(CardLoadError, match="canonical fact catalog reference validation failed"):
        validate_canonical_scheduling(catalog, substances, products)


def test_plan_inputs_keeps_runtime_program_as_canonical_scheduling_authority(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    substances, products = _cards()
    catalog = _catalog()
    runtime = SimpleNamespace(
        canonical_scheduling=catalog,
        glue_contract=SimpleNamespace(
            inactive_stack_name="inactive",
            stack_partition=SimpleNamespace(routable_stack_names=("daily", "training")),
        ),
    )
    bundle = SimpleNamespace(runtime_program=runtime)
    monkeypatch.setattr(plan_inputs_module, "load_pillboxes", lambda *_args: {})
    monkeypatch.setattr(plan_inputs_module, "check_pillbox_slot_anchors", lambda *_args: [])
    monkeypatch.setattr(plan_inputs_module, "load_yaml", lambda *_args: {})
    monkeypatch.setattr(plan_inputs_module, "flatten_pillbox_slots", lambda *_args: {})
    monkeypatch.setattr(plan_inputs_module, "load_substance_registry", lambda *_args: substances)
    monkeypatch.setattr(plan_inputs_module, "load_product_registry", lambda *_args: products)
    monkeypatch.setattr(plan_inputs_module, "normalize_stack_entries", lambda *_args: {})
    monkeypatch.setattr(plan_inputs_module, "check_stack_alignment", lambda *_args: ([], object()))
    monkeypatch.setattr(plan_inputs_module, "check_routable_topologies", lambda *_args: [])

    result = plan_inputs_module.load_plan_inputs(Paths.from_root(tmp_path), bundle)  # type: ignore[arg-type]

    assert isinstance(result, PlanInputs)
    assert result.runtime_program.canonical_scheduling is catalog
    assert "canonical_scheduling" not in PlanInputs._fields


def test_plan_inputs_rejects_full_canonical_scheduling_before_relation_processing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A dangling canonical reference cannot disappear through later plan scoping."""
    substances, products = _cards()
    catalog = _catalog()
    catalog = replace(
        catalog,
        facts=(replace(catalog.facts[0], applicability=RuntimeFactApplicability("sub_missing", None)),),
    )
    bundle = SimpleNamespace(
        runtime_program=SimpleNamespace(
            canonical_scheduling=catalog,
            glue_contract=SimpleNamespace(
                inactive_stack_name="inactive",
                stack_partition=SimpleNamespace(routable_stack_names=("daily", "training")),
            ),
        )
    )
    monkeypatch.setattr(plan_inputs_module, "load_pillboxes", lambda *_args: {})
    monkeypatch.setattr(plan_inputs_module, "check_pillbox_slot_anchors", lambda *_args: [])
    monkeypatch.setattr(plan_inputs_module, "load_yaml", lambda *_args: {})
    monkeypatch.setattr(plan_inputs_module, "flatten_pillbox_slots", lambda *_args: {})
    monkeypatch.setattr(plan_inputs_module, "load_substance_registry", lambda *_args: substances)
    monkeypatch.setattr(plan_inputs_module, "load_product_registry", lambda *_args: products)
    monkeypatch.setattr(plan_inputs_module, "check_stack_alignment", lambda *_args: ([], object()))
    monkeypatch.setattr(plan_inputs_module, "check_routable_topologies", lambda *_args: [])

    assert plan_inputs_module.load_plan_inputs(Paths.from_root(tmp_path), bundle) is None  # type: ignore[arg-type]


def test_check_uses_the_same_canonical_reference_validator(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    substances, products = _cards()
    catalog = _catalog()
    runtime = SimpleNamespace(canonical_scheduling=catalog)
    bundle = SimpleNamespace(runtime_program=runtime)
    calls: list[tuple[object, object, object]] = []
    monkeypatch.setattr(check_module, "check_substances", lambda *_args: ([], [], set(substances)))
    monkeypatch.setattr(check_module, "load_substance_registry", lambda *_args: substances)
    monkeypatch.setattr(check_module, "load_yaml", lambda *_args: {})
    monkeypatch.setattr(check_module, "check_global_relations", lambda *_args: [])
    monkeypatch.setattr(check_module, "check_product_formulas", lambda *_args: ([], [], set(products)))
    monkeypatch.setattr(check_module, "load_product_registry", lambda *_args: products)
    monkeypatch.setattr(check_module, "validate_stacks", lambda *_args: ([], []))
    monkeypatch.setattr(check_module, "check_dashboards", lambda *_args: [])
    monkeypatch.setattr(
        check_module,
        "validate_canonical_scheduling",
        lambda actual, actual_substances, actual_products: calls.append((actual, actual_substances, actual_products)),
    )

    check_module._extend_card_validation_errors(Paths.from_root(tmp_path), [], [], bundle)  # type: ignore[arg-type]

    assert calls == [(catalog, substances, products)]
