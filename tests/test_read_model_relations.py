"""Unit tests for read-model relation warning semantics."""

from __future__ import annotations

from planner.contracts import OntologyAssertion, Relation, RelationSelector
from planner.query_model import build_stack_read_model
from planner.query_model.relation_matches import _row_match_labels
from planner.query_model.surreal_records import relation_record

from tests.scheduling_fixtures import make_substance


def test_collect_missing_support_relations_source_active_target_absent_no_warning() -> None:
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

    read_model = build_stack_read_model(substances, [relation], ontology_assertions=(_assertion(relation),))
    result = read_model.collect_missing_support_relations(active_substances)

    assert len(result) == 0


def test_collect_missing_support_relations_target_active_source_absent_emits_warning() -> None:
    """Target-active / source-absent direction triggers missing_support_substance."""
    sub_src = make_substance("sub_src", "Src Supporter")
    sub_tgt = make_substance("sub_tgt", "Tgt Supported")
    substances = {"sub_src": sub_src, "sub_tgt": sub_tgt}
    active_substances = {"sub_tgt"}
    relation = Relation(
        id="rel_support_2",
        type="supports",
        reason="supports pair",
        source_selector=RelationSelector(entity_id="sub_src"),
        target_selector=RelationSelector(entity_id="sub_tgt"),
    )

    read_model = build_stack_read_model(substances, [relation], ontology_assertions=(_assertion(relation),))
    result = read_model.collect_missing_support_relations(active_substances)

    assert len(result) == 1
    warning = result[0]
    assert warning["type"] == "missing_support_substance"
    assert warning["source_substance"] == "sub_src"
    assert warning["source_name"] == sub_src.name
    assert warning["target_substance"] == "sub_tgt"
    assert warning["target_name"] == sub_tgt.name
    assert warning["reason"] == "supports pair"


def test_row_match_labels_reports_canonical_selector_matches() -> None:
    row: dict[str, object] = {
        "src_substances": ["sub_target"],
        "tgt_substances": ["sub_target"],
    }

    labels = _row_match_labels(row, "sub_target")

    assert labels == ["source selector", "target selector"]


def test_row_match_labels_returns_no_label_without_selector_membership() -> None:
    row: dict[str, object] = {
        "src_substances": ["sub_other"],
        "tgt_substances": ["sub_other"],
    }

    labels = _row_match_labels(row, "sub_target")

    assert labels == []


def test_row_match_labels_uses_declared_entity_name_when_endpoint_is_unresolved() -> None:
    row: dict[str, object] = {
        "src_substances": [],
        "tgt_substances": [],
        "src_selector": {"kind": "entity", "name": "Vitamin B6"},
        "tgt_selector": {"kind": "entity", "name": "Levodopa"},
    }

    labels = _row_match_labels(row, "sub_fixture_b6", "Vitamin B6")

    assert labels == ["source selector"]


def test_relation_projection_uses_entity_label_for_id_selector() -> None:
    substance = make_substance("sub_source", "Readable Source")
    relation = Relation(
        id="rel_projection",
        type="supports",
        reason="test",
        source_selector=RelationSelector(entity_id="sub_source"),
        target_selector=RelationSelector(entity_name="Readable Target"),
    )

    record = relation_record(relation, {substance.id: substance})

    assert record["src_key"] == "sub_source"
    assert record["src_display"] == "Readable Source"
    assert record["tgt_display"] == "Readable Target"


def _assertion(relation: Relation) -> OntologyAssertion:
    return OntologyAssertion(
        id=relation.id,
        relation_type=relation.type,
        assertion_kind="ontology_assertion",
        semantic_family="biochemical_mechanism_assertion",
        reason=relation.reason,
        source_selector=relation.source_selector,
        target_selector=relation.target_selector,
        action=relation.action,
        severity=relation.severity,
    )
