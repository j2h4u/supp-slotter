"""`find` command: fuzzy multi-word search over product/substance cards."""

from __future__ import annotations

import sys
from pathlib import Path

from planner.cards.product import find_product_results
from planner.cards.search import format_find_result
from planner.cards.substance import find_substance_results
from planner.engine._root_patch import maybe_patch_root
from planner.engine.results import FindResult
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


def cmd_find(
    query_parts: list[str], limit: int = 8, data_root: Path | None = None
) -> FindResult:
    """Run auto-maintenance and schema validation before fuzzy-searching cards, so results reflect the normalised state."""
    query = " ".join(part.strip() for part in query_parts if part.strip())
    if not query:
        print("find: query must not be empty", file=sys.stderr)
        return FindResult(exit_code=1, query="", substances=[], products=[])

    with maybe_patch_root(data_root):
        schema_result = validate_schemas()
        if schema_result != 0:
            return FindResult(exit_code=schema_result, query=query, substances=[], products=[])

        maintenance_result = run_auto_maintenance(suppress_output=True)
        if maintenance_result != 0:
            return FindResult(exit_code=maintenance_result, query=query, substances=[], products=[])

        substance_results = find_substance_results(query)
        product_results = find_product_results(query)

        print(f"Search results for: {query}")
        print_find_section("Substances", substance_results, limit)
        print_find_section("Products", product_results, limit)

        return FindResult(
            exit_code=0,
            query=query,
            substances=substance_results,
            products=product_results,
        )
