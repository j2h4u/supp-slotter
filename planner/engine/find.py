"""`find` command: fuzzy multi-word search over product/substance cards."""

from __future__ import annotations

import sys
from pathlib import Path

from planner.cards import (
    find_product_results,
    find_substance_results,
    format_find_result,
)
from planner.io import validate_schemas
from planner.maintenance import run_auto_maintenance


def print_find_section(
    title: str,
    results: list[tuple[float, str, str, Path]],
    limit: int,
) -> None:
    print(f"\n{title}")
    if not results:
        print("  none")
        return
    for score, card_id, label, path in results[:limit]:
        print(format_find_result(score, card_id, label, path))

def cmd_find(query_parts: list[str], limit: int) -> int:
    query = " ".join(part.strip() for part in query_parts if part.strip())
    if not query:
        print("find: query must not be empty", file=sys.stderr)
        return 1

    schema_result = validate_schemas()
    if schema_result != 0:
        return schema_result

    maintenance_result = run_auto_maintenance(quiet=True)
    if maintenance_result != 0:
        return maintenance_result

    print(f"Search results for: {query}")
    print_find_section("Substances", find_substance_results(query), limit)
    print_find_section("Products", find_product_results(query), limit)
    return 0

