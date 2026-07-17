"""Canonical dashboard selector validation."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping
from planner.contracts import CardLoadError
from planner.ontology.artifacts import OntologyBundle
from planner.paths import Paths
from planner.schema_validation import schema_errors


def check_dashboards(
    dashboard_files: list[Path], _policy_ids: set[str], _paths: Paths, bundle: OntologyBundle
) -> list[str]:
    vocabulary = bundle.runtime_vocabulary
    known_terms = {
        (str(term["semantic_category"]), str(term["slug"]))
        for raw in cast(list[object], vocabulary.get("terms", []))
        if isinstance(raw, dict)
        for term in [cast(dict[str, object], raw)]
    }
    errors: list[str] = []
    for path in dashboard_files:
        try:
            dashboard = load_card_mapping(path, "dashboard")
        except CardLoadError as error:
            errors.append(error.message)
            continue
        errors.extend(schema_errors(dashboard, "dashboard", path, bundle))
        selectors = dashboard.get("selectors")
        if not isinstance(selectors, list):
            continue
        for index, raw in enumerate(selectors):
            if not isinstance(raw, dict):
                continue
            selector = cast(dict[str, object], raw)
            category, term = selector.get("category"), selector.get("term")
            if isinstance(category, str) and isinstance(term, str) and (category, term) not in known_terms:
                errors.append(
                    f"{path}: selectors[{index}] term '{category}:{term}' is not in canonical ontology vocabulary"
                )
    return errors
