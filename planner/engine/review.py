"""`review` and `review-substance` commands."""

from __future__ import annotations

import contextlib
import io as _io
import sys
import textwrap
from pathlib import Path
from typing import Any, cast

import yaml

from planner.cards.dashboards import build_dashboard_review
from planner.cards.product import format_product_name, load_product_registry
from planner.cards.relations import (
    load_global_relations,
    relation_endpoint_display,
    relation_endpoint_is_active,
)
from planner.cards.relations_surreal import (
    build_surreal_db,
    print_central_relation_matches_surreal,
)
from planner.cards.stacks import normalize_stack_entries
from planner.cards.substance import (
    format_substance_name,
    load_substance,
    load_substance_registry,
)
from planner.cards.traits import (
    NAMESPACE_ORDER,
    grouped_trait_defs,
    load_traits,
    print_trait_details,
)
from planner.contracts import CardLoadError, Product, Relation, Substance
from planner.engine._root_patch import maybe_patch_root
from planner.engine.results import ReviewResult
from planner.io import (
    DASHBOARDS_DIR,
    DATA_DIR,
    ROOT,
    STACKS_PATH,
    SUBSTANCES_DIR,
    display_path,
    load_yaml,
    strip_root_prefix,
    validate_schemas,
)

# --- cmd_review (full active-stack Reviewer output) ---

SEPARATOR = "─" * 41
_WRAP_WIDTH = 79
_INDENT = "    "

_HEADERS: dict[str, str] = {
    "safety": "Safety",
    "data_quality": "Data Quality",
    "model_gap": "Model Gaps",
}

_RELATION_STATUS_DESC: dict[str, str] = {
    "missing_source": "target present, source absent",
    "missing_target": "source present, target absent",
    "neither_active": "both absent",
}


def _build_active_substance_ids(
    stack_entries: dict[str, Any],
    products: dict[str, Product],
) -> set[str]:
    active: set[str] = set()
    for entry in stack_entries.values():
        if entry.get("stack") == "inactive":
            continue
        product_id = entry.get("product")
        if not isinstance(product_id, str):
            continue
        product = products.get(product_id)
        if product is None:
            continue
        for component in product.components:
            active.add(component.substance)
    return active


def _classify_relations(
    relations: list[Relation],
    substances: dict[str, Substance],
    active_substances: set[str],
) -> dict[str, list[dict[str, str]]]:
    by_status: dict[str, list[dict[str, str]]] = {
        "both_active": [],
        "missing_source": [],
        "missing_target": [],
        "neither_active": [],
    }
    for relation in relations:
        source_active = relation_endpoint_is_active(relation, "source", substances, active_substances)
        target_active = relation_endpoint_is_active(relation, "target", substances, active_substances)
        if source_active and target_active:
            status = "both_active"
        elif source_active:
            status = "missing_target"
        elif target_active:
            status = "missing_source"
        else:
            status = "neither_active"
        _, source_name = relation_endpoint_display(relation, "source", substances)
        _, target_name = relation_endpoint_display(relation, "target", substances)
        by_status[status].append({
            "type": relation.type,
            "source": source_name,
            "target": target_name,
            "reason": relation.reason,
        })
    return by_status


def _review_inner(data_root: Path | None) -> int:  # noqa: C901
    substances = load_substance_registry()
    products = load_product_registry()

    # Determine active/inactive substance IDs from stacks.
    active_substances: set[str] = set()
    inactive_substances: set[str] = set()
    stacks_data = load_yaml(STACKS_PATH) if STACKS_PATH.exists() else None
    if isinstance(stacks_data, dict):
        stack_entries = normalize_stack_entries(cast(dict[str, Any], stacks_data))
        active_substances = _build_active_substance_ids(stack_entries, products)
        # Inactive: substance is referenced by a product in the inactive stack entry.
        for entry in stack_entries.values():
            if entry.get("stack") != "inactive":
                continue
            product_id = entry.get("product")
            if not isinstance(product_id, str):
                continue
            product = products.get(product_id)
            if product is None:
                continue
            for component in product.components:
                inactive_substances.add(component.substance)

    # --- Concerns ---
    by_kind: dict[str, list[tuple[str, str]]] = {k: [] for k in _HEADERS}
    for substance in sorted(substances.values(), key=lambda s: s.name.casefold()):
        for concern in substance.concerns:
            by_kind[concern.kind].append((format_substance_name(substance), concern.text))
    for product in sorted(products.values(), key=lambda p: p.name.casefold()):
        for concern in product.concerns:
            by_kind[concern.kind].append((format_product_name(product), concern.text))

    any_output = False
    for kind, header in _HEADERS.items():
        entries = by_kind[kind]
        if not entries:
            continue
        if any_output:
            print()
        print(f"{header} ({len(entries)})")
        print(SEPARATOR)
        for name, text in entries:
            print(f"  {name}")
            wrapped = textwrap.fill(text, width=_WRAP_WIDTH, initial_indent=_INDENT, subsequent_indent=_INDENT)
            print(wrapped)
        any_output = True

    if not any_output:
        print("No concerns recorded.")

    # --- Relations ---
    global_relations = load_global_relations()
    relations_by_status = _classify_relations(global_relations, substances, active_substances)
    total_relations = sum(len(v) for v in relations_by_status.values())

    print()
    print(f"Relations ({total_relations})")
    print(SEPARATOR)
    if total_relations == 0:
        print("  No relations defined.")
    else:
        for status in ("both_active", "missing_source", "missing_target", "neither_active"):
            entries_r = relations_by_status[status]
            if not entries_r:
                continue
            desc = _RELATION_STATUS_DESC.get(status, "")
            suffix = f"  [{desc}]" if desc else ""
            print(f"\n  {status} ({len(entries_r)}){suffix}")
            for entry in sorted(entries_r, key=lambda e: (e["type"], e["source"].casefold())):
                line = f"[{entry['type']}] {entry['source']} -> {entry['target']}"
                if entry["reason"]:
                    line += f": {entry['reason']}"
                print(f"    {line}")

    # --- Risk flags ---
    risk_index: dict[str, list[str]] = {}
    for sid in sorted(active_substances):
        sub = substances.get(sid)
        if sub is None:
            continue
        for slug in sub.risk:
            risk_index.setdefault(slug, []).append(format_substance_name(sub))

    total_risk_carriers = sum(len(v) for v in risk_index.values())
    print()
    print(f"Risk flags ({total_risk_carriers})")
    print(SEPARATOR)
    if not risk_index:
        print("  No risk flags on active substances.")
    else:
        for slug in sorted(risk_index):
            names = risk_index[slug]
            print(f"  {slug} ({len(names)})")
            for name in names:
                print(f"    - {name}")

    # --- Pathway memberships ---
    pathway_index: dict[str, list[str]] = {}
    for sid in sorted(active_substances):
        sub = substances.get(sid)
        if sub is None:
            continue
        for slug in sub.pathway:
            pathway_index.setdefault(slug, []).append(format_substance_name(sub))

    total_pathway = sum(len(v) for v in pathway_index.values())
    print()
    print(f"Pathway memberships ({total_pathway})")
    print(SEPARATOR)
    if not pathway_index:
        print("  No pathway memberships on active substances.")
    else:
        for slug in sorted(pathway_index):
            names = pathway_index[slug]
            print(f"  {slug} ({len(names)})")
            for name in names:
                print(f"    - {name}")

    # --- Dashboard summary (reuses build_dashboard_review per 09-REVIEWS.md NICE-4) ---
    dashboard_files = sorted(DASHBOARDS_DIR.glob("*.yaml")) if DASHBOARDS_DIR.exists() else []
    review_data = build_dashboard_review(
        dashboard_files=dashboard_files,
        active_substances=active_substances,
        inactive_substances=inactive_substances,
        substances=substances,
    )
    # Merge benefits + risks by dashboard name into a single summary set.
    seen: dict[str, dict[str, Any]] = {}
    for entry in review_data["benefits"] + review_data["risks"]:
        seen.setdefault(entry["name"], entry)

    print()
    print(f"Dashboard summary ({len(seen)})")
    print(SEPARATOR)
    if not seen:
        print("  No dashboards with benefit or risk blocks found.")
        print("  (Dashboards lacking both benefit: and risk: blocks are excluded from this summary.)")
    else:
        for name, entry in sorted(seen.items(), key=lambda x: x[0].casefold()):
            covered: list[str] = list(entry.get("covered") or entry.get("active") or [])
            inactive_list: list[str] = list(entry.get("inactive") or [])
            missing_list: list[str] = list(entry.get("missing") or [])
            total = len(covered) + len(inactive_list) + len(missing_list)
            print(f"  {name}: {len(covered)}/{total} covered (inactive: {len(inactive_list)}, missing: {len(missing_list)})")

    return 0


def cmd_review(data_root: Path | None = None) -> ReviewResult:
    """Knowledge-section review of the active stack: concerns, relations, risk flags, pathways, dashboard summary."""
    if data_root is not None:
        stdout_buf = _io.StringIO()
        stderr_buf = _io.StringIO()
        with maybe_patch_root(data_root), \
             contextlib.redirect_stdout(stdout_buf), \
             contextlib.redirect_stderr(stderr_buf):
            exit_code = _review_inner(data_root)
        return ReviewResult(
            exit_code=exit_code,
            output=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
        )
    else:
        exit_code = _review_inner(None)
        return ReviewResult(exit_code=exit_code, output="", stderr="")


# --- cmd_review_substance (single-card trait checklist) ---


def cmd_review_substance(
    target: str, data_root: Path | None = None
) -> ReviewResult:
    """Show a grouped trait checklist for one substance card."""
    if data_root is not None:
        stdout_buf = _io.StringIO()
        stderr_buf = _io.StringIO()
        with maybe_patch_root(data_root), \
             contextlib.redirect_stdout(stdout_buf), \
             contextlib.redirect_stderr(stderr_buf):
            exit_code = _review_substance_inner(target)
        return ReviewResult(
            exit_code=exit_code,
            output=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
        )
    else:
        exit_code = _review_substance_inner(target)
        return ReviewResult(exit_code=exit_code, output="", stderr="")


def _review_substance_inner(target: str) -> int:
    path = Path(target)
    if not path.is_absolute():
        path = ROOT / path

    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        print(f"{display_path(path)}: file not found", file=sys.stderr)
        return 1

    substances_root = SUBSTANCES_DIR.resolve()
    try:
        resolved.relative_to(substances_root)
    except ValueError:
        print(
            f"{display_path(path)}: review-substance only accepts paths "
            f"inside {display_path(SUBSTANCES_DIR)}/",
            file=sys.stderr,
        )
        return 1

    if resolved.suffix != ".yaml":
        print(
            f"{display_path(path)}: review-substance only accepts .yaml files",
            file=sys.stderr,
        )
        return 1

    schema_result = validate_schemas()
    if schema_result != 0:
        return schema_result

    path = resolved
    try:
        substance = load_substance(path)
    except CardLoadError as e:
        print(strip_root_prefix(e.message), file=sys.stderr)
        return 1

    try:
        trait_defs = load_traits(DATA_DIR / "traits.yaml")
    except CardLoadError as e:
        print(strip_root_prefix(e.message), file=sys.stderr)
        return 1
    if not trait_defs:
        print("data/traits.yaml: no traits found", file=sys.stderr)
        return 1

    # Build namespace -> substance slugs map; derive flat set for marker lookups.
    ns_to_substance_slugs: dict[str, set[str]] = {}
    for field, ns in [
        ("intake", "intake"),
        ("timing", "timing"),
        ("activity", "activity"),
        ("is_", "is"),
        ("effect", "effect"),
        ("risk", "risk"),
        ("context", "context"),
        ("pathway", "pathway"),
    ]:
        ns_to_substance_slugs[ns] = set(getattr(substance, field))
    current_traits: set[str] = {
        f"{ns}:{slug}"
        for ns, slugs in ns_to_substance_slugs.items()
        for slug in slugs
    }

    print(f"Substance review: {format_substance_name(substance)}")
    print(f"File: {display_path(path)}")
    if substance.id:
        print(f"ID: {substance.id}")
    if substance.aliases:
        print("Aliases: " + ", ".join(substance.aliases))
    review_substances = load_substance_registry()
    review_db = build_surreal_db(review_substances, load_global_relations())
    print_central_relation_matches_surreal(review_db, substance.id, substance.name)
    print()
    print("Before editing traits, scan this checklist and mark only source-backed facts.")
    print("If a fact matters but no trait fits, add it to concerns with the appropriate kind.")
    print("Put substance-to-substance relations in data/relations.yaml, not in this card.")
    print()
    print("Traits")

    ns_to_registered = grouped_trait_defs(trait_defs)

    # Iterate all 6 namespaces in stable order; show heading even when empty.
    all_namespaces: list[str] = list(NAMESPACE_ORDER)
    for extra_ns in sorted(ns for ns in ns_to_registered if ns not in NAMESPACE_ORDER):
        all_namespaces.append(extra_ns)

    for namespace in all_namespaces:
        substance_slugs = ns_to_substance_slugs.get(namespace, set())
        print(f"\n{namespace}")

        # context: namespace — labels come from dashboard YAML files, not traits.yaml.
        if namespace == "context":
            if not substance_slugs:
                print("  (empty)")
            else:
                for slug in sorted(substance_slugs, key=str.casefold):
                    yaml_path = DASHBOARDS_DIR / f"{slug}.yaml"
                    if yaml_path.exists():
                        data = yaml.safe_load(yaml_path.read_text())
                        name = data.get("name", slug)
                        print(f"  [x] {slug} - {name}")
                        desc = data.get("description", "")
                        if desc:
                            print(f"      {desc}")
                    else:
                        print(f"  [x] {slug}  (no dashboard yaml — run planner check)")
            continue

        registered_traits = ns_to_registered.get(namespace, [])
        registered_short_names = {t.short_name for t in registered_traits}

        # Determine if the namespace has any content to show.
        unknown_slugs = sorted(
            (slug for slug in substance_slugs if slug not in registered_short_names),
            key=str.casefold,
        )
        has_content = registered_traits or unknown_slugs

        if not has_content:
            print("  (empty)")
            continue

        for trait in registered_traits:
            marker = "x" if trait.id in current_traits else " "
            label_text = f" - {trait.label}" if trait.label else ""
            print(f"  [{marker}] {trait.short_name}{label_text}")
            print_trait_details(trait)

        if unknown_slugs:
            print("  unknown")
            for slug in unknown_slugs:
                print(f"    [x] {namespace}:{slug}  (not registered in traits.yaml)")

    print("\nConcerns")
    if substance.concerns:
        for concern in substance.concerns:
            print(f"  [{concern.kind}] {concern.text}")
    else:
        print("  none")

    return 0
