"""SurrealDB session construction for the planner read model.

YAML cards and dataclasses remain the source of truth. This module owns the
SurrealDB SDK construction and command-scoped in-memory database population.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from surrealdb import Surreal

from planner.contracts import Dashboard, Product, Relation, Substance, TraitDef
from planner.query_model.session import SurrealSession
from planner.query_model.surreal_records import (
    dashboard_record,
    product_record,
    relation_record,
    substance_record,
)


@dataclass(frozen=True, slots=True)
class SurrealLoadContext:
    trait_defs: dict[str, TraitDef] | None
    stacks_data: dict[str, list[str]] | None
    pillbox_stack_names: set[str] | None
    dashboards: dict[str, Dashboard] | None


def build_surreal_session(
    substances: dict[str, Substance],
    relations: list[Relation],
    products: dict[str, Product] | None = None,
    load_context: SurrealLoadContext | None = None,
) -> SurrealSession:
    """Load domain objects into an in-memory SurrealDB session."""
    context = load_context or SurrealLoadContext(
        trait_defs=None,
        stacks_data=None,
        pillbox_stack_names=None,
        dashboards=None,
    )
    db = cast(SurrealSession, Surreal("mem://"))
    db.use("planner", "read_model")

    _load_substances(db, substances)
    _load_relations(db, relations, substances)
    _load_products(db, products)
    _load_stacks(db, context.stacks_data)
    _load_pillboxes(db, context.pillbox_stack_names)
    _load_dashboards(db, context.dashboards)
    return db


def _load_substances(db: SurrealSession, substances: dict[str, Substance]) -> None:
    for substance_id, substance in substances.items():
        db.create("substance", substance_record(substance_id, substance))


def _load_relations(
    db: SurrealSession,
    relations: list[Relation],
    substances: dict[str, Substance],
) -> None:
    for relation in relations:
        db.create("relation", relation_record(relation, substances))


def _load_products(db: SurrealSession, products: dict[str, Product] | None) -> None:
    if not products:
        return
    for product_id, product in products.items():
        db.create("product", product_record(product_id, product))


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
