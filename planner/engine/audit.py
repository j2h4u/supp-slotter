"""`audit` command: show all concerns from every substance and product card, grouped by kind."""

from __future__ import annotations

import textwrap

from planner.cards.product import format_product_name, load_product_registry
from planner.cards.substance import format_substance_name, load_substance_registry

SEPARATOR = "─" * 41
_WRAP_WIDTH = 79
_INDENT = "    "

_HEADERS: dict[str, str] = {
    "safety": "Safety",
    "data_quality": "Data Quality",
    "model_gap": "Model Gaps",
}


def cmd_audit() -> int:
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

    return 0
