"""Dashboard cluster validation and review-output building."""

from __future__ import annotations

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
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.runtime_program import RuntimeDashboardStateCatalog
from planner.ontology.selector import resolve_dashboard_selector
from planner.ontology.substance_fields import dashboard_selector_category, substance_terms_for_category
from planner.ontology.warning_policy import authored_term_label
from planner.schedule_types import (
    DashboardMatchedTrait,
    DashboardMember,
    DashboardProductPresence,
    DashboardUsage,
    ProductTrackingState,
)
from planner.schema_validation import schema_errors


def load_dashboard(path: Path, bundle: OntologyBundle) -> Dashboard:
    """Load a dashboard card into a Dashboard dataclass.

    Raises CardLoadError on missing file, parse error, schema violation, or
    missing required field.
    """
    data = load_card_mapping(path, "dashboard")
    typed_data = cast(dict[str, object], data)
    selectors = _load_dashboard_selectors(typed_data, path, bundle)
    errors = schema_errors(data, "dashboard", path, bundle)
    if errors:
        raise CardLoadError(path, errors[0])
    dashboard_id = cast(str, data["id"])
    declares_context = _load_declares_context(typed_data, path, bundle)
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

        return Dashboard(
            id=dashboard_id,
            name=cast(str, data["name"]),
            description=cast(str, data["description"]),
            selectors=tuple(selectors),
            declares_context=declares_context,
            benefit=benefit,
            risk=risk,
            source_path=path,
        )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e


def _load_dashboard_selectors(
    data: dict[str, object], path: Path, bundle: OntologyBundle
) -> tuple[RelationSelector, ...]:
    if "selectors" not in data:
        raise CardLoadError(path, f"{path}: dashboard selectors is required")
    selectors_raw = data["selectors"]
    if not isinstance(selectors_raw, list):
        raise CardLoadError(path, f"{path}: dashboard selectors must be a list")
    selectors: list[RelationSelector] = []
    for index, raw_selector in enumerate(cast(list[object], selectors_raw)):
        if not isinstance(raw_selector, dict):
            raise CardLoadError(path, f"{path}: dashboard selectors[{index}] must be a mapping")
        selector = cast(dict[str, object], raw_selector)
        if set(selector) != {"category", "term"}:
            raise CardLoadError(
                path,
                f"{path}: dashboard selectors[{index}] requires exactly category and term",
            )
        category = selector.get("category")
        term = selector.get("term")
        if not isinstance(category, str) or not category.strip():
            raise CardLoadError(path, f"{path}: dashboard selectors[{index}].category must be a non-empty string")
        if not isinstance(term, str) or not term.strip():
            raise CardLoadError(path, f"{path}: dashboard selectors[{index}].term must be a non-empty string")
        typed_selector = RelationSelector(category=category, term=term)
        resolution = resolve_dashboard_selector(typed_selector, {}, bundle)
        if resolution.outcome not in {"resolved", "empty"}:
            raise CardLoadError(
                path,
                f"{path}: dashboard selectors[{index}] term '{category}:{term}' is not in canonical ontology vocabulary",
            )
        selectors.append(typed_selector)
    return tuple(selectors)


def _load_declares_context(data: dict[str, object], path: Path, bundle: OntologyBundle) -> tuple[str, ...]:
    raw_context = data.get("declares_context")
    if raw_context is None:
        return ()
    if not isinstance(raw_context, list):
        raise CardLoadError(path, f"{path}: dashboard declares_context must be a list")

    contexts: list[str] = []
    for index, raw_term in enumerate(cast(list[object], raw_context)):
        if not isinstance(raw_term, str) or not raw_term.strip():
            raise CardLoadError(
                path,
                f"{path}: dashboard declares_context[{index}] must be a non-empty canonical context term",
            )
        selector = RelationSelector(category="context", term=raw_term)
        resolution = resolve_dashboard_selector(selector, {}, bundle)
        if resolution.outcome not in {"resolved", "empty"}:
            raise CardLoadError(
                path,
                f"{path}: dashboard declares_context[{index}] term 'context:{raw_term}' "
                "is not in canonical ontology vocabulary",
            )
        # Resolve the authored label at load time as part of the same
        # canonical context contract used by review/read-model presentation.
        authored_term_label(f"context:{raw_term}", bundle)
        contexts.append(raw_term)
    return tuple(contexts)


def selector_pairs(selectors: tuple[RelationSelector, ...]) -> Iterator[tuple[str, str]]:
    """Yield canonical category/term selectors."""
    for selector in selectors:
        if selector.category is not None and selector.term is not None:
            yield selector.category, selector.term


def matched_traits(
    substance: Substance,
    selectors: tuple[RelationSelector, ...],
    bundle: OntologyBundle,
) -> list[DashboardMatchedTrait]:
    """Return the concrete dashboard selector pairs matched by a substance."""
    matched: list[DashboardMatchedTrait] = []
    for category, slug in selector_pairs(selectors):
        if not dashboard_selector_category(bundle, category):
            continue
        terms = substance_terms_for_category(substance, category, bundle)
        if terms is not None and slug in terms:
            matched.append({"namespace": category, "slug": slug})
    return matched


def _product_presence_by_substance(
    products: dict[str, Product],
    stack_entries: dict[str, StackEntry],
) -> dict[str, DashboardProductPresence]:
    stack_by_product_id: dict[str, str] = {}
    for entry in stack_entries.values():
        product_id = entry["product"]
        previous_stack = stack_by_product_id.get(product_id)
        if previous_stack is not None and previous_stack != entry["stack"]:
            raise ValueError(
                f"stack item '{product_id}' appears in multiple stacks: {previous_stack}, {entry['stack']}"
            )
        stack_by_product_id[product_id] = entry["stack"]
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
    inactive_stack_name: str,
    state_catalog: RuntimeDashboardStateCatalog,
) -> DashboardUsage:
    stacks = product_presence["stacks"] if product_presence is not None else []
    active_stacks = [stack for stack in stacks if stack != inactive_stack_name]
    inactive_stacks = [stack for stack in stacks if stack == inactive_stack_name]
    state = state_catalog.usage_state_for(
        active_stack_membership=bool(active_stacks),
        inactive_stack_membership=bool(inactive_stacks),
        tracked_product_presence=product_presence is not None and product_presence["product_count"] > 0,
    )
    # Stack membership is an observed fact projection, independent of the
    # authored state ID.  The state table classifies the facts; it does not
    # carry a second role token telling Python which list to select.
    return {
        "state": state.state,
        "stacks": stacks,
    }


def _build_member(  # noqa: PLR0913, PLR0917
    substance_id: str,
    substance: Substance,
    product_presence: DashboardProductPresence | None,
    inactive_stack_name: str,
    state_catalog: RuntimeDashboardStateCatalog,
    matched_traits_for_substance: list[DashboardMatchedTrait],
) -> DashboardMember:
    product_count = product_presence["product_count"] if product_presence is not None else 0
    tracking_state = state_catalog.product_tracking_state_for(
        tracked_product_presence=product_count > 0,
    )
    return {
        "substance_id": substance_id,
        "substance": format_substance_name(substance),
        "relevance": {
            "matched_traits": matched_traits_for_substance,
        },
        "product_tracking": {
            "state": cast(ProductTrackingState, tracking_state.state),
            "product_count": product_count,
        },
        "usage": _usage_for_product_presence(product_presence, inactive_stack_name, state_catalog),
    }


def build_dashboard_review(
    *,
    dashboard_files: list[Path],
    products: dict[str, Product],
    stack_entries: dict[str, StackEntry],
    substances: dict[str, Substance],
    bundle: OntologyBundle,
) -> dict[str, list[dict[str, object]]]:
    """Resolve dashboard membership by canonical selectors.

    A substance is a member when it carries any declared category/term selector.
    """
    benefits: list[dict[str, object]] = []
    risks: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    product_presence_by_substance = _product_presence_by_substance(products, stack_entries)
    inactive_stack_name = bundle.runtime_program.glue_contract.inactive_stack_name
    state_catalog = bundle.runtime_program.dashboard_state_catalog
    loaded_dashboard_ids: dict[str, Path] = {}

    for dashboard_file in dashboard_files:
        dashboard = load_dashboard(dashboard_file, bundle)
        previous_path = loaded_dashboard_ids.get(dashboard.id)
        if previous_path is not None:
            raise CardLoadError(
                dashboard_file,
                f"{dashboard_file}: duplicate dashboard id {dashboard.id!r}; already defined in {previous_path}",
            )
        loaded_dashboard_ids[dashboard.id] = dashboard_file

        members: list[DashboardMember] = []
        for substance_id, substance in substances.items():
            matched = matched_traits(substance, dashboard.selectors, bundle)
            if not matched:
                continue

            product_presence = product_presence_by_substance.get(substance_id)
            members.append(
                _build_member(
                    substance_id=substance_id,
                    substance=substance,
                    product_presence=product_presence,
                    inactive_stack_name=inactive_stack_name,
                    state_catalog=state_catalog,
                    matched_traits_for_substance=matched,
                )
            )

        members = sorted(members, key=lambda item: item["substance"].casefold())

        if dashboard.benefit is not None:
            benefit_entry: dict[str, object] = _dashboard_review_entry(dashboard, bundle)
            if members:
                benefit_entry["members"] = members
            benefits.append(benefit_entry)

        if dashboard.risk is not None:
            risk_entry: dict[str, object] = _dashboard_review_entry(dashboard, bundle)
            if members:
                risk_entry["members"] = members
            risks.append(risk_entry)

    return {"benefits": benefits, "risks": risks, "warnings": warnings}


def _dashboard_review_entry(dashboard: Dashboard, bundle: OntologyBundle) -> dict[str, object]:
    """Retain dashboard identity/context in review output without scheduling semantics."""
    return {
        "id": dashboard.id,
        "name": dashboard.name,
        "declares_context": list(dashboard.declares_context),
        "declares_context_labels": [
            authored_term_label(f"context:{term}", bundle) for term in dashboard.declares_context
        ],
    }
