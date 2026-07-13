"""Unit tests for read-model relation warning semantics."""

from __future__ import annotations

from planner.contracts import Relation, RelationSelector
from planner.query_model import build_stack_read_model
from planner.query_model.relation_matches import _row_match_labels

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

    read_model = build_stack_read_model(substances, [relation])
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

    read_model = build_stack_read_model(substances, [relation])
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
