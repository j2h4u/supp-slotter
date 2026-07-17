"""Scheduling-constraint query governance tests."""

from typing import cast

from planner.query_model.relation_conflicts import (
    _find_matching_row_for_pair,
    collect_intra_product_scheduling_constraint_conflicts,
)


class _QueryCapture:
    sql: str = ""

    def use(self, namespace: str, _database: str, /) -> object:
        return None

    def create(self, _table: str, data: dict[str, object], /) -> object:
        return data

    def query(self, sql: str, params: dict[str, object] | None = None, /) -> list[dict[str, object]]:
        self.sql = sql
        return []


def test_intra_product_conflict_query_requires_approved_block_with_evidence() -> None:
    db = _QueryCapture()

    assert (
        collect_intra_product_scheduling_constraint_conflicts(
            db,
            item_id="item",
            product_id="product",
            component_ids=["sub_a", "sub_b"],
        )
        == []
    )
    assert "enforcement = 'block'" in db.sql
    assert "status = 'approved'" in db.sql
    assert "array::len(evidence) > 0" in db.sql


def test_find_matching_row_skips_empty_rows_and_matches_forward_pair() -> None:
    matching = {"src_substances": ["a"], "tgt_substances": ["b"], "action": "separate"}
    assert (
        _find_matching_row_for_pair(
            [{}, {"src_substances": ["a"], "tgt_substances": []}, matching],
            "a",
            "b",
            {"a", "b"},
        )
        is matching
    )


def test_find_matching_row_matches_reverse_orientation_and_limits_to_product() -> None:
    matching = {"src_substances": ["outside", "b"], "tgt_substances": ["a"]}
    assert _find_matching_row_for_pair(cast(list[dict[str, object]], [matching]), "a", "b", {"a", "b"}) is matching


def test_find_matching_row_returns_none_for_non_matching_or_unknown_pairs() -> None:
    rows: list[dict[str, object]] = [
        {"src_substances": ["a"], "tgt_substances": ["c"]},
        {"src_substances": ["outside"], "tgt_substances": ["b"]},
    ]
    assert _find_matching_row_for_pair(rows, "a", "b", {"a", "b"}) is None
