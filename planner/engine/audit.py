"""`audit` command: reference diagnostics and optional deep card-quality checks.

Concerns, relations status, risk flags, and pathways have moved to `planner review`
(cmd_review in planner/engine/review.py) as of Phase 9.
"""

from __future__ import annotations

from pathlib import Path

from planner.cards.product import load_product_registry
from planner.cards.relations import load_global_relations
from planner.cards.relations_surreal import (
    build_surreal_db,
    dashboards_for_surreal,
    pillbox_stack_names,
    stacks_for_surreal,
)
from planner.cards.substance import load_substance_registry
from planner.cards.traits import load_traits
from planner.engine.audit_surreal import collect_cleanup_sections, collect_full_audit_sections
from planner.engine.results import AuditResult
from planner.io import Paths

SEPARATOR = "─" * 41

_CLEANUP_HEADERS: dict[str, str] = {
    "substances.reference_only": "Reference-only substances",
    "products.without_stack": "Products without stack entry",
    "traits.unused": "Traits unused",
    "stacks.empty": "Empty stacks",
    "stacks.without_pillboxes": "Stacks without pillboxes",
    "pillboxes.without_stack": "Pillboxes without stack",
    "substances.similar_names": "Similar substance names",
    "dashboard.empty_cluster": "Dashboards resolving to zero members",
}


_FULL_AUDIT_HEADERS: dict[str, str] = {
    "full.stubs_orphan": "Orphan stubs — no form, not referenced in any product",
    "full.stubs_used": "Used stubs — no form but referenced in products (intentional catch-all?)",
    "full.no_classification": "Missing is: classification",
    "full.no_intake": "Missing intake: trait",
    "full.intake_review": "Intake review candidates — is: suggests an intake trait worth verifying",
    "full.relations_integrity": "Relations integrity errors — unknown names or IDs in relations.yaml",
}

def cmd_audit(data_root: Path | None = None, full: bool = False) -> AuditResult:
    """Show knowledge-base diagnostics and cleanup candidates.

    Reference-only substances are valid knowledge-base cards that are not currently
    referenced by products or relations; they are not deletion recommendations.

    With --full also runs deep card-quality checks (stub detection, missing
    classifications, intake review, relations integrity). Concerns, relations
    status, risk flags, and pathways now live in `planner review`.
    """
    paths = Paths.from_root(data_root) if data_root is not None else Paths.default()
    substances = load_substance_registry(paths)
    products = load_product_registry(paths)
    global_relations = load_global_relations(paths)

    # --- Audit diagnostics ---
    db = build_surreal_db(
        substances,
        global_relations,
        products,
        trait_defs=load_traits(paths.data / "traits.yaml"),
        stacks_data=stacks_for_surreal(paths),
        pillbox_stack_names=pillbox_stack_names(paths),
        dashboards=dashboards_for_surreal(paths),
    )
    cleanup = collect_cleanup_sections(db, substances)
    total_issues = sum(len(v) for v in cleanup.values())

    print(f"Audit diagnostics ({total_issues})")
    print(SEPARATOR)
    for key, header in _CLEANUP_HEADERS.items():
        items = cleanup.get(key, [])
        print(f"\n  {header} ({len(items)})")
        for item in items:
            print(f"    - {item}")

    # --- Full audit (--full only) ---
    full_sections: dict[str, list[str]] = {}
    if full:
        full_sections = collect_full_audit_sections(db, substances)
        total_full = sum(len(v) for v in full_sections.values())
        print()
        print(f"Full audit ({total_full})")
        print(SEPARATOR)
        for key, header in _FULL_AUDIT_HEADERS.items():
            items_f = full_sections.get(key, [])
            print(f"\n  {header} ({len(items_f)})")
            for item in items_f:
                print(f"    - {item}")

    # concerns + relations moved to cmd_review in Phase 9; kept as empty dicts for ResultShape backward compat.
    return AuditResult(
        exit_code=0,
        by_kind={},
        relations_by_status={},
        cleanup=cleanup,
        full=full_sections,
    )
