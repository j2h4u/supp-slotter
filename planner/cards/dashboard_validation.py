"""Canonical dashboard selector validation."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping
from planner.cards.dashboards import load_dashboard
from planner.contracts import CardLoadError, RelationSelector
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.selector import resolve_dashboard_selector
from planner.paths import Paths
from planner.schema_validation import schema_errors


def check_dashboards(
    dashboard_files: list[Path], _policy_ids: set[str], _paths: Paths, bundle: OntologyBundle
) -> list[str]:
    dashboard_paths_by_id: dict[str, Path] = {}
    return [error for path in dashboard_files for error in _check_dashboard_file(path, bundle, dashboard_paths_by_id)]


def _check_dashboard_file(
    path: Path,
    bundle: OntologyBundle,
    dashboard_paths_by_id: dict[str, Path],
) -> list[str]:
    try:
        dashboard = load_card_mapping(path, "dashboard")
    except CardLoadError as error:
        return [error.message]
    errors = schema_errors(dashboard, "dashboard", path, bundle)
    try:
        typed_dashboard = load_dashboard(path, bundle)
    except CardLoadError as error:
        # The typed loader is the canonical fail-closed identity/context
        # boundary. Schema errors are already reported above.
        if error.message not in errors:
            errors.append(error.message)
        return errors
    identity_error = _dashboard_identity_error(typed_dashboard.id, path, dashboard_paths_by_id)
    if identity_error is not None:
        errors.append(identity_error)
    selectors = dashboard.get("selectors")
    if not isinstance(selectors, list):
        return errors
    for index, raw in enumerate(selectors):
        if not isinstance(raw, dict):
            continue
        selector = cast(dict[str, object], raw)
        category, term = selector.get("category"), selector.get("term")
        if not isinstance(category, str) or not isinstance(term, str):
            continue
        resolution = resolve_dashboard_selector(
            RelationSelector(category=category, term=term),
            {},
            bundle,
        )
        if resolution.outcome not in {"resolved", "empty"}:
            errors.append(
                f"{path}: selectors[{index}] term '{category}:{term}' is not in canonical ontology vocabulary"
            )
    return errors


def _dashboard_identity_error(
    dashboard_id: str,
    path: Path,
    dashboard_paths_by_id: dict[str, Path],
) -> str | None:
    previous_path = dashboard_paths_by_id.get(dashboard_id)
    if previous_path is not None:
        return f"{path}: duplicate dashboard id {dashboard_id!r}; already defined in {previous_path}"
    dashboard_paths_by_id[dashboard_id] = path
    return None
