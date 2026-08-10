"""Substance-card fuzzy search."""

from __future__ import annotations

from pathlib import Path

from planner.cards.search import collect_search_strings, combined_search_score
from planner.cards.substance import format_substance_name, load_substance
from planner.domain_constants import FIND_MIN_SCORE
from planner.ontology.artifacts import OntologyBundle
from planner.paths import Paths


def find_substance_results(query: str, paths: Paths, bundle: OntologyBundle) -> list[tuple[float, str, str, Path]]:
    results: list[tuple[float, str, str, Path]] = []
    for path in sorted(paths.substances.glob("*.yaml")):
        # Search is an all-cards operation.  A malformed card makes the
        # result set incomplete, so surface the canonical loader failure
        # instead of reporting a misleading successful partial search.
        substance = load_substance(path, bundle)
        identity_values = [
            substance.id,
            substance.name,
            substance.form or "",
            path.name,
        ]
        identity_values.extend(substance.aliases)
        full_values = collect_search_strings(substance)
        full_values.append(path.name)
        score = combined_search_score(query, identity_values, full_values)
        if score >= FIND_MIN_SCORE:
            results.append((score, substance.id, format_substance_name(substance), path))
    return sorted(results, key=lambda item: (-item[0], item[2].casefold(), item[1]))
