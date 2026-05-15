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

from surrealdb import RecordID, Surreal

from planner.cards.dashboards import load_dashboard
from planner.cards.product import format_product_name
from planner.cards.substance import format_substance_name
from planner.contracts import Dashboard, Product, Relation, Substance, TraitDef
from planner.io import DASHBOARDS_DIR, DATA_DIR, STACKS_PATH, load_yaml_mapping


def id_str(value: Any) -> str:
    """Coerce a SurrealDB id field to its bare string. The bare string lives at
    `.id` on the RecordID (the repr prints `record_id=…` but the attribute is
    `.id`). Fall through if the value is already a string.
    """
    if isinstance(value, RecordID):
        return cast(str, value.id)
    return cast(str, value)


# --- YAML-on-disk helpers used by command entry points to feed build_surreal_db ---

def stacks_for_surreal() -> dict[str, list[str]]:
    """Read data/stacks.yaml and return {stack_name: [product_id, ...]}."""
    raw = load_yaml_mapping(STACKS_PATH)
    out: dict[str, list[str]] = {}
    for name, items in raw.items():
        if isinstance(items, list):
            items_list = cast("list[Any]", items)
            out[name] = [item for item in items_list if isinstance(item, str)]
    return out


def pillbox_stack_names() -> set[str]:
    """Top-level stack names declared in data/pillboxes.yaml."""
    raw = load_yaml_mapping(DATA_DIR / "pillboxes.yaml")
    return set(raw.keys())


def dashboards_for_surreal() -> dict[str, Dashboard]:
    """Load all data/dashboards/*.yaml into a {slug: Dashboard} map."""
    return {p.stem: load_dashboard(p) for p in sorted(DASHBOARDS_DIR.glob("*.yaml"))}


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


# Namespaces tracked on substance records. Order is fixed for trait_refs determinism.
_SUBSTANCE_NAMESPACES: tuple[tuple[str, str], ...] = (
    ("intake", "intake"),
    ("timing", "timing"),
    ("activity", "activity"),
    ("is", "is_"),
    ("effect", "effect"),
    ("risk", "risk"),
    ("context", "context"),
    ("pathway", "pathway"),
)


def _substance_trait_refs(substance: Substance) -> list[str]:
    """Pre-compute all "namespace:slug" pairs the substance carries.

    Used by cleanup queries (dashboard.empty_cluster, traits.unused) so dashboards
    can do a single `trait_refs ANYINSIDE $pairs` match without per-namespace field
    indirection.
    """
    refs: list[str] = []
    for namespace, field_name in _SUBSTANCE_NAMESPACES:
        slugs: tuple[str, ...] = getattr(substance, field_name, ())
        for slug in slugs:
            refs.append(f"{namespace}:{slug}")
    return refs


def build_surreal_db(
    substances: dict[str, Substance],
    relations: list[Relation],
    products: dict[str, Product] | None = None,
    *,
    trait_defs: dict[str, TraitDef] | None = None,
    stacks_data: dict[str, list[str]] | None = None,
    pillbox_stack_names: set[str] | None = None,
    dashboards: dict[str, Dashboard] | None = None,
) -> SurrealSession:
    """Load substances, pre-resolved relations, and (optionally) products / traits /
    stacks / pillboxes / dashboards into an in-memory SurrealDB.

    The relations queries only need substances + relations + products. Cleanup
    queries (audit_surreal) additionally need trait_defs, stacks_data,
    pillbox_stack_names, and dashboards. Caller owns the returned handle.
    """
    db = cast(SurrealSession, Surreal("mem://"))
    db.use("planner", "poc")

    for sid, substance in substances.items():
        substance_record: dict[str, Any] = {
            "id": sid,
            "name": substance.name,
            "intake": list(substance.intake),
            "timing": list(substance.timing),
            "activity": list(substance.activity),
            "is_": list(substance.is_),
            "effect": list(substance.effect),
            "risk": list(substance.risk),
            "context": list(substance.context),
            "pathway": list(substance.pathway),
            "prefer_with": list(substance.prefer_with),
            "trait_refs": _substance_trait_refs(substance),
        }
        if substance.form is not None:
            substance_record["form"] = substance.form
        db.create("substance", substance_record)

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
            # Raw endpoint fields preserved so collect_substance_relation_matches
            # can compute "exact id" vs "exact name" match labels per side.
            "src_substance_raw": relation.source_substance,
            "src_name_raw": relation.source_name,
            "tgt_substance_raw": relation.target_substance,
            "tgt_name_raw": relation.target_name,
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
                    "display_name": format_product_name(product),
                    "components": [c.substance for c in product.components],
                },
            )

    if trait_defs:
        for trait_id, trait in trait_defs.items():
            db.create(
                "trait",
                {
                    "id": trait_id,
                    "namespace": trait.namespace,
                    "short_name": trait.short_name,
                    "label": trait.label,
                },
            )

    if stacks_data:
        for stack_name, product_ids in stacks_data.items():
            db.create("stack", {"name": stack_name, "products": list(product_ids)})

    if pillbox_stack_names:
        for stack_name in pillbox_stack_names:
            db.create("pillbox", {"stack_name": stack_name})

    if dashboards:
        for slug, dashboard in dashboards.items():
            from_traits_pairs_list = [
                f"{ns}:{s}"
                for ns, slugs in dashboard.from_traits.items()
                for s in slugs
            ]
            db.create(
                "dashboard",
                {
                    "slug": slug,
                    "name": dashboard.name,
                    "from_traits_pairs": from_traits_pairs_list,
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


_RELATION_WARNING_PROJECTION = (
    "src_key, tgt_key, src_display, tgt_display, reason, action, severity"
)


def _collect_relation_warnings(
    db: SurrealSession,
    *,
    relation_type: str,
    warning_type: str,
    queries: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Run one or more relation SELECTs, merge rows, dedup by
    `(src_key, relation_type, tgt_key)`, and emit warnings via `_warning_from_row`.

    Multiple queries support balance's symmetric forward+reverse pattern; a
    single-query call covers antagonizes and supports.
    """
    rows: list[dict[str, Any]] = []
    for sql, params in queries:
        rows.extend(db.query(sql, params))
    seen: set[tuple[str, str, str]] = set()
    warnings: list[dict[str, Any]] = []
    for row in rows:
        key = (row["src_key"], relation_type, row["tgt_key"])
        if key in seen:
            continue
        seen.add(key)
        warnings.append(_warning_from_row(row, warning_type))
    return warnings


def collect_antagonizing_relations(
    db: SurrealSession,
    active_substances: set[str],
) -> list[dict[str, Any]]:
    """SurrealDB-backed `collect_antagonizing_relations`.

    Fires one warning per antagonizes relation where both endpoints have at
    least one matching active substance. Deduplicated by (src_key, target_key).
    """
    return _collect_relation_warnings(
        db,
        relation_type="antagonizes",
        warning_type="antagonizes_substance_present",
        queries=[(
            f"SELECT {_RELATION_WARNING_PROJECTION} FROM relation "
            "WHERE type = 'antagonizes' "
            "  AND src_substances ANYINSIDE $active "
            "  AND tgt_substances ANYINSIDE $active",
            {"active": list(active_substances)},
        )],
    )


def collect_missing_balance_relations(
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
    return _collect_relation_warnings(
        db,
        relation_type="balance",
        warning_type="missing_balance_substance",
        queries=[
            (
                f"SELECT {_RELATION_WARNING_PROJECTION} FROM relation "
                "WHERE type = 'balance' "
                "  AND src_substances ANYINSIDE $active "
                "  AND tgt_substances NONEINSIDE $active",
                params,
            ),
            (
                "SELECT tgt_key AS src_key, src_key AS tgt_key, "
                "       tgt_display AS src_display, src_display AS tgt_display, "
                "       reason, action, severity "
                "FROM relation "
                "WHERE type = 'balance' "
                "  AND tgt_substances ANYINSIDE $active "
                "  AND src_substances NONEINSIDE $active",
                params,
            ),
        ],
    )


def collect_missing_support_relations(
    db: SurrealSession,
    active_substances: set[str],
) -> list[dict[str, Any]]:
    """SurrealDB-backed `collect_missing_support_relations`.

    Supports is directional: source = cofactor/enabler, target = primary actor.
    Fires only the forward direction — primary active, cofactor absent. The
    reverse (cofactor active, primary absent) is not a warning. Display keeps
    source=source (the absent cofactor) and target=target (the active primary).
    """
    return _collect_relation_warnings(
        db,
        relation_type="supports",
        warning_type="missing_support_substance",
        queries=[(
            f"SELECT {_RELATION_WARNING_PROJECTION} FROM relation "
            "WHERE type = 'supports' "
            "  AND tgt_substances ANYINSIDE $active "
            "  AND src_substances NONEINSIDE $active",
            {"active": list(active_substances)},
        )],
    )


def collect_intra_product_relation_conflicts(
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


def relation_substance_pairs(
    db: SurrealSession,
    relation_type: str,
) -> set[frozenset[str]]:
    """Pre-extract all unordered substance pairs participating in relations of the given type.

    For each matching row, every (src, tgt) cross-product entry (excluding
    self-pairs) is added as a `frozenset({src, tgt})`. Used by scheduler hot
    paths that would otherwise issue a per-pair SurrealQL query inside a
    planning loop — one upfront query, then O(1) set membership per check.
    """
    pairs: set[frozenset[str]] = set()
    rows = db.query(
        "SELECT src_substances, tgt_substances FROM relation WHERE type = $t",
        {"t": relation_type},
    )
    for row in rows:
        src_ids = cast("list[str]", row.get("src_substances") or [])
        tgt_ids = cast("list[str]", row.get("tgt_substances") or [])
        for src in src_ids:
            for tgt in tgt_ids:
                if src != tgt:
                    pairs.add(frozenset({src, tgt}))
    return pairs


def _row_match_labels(
    row: dict[str, Any], substance_id: str, substance_name: str
) -> list[str]:
    """Compute 'source exact id' / 'target exact name' style labels.

    Mirrors `relation_endpoint_match_label`: per side, exact-id check wins if
    the id was set and matches; otherwise exact-name check fires when the name
    was set and matches. Both sides can fire independently for one relation.
    """
    labels: list[str] = []
    for side, id_field, name_field in (
        ("source", "src_substance_raw", "src_name_raw"),
        ("target", "tgt_substance_raw", "tgt_name_raw"),
    ):
        exact_id = row.get(id_field)
        expected_name = row.get(name_field)
        if isinstance(exact_id, str) and substance_id == exact_id:
            labels.append(f"{side} exact id")
        elif isinstance(expected_name, str) and substance_name == expected_name:
            labels.append(f"{side} exact name")
    return labels


def collect_substance_relation_matches(
    db: SurrealSession,
    substance_id: str,
    substance_name: str,
) -> list[tuple[dict[str, Any], list[str]]]:
    """SurrealDB-backed `collect_substance_relation_matches`. Returns each
    matching relation row paired with the list of side-labels that explain why
    it matched. A relation can match by source, target, or both.
    """
    rows = db.query(
        "SELECT * FROM relation "
        "WHERE src_substances CONTAINS $sid OR tgt_substances CONTAINS $sid "
        "   OR src_name_raw = $name OR tgt_name_raw = $name",
        {"sid": substance_id, "name": substance_name},
    )
    matches: list[tuple[dict[str, Any], list[str]]] = []
    for row in rows:
        labels = _row_match_labels(row, substance_id, substance_name)
        if labels:
            matches.append((row, labels))
    return matches


def print_central_relation_matches(
    db: SurrealSession,
    substance_id: str,
    substance_name: str,
) -> None:
    """SurrealDB-backed `print_central_relation_matches`. Output is identical
    to the original, line-for-line.
    """
    print("\nCentral relations from data/relations.yaml (read-only)")
    print("Edit these in data/relations.yaml, not in this substance card.")
    if substance_id:
        print(f"Matches this substance by id: {substance_id}")
    if substance_name:
        print(f"Matches this substance by exact name: {substance_name}")

    matches = collect_substance_relation_matches(db, substance_id, substance_name)
    if not matches:
        print("  none matched; add links in data/relations.yaml if needed.")
        return

    print("Note: balance/competes are symmetric; supports/antagonizes are directional.")
    grouped: dict[str, list[tuple[dict[str, Any], list[str]]]] = {}
    for row, matched_by in matches:
        grouped.setdefault(cast(str, row["type"]), []).append((row, matched_by))

    for relation_type in ("balance", "competes", "supports", "antagonizes"):
        relation_group = grouped.get(relation_type)
        if not relation_group:
            continue
        print(f"\n{relation_type}")
        for row, matched_by in relation_group:
            print(f"  {row['src_display']} -> {row['tgt_display']}")
            print(f"    matched by: {', '.join(matched_by)}")
            reason = row.get("reason")
            if reason:
                print(f"    reason: {reason}")
            action = row.get("action")
            if action:
                print(f"    action: {action}")


def _stack_partition_substance_ids(db: SurrealSession, *, inactive: bool) -> set[str]:
    """Substance IDs referenced by products in stacks matching the partition."""
    op = "==" if inactive else "!="
    target_product_ids: set[str] = set()
    for row in db.query(f"SELECT products FROM stack WHERE name {op} 'inactive'"):
        target_product_ids.update(row.get("products") or [])
    result: set[str] = set()
    for row in db.query("SELECT id, components FROM product"):
        if id_str(row["id"]) in target_product_ids:
            result.update(row.get("components") or [])
    return result


def active_substance_ids(db: SurrealSession) -> set[str]:
    """Substance IDs referenced by any product in a non-inactive stack.

    Mirrors `_build_active_substance_ids` from review.py. Built from stack +
    product tables — does NOT include substances referenced only via relations
    or dashboards.
    """
    return _stack_partition_substance_ids(db, inactive=False)


def inactive_substance_ids(db: SurrealSession) -> set[str]:
    """Substance IDs referenced by any product in the 'inactive' stack."""
    return _stack_partition_substance_ids(db, inactive=True)


_RELATION_STATUS_PROJECTION = (
    "SELECT type, src_display AS source, tgt_display AS target, reason, "
    "  IF src_substances ANYINSIDE $active AND tgt_substances ANYINSIDE $active "
    "    THEN 'both_active' "
    "  ELSE IF src_substances ANYINSIDE $active "
    "    THEN 'missing_target' "
    "  ELSE IF tgt_substances ANYINSIDE $active "
    "    THEN 'missing_source' "
    "  ELSE 'neither_active' "
    "  END AS status "
    "FROM relation"
)


def classify_relations(
    db: SurrealSession,
    active_substances: set[str],
) -> dict[str, list[dict[str, str]]]:
    """Bucket each relation by which endpoints are active.

    Mirrors `_classify_relations` in review.py. Output shape:
    {status: [{type, source, target, reason}, ...]} where status ∈
    {both_active, missing_source, missing_target, neither_active}.
    """
    by_status: dict[str, list[dict[str, str]]] = {
        "both_active": [],
        "missing_source": [],
        "missing_target": [],
        "neither_active": [],
    }
    rows = db.query(_RELATION_STATUS_PROJECTION, {"active": list(active_substances)})
    for row in rows:
        status = cast(str, row["status"])
        by_status[status].append({
            "type": cast(str, row["type"]),
            "source": cast(str, row["source"]),
            "target": cast(str, row["target"]),
            "reason": cast(str, row.get("reason") or ""),
        })
    return by_status


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


_KNOWLEDGE_NAMESPACE_ORDER: tuple[str, ...] = ("risk", "pathway", "effect", "context")


def _title_from_slug(slug: str) -> str:
    return slug.replace("_", " ").title()


def active_fact_index(
    db: SurrealSession,
    *,
    item_id_sequence: list[str],
    item_products: dict[str, str],
) -> list[dict[str, Any]]:
    """SurrealDB-backed `build_active_fact_index`.

    Builds an inverted index of active knowledge facts → products. Each
    substance's risk/pathway/effect/context arrays are projected onto its
    product memberships. Output shape matches the original Python emitter
    byte-for-byte: list of {namespace, fact, label, product_count, products}.

    The scheduler-internal (item_id, product_id) mapping is passed in because
    it isn't in the DB — items are runtime placements, not first-class records.
    Everything else (products, substances, trait labels, dashboard names) is
    read from SurrealDB.
    """
    active_product_ids: set[str] = {
        item_products[item_id] for item_id in item_id_sequence
    }
    if not active_product_ids:
        return []

    products_by_id: dict[str, dict[str, Any]] = {}
    for row in db.query("SELECT id, display_name, components FROM product"):
        pid = id_str(row["id"])
        if pid in active_product_ids:
            products_by_id[pid] = row

    active_component_ids: set[str] = set()
    for row in products_by_id.values():
        active_component_ids.update(row.get("components") or [])

    substances_by_id: dict[str, dict[str, Any]] = {}
    if active_component_ids:
        for row in db.query(
            "SELECT id, risk, pathway, effect, context FROM substance"
        ):
            sid = id_str(row["id"])
            if sid in active_component_ids:
                substances_by_id[sid] = row

    facts: dict[tuple[str, str], dict[str, str]] = {}
    for product_id, product_row in products_by_id.items():
        product_name = cast(str, product_row["display_name"])
        components = cast("list[str]", product_row.get("components") or [])
        for component_id in components:
            substance_row = substances_by_id.get(component_id)
            if substance_row is None:
                continue
            for namespace in _KNOWLEDGE_NAMESPACE_ORDER:
                slugs = cast("list[str]", substance_row.get(namespace) or [])
                for slug in slugs:
                    facts.setdefault((namespace, slug), {})[product_id] = product_name

    trait_label_by_pair: dict[tuple[str, str], str] = {}
    for row in db.query(
        "SELECT namespace, short_name, label FROM trait "
        "WHERE namespace INSIDE $namespaces",
        {"namespaces": list(_KNOWLEDGE_NAMESPACE_ORDER)},
    ):
        trait_label_by_pair[
            (cast(str, row["namespace"]), cast(str, row["short_name"]))
        ] = cast(str, row["label"])

    dashboard_name_by_slug: dict[str, str] = {
        cast(str, row["slug"]): cast(str, row["name"])
        for row in db.query("SELECT slug, name FROM dashboard")
    }

    def fact_label(namespace: str, slug: str) -> str:
        label = trait_label_by_pair.get((namespace, slug))
        if label:
            return label
        if namespace == "context":
            return dashboard_name_by_slug.get(slug, _title_from_slug(slug))
        return _title_from_slug(slug)

    namespace_rank = {
        namespace: index
        for index, namespace in enumerate(_KNOWLEDGE_NAMESPACE_ORDER)
    }
    index: list[dict[str, Any]] = []
    for namespace, slug in sorted(
        facts,
        key=lambda key: (
            namespace_rank.get(key[0], len(namespace_rank)),
            fact_label(key[0], key[1]).casefold(),
            key[1],
        ),
    ):
        product_entries = sorted(
            facts[(namespace, slug)].values(), key=str.casefold
        )
        index.append(
            {
                "namespace": namespace,
                "fact": slug,
                "label": fact_label(namespace, slug),
                "product_count": len(product_entries),
                "products": product_entries,
            }
        )
    return index
