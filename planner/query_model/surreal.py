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

    for sid, substance in substances.items():
        db.create("substance", substance_record(sid, substance))

    for relation in relations:
        db.create("relation", relation_record(relation, substances, trait_defs))

    if products:
        for pid, product in products.items():
            db.create("product", product_record(pid, product))

    if trait_defs:
        for trait_id, trait in trait_defs.items():
            db.create("trait", trait_record(trait_id, trait))

    if stacks_data:
        for stack_name, product_ids in stacks_data.items():
            db.create("stack", {"name": stack_name, "products": list(product_ids)})

    if pillbox_stack_names:
        for stack_name in pillbox_stack_names:
            db.create("pillbox", {"stack_name": stack_name})

    if dashboards:
        for slug, dashboard in dashboards.items():
            db.create("dashboard", dashboard_record(slug, dashboard))

    return db
