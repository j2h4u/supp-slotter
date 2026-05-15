"""POC: equivalence tests for planner.cards.relations_surreal vs the canonical
Python implementations in planner.cards.relations.

The POC stands or falls on this file. The SurrealDB-backed implementations must
produce byte-identical output (after order normalization) for every relation
query, on the real data/ directory.

See POC-NOTES.md for the writeup of LOC, readability, and surprises.
"""

from __future__ import annotations

from typing import Any

import pytest

from planner.cards.product import load_product_registry
from planner.cards.relations import (
    collect_antagonizing_relations,
    collect_intra_product_relation_conflicts,
    collect_missing_balance_relations,
    collect_missing_support_relations,
    load_global_relations,
)
from planner.cards.relations_surreal import (
    SurrealSession,
    build_surreal_db,
    collect_antagonizing_relations_surreal,
    collect_intra_product_relation_conflicts_surreal,
    collect_missing_balance_relations_surreal,
    collect_missing_support_relations_surreal,
)
from planner.cards.substance import load_substance_registry
from planner.contracts import Product, Relation, Substance


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
def surreal_db(
    real_substances: dict[str, Substance],
    real_relations: list[Relation],
    real_products: dict[str, Product],
) -> SurrealSession:
    return build_surreal_db(real_substances, real_relations, real_products)


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
