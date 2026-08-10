"""`audit` command: reference diagnostics and optional deep card-quality checks.

Concerns, relation status, and fact memberships have moved to `planner review`
(cmd_review in planner/engine/review.py) as of Phase 9.
"""

from __future__ import annotations

import sys
from pathlib import Path

from planner.cards.product import load_product_registry
from planner.cards.relations import load_global_relations
from planner.cards.substance import load_substance_registry
from planner.contracts import CardLoadError
from planner.engine.results import AuditResult
from planner.ontology.artifacts import load_ontology
from planner.ontology.policies import load_scheduling_constraints, load_scheduling_policies
from planner.paths import ROOT, Paths
from planner.query_model import (
    build_stack_read_model,
    dashboards_for_read_model,
    pillbox_stack_names,
    stacks_for_read_model,
)
from planner.query_model.surreal import SurrealLoadContext
from planner.schema_validation import validate_schemas

SEPARATOR = "─" * 41


def cmd_audit(data_root: Path | None = None, full: bool = False) -> AuditResult:
    """Show knowledge-base diagnostics and card-quality checks.

    Knowledge-only substance cards are valid substance cards that are not currently
    referenced by products or relations; they are not deletion recommendations.

    With --full also runs generic source and selector assertions. Concerns,
    relation status and fact memberships now live in `planner review`.
    """
    paths = Paths.from_root(data_root) if data_root is not None else Paths.default()
    bundle = load_ontology(ROOT / "ontology")
    schema_result = validate_schemas(paths, bundle)
    if schema_result != 0:
        return AuditResult(
            exit_code=schema_result,
            cleanup={},
            full={},
        )
    substances = load_substance_registry(paths, bundle)
    products = load_product_registry(paths, bundle)
    try:
        global_relations = load_global_relations(paths, bundle, substances)
    except CardLoadError as error:
        print(f"audit: {error.message}", file=sys.stderr)
        return AuditResult(exit_code=1, cleanup={}, full={})
    # --- Audit diagnostics ---
    read_model = build_stack_read_model(
        substances,
        global_relations,
        products,
        context=SurrealLoadContext(
            policies=load_scheduling_policies(bundle),
            stacks_data=stacks_for_read_model(paths),
            pillbox_stack_names=pillbox_stack_names(paths),
            dashboards=dashboards_for_read_model(paths, bundle),
            # Planner/read-model contexts stay on active constraints by default;
            # the deep audit is the one diagnostic surface that intentionally
            # projects retired provenance as well.
            scheduling_constraints=load_scheduling_constraints(bundle),
        ),
        ontology_bundle=bundle,
    )
    cleanup = read_model.cleanup_sections(substances)
    cleanup_items = _flatten_audit_sections(cleanup)
    print(f"Audit diagnostics ({len(cleanup_items)})")
    print(SEPARATOR)
    for item in cleanup_items:
        print(f"  - {item}")

    # --- Full audit (--full only) ---
    full_sections: dict[str, list[str]] = {}
    if full:
        full_sections = read_model.full_audit_sections(substances, products)
        full_items = _flatten_audit_sections(full_sections)
        print()
        print(f"Full audit ({len(full_items)})")
        print(SEPARATOR)
        for item in full_items:
            print(f"  - {item}")

    return AuditResult(
        exit_code=0,
        cleanup={"diagnostics": cleanup_items},
        full={"diagnostics": _flatten_audit_sections(full_sections)} if full else {},
    )


def _flatten_audit_sections(sections: dict[str, list[str]]) -> list[str]:
    """Keep audit data generic; section names are not an executable contract."""
    return [item for items in sections.values() for item in items]
