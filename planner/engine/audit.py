"""`audit` command: cleanup candidates and optional deep card-quality checks.

Concerns, relations status, risk flags, and pathways have moved to `planner review`
(cmd_review in planner/engine/review.py) as of Phase 9.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, cast

from planner.cards.dashboards import (
    collect_dashboard_substance_refs,
    from_traits_pairs,
    load_dashboard,
    substance_carries,
)
from planner.cards.product import (
    load_product_registry,
)
from planner.cards.relations import (
    global_relation_refs,
    load_global_relations,
)
from planner.cards.stacks import normalize_stack_entries
from planner.cards.substance import (
    collect_similar_substances,
    format_substance_name,
    load_substance_registry,
)
from planner.cards.traits import load_traits
from planner.contracts import CardLoadError, Relation, Substance
from planner.engine._root_patch import maybe_patch_root
from planner.engine.results import AuditResult
from planner.io import DASHBOARDS_DIR, DATA_DIR, STACKS_PATH, load_yaml

SEPARATOR = "─" * 41

_CLEANUP_HEADERS: dict[str, str] = {
    "substances.unused": "Substances unused",
    "products.without_stack": "Products without stack entry",
    "traits.unused": "Traits unused",
    "stacks.empty": "Empty stacks",
    "stacks.without_pillboxes": "Stacks without pillboxes",
    "pillboxes.without_stack": "Pillboxes without stack",
    "substances.similar_names": "Similar substance names",
    "dashboard.empty_cluster": "Dashboards resolving to zero members",
}


def _collect_cleanup_sections(
    substances: dict[str, Substance],
    products: dict[str, Any],
) -> dict[str, list[str]]:
    dashboard_files = sorted(DASHBOARDS_DIR.glob("*.yaml")) if DASHBOARDS_DIR.exists() else []

    product_substance_refs: set[str] = set()
    for product in products.values():
        for component in product.components:
            product_substance_refs.add(component.substance)

    prefer_with_refs: set[str] = set()
    relation_refs: set[str] = set()
    trait_refs: set[str] = set()
    for substance_id, substance in substances.items():
        if substance.prefer_with:
            prefer_with_refs.add(substance_id)
        for target_id in substance.prefer_with:
            prefer_with_refs.add(target_id)
        for field_name, ns in [
            ("intake", "intake"),
            ("timing", "timing"),
            ("activity", "activity"),
            ("is_", "is"),
            ("effect", "effect"),
            ("risk", "risk"),
            ("dashboard", "dashboard"),
            ("pathway", "pathway"),
        ]:
            for slug in getattr(substance, field_name):
                trait_refs.add(f"{ns}:{slug}")
    relation_refs.update(global_relation_refs(substances, load_global_relations()))

    trait_defs = load_traits(DATA_DIR / "traits.yaml")
    # separate_from removed from TraitDef in Phase 9 (plan 09-04); no trait refs to collect here.

    stacks_data = load_yaml(STACKS_PATH)
    stack_entries = (
        normalize_stack_entries(cast(dict[str, Any], stacks_data))
        if isinstance(stacks_data, dict)
        else {}
    )
    stack_products = {
        cast(str, entry.get("product"))
        for entry in stack_entries.values()
        if isinstance(entry.get("product"), str)
    }
    stacks_by_name: dict[str, Any] = cast(dict[str, Any], stacks_data) if isinstance(stacks_data, dict) else {}

    slots_data = load_yaml(DATA_DIR / "pillboxes.yaml")
    slots_dict = cast(dict[str, Any], slots_data) if isinstance(slots_data, dict) else {}
    pillbox_stacks: set[str] = set(slots_dict.keys()) if slots_dict else set()

    substance_refs = (
        product_substance_refs
        | collect_dashboard_substance_refs(dashboard_files)
        | prefer_with_refs
        | relation_refs
    )
    unused_substances = sorted(set(substances) - substance_refs)
    products_without_stack = sorted(set(products) - stack_products)
    unused_traits = sorted(set(trait_defs) - trait_refs)
    empty_stacks = sorted(
        stack
        for stack, items in stacks_by_name.items()
        if isinstance(items, list) and not items
    )
    stacks_without_pillboxes = sorted(set(stacks_by_name) - pillbox_stacks - {"inactive"})
    pillboxes_without_stack = sorted(pillbox_stacks - set(stacks_by_name))

    empty_cluster_messages: list[str] = []
    for dashboard_file in dashboard_files:
        try:
            dashboard = load_dashboard(dashboard_file)
        except CardLoadError:
            continue
        pairs = list(from_traits_pairs(dashboard.from_traits))
        member_count = (
            sum(1 for s in substances.values() if any(substance_carries(s, ns, slug) for ns, slug in pairs))
            if pairs else 0
        )
        if member_count == 0:
            slug = dashboard_file.stem
            empty_cluster_messages.append(
                f"Empty cluster: data/dashboards/{slug}.yaml from_traits resolves to "
                f"zero member substances (using union resolution: OR across all listed "
                f"(namespace, slug) pairs). Resolution: update from_traits to match "
                f"substance traits, OR remove the dashboard yaml if abandoned."
            )

    return {
        "substances.unused": unused_substances,
        "products.without_stack": products_without_stack,
        "traits.unused": unused_traits,
        "stacks.empty": empty_stacks,
        "stacks.without_pillboxes": stacks_without_pillboxes,
        "pillboxes.without_stack": pillboxes_without_stack,
        "substances.similar_names": collect_similar_substances(substances),
        "dashboard.empty_cluster": empty_cluster_messages,
    }


_FULL_AUDIT_HEADERS: dict[str, str] = {
    "full.stubs_orphan": "Orphan stubs — no form, not referenced in any product",
    "full.stubs_used": "Used stubs — no form but referenced in products (intentional catch-all?)",
    "full.no_classification": "Missing is: classification",
    "full.no_intake": "Missing intake: trait",
    "full.intake_review": "Intake review candidates — is: suggests an intake trait worth verifying",
    "full.relations_integrity": "Relations integrity errors — unknown names or IDs in relations.yaml",
}

# Correlations from traits.yaml applies_when. NOT hard rules — a card that
# doesn't satisfy these is a prompt for human review, not a guaranteed bug.
_INTAKE_REVIEW_HINTS: dict[str, set[str]] = {
    "mineral": {"food_preferred", "food_required"},
    "fat_soluble": {"fat_meal_required", "food_required"},
    "enzyme": {"empty_preferred"},
}


def _collect_full_audit_sections(
    substances: dict[str, Substance],
    products: dict[str, Any],
    relations: list[Relation],
) -> dict[str, list[str]]:
    product_substance_refs: set[str] = set()
    for product in products.values():
        for component in product.components:
            product_substance_refs.add(component.substance)

    by_name: dict[str, list[tuple[str, Substance]]] = defaultdict(list)
    for sid, sub in substances.items():
        by_name[sub.name.strip()].append((sid, sub))

    stubs_orphan: list[str] = []
    stubs_used: list[str] = []
    for name, entries in sorted(by_name.items()):
        no_form = [(sid, s) for sid, s in entries if not s.form]
        with_form = [(sid, s) for sid, s in entries if s.form]
        if no_form and with_form:
            form_list = ", ".join(sorted(str(s.form) for _, s in with_form))
            for sid, _ in no_form:
                line = f"{name} ({sid}) — forms: {form_list}"
                (stubs_used if sid in product_substance_refs else stubs_orphan).append(line)

    missing_classification: list[str] = []
    missing_intake: list[str] = []
    intake_review: list[str] = []

    for sid, sub in sorted(substances.items(), key=lambda x: x[1].name.casefold()):
        display = format_substance_name(sub)
        is_set = set(sub.is_)
        intake_set = set(sub.intake)

        if not is_set:
            missing_classification.append(f"{display} ({sid})")
        if not intake_set:
            missing_intake.append(f"{display} ({sid})")
        else:
            for is_slug, acceptable in _INTAKE_REVIEW_HINTS.items():
                if is_slug in is_set and not (intake_set & acceptable):
                    intake_review.append(
                        f"{display} ({sid}): is:{is_slug}, "
                        f"intake:{sorted(intake_set)} — none of {sorted(acceptable)}"
                    )

    name_set = {s.name for s in substances.values()}
    id_set = set(substances.keys())
    relation_errors: list[str] = []
    for rel in relations:
        if rel.source_name and rel.source_name not in name_set:
            relation_errors.append(f"unknown source_name '{rel.source_name}' in {rel.type}")
        if rel.target_name and rel.target_name not in name_set:
            relation_errors.append(f"unknown target_name '{rel.target_name}' in {rel.type}")
        if rel.source_substance and rel.source_substance not in id_set:
            relation_errors.append(f"unknown source_substance '{rel.source_substance}' in {rel.type}")
        if rel.target_substance and rel.target_substance not in id_set:
            relation_errors.append(f"unknown target_substance '{rel.target_substance}' in {rel.type}")

    return {
        "full.stubs_orphan": stubs_orphan,
        "full.stubs_used": stubs_used,
        "full.no_classification": missing_classification,
        "full.no_intake": missing_intake,
        "full.intake_review": intake_review,
        "full.relations_integrity": relation_errors,
    }


def cmd_audit(data_root: Path | None = None, full: bool = False) -> AuditResult:
    """Show cleanup candidates (unused substances/products/traits, similar names, empty dashboards).

    With --full also runs deep card-quality checks (stub detection, missing
    classifications, intake review, relations integrity). Concerns, relations
    status, risk flags, and pathways now live in `planner review`.
    """
    with maybe_patch_root(data_root):
        substances = load_substance_registry()
        products = load_product_registry()
        global_relations = load_global_relations()

        # --- Cleanup candidates ---
        cleanup = _collect_cleanup_sections(substances, products)
        total_issues = sum(len(v) for v in cleanup.values())

        print(f"Cleanup candidates ({total_issues})")
        print(SEPARATOR)
        for key, header in _CLEANUP_HEADERS.items():
            items = cleanup.get(key, [])
            print(f"\n  {header} ({len(items)})")
            for item in items:
                print(f"    - {item}")

        # --- Full audit (--full only) ---
        full_sections: dict[str, list[str]] = {}
        if full:
            full_sections = _collect_full_audit_sections(
                substances, products, global_relations
            )
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
