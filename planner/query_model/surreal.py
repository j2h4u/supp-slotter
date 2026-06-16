"""SurrealDB session construction for the planner read model.

YAML cards and dataclasses remain the source of truth. This module owns the
SurrealDB SDK construction and command-scoped in-memory database population.
"""

from __future__ import annotations

from typing import cast

from surrealdb import Surreal

from planner.contracts import Dashboard, Product, Relation, Substance, TraitDef
from planner.query_model.session import SurrealSession
from planner.query_model.surreal_records import (
    dashboard_record,
    product_record,
    relation_record,
    substance_record,
    trait_record,
)


def build_surreal_session(
    substances: dict[str, Substance],
    relations: list[Relation],
    products: dict[str, Product] | None = None,
    *,
    trait_defs: dict[str, TraitDef] | None = None,
    stacks_data: dict[str, list[str]] | None = None,
    pillbox_stack_names: set[str] | None = None,
    dashboards: dict[str, Dashboard] | None = None,
) -> SurrealSession:
    """Load domain objects into an in-memory SurrealDB session."""
    db = cast(SurrealSession, Surreal("mem://"))
    db.use("planner", "read_model")

    _load_substances(db, substances)
    _load_relations(db, relations, substances, trait_defs)
    _load_products(db, products)
    _load_traits(db, trait_defs)
    _load_stacks(db, stacks_data)
    _load_pillboxes(db, pillbox_stack_names)
    _load_dashboards(db, dashboards)
    return db


def _load_substances(db: SurrealSession, substances: dict[str, Substance]) -> None:
    for substance_id, substance in substances.items():
        db.create("substance", substance_record(substance_id, substance))


def _load_relations(
    db: SurrealSession,
    relations: list[Relation],
    substances: dict[str, Substance],
    trait_defs: dict[str, TraitDef] | None,
) -> None:
    for relation in relations:
        db.create("relation", relation_record(relation, substances, trait_defs))


def _load_products(db: SurrealSession, products: dict[str, Product] | None) -> None:
    if not products:
        return
    for product_id, product in products.items():
        db.create("product", product_record(product_id, product))


def _load_traits(db: SurrealSession, trait_defs: dict[str, TraitDef] | None) -> None:
    if not trait_defs:
        return
    for trait_id, trait in trait_defs.items():
        db.create("trait", trait_record(trait_id, trait))


def _load_stacks(db: SurrealSession, stacks_data: dict[str, list[str]] | None) -> None:
    if not stacks_data:
        return
    for stack_name, product_ids in stacks_data.items():
        db.create("stack", {"name": stack_name, "products": list(product_ids)})


def _load_pillboxes(db: SurrealSession, pillbox_stack_names: set[str] | None) -> None:
    if not pillbox_stack_names:
        return
    for stack_name in pillbox_stack_names:
        db.create("pillbox", {"stack_name": stack_name})


def _load_dashboards(db: SurrealSession, dashboards: dict[str, Dashboard] | None) -> None:
    if not dashboards:
        return
    for slug, dashboard in dashboards.items():
        db.create("dashboard", dashboard_record(slug, dashboard))
