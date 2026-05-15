"""`audit` command: reference diagnostics and optional deep card-quality checks.

Concerns, relations status, risk flags, and pathways have moved to `planner review`
(cmd_review in planner/engine/review.py) as of Phase 9.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from planner.cards.dashboards import (
    load_dashboard,
)
from planner.cards.product import (
    load_product_registry,
)
from planner.cards.relations import (
    load_global_relations,
)
from planner.cards.relations_surreal import build_surreal_db
from planner.cards.substance import (
    load_substance_registry,
)
from planner.cards.traits import load_traits
from planner.contracts import Dashboard
from planner.engine._root_patch import maybe_patch_root
from planner.engine.audit_surreal import collect_cleanup_sections, collect_full_audit_sections
from planner.engine.results import AuditResult
from planner.io import DASHBOARDS_DIR, DATA_DIR, STACKS_PATH, load_yaml_mapping

SEPARATOR = "─" * 41


def _stacks_for_surreal() -> dict[str, list[str]]:
    raw = load_yaml_mapping(STACKS_PATH)
    out: dict[str, list[str]] = {}
    for name, items in raw.items():
        if isinstance(items, list):
            items_list = cast("list[Any]", items)
            out[name] = [item for item in items_list if isinstance(item, str)]
    return out


def _pillbox_stack_names() -> set[str]:
    raw = load_yaml_mapping(DATA_DIR / "pillboxes.yaml")
    return set(raw.keys())


def _dashboards_for_surreal() -> dict[str, Dashboard]:
    return {p.stem: load_dashboard(p) for p in sorted(DASHBOARDS_DIR.glob("*.yaml"))}

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
    with maybe_patch_root(data_root):
        substances = load_substance_registry()
        products = load_product_registry()
        global_relations = load_global_relations()

        # --- Audit diagnostics ---
        db = build_surreal_db(
            substances,
            global_relations,
            products,
            trait_defs=load_traits(DATA_DIR / "traits.yaml"),
            stacks_data=_stacks_for_surreal(),
            pillbox_stack_names=_pillbox_stack_names(),
            dashboards=_dashboards_for_surreal(),
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
