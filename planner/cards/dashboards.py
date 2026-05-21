"""Dashboard cluster validation and review-output building."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from planner.cards._common import load_card_mapping
from planner.cards.substance import format_substance_name
from planner.contracts import (
    CardLoadError,
    Dashboard,
    DashboardBenefit,
    DashboardRisk,
    Product,
    StackEntry,
    Substance,
)
from planner.schema_validation import schema_errors

ProductTrackingState = Literal["tracked_product", "no_tracked_product"]
UsageState = Literal["current", "on_shelf", "unassigned", "not_current"]


class DashboardMatchedTrait(TypedDict):
    namespace: str
    slug: str


class DashboardRelevance(TypedDict):
    matched_traits: list[DashboardMatchedTrait]


class DashboardProductTracking(TypedDict):
    state: ProductTrackingState
    product_count: int


class DashboardUsage(TypedDict):
    state: UsageState
    stacks: list[str]


class DashboardProductPresence(TypedDict):
    product_count: int
    stacks: list[str]


class DashboardMember(TypedDict):
    substance_id: str
    substance: str
    relevance: DashboardRelevance
    product_tracking: DashboardProductTracking
    usage: DashboardUsage


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
    Supported namespace keys: is, intake, timing, activity, prefer_with, effect, risk, context, pathway.
    Returns False (no AttributeError) for any namespace key not present on Substance.
    """
    field_name = "is_" if namespace == "is" else namespace
    if not hasattr(substance, field_name):
        return False
    field_value: tuple[str, ...] = getattr(substance, field_name, ())
    return slug in field_value


def matched_traits(
    substance: Substance,
    from_traits: dict[str, tuple[str, ...]],
) -> list[DashboardMatchedTrait]:
    """Return the concrete dashboard selector pairs matched by a substance."""
    return [
        {"namespace": namespace, "slug": slug}
        for namespace, slug in from_traits_pairs(from_traits)
        if substance_carries(substance, namespace, slug)
    ]


def _product_presence_by_substance(
    products: dict[str, Product],
    stack_entries: dict[str, StackEntry],
) -> dict[str, DashboardProductPresence]:
    stack_by_product_id = {
        entry["product"]: entry["stack"]
        for entry in stack_entries.values()
    }
    product_counts: dict[str, int] = {}
    stacks_by_substance: dict[str, set[str]] = {}

    for product in products.values():
        stack = stack_by_product_id.get(product.id)
        for component in product.components:
            product_counts[component.substance] = product_counts.get(component.substance, 0) + 1
            if stack is not None:
                stacks_by_substance.setdefault(component.substance, set()).add(stack)

    return {
        substance_id: {
            "product_count": count,
            "stacks": sorted(stacks_by_substance.get(substance_id, set()), key=str.casefold),
        }
        for substance_id, count in product_counts.items()
    }


def _usage_for_product_presence(
    product_presence: DashboardProductPresence | None,
) -> DashboardUsage:
    if product_presence is None:
        return {"state": "not_current", "stacks": []}
    stacks = product_presence["stacks"]
    active_stacks = [stack for stack in stacks if stack != "inactive"]
    if active_stacks:
        return {"state": "current", "stacks": active_stacks}
    if "inactive" in stacks:
        return {"state": "on_shelf", "stacks": ["inactive"]}
    if product_presence["product_count"] > 0:
        return {"state": "unassigned", "stacks": []}
    return {"state": "not_current", "stacks": []}


def _build_member(
    substance_id: str,
    substance: Substance,
    dashboard: Dashboard,
    product_presence: DashboardProductPresence | None,
) -> DashboardMember:
    product_count = product_presence["product_count"] if product_presence is not None else 0
    tracking_state: ProductTrackingState = (
        "tracked_product" if product_count > 0 else "no_tracked_product"
    )
    return {
        "substance_id": substance_id,
        "substance": format_substance_name(substance),
        "relevance": {
            "matched_traits": matched_traits(substance, dashboard.from_traits),
        },
        "product_tracking": {
            "state": tracking_state,
            "product_count": product_count,
        },
        "usage": _usage_for_product_presence(product_presence),
    }


def build_dashboard_review(
    *,
    dashboard_files: list[Path],
    products: dict[str, Product],
    stack_entries: dict[str, StackEntry],
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
    product_presence_by_substance = _product_presence_by_substance(products, stack_entries)

    for dashboard_file in dashboard_files:
        try:
            dashboard = load_dashboard(dashboard_file)
        except CardLoadError as e:
            print(f"warning: skipping dashboard card: {e.message}", file=sys.stderr)
            continue

        members: list[DashboardMember] = []
        for substance_id, substance in substances.items():
            if not any(
                substance_carries(substance, ns, slug)
                for ns, slug in from_traits_pairs(dashboard.from_traits)
            ):
                continue

            product_presence = product_presence_by_substance.get(substance_id)
            members.append(_build_member(substance_id, substance, dashboard, product_presence))

        members = sorted(members, key=lambda item: item["substance"].casefold())

        if dashboard.benefit is not None:
            benefit_entry: dict[str, Any] = {"name": dashboard.name}
            if members:
                benefit_entry["members"] = members
            benefits.append(benefit_entry)

        if dashboard.risk is not None:
            risk_entry: dict[str, Any] = {"name": dashboard.name}
            if members:
                risk_entry["members"] = members
            risks.append(risk_entry)

    return {"benefits": benefits, "risks": risks, "warnings": warnings}
