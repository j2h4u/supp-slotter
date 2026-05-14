"""Fact-first active-stack review index."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from planner.cards.dashboards import load_dashboard
from planner.cards.product import format_product_name
from planner.contracts import CardLoadError, Product, Substance, TraitDef

KNOWLEDGE_NAMESPACE_ORDER = ("risk", "pathway", "effect", "context")


def _title_from_slug(slug: str) -> str:
    return slug.replace("_", " ").title()


def _context_labels(dashboard_files: list[Path]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for dashboard_file in dashboard_files:
        try:
            dashboard = load_dashboard(dashboard_file)
        except CardLoadError as e:
            print(f"warning: skipping dashboard card: {e.message}", file=sys.stderr)
            continue
        labels[dashboard_file.stem] = dashboard.name
    return labels


def _fact_label(
    namespace: str,
    slug: str,
    trait_defs: dict[str, TraitDef],
    context_labels: dict[str, str],
) -> str:
    trait_def = trait_defs.get(f"{namespace}:{slug}")
    if trait_def is not None:
        return trait_def.label
    if namespace == "context":
        return context_labels.get(slug, _title_from_slug(slug))
    return _title_from_slug(slug)


def _substance_facts(substance: Substance) -> list[tuple[str, str]]:
    facts: list[tuple[str, str]] = []
    for namespace, slugs in (
        ("risk", substance.risk),
        ("pathway", substance.pathway),
        ("effect", substance.effect),
        ("context", substance.context),
    ):
        for slug in slugs:
            facts.append((namespace, slug))
    return facts


def build_active_fact_index(
    *,
    item_id_sequence: list[str],
    item_products: dict[str, str],
    products: dict[str, Product],
    substances: dict[str, Substance],
    trait_defs: dict[str, TraitDef],
    dashboard_files: list[Path],
) -> list[dict[str, Any]]:
    """Build an inverted index of active knowledge facts to products/components.

    This is intentionally not a rules engine. It does not infer roles, importance,
    replacement candidates, or reviewer questions. It only projects existing
    substance knowledge facts into a compact product-readable active-stack index.
    """
    context_labels = _context_labels(dashboard_files)
    facts: dict[tuple[str, str], dict[str, str]] = {}

    for item_id in item_id_sequence:
        product_id = item_products[item_id]
        product = products.get(product_id)
        if product is None:
            continue
        product_name = format_product_name(product)

        for component in product.components:
            substance = substances.get(component.substance)
            if substance is None:
                continue
            for namespace, slug in _substance_facts(substance):
                facts.setdefault((namespace, slug), {})[product_id] = product_name

    namespace_rank = {
        namespace: index for index, namespace in enumerate(KNOWLEDGE_NAMESPACE_ORDER)
    }
    index: list[dict[str, Any]] = []
    for namespace, slug in sorted(
        facts,
        key=lambda key: (
            namespace_rank.get(key[0], len(namespace_rank)),
            _fact_label(key[0], key[1], trait_defs, context_labels).casefold(),
            key[1],
        ),
    ):
        product_entries = sorted(
            facts[(namespace, slug)].values(),
            key=str.casefold,
        )
        index.append(
            {
                "namespace": namespace,
                "fact": slug,
                "label": _fact_label(namespace, slug, trait_defs, context_labels),
                "product_count": len(product_entries),
                "products": product_entries,
            }
        )
    return index
