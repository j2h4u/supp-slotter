"""POC: equivalence tests for planner.cards.relations_surreal vs the canonical
Python implementations in planner.cards.relations.

The POC stands or falls on this file. The SurrealDB-backed implementations must
produce byte-identical output (after order normalization) for every relation
query, on the real data/ directory.

See POC-NOTES.md for the writeup of LOC, readability, and surprises.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from planner.cards.dashboards import load_dashboard
from planner.cards.product import load_product_registry
from planner.cards.relations import (
    collect_antagonizing_relations,
    collect_intra_product_relation_conflicts,
    collect_missing_balance_relations,
    collect_missing_support_relations,
    collect_substance_relation_matches,
    component_sets_have_relation,
    global_relation_refs,
    load_global_relations,
)
from planner.cards.relations_surreal import (
    SurrealSession,
    build_surreal_db,
    collect_antagonizing_relations_surreal,
    collect_intra_product_relation_conflicts_surreal,
    collect_missing_balance_relations_surreal,
    collect_missing_support_relations_surreal,
    collect_substance_relation_matches_surreal,
    component_sets_have_relation_surreal,
    global_relation_refs_surreal,
)
from planner.cards.substance import load_substance_registry
from planner.cards.traits import load_traits
from planner.contracts import Dashboard, Product, Relation, Substance, TraitDef
from planner.engine.audit_surreal import collect_cleanup_sections_surreal
from planner.io import DASHBOARDS_DIR, DATA_DIR, STACKS_PATH, load_yaml_mapping


@pytest.fixture(scope="module")
def real_substances() -> dict[str, Substance]:
    return load_substance_registry()


@pytest.fixture(scope="module")
def real_relations() -> list[Relation]:
    return load_global_relations()


@pytest.fixture(scope="module")
def real_products() -> dict[str, Product]:
    return load_product_registry()


@pytest.fixture(scope="module")
def real_trait_defs() -> dict[str, TraitDef]:
    return load_traits(DATA_DIR / "traits.yaml")


@pytest.fixture(scope="module")
def real_stacks_data() -> dict[str, list[str]]:
    raw = load_yaml_mapping(STACKS_PATH)
    out: dict[str, list[str]] = {}
    for name, items in raw.items():
        if isinstance(items, list):
            items_list = cast("list[Any]", items)
            out[name] = [item for item in items_list if isinstance(item, str)]
    return out


@pytest.fixture(scope="module")
def real_pillbox_stack_names() -> set[str]:
    raw = load_yaml_mapping(DATA_DIR / "pillboxes.yaml")
    return set(raw.keys())


@pytest.fixture(scope="module")
def real_dashboards() -> dict[str, Dashboard]:
    return {p.stem: load_dashboard(p) for p in sorted(DASHBOARDS_DIR.glob("*.yaml"))}


@pytest.fixture(scope="module")
def surreal_db(
    real_substances: dict[str, Substance],
    real_relations: list[Relation],
    real_products: dict[str, Product],
    real_trait_defs: dict[str, TraitDef],
    real_stacks_data: dict[str, list[str]],
    real_pillbox_stack_names: set[str],
    real_dashboards: dict[str, Dashboard],
) -> SurrealSession:
    return build_surreal_db(
        real_substances,
        real_relations,
        real_products,
        trait_defs=real_trait_defs,
        stacks_data=real_stacks_data,
        pillbox_stack_names=real_pillbox_stack_names,
        dashboards=real_dashboards,
    )


def _sort_key(warning: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(warning.get("type", "")),
        str(warning.get("source_substance", "")),
        str(warning.get("target_substance", "")),
        str(warning.get("reason", "")),
    )


def _normalize(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(warnings, key=_sort_key)


# ---------------------------------------------------------------------------
# Active-set fixtures: cover the two regimes that exercise different code paths
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def active_all(real_substances: dict[str, Substance]) -> set[str]:
    """Every substance treated as active — maximises 'both endpoints active' matches."""
    return set(real_substances.keys())


@pytest.fixture(scope="module")
def active_partial(real_substances: dict[str, Substance]) -> set[str]:
    """Deterministic ~25% slice — exercises missing-partner branches."""
    sorted_ids = sorted(real_substances.keys())
    return set(sorted_ids[::4])


@pytest.fixture(scope="module")
def active_empty() -> set[str]:
    return set()


# ---------------------------------------------------------------------------
# Antagonizing equivalence — "both endpoints active"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "active_fixture",
    ["active_all", "active_partial", "active_empty"],
)
def test_antagonizing_equivalence(
    request: pytest.FixtureRequest,
    real_substances: dict[str, Substance],
    real_relations: list[Relation],
    surreal_db: SurrealSession,
    active_fixture: str,
) -> None:
    active: set[str] = request.getfixturevalue(active_fixture)
    py_out = collect_antagonizing_relations(real_substances, active, real_relations)
    surreal_out = collect_antagonizing_relations_surreal(surreal_db, active)
    assert _normalize(py_out) == _normalize(surreal_out)


# ---------------------------------------------------------------------------
# Missing balance equivalence — "one active, the other absent"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "active_fixture",
    ["active_all", "active_partial", "active_empty"],
)
def test_missing_balance_equivalence(
    request: pytest.FixtureRequest,
    real_substances: dict[str, Substance],
    real_relations: list[Relation],
    surreal_db: SurrealSession,
    active_fixture: str,
) -> None:
    active: set[str] = request.getfixturevalue(active_fixture)
    py_out = collect_missing_balance_relations(real_substances, active, real_relations)
    surreal_out = collect_missing_balance_relations_surreal(surreal_db, active)
    assert _normalize(py_out) == _normalize(surreal_out)


# ---------------------------------------------------------------------------
# Missing support equivalence — "target (primary) active, source (cofactor) absent"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "active_fixture",
    ["active_all", "active_partial", "active_empty"],
)
def test_missing_support_equivalence(
    request: pytest.FixtureRequest,
    real_substances: dict[str, Substance],
    real_relations: list[Relation],
    surreal_db: SurrealSession,
    active_fixture: str,
) -> None:
    active: set[str] = request.getfixturevalue(active_fixture)
    py_out = collect_missing_support_relations(real_substances, active, real_relations)
    surreal_out = collect_missing_support_relations_surreal(surreal_db, active)
    assert _normalize(py_out) == _normalize(surreal_out)


# ---------------------------------------------------------------------------
# global_relation_refs equivalence
# ---------------------------------------------------------------------------

def test_global_relation_refs_equivalence(
    real_substances: dict[str, Substance],
    real_relations: list[Relation],
    surreal_db: SurrealSession,
) -> None:
    py_out = global_relation_refs(real_substances, real_relations)
    surreal_out = global_relation_refs_surreal(surreal_db)
    assert py_out == surreal_out


# ---------------------------------------------------------------------------
# component_sets_have_relation equivalence — every product pair, every type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("relation_type", ["balance", "competes", "antagonizes", "supports"])
def test_component_sets_have_relation_equivalence(
    real_substances: dict[str, Substance],
    real_relations: list[Relation],
    real_products: dict[str, Product],
    surreal_db: SurrealSession,
    relation_type: str,
) -> None:
    # Pick a handful of multi-component products to pair up — full N^2 over all
    # products would be slow without adding signal beyond the first few samples.
    multi = [p for p in real_products.values() if len(p.components) >= 2][:8]
    assert len(multi) >= 2

    mismatches: list[str] = []
    for left in multi:
        for right in multi:
            left_ids = [c.substance for c in left.components]
            right_ids = [c.substance for c in right.components]
            py = component_sets_have_relation(
                left_ids, right_ids, real_substances, relation_type, real_relations
            )
            surreal = component_sets_have_relation_surreal(
                surreal_db, left_ids, right_ids, relation_type
            )
            if py != surreal:
                mismatches.append(
                    f"left={left.id} right={right.id} type={relation_type}: "
                    f"py={py} surreal={surreal}"
                )
    assert not mismatches, "\n".join(mismatches)


# ---------------------------------------------------------------------------
# collect_substance_relation_matches equivalence — sample of substances
# ---------------------------------------------------------------------------

def test_collect_substance_relation_matches_equivalence(
    real_substances: dict[str, Substance],
    real_relations: list[Relation],
    surreal_db: SurrealSession,
) -> None:
    # Every substance that appears in any relation refs — these are the
    # interesting cases. Plus a few that don't, to verify the empty path.
    ref_ids = global_relation_refs(real_substances, real_relations)
    test_ids = sorted(ref_ids)[:20] + sorted(set(real_substances) - ref_ids)[:3]

    mismatches: list[str] = []
    for sid in test_ids:
        substance = real_substances.get(sid)
        if substance is None:
            continue
        py_matches = collect_substance_relation_matches(substance, real_relations)
        surreal_matches = collect_substance_relation_matches_surreal(
            surreal_db, substance.id, substance.name
        )
        # Compare on (relation identity tuple, sorted labels)
        py_normalized = sorted(
            (
                rel.type,
                rel.source_substance or rel.source_name or "",
                rel.target_substance or rel.target_name or "",
                rel.reason,
                tuple(sorted(labels)),
            )
            for rel, labels in py_matches
        )
        surreal_normalized = sorted(
            (
                cast(str, row["type"]),
                cast(str, row.get("src_substance_raw") or row.get("src_name_raw") or ""),
                cast(str, row.get("tgt_substance_raw") or row.get("tgt_name_raw") or ""),
                cast(str, row.get("reason") or ""),
                tuple(sorted(labels)),
            )
            for row, labels in surreal_matches
        )
        if py_normalized != surreal_normalized:
            mismatches.append(
                f"substance {sid}: py={py_normalized!r} surreal={surreal_normalized!r}"
            )
    assert not mismatches, "\n".join(mismatches)


# ---------------------------------------------------------------------------
# Cleanup-sections smoke — verify the SurrealDB-backed cleanup runs to completion
# on real data/ and returns the expected 8 categories. Behavioral coverage now
# lives in tests/test_review_command.py (test_cmd_audit_*) and tests/test_phase_03.py.
# ---------------------------------------------------------------------------

def test_cleanup_sections_runs_and_returns_expected_keys(
    real_substances: dict[str, Substance],
    surreal_db: SurrealSession,
) -> None:
    out = collect_cleanup_sections_surreal(surreal_db, real_substances)
    assert set(out.keys()) == {
        "substances.reference_only",
        "products.without_stack",
        "traits.unused",
        "stacks.empty",
        "stacks.without_pillboxes",
        "pillboxes.without_stack",
        "substances.similar_names",
        "dashboard.empty_cluster",
    }
    for key, items in out.items():
        assert isinstance(items, list), f"{key} must be a list, got {type(items).__name__}"


# ---------------------------------------------------------------------------
# Intra-product equivalence — for every multi-component product, every relation type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("relation_type", ["balance", "competes", "antagonizes", "supports"])
def test_intra_product_conflicts_equivalence_all_products(
    real_substances: dict[str, Substance],
    real_relations: list[Relation],
    real_products: dict[str, Product],
    surreal_db: SurrealSession,
    relation_type: str,
) -> None:
    multi_component = {
        pid: p for pid, p in real_products.items() if len(p.components) >= 2
    }
    assert multi_component, "expected at least one multi-component product in real data"

    mismatches: list[str] = []
    for pid, product in multi_component.items():
        component_ids = [c.substance for c in product.components]
        item_id = f"item_{pid}"

        py_out = collect_intra_product_relation_conflicts(
            item_id=item_id,
            product_id=pid,
            component_ids=component_ids,
            substances=real_substances,
            relation_type=relation_type,
            global_relations=real_relations,
        )
        surreal_out = collect_intra_product_relation_conflicts_surreal(
            surreal_db,
            item_id=item_id,
            product_id=pid,
            component_ids=component_ids,
            relation_type=relation_type,
        )

        if py_out != surreal_out:
            mismatches.append(
                f"product={pid} type={relation_type}: "
                f"py={py_out!r} surreal={surreal_out!r}"
            )

    assert not mismatches, "\n".join(mismatches)
