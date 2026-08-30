"""Runtime parity for generated non-blocking ontology assertions."""

from __future__ import annotations

import pytest
from planner.contracts import Substance
from planner.ontology.policies import load_ontology_assertions
from planner.ontology.selector import resolve_selector
from planner.query_model.relations import classify_relations, resolve_relation_queries

from tests.helpers import ontology_bundle
from tests.scheduling_fixtures import SubstanceTraitOverrides, make_substance


def _canonical_relation_rows(substances: dict[str, Substance], active_substances: set[str]):
    bundle = ontology_bundle()
    assertions = tuple(
        assertion
        for assertion in load_ontology_assertions(bundle)
        if resolve_selector(assertion.source_selector, substances, bundle).outcome == "resolved"
        and resolve_selector(assertion.target_selector, substances, bundle).outcome == "resolved"
    )
    return classify_relations(
        resolve_relation_queries(assertions, substances, bundle), active_substances, bundle.runtime_program
    )


def test_assertion_projection_resolves_id_and_name_selectors_without_scheduling_effect() -> None:
    metformin = make_substance("sub_605u9zvqt2", "Metformin")
    b12 = make_substance("sub_b12", "Vitamin B12")

    rows = _canonical_relation_rows({metformin.id: metformin, b12.id: b12}, {metformin.id, b12.id})
    warnings = [row for row in rows["both_active"] if row["warning_type"] == "review_with_substance_present"]

    assert len(warnings) == 1
    assert warnings[0]["source"] == "Metformin"
    assert warnings[0]["target"] == "Vitamin B12"
    assert warnings[0]["warning_type"] == "review_with_substance_present"


def test_relation_warning_query_does_not_cross_relation_types_with_shared_filter() -> None:
    """A balance assertion must not satisfy the review_with warning rule."""
    zinc = make_substance("sub_zinc", "Zinc")
    copper = make_substance("sub_copper", "Copper")
    rows = _canonical_relation_rows({zinc.id: zinc, copper.id: copper}, {zinc.id, copper.id})

    assert not [
        row for entries in rows.values() for row in entries if row["warning_type"] == "review_with_substance_present"
    ]


@pytest.mark.parametrize(
    ("source_id", "source_name", "target_id", "target_name", "severity"),
    [
        ("sub_vvmld46dbz", "Calcium", "sub_ses5czfzi1", "Iron", "medium"),
        ("sub_vvmld46dbz", "Calcium", "sub_8ppxce3s17", "Zinc", "medium"),
        ("sub_60e4d06f8c", "L-Lysine", "sub_699a985e61", "L-Arginine", "low"),
        ("sub_c9720c7240", "Glycine", "sub_abb9604e58", "Beta-alanine", "low"),
        ("sub_c9720c7240", "Glycine", "sub_edcaca3af0", "Taurine", "low"),
        ("sub_844a87d72b", "Vitamin E", "sub_5723eafac4", "Vitamin E", "low"),
    ],
)
def test_eight_rule_cutover_review_pairs_emit_only_review_warnings(
    source_id: str,
    source_name: str,
    target_id: str,
    target_name: str,
    severity: str,
) -> None:
    source = make_substance(source_id, source_name)
    target = make_substance(target_id, target_name)
    rows = _canonical_relation_rows({source.id: source, target.id: target}, {source.id, target.id})
    warnings = [row for row in rows["both_active"] if row["warning_type"] == "review_with_substance_present"]

    assert len(warnings) == 1
    assert warnings[0]["source"] == source_name
    assert warnings[0]["target"] == target_name
    assert warnings[0]["severity"] == severity


def test_retired_mineral_fat_soluble_rule_emits_no_relation_warning() -> None:
    mineral = make_substance("sub_mineral", "Zinc", traits=SubstanceTraitOverrides(kind=("mineral",)))
    fat_soluble = make_substance("sub_fat_soluble", "Vitamin E", traits=SubstanceTraitOverrides(kind=("fat_soluble",)))
    rows = _canonical_relation_rows({mineral.id: mineral, fat_soluble.id: fat_soluble}, {mineral.id, fat_soluble.id})
    assert not [
        row for entries in rows.values() for row in entries if row["warning_type"] == "review_with_substance_present"
    ]


def test_tocopherol_review_relation_does_not_broaden_to_other_vitamin_e_forms() -> None:
    tocopherol = make_substance("sub_844a87d72b", "Vitamin E")
    other_form = make_substance("sub_grely3rikd", "Vitamin E")
    rows = _canonical_relation_rows(
        {tocopherol.id: tocopherol, other_form.id: other_form}, {tocopherol.id, other_form.id}
    )
    assert not [
        row for entries in rows.values() for row in entries if row["warning_type"] == "review_with_substance_present"
    ]
