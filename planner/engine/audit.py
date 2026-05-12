"""`audit` command: show all concerns from every substance and product card, grouped by kind."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, cast

from planner.cards.product import format_product_name, load_product_registry
from planner.cards.relations import (
    load_global_relations,
    relation_endpoint_display,
    relation_endpoint_is_active,
)
from planner.cards.stacks import normalize_stack_entries
from planner.cards.substance import format_substance_name, load_substance_registry
from planner.contracts import Product, Relation, Substance
from planner.engine._root_patch import maybe_patch_root
from planner.engine.results import AuditResult
from planner.io import STACKS_PATH, load_yaml

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


def cmd_audit(data_root: Path | None = None) -> AuditResult:
    """Show all concerns grouped by kind; returns exit_code 0 always."""
    with maybe_patch_root(data_root):
        substances = load_substance_registry()
        products = load_product_registry()

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

        # Relations section
        global_relations = load_global_relations()
        active_substances: set[str] = set()
        stacks_data = load_yaml(STACKS_PATH) if STACKS_PATH.exists() else None
        if isinstance(stacks_data, dict):
            stack_entries = normalize_stack_entries(cast(dict[str, Any], stacks_data))
            active_substances = _build_active_substance_ids(stack_entries, products)

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

        return AuditResult(exit_code=0, by_kind=by_kind, relations_by_status=relations_by_status)
