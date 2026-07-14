"""Scheduling-constraint query governance tests."""

from planner.query_model.relation_conflicts import collect_intra_product_scheduling_constraint_conflicts


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
