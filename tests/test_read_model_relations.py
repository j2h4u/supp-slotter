"""Unit tests for read-model relation warning semantics."""

from __future__ import annotations

import pytest
from planner.contracts import Relation, RelationSelector
from planner.ontology.policies import load_ontology_assertions
from planner.query_model import build_stack_read_model
from planner.query_model.relation_matches import _row_match_labels

from tests.helpers import ontology_bundle
from tests.scheduling_fixtures import make_substance


def test_canonical_balance_assertion_retains_current_authored_review_metadata() -> None:
    bundle = ontology_bundle()
    assertion = next(item for item in load_ontology_assertions(bundle) if item.id == "rel_balance_001")

    read_model = build_stack_read_model({}, [], ontology_bundle=bundle)
    rows = read_model.classify_relations(set())
    row = next(row for entries in rows.values() for row in entries if row["reason"] == assertion.reason)

    assert row["reason"] == assertion.reason
    assert row["severity"] == "medium"
    assert row["action"] == (
        "Review zinc/copper balance for sustained high-zinc exposure; do not split the same product or apply a "
        "universal zinc-copper interval."
    )


def test_canonical_vitamin_c_iron_support_assertion_retains_authored_review_metadata() -> None:
    bundle = ontology_bundle()
    assertion = next(item for item in load_ontology_assertions(bundle) if item.id == "rel_supports_009")

    assert assertion.severity == "low"
    assert assertion.action == (
        "Review only when nonheme iron supplementation or other relevant iron context is active; no required "
        "vitamin C supplement, co-dose, separation interval, or guaranteed outcome is established."
    )


def test_collect_relation_warnings_support_source_active_target_absent_no_warning() -> None:
    """Cofactor present but primary actor absent does not warn."""
    sub_src = make_substance("sub_src", "Src")
    substances = {"sub_src": sub_src}
    active_substances = {"sub_src"}
    relation = Relation(
        id="rel_support_1",
        type="supports",
        reason="supports pair",
        source_selector=RelationSelector(entity_id="sub_src"),
        target_selector=RelationSelector(entity_id="sub_tgt"),
    )

    read_model = build_stack_read_model(substances, [relation], ontology_bundle=ontology_bundle())
    result = [
        warning
        for warning in read_model.collect_relation_warnings(active_substances)
        if warning["type"] == "missing_support_substance"
    ]

    assert len(result) == 0


def test_collect_relation_warnings_support_target_active_source_absent_emits_warning() -> None:
    """Target-active / source-absent direction triggers missing_support_substance."""
    sub_src = make_substance("sub_src", "Src Supporter")
    sub_tgt = make_substance("sub_tgt", "Tgt Supported")
    substances = {"sub_src": sub_src, "sub_tgt": sub_tgt}
    active_substances = {"sub_tgt"}
    relation = Relation(
        id="rel_support_2",
        type="supports",
        assertion_kind="ontology_assertion",
        semantic_family="biochemical_mechanism_assertion",
        reason="supports pair",
        source_selector=RelationSelector(entity_id="sub_src"),
        target_selector=RelationSelector(entity_id="sub_tgt"),
    )

    read_model = build_stack_read_model(substances, [relation], ontology_bundle=ontology_bundle())
    result = [
        warning
        for warning in read_model.collect_relation_warnings(active_substances)
        if warning["type"] == "missing_support_substance"
    ]

    assert len(result) == 1
    warning = result[0]
    assert warning["type"] == "missing_support_substance"
    assert warning["source_substance"] == "sub_src"
    assert warning["source_name"] == sub_src.name
    assert warning["target_substance"] == "sub_tgt"
    assert warning["target_name"] == sub_tgt.name
    assert warning["reason"] == "supports pair"


@pytest.mark.parametrize(
    ("row", "substance_id", "substance_name", "expected"),
    [
        (
            {"src_substances": ["sub_target"], "tgt_substances": ["sub_target"]},
            "sub_target",
            "",
            ["source selector", "target selector"],
        ),
        (
            {"src_substances": ["sub_other"], "tgt_substances": ["sub_other"]},
            "sub_target",
            "",
            [],
        ),
        (
            {
                "src_substances": [],
                "tgt_substances": [],
                "src_selector": {"kind": "entity", "name": "Vitamin B6"},
                "tgt_selector": {"kind": "entity", "name": "Levodopa"},
            },
            "sub_fixture_b6",
            "Vitamin B6",
            ["source selector"],
        ),
    ],
)
def test_row_match_labels_reports_selector_matches(
    row: dict[str, object], substance_id: str, substance_name: str, expected: list[str]
) -> None:
    assert _row_match_labels(row, substance_id, substance_name) == expected
