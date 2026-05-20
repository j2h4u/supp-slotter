"""Dashboard-card validation for `planner check`."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from planner.cards._common import load_card_mapping
from planner.contracts import CardLoadError
from planner.paths import Paths
from planner.schema_validation import schema_errors


def check_dashboards(
    dashboard_files: list[Path],
    trait_ids: set[str],
    paths: Paths,
) -> list[str]:
    """Validate dashboard cards against schema and from_traits slug refs."""
    errors: list[str] = []

    for gf in dashboard_files:
        try:
            dashboard = load_card_mapping(gf, "dashboard")
        except CardLoadError as e:
            errors.append(e.message)
            continue

        errors.extend(schema_errors(dashboard, "dashboard", gf))
        _validate_from_traits(gf, dashboard, trait_ids, paths, errors)

    return errors


def _validate_from_traits(
    path: Path,
    dashboard: dict[str, Any],
    trait_ids: set[str],
    paths: Paths,
    errors: list[str],
) -> None:
    from_traits_raw: Any = dashboard.get("from_traits") or {}
    if not isinstance(from_traits_raw, dict):
        return

    from_traits_dict = cast(dict[str, Any], from_traits_raw)
    for namespace, slugs_raw in from_traits_dict.items():
        if not isinstance(slugs_raw, list):
            continue
        for slug in cast(list[object], slugs_raw):
            if not isinstance(slug, str):
                continue
            _validate_from_trait_slug(path, str(namespace), slug, trait_ids, paths, errors)


def _validate_from_trait_slug(
    path: Path,
    namespace: str,
    slug: str,
    trait_ids: set[str],
    paths: Paths,
    errors: list[str],
) -> None:
    if namespace == "context":
        if not (paths.dashboards / f"{slug}.yaml").exists():
            errors.append(
                f"{path}: Unknown review context '{slug}' in from_traits "
                f"- create data/dashboards/{slug}.yaml first."
            )
    else:
        full_id = f"{namespace}:{slug}"
        if full_id not in trait_ids:
            errors.append(
                f"{path}: Unknown trait '{slug}' under namespace '{namespace}:' "
                f"in from_traits - register it in data/traits/ under "
                f"'{namespace}:' first (with label and description)."
            )
