"""Dashboard cluster validation and review-output building."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping
from planner.cards.substance import format_substance_name
from planner.contracts import (
    CardLoadError,
    Dashboard,
    DashboardBenefit,
    DashboardRisk,
    Product,
    RelationSelector,
    StackEntry,
    Substance,
)
from planner.schedule_types import (
    DashboardMatchedTrait,
    DashboardMember,
    DashboardProductPresence,
    DashboardUsage,
    ProductTrackingState,
)
from planner.schema_validation import schema_errors


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
            benefit_dict = cast(dict[str, object], benefit_raw)
            desc = benefit_dict.get("description")
            if isinstance(desc, str):
                benefit = DashboardBenefit(description=desc)

        risk_raw = data.get("risk")
        risk: DashboardRisk | None = None
        if isinstance(risk_raw, dict):
            risk_dict = cast(dict[str, object], risk_raw)
            desc = risk_dict.get("description")
            if isinstance(desc, str):
                risk = DashboardRisk(description=desc)

        selectors_raw = data.get("selectors")
        selector_items = selectors_raw if isinstance(selectors_raw, list) else []
        selectors = tuple(
            RelationSelector(category=cast(str, selector["category"]), term=cast(str, selector["term"]))
            for raw_selector in selector_items
            if isinstance(raw_selector, dict)
            for selector in [cast(dict[str, object], raw_selector)]
            if isinstance(selector.get("category"), str) and isinstance(selector.get("term"), str)
        )

        return Dashboard(
            name=cast(str, data["name"]),
            description=cast(str, data["description"]),
            selectors=selectors,
            benefit=benefit,
            risk=risk,
            started=cast(str | None, data.get("started")),
        )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e


def selector_pairs(selectors: tuple[RelationSelector, ...]) -> Iterator[tuple[str, str]]:
    """Yield canonical category/term selectors."""
    for selector in selectors:
        if selector.category is not None and selector.term is not None:
            yield selector.category, selector.term


def substance_carries(substance: Substance, namespace: str, slug: str) -> bool:
    """Return True if the substance has the given slug in the given namespace field.

    Maps the 'is' namespace to the 'is_' Python field (keyword conflict).
    Supported namespace keys: is, intake, timing, activity, prefer_with, effect, risk, context, pathway.
    Returns False (no AttributeError) for any namespace key not present on Substance.
    """
    field_name = namespace
    if not hasattr(substance, field_name):
        return False
    field_value: tuple[str, ...] = getattr(substance, field_name, ())
    return slug in field_value


def matched_traits(
    substance: Substance,
    selectors: tuple[RelationSelector, ...],
) -> list[DashboardMatchedTrait]:
    """Return the concrete dashboard selector pairs matched by a substance."""
    return [
        {"namespace": namespace, "slug": slug}
        for namespace, slug in selector_pairs(selectors)
        if substance_carries(substance, namespace, slug)
    ]


def _product_presence_by_substance(
    products: dict[str, Product],
    stack_entries: dict[str, StackEntry],
) -> dict[str, DashboardProductPresence]:
    stack_by_product_id = {entry["product"]: entry["stack"] for entry in stack_entries.values()}
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
    tracking_state: ProductTrackingState = "tracked_product" if product_count > 0 else "no_tracked_product"
    return {
        "substance_id": substance_id,
        "substance": format_substance_name(substance),
        "relevance": {
            "matched_traits": matched_traits(substance, dashboard.selectors),
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
) -> dict[str, list[dict[str, object]]]:
    """Resolve dashboard membership by canonical selectors.

    A substance is a member when it carries any declared category/term selector.
    """
    benefits: list[dict[str, object]] = []
    risks: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    product_presence_by_substance = _product_presence_by_substance(products, stack_entries)

    for dashboard_file in dashboard_files:
        try:
            dashboard = load_dashboard(dashboard_file)
        except CardLoadError as e:
            print(f"warning: skipping dashboard card: {e.message}", file=sys.stderr)
            continue

        members: list[DashboardMember] = []
        for substance_id, substance in substances.items():
            if not any(substance_carries(substance, ns, slug) for ns, slug in selector_pairs(dashboard.selectors)):
                continue

            product_presence = product_presence_by_substance.get(substance_id)
            members.append(_build_member(substance_id, substance, dashboard, product_presence))

        members = sorted(members, key=lambda item: item["substance"].casefold())

        if dashboard.benefit is not None:
            benefit_entry: dict[str, object] = {"name": dashboard.name}
            if members:
                benefit_entry["members"] = members
            benefits.append(benefit_entry)

        if dashboard.risk is not None:
            risk_entry: dict[str, object] = {"name": dashboard.name}
            if members:
                risk_entry["members"] = members
            risks.append(risk_entry)

    return {"benefits": benefits, "risks": risks, "warnings": warnings}
