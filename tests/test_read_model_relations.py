"""Unit tests for read-model relation warning semantics."""

from __future__ import annotations

from planner.contracts import Relation
from planner.query_model import build_stack_read_model
from planner.query_model.relation_matches import _row_match_labels

from tests.scheduling_fixtures import make_substance


def test_collect_missing_support_relations_source_active_target_absent_no_warning() -> None:
    """Cofactor present but primary actor absent does not warn."""
    sub_src = make_substance("sub_src", "Src")
    substances = {"sub_src": sub_src}
    active_substances = {"sub_src"}
    relation = Relation(
        type="supports",
        reason="supports pair",
        source_substance="sub_src",
        target_substance="sub_tgt",
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
        type="supports",
        reason="supports pair",
        source_substance="sub_src",
        target_substance="sub_tgt",
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


def test_row_match_labels_reports_id_name_trait_and_class_matches() -> None:
    row: dict[str, object] = {
        "src_substance_raw": "sub_target",
        "src_name_raw": "Other",
        "src_trait_raw": "intake:empty_preferred",
        "src_class_raw": "mineral",
        "src_substances": ["sub_target"],
        "tgt_substance_raw": "sub_other",
        "tgt_name_raw": "Target",
        "tgt_trait_raw": "effect:target",
        "tgt_class_raw": "adaptogen",
        "tgt_substances": ["sub_target"],
    }

    labels = _row_match_labels(row, "sub_target", "Target")

    assert labels == ["source exact id", "target exact name"]


def test_row_match_labels_falls_back_to_trait_and_class_matches() -> None:
    row: dict[str, object] = {
        "src_substance_raw": "sub_other",
        "src_name_raw": "Other",
        "src_trait_raw": "intake:empty_preferred",
        "src_class_raw": "mineral",
        "src_substances": ["sub_target"],
        "tgt_substance_raw": "sub_other",
        "tgt_name_raw": "Other",
        "tgt_trait_raw": None,
        "tgt_class_raw": "adaptogen",
        "tgt_substances": ["sub_target"],
    }

    labels = _row_match_labels(row, "sub_target", "Target")

    assert labels == ["source trait intake:empty_preferred", "target class is:adaptogen"]
