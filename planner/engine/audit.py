"""`audit` command: reference diagnostics and optional deep card-quality checks.

Concerns, relations status, risk flags, and pathways have moved to `planner review`
(cmd_review in planner/engine/review.py) as of Phase 9.
"""

from __future__ import annotations

from pathlib import Path

from planner.cards.product import load_product_registry
from planner.cards.relations import load_global_relations
from planner.cards.substance import load_substance_registry
from planner.cards.traits import load_scheduling_policies
from planner.engine.results import AuditResult
from planner.paths import Paths
from planner.query_model import (
    build_stack_read_model,
    dashboards_for_read_model,
    pillbox_stack_names,
    stacks_for_read_model,
)
from planner.query_model.surreal import SurrealLoadContext
from planner.schema_validation import validate_schemas

SEPARATOR = "─" * 41

_CLEANUP_HEADERS: dict[str, str] = {
    "substances.knowledge_only": "Knowledge-only substance cards (valid, unlinked)",
    "products.without_stack": "Tracked-unassigned products (reference/depleted/candidate)",
    "traits.unused": "Unused review traits",
    "context.without_dashboard_selector": "Context tags without dashboard selector",
    "stacks.empty": "Empty stacks",
    "stacks.without_pillboxes": "Stacks without pillboxes",
    "pillboxes.without_stack": "Pillboxes without stack",
    "substances.similar_names": "Potential duplicate substance cards",
    "dashboard.empty_cluster": "Dashboards resolving to zero members",
    "effects.context_without_consumer": "Context effects without dashboard/relation consumer",
    "effects.overlap_review": "Effect overlap review hints",
    "relations.broad_trait_endpoint": "Broad relation trait endpoints",
}


_FULL_AUDIT_HEADERS: dict[str, str] = {
    "full.active_product_source": "Active product source/identity gaps",
    "full.no_form_unreferenced": ("Generic no-form cards — no product reference, form-specific cards exist"),
    "full.no_form_used": ("Products using generic no-form cards while form-specific cards exist"),
    "full.no_classification": "Missing is: classification",
    "full.no_intake": "Product component substances missing intake: trait",
    "full.intake_review": "Intake review candidates — is: suggests an intake trait worth verifying",
    "full.relations_integrity": "Relations integrity errors — unknown names or IDs in relations.yaml",
}

_REFERENCE_REVIEW_KEYS = frozenset({
    "substances.knowledge_only",
    "products.without_stack",
    "substances.similar_names",
    "effects.overlap_review",
})


def cmd_audit(data_root: Path | None = None, full: bool = False) -> AuditResult:
    """Show knowledge-base diagnostics and card-quality checks.

    Knowledge-only substance cards are valid substance cards that are not currently
    referenced by products or relations; they are not deletion recommendations.

    With --full also runs deep card-quality checks (no-form variants, missing
    classifications, intake review, relations integrity). Concerns, relations
    status, risk flags, and pathways now live in `planner review`.
    """
    paths = Paths.from_root(data_root) if data_root is not None else Paths.default()
    schema_result = validate_schemas(paths)
    if schema_result != 0:
        return AuditResult(
            exit_code=schema_result,
            cleanup={},
            full={},
        )
    substances = load_substance_registry(paths)
    products = load_product_registry(paths)
    global_relations = load_global_relations(paths)

    # --- Audit diagnostics ---
    read_model = build_stack_read_model(
        substances,
        global_relations,
        products,
        context=SurrealLoadContext(
            policies=load_scheduling_policies(),
            stacks_data=stacks_for_read_model(paths),
            pillbox_stack_names=pillbox_stack_names(paths),
            dashboards=dashboards_for_read_model(paths),
        ),
    )
    cleanup = read_model.cleanup_sections(substances)
    actionable_total = sum(len(items) for key, items in cleanup.items() if key not in _REFERENCE_REVIEW_KEYS)
    review_total = sum(len(items) for key, items in cleanup.items() if key in _REFERENCE_REVIEW_KEYS)

    print(f"Audit diagnostics ({actionable_total} actionable, {review_total} reference/review)")
    print(SEPARATOR)
    for key, header in _CLEANUP_HEADERS.items():
        items = cleanup.get(key, [])
        print(f"\n  {header} ({len(items)})")
        for item in items:
            print(f"    - {item}")

    # --- Full audit (--full only) ---
    full_sections: dict[str, list[str]] = {}
    if full:
        full_sections = read_model.full_audit_sections(substances, products)
        total_full = sum(len(v) for v in full_sections.values())
        print()
        print(f"Full audit ({total_full})")
        print(SEPARATOR)
        for key, header in _FULL_AUDIT_HEADERS.items():
            items_f = full_sections.get(key, [])
            print(f"\n  {header} ({len(items_f)})")
            for item in items_f:
                print(f"    - {item}")

    return AuditResult(
        exit_code=0,
        cleanup=cleanup,
        full=full_sections,
    )
