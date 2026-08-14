"""Dashboard-card validation for `planner check`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from planner.cards._common import load_card_mapping
from planner.contracts import CardLoadError
from planner.paths import Paths
from planner.schema_validation import schema_errors
from planner.yaml_io import YamlValue


@dataclass
class _FromTraitValidationContext:
    path: Path
    trait_ids: set[str]
    paths: Paths
    errors: list[str]


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
    dashboard: dict[str, YamlValue],
    trait_ids: set[str],
    paths: Paths,
    errors: list[str],
) -> None:
    context = _FromTraitValidationContext(
        path=path,
        trait_ids=trait_ids,
        paths=paths,
        errors=errors,
    )
    from_traits_raw = dashboard.get("from_traits") or {}
    if not isinstance(from_traits_raw, dict):
        return

    from_traits_dict = from_traits_raw
    for namespace, slugs_raw in from_traits_dict.items():
        if not isinstance(slugs_raw, list):
            continue
        for slug in slugs_raw:
            if not isinstance(slug, str):
                continue
            _validate_from_trait_slug(context, str(namespace), slug)


def _validate_from_trait_slug(
    context: _FromTraitValidationContext,
    namespace: str,
    slug: str,
) -> None:
    if namespace == "context":
        if not (context.paths.dashboards / f"{slug}.yaml").exists():
            context.errors.append(
                f"{context.path}: Unknown review context '{slug}' in from_traits - create data/dashboards/{slug}.yaml first."
            )
    else:
        full_id = f"{namespace}:{slug}"
        if full_id not in context.trait_ids:
            context.errors.append(
                f"{context.path}: Unknown trait '{slug}' under namespace '{namespace}:' "
                f"in from_traits - register it in data/traits/ under "
                f"'{namespace}:' first (with label and description)."
            )
