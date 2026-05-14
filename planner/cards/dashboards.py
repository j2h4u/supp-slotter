"""Dashboard cluster validation and review-output building."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from planner.cards._common import load_card_mapping
from planner.cards.substance import format_substance_name
from planner.contracts import (
    CardLoadError,
    Dashboard,
    DashboardBenefit,
    DashboardRisk,
    Substance,
)
from planner.io import DASHBOARDS_DIR, schema_errors


def load_dashboard(path: Path) -> Dashboard:
    """Load a dashboard card into a Dashboard dataclass.

    Raises CardLoadError on missing file, parse error, schema violation, or
    missing required field.
    """
    data = load_card_mapping(path, "dashboard")
    errors = schema_errors(data, "dashboard", path)
    if errors:
        raise CardLoadError(path, errors[0])
    try:
        benefit_raw = data.get("benefit")
        benefit: DashboardBenefit | None = None
        if isinstance(benefit_raw, dict):
            benefit_dict = cast(dict[str, Any], benefit_raw)
            desc = benefit_dict.get("description")
            if isinstance(desc, str):
                benefit = DashboardBenefit(description=desc)

        risk_raw = data.get("risk")
        risk: DashboardRisk | None = None
        if isinstance(risk_raw, dict):
            risk_dict = cast(dict[str, Any], risk_raw)
            desc = risk_dict.get("description")
            if isinstance(desc, str):
                risk = DashboardRisk(description=desc)

        from_traits_raw = cast(dict[str, Any], data.get("from_traits") or {})
        from_traits: dict[str, tuple[str, ...]] = {
            ns: tuple(cast(list[str], slugs))
            for ns, slugs in from_traits_raw.items()
            if isinstance(slugs, list)
        }

        return Dashboard(
            name=data["name"],
            description=data["description"],
            from_traits=from_traits,
            benefit=benefit,
            risk=risk,
            started=data.get("started"),
        )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e


def collect_dashboard_substance_refs(dashboard_files: list[Path]) -> set[str]:
    """After refactor, dashboards resolve membership via from_traits tags, not substance IDs.
    Returns empty set — no direct substance ID refs in dashboard cards."""
    return set()


def from_traits_pairs(
    from_traits: dict[str, tuple[str, ...]],
) -> Iterator[tuple[str, str]]:
    """Yield (namespace, slug) pairs from a from_traits dict."""
    for namespace, slugs in from_traits.items():
        for slug in slugs:
            yield namespace, slug


def substance_carries(substance: Substance, namespace: str, slug: str) -> bool:
    """Return True if the substance has the given slug in the given namespace field.

    Maps the 'is' namespace to the 'is_' Python field (keyword conflict).
    Supported namespace keys: is, intake, timing, activity, prefer_with, effect, risk, dashboard, pathway.
    Returns False (no AttributeError) for any namespace key not present on Substance.
    """
    field_name = "is_" if namespace == "is" else namespace
    if not hasattr(substance, field_name):
        return False
    field_value: tuple[str, ...] = getattr(substance, field_name, ())
    return slug in field_value


def build_dashboard_review(
    *,
    dashboard_files: list[Path],
    active_substances: set[str],
    inactive_substances: set[str],
    substances: dict[str, Substance],
) -> dict[str, list[dict[str, Any]]]:
    """Resolve dashboard membership by from_traits.

    Canonical semantics (union / logical OR across the entire from_traits object):
    A substance is a member of dashboard D if there exists at least one (namespace N, slug S) pair
    where N appears as a key in D.from_traits, S appears in D.from_traits[N], and S appears in the
    substance's per-namespace field for N. There is NO AND semantic across namespace groups.
    Mixing namespaces in one from_traits widens membership, never narrows it.
    """
    benefits: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for dashboard_file in dashboard_files:
        try:
            dashboard = load_dashboard(dashboard_file)
        except CardLoadError as e:
            print(f"warning: skipping dashboard card: {e.message}", file=sys.stderr)
            continue

        covered: list[str] = []
        inactive: list[str] = []
        missing: list[str] = []

        # Resolve membership: a substance is a member if ANY (ns, slug) pair matches.
        for substance_id, substance in substances.items():
            is_member = any(
                substance_carries(substance, ns, slug)
                for ns, slug in from_traits_pairs(dashboard.from_traits)
            )
            if not is_member:
                continue

            label = format_substance_name(substance)
            if substance_id in active_substances:
                covered.append(label)
            elif substance_id in inactive_substances:
                inactive.append(label)
            else:
                missing.append(label)

        if dashboard.benefit is not None:
            benefit_entry: dict[str, Any] = {"name": dashboard.name}
            if covered:
                benefit_entry["covered"] = sorted(covered, key=str.casefold)
            if inactive:
                benefit_entry["inactive"] = sorted(inactive, key=str.casefold)
            if missing:
                benefit_entry["missing"] = sorted(missing, key=str.casefold)
            benefits.append(benefit_entry)

        if dashboard.risk is not None:
            risk_entry: dict[str, Any] = {"name": dashboard.name}
            if covered:
                risk_entry["active"] = sorted(covered, key=str.casefold)
            if inactive:
                risk_entry["inactive"] = sorted(inactive, key=str.casefold)
            if missing:
                risk_entry["missing"] = sorted(missing, key=str.casefold)
            risks.append(risk_entry)

    return {"benefits": benefits, "risks": risks, "warnings": warnings}


def check_dashboards(
    dashboard_files: list[Path],
    substance_ids: dict[str, Path],
    substances: dict[str, Substance],
    trait_ids: set[str],
) -> list[str]:
    """Validate dashboard cards against schema and from_traits slug refs.

    For non-dashboard namespaces: every registered-trait slug must be registered in traits.yaml.
    effect: is operator-curated on substance cards and is not a traits.yaml namespace.
    For the dashboard: namespace: every slug must have a matching dashboard YAML file
    (dashboard membership is validated by file existence, not by traits.yaml).
    """
    errors: list[str] = []

    for gf in dashboard_files:
        try:
            dashboard = load_card_mapping(gf, "dashboard")
        except CardLoadError as e:
            errors.append(e.message)
            continue

        errors.extend(schema_errors(dashboard, "dashboard", gf))

        from_traits_raw: Any = dashboard.get("from_traits") or {}
        if isinstance(from_traits_raw, dict):
            from_traits_dict = cast(dict[str, Any], from_traits_raw)
            for namespace, slugs_raw in from_traits_dict.items():
                if not isinstance(slugs_raw, list):
                    continue
                for slug in cast(list[object], slugs_raw):
                    if not isinstance(slug, str):
                        continue
                    if namespace == "dashboard":
                        if not (DASHBOARDS_DIR / f"{slug}.yaml").exists():
                            errors.append(
                                f"{gf}: Unknown dashboard cluster '{slug}' in from_traits "
                                f"— create data/dashboards/{slug}.yaml first."
                            )
                    elif namespace == "effect":
                        continue
                    else:
                        full_id = f"{namespace}:{slug}"
                        if full_id not in trait_ids:
                            errors.append(
                                f"{gf}: Unknown trait '{slug}' under namespace '{namespace}:' "
                                f"in from_traits — register it in data/traits.yaml under "
                                f"'{namespace}:' first (with label and description)."
                            )

    return errors
