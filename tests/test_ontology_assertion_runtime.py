"""Runtime parity for generated non-blocking ontology assertions."""

from __future__ import annotations

from planner.ontology.policies import load_ontology_assertions
from planner.query_model import build_stack_read_model

from tests.scheduling_fixtures import make_substance


def test_generated_assertions_preserve_all_canonical_records_and_semantics() -> None:
    assertions = load_ontology_assertions()

    assert len(assertions) == 28
    assert {assertion.id for assertion in assertions} == {
        f"rel_balance_{index:03d}" for index in range(1, 3)
    } | {f"rel_review_with_{index:03d}" for index in range(1, 16)} | {
        f"rel_supports_{index:03d}" for index in range(1, 12)
    }
    assert all(assertion.assertion_kind in {"clinical_review_signal", "ontology_assertion"} for assertion in assertions)
    assert all(assertion.semantic_family for assertion in assertions)


def test_assertion_projection_resolves_id_and_name_selectors_without_scheduling_effect() -> None:
    metformin = make_substance("sub_605u9zvqt2", "Metformin")
    b12 = make_substance("sub_b12", "Vitamin B12")
    assertions = tuple(
        assertion
        for assertion in load_ontology_assertions()
        if assertion.id == "rel_review_with_002"
    )

    read_model = build_stack_read_model(
        {metformin.id: metformin, b12.id: b12},
        [],
        ontology_assertions=assertions,
    )
    warnings = read_model.collect_review_with_relations({metformin.id, b12.id})

    assert len(warnings) == 1
    assert warnings[0]["source_substance"] == metformin.id
    assert warnings[0]["target_substance"] == "Vitamin B12"
    assert warnings[0]["type"] == "review_with_substance_present"
