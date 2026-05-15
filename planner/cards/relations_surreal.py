"""POC: SurrealDB-backed implementations of three relation queries.

Mirrors three functions from planner.cards.relations:
- collect_antagonizing_relations  (both endpoints active)
- collect_missing_balance_relations  (one endpoint active, the other absent)
- collect_intra_product_relation_conflicts  (relation between product components)

The loader pre-resolves each relation endpoint into a list of substance IDs
(matching by exact ID or by name) and stores the resolved arrays directly on
the relation record. This collapses the original "match by id OR by name"
plumbing into the loader, so the query side is array-set arithmetic.

Output shapes are byte-for-byte identical to the originals — equivalence is
asserted in tests/test_poc_surrealdb.py against the real data/ directory.

Not for production use; this module exists to evaluate ergonomic fit of
SurrealDB embedded against the relations-layer workload.
"""

from __future__ import annotations

from typing import Any, Protocol, cast

from surrealdb import Surreal

from planner.cards.substance import format_substance_name
from planner.contracts import Product, Relation, Substance


class SurrealSession(Protocol):
    """Structural type for the subset of surrealdb sync session methods we use.

    The surrealdb 2.x SDK exposes `Surreal` as a factory function (returning a
    union of connection types) and uses internal types (RecordIdType, Value)
    that don't conform cleanly to a plain Protocol — so we cast at the single
    construction seam (build_surreal_db) and use this Protocol everywhere
    downstream. Positional-only params decouple from SDK parameter names.
    """

    def use(self, namespace: str, database: str, /) -> Any: ...
    def create(self, table: str, data: dict[str, Any], /) -> Any: ...
    def query(self, sql: str, params: dict[str, Any] | None = None, /) -> list[dict[str, Any]]: ...


def _endpoint_fields(relation: Relation, side: str) -> tuple[str | None, str | None]:
    if side == "source":
        return relation.source_substance, relation.source_name
    return relation.target_substance, relation.target_name


def _resolve_endpoint_ids(
    relation: Relation,
    side: str,
    substances: dict[str, Substance],
) -> list[str]:
    """Resolve one relation endpoint to the substance IDs it matches.

    Matches by exact ID if present, otherwise by name (which can match multiple
    substances when the same name has several form variants).
    """
    exact_id, name = _endpoint_fields(relation, side)
    if exact_id is not None:
        return [exact_id] if exact_id in substances else []
    if name is not None:
        return [sid for sid, s in substances.items() if s.name == name]
    return []


def _endpoint_key_and_display(
    relation: Relation,
    side: str,
    substances: dict[str, Substance],
) -> tuple[str, str]:
    """Identity (key, display_name) for warning dedup — mirrors relation_endpoint_display."""
    exact_id, name = _endpoint_fields(relation, side)
    if exact_id is not None:
        substance = substances.get(exact_id)
        if substance is not None:
            return exact_id, format_substance_name(substance)
        return exact_id, exact_id
    if name is not None:
        return name, name
    return "<unknown>", "<unknown>"


def build_surreal_db(
    substances: dict[str, Substance],
    relations: list[Relation],
    products: dict[str, Product] | None = None,
) -> SurrealSession:
    """Load substances, pre-resolved relations, and (optionally) products into an in-memory SurrealDB.

    Returns the connected db handle. Caller owns it and should not share across threads.
    """
    db = cast(SurrealSession, Surreal("mem://"))
    db.use("planner", "poc")

    for sid, substance in substances.items():
        db.create("substance", {"id": sid, "name": substance.name})

    for relation in relations:
        src_ids = _resolve_endpoint_ids(relation, "source", substances)
        tgt_ids = _resolve_endpoint_ids(relation, "target", substances)
        src_key, src_display = _endpoint_key_and_display(relation, "source", substances)
        tgt_key, tgt_display = _endpoint_key_and_display(relation, "target", substances)
        record: dict[str, Any] = {
            "type": relation.type,
            "src_substances": src_ids,
            "tgt_substances": tgt_ids,
            "src_key": src_key,
            "tgt_key": tgt_key,
            "src_display": src_display,
            "tgt_display": tgt_display,
            "reason": relation.reason,
            "action": relation.action or "",
        }
        if relation.severity is not None:
            record["severity"] = relation.severity
        db.create("relation", record)

    if products:
        for pid, product in products.items():
            db.create(
                "product",
                {
                    "id": pid,
                    "name": product.name,
                    "components": [c.substance for c in product.components],
                },
            )

    return db


def _warning_from_row(row: dict[str, Any], warning_type: str) -> dict[str, Any]:
    """Build the canonical warning dict shape from a SurrealDB relation row.

    Matches the exact key set and ordering used by _append_missing_relation_warning
    in planner.cards.relations.
    """
    out: dict[str, Any] = {
        "type": warning_type,
        "source_substance": row["src_key"],
        "source_name": row["src_display"],
        "target_substance": row["tgt_key"],
        "target_name": row["tgt_display"],
        "reason": row.get("reason") or "",
        "action": row.get("action") or "",
    }
    severity = row.get("severity")
    if severity is not None:
        out["severity"] = severity
    return out


def collect_antagonizing_relations_surreal(
    db: SurrealSession,
    active_substances: set[str],
) -> list[dict[str, Any]]:
    """SurrealDB-backed `collect_antagonizing_relations`.

    Fires one warning per antagonizes relation where both endpoints have at
    least one matching active substance. Deduplicated by (src_key, target_key).
    """
    rows = db.query(
        "SELECT src_key, tgt_key, src_display, tgt_display, reason, action, severity "
        "FROM relation "
        "WHERE type = 'antagonizes' "
        "  AND src_substances ANYINSIDE $active "
        "  AND tgt_substances ANYINSIDE $active",
        {"active": list(active_substances)},
    )
    seen: set[tuple[str, str, str]] = set()
    warnings: list[dict[str, Any]] = []
    for row in rows:
        key = (row["src_key"], "antagonizes", row["tgt_key"])
        if key in seen:
            continue
        seen.add(key)
        warnings.append(_warning_from_row(row, "antagonizes_substance_present"))
    return warnings


def collect_missing_balance_relations_surreal(
    db: SurrealSession,
    active_substances: set[str],
) -> list[dict[str, Any]]:
    """SurrealDB-backed `collect_missing_balance_relations`.

    Balance is symmetric: fires from both directions independently — one side
    active, the other absent. The display always shows active → missing.

    SurrealQL has no top-level UNION combinator, so we issue two queries
    (forward, reverse) and merge in Python; dedup follows the original Python
    semantics on (src_key, type, tgt_key).
    """
    params = {"active": list(active_substances)}
    forward = db.query(
        "SELECT src_key, tgt_key, src_display, tgt_display, reason, action, severity "
        "FROM relation "
        "WHERE type = 'balance' "
        "  AND src_substances ANYINSIDE $active "
        "  AND tgt_substances NONEINSIDE $active",
        params,
    )
    reverse = db.query(
        "SELECT tgt_key AS src_key, src_key AS tgt_key, "
        "       tgt_display AS src_display, src_display AS tgt_display, "
        "       reason, action, severity "
        "FROM relation "
        "WHERE type = 'balance' "
        "  AND tgt_substances ANYINSIDE $active "
        "  AND src_substances NONEINSIDE $active",
        params,
    )
    seen: set[tuple[str, str, str]] = set()
    warnings: list[dict[str, Any]] = []
    for row in (*forward, *reverse):
        key = (row["src_key"], "balance", row["tgt_key"])
        if key in seen:
            continue
        seen.add(key)
        warnings.append(_warning_from_row(row, "missing_balance_substance"))
    return warnings


def collect_intra_product_relation_conflicts_surreal(
    db: SurrealSession,
    *,
    item_id: str,
    product_id: str,
    component_ids: list[str],
    relation_type: str,
) -> list[dict[str, Any]]:
    """SurrealDB-backed `collect_intra_product_relation_conflicts`.

    For one product's components, finds relations of the given type that
    connect any pair of those components. The original Python emits one
    conflict per *pair* (deduped by frozenset of substance IDs); this matches
    that semantic by deriving the pair from each matching relation row.
    """
    rows = db.query(
        "SELECT src_substances, tgt_substances, action FROM relation "
        "WHERE type = $type "
        "  AND src_substances ANYINSIDE $components "
        "  AND tgt_substances ANYINSIDE $components",
        {"type": relation_type, "components": component_ids},
    )

    # Mirror Python: iterate component_ids in order, pick first pair where a relation
    # row touches both sides, dedup by frozenset, attribute the row's action to the conflict.
    component_set = set(component_ids)
    conflicts: list[dict[str, Any]] = []
    seen_pairs: set[frozenset[str]] = set()

    for index, source_id in enumerate(component_ids):
        for target_id in component_ids[index + 1 :]:
            if source_id == target_id:
                continue
            pair_key = frozenset([source_id, target_id])
            if pair_key in seen_pairs:
                continue
            matching_row = _find_matching_row_for_pair(rows, source_id, target_id, component_set)
            if matching_row is None:
                continue
            seen_pairs.add(pair_key)
            conflicts.append(
                {
                    "type": "intra_product_relation_conflict",
                    "item": item_id,
                    "product": product_id,
                    "relation": relation_type,
                    "source_substance": source_id,
                    "target_substance": target_id,
                    "message": (
                        "Component relation conflicts inside one physical product; "
                        "scheduling keeps the product together and emits this warning"
                    ),
                    "action": matching_row.get("action") or "",
                }
            )
    return conflicts


def _find_matching_row_for_pair(
    rows: list[dict[str, Any]],
    source_id: str,
    target_id: str,
    component_set: set[str],
) -> dict[str, Any] | None:
    """Return the first relation row whose src/tgt resolved arrays cover this pair
    (in either order), restricted to substance IDs actually in the product."""
    for row in rows:
        src_ids: set[str] = set(row.get("src_substances") or [])
        tgt_ids: set[str] = set(row.get("tgt_substances") or [])
        if not src_ids or not tgt_ids:
            continue
        src_in_product = src_ids & component_set
        tgt_in_product = tgt_ids & component_set
        if (source_id in src_in_product and target_id in tgt_in_product) or (
            target_id in src_in_product and source_id in tgt_in_product
        ):
            return row
    return None
