"""Data builder for the full `review` command."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple, cast

from planner.cards.dashboards import build_dashboard_review
from planner.cards.product import format_product_name, load_product_registry
from planner.cards.relations import check_global_relations, load_global_relations
from planner.cards.stacks import normalize_stack_entries
from planner.cards.substance import format_substance_name, load_substance_registry
from planner.cards.traits import load_traits
from planner.contracts import CardLoadError, Product, StackEntry, Substance
from planner.engine._types import RelationReviewRow
from planner.paths import Paths
from planner.query_model import build_stack_read_model, stacks_for_read_model
from planner.query_model.surreal import SurrealLoadContext
from planner.schedule_types import DashboardReviewEntryWithMembers, DashboardReviewResult
from planner.yaml_io import load_yaml

ReviewRelationRows = dict[str, list[RelationReviewRow]]

_CONCERN_KINDS = ("safety", "data_quality", "model_gap")


@dataclass(frozen=True, slots=True)
class ReviewModel:
    concerns_by_kind: dict[str, list[ConcernEntry]]
    relations_by_status: ReviewRelationRows
    risk_index: dict[str, list[str]]
    pathway_index: dict[str, list[str]]
    dashboard_summary: dict[str, DashboardReviewEntryWithMembers]


@dataclass(frozen=True, slots=True)
class ConcernEntry:
    name: str
    text: str
    status: str


class _ConcernFilterContext(NamedTuple):
    substances: dict[str, Substance]
    products: dict[str, Product]
    active_substances: set[str]
    inactive_substances: set[str]
    active_products: set[str]
    inactive_products: set[str]


def build_review_model(paths: Paths) -> tuple[ReviewModel | None, list[str]]:
    substances = load_substance_registry(paths)
    try:
        trait_defs = load_traits(paths.traits)
    except CardLoadError as e:
        return None, [f"review: {e.message}"]

    relations_data = load_yaml(paths.relations_file)
    relation_errors = check_global_relations(relations_data, substances, trait_defs, paths)
    if relation_errors:
        return None, [
            *relation_errors,
            "review: refusing — data/relations.yaml has validation errors "
            "(run `planner check` to surface and fix them)",
        ]

    products = load_product_registry(paths)
    global_relations = load_global_relations(paths)
    stacks_data = stacks_for_read_model(paths) if paths.stacks_file.exists() else {}
    stack_entries = normalize_stack_entries(cast(dict[str, object], stacks_data))
    read_model = build_stack_read_model(
        substances,
        global_relations,
        products,
        context=SurrealLoadContext(
            trait_defs=trait_defs,
            stacks_data=stacks_data,
            pillbox_stack_names=None,
            dashboards=None,
        ),
    )
    active_substances = read_model.active_substance_ids()
    inactive_substances = read_model.inactive_substance_ids()
    active_products = {
        product_id
        for stack_name, product_ids in stacks_data.items()
        if stack_name != "inactive"
        for product_id in product_ids
    }
    inactive_products = set(stacks_data.get("inactive", []))

    return (
        ReviewModel(
            concerns_by_kind=_concerns_by_kind(
                _ConcernFilterContext(
                    substances=substances,
                    products=products,
                    active_substances=active_substances,
                    inactive_substances=inactive_substances,
                    active_products=active_products,
                    inactive_products=inactive_products,
                )
            ),
            relations_by_status=cast(ReviewRelationRows, read_model.classify_relations(active_substances)),
            risk_index=_risk_index(active_substances, substances),
            pathway_index=_pathway_index(active_substances, substances),
            dashboard_summary=_dashboard_summary(
                paths,
                products,
                stack_entries,
                substances,
            ),
        ),
        [],
    )


def _concerns_by_kind(
    context: _ConcernFilterContext,
) -> dict[str, list[ConcernEntry]]:
    by_kind: dict[str, list[ConcernEntry]] = {kind: [] for kind in _CONCERN_KINDS}
    for substance in sorted(context.substances.values(), key=lambda item: item.name.casefold()):
        for concern in substance.concerns:
            by_kind[concern.kind].append(
                ConcernEntry(
                    name=format_substance_name(substance),
                    text=concern.text,
                    status=_membership_status(
                        substance.id,
                        context.active_substances,
                        context.inactive_substances,
                        fallback="knowledge-only",
                    ),
                )
            )
    for product in sorted(context.products.values(), key=lambda item: item.name.casefold()):
        for concern in product.concerns:
            by_kind[concern.kind].append(
                ConcernEntry(
                    name=format_product_name(product),
                    text=concern.text,
                    status=_membership_status(
                        product.id,
                        context.active_products,
                        context.inactive_products,
                        fallback="tracked-unassigned",
                    ),
                )
            )
    return by_kind


def _membership_status(
    item_id: str,
    active_ids: set[str],
    inactive_ids: set[str],
    *,
    fallback: str,
) -> str:
    if item_id in active_ids:
        return "active"
    if item_id in inactive_ids:
        return "inactive"
    return fallback


def _risk_index(
    active_substances: set[str],
    substances: dict[str, Substance],
) -> dict[str, list[str]]:
    risk_index: dict[str, list[str]] = {}
    for substance_id in sorted(active_substances):
        substance = substances.get(substance_id)
        if substance is None:
            continue
        for slug in substance.risk:
            risk_index.setdefault(slug, []).append(format_substance_name(substance))
    return risk_index


def _pathway_index(
    active_substances: set[str],
    substances: dict[str, Substance],
) -> dict[str, list[str]]:
    pathway_index: dict[str, list[str]] = {}
    for substance_id in sorted(active_substances):
        substance = substances.get(substance_id)
        if substance is None:
            continue
        for slug in substance.pathway:
            pathway_index.setdefault(slug, []).append(format_substance_name(substance))
    return pathway_index


def _dashboard_summary(
    paths: Paths,
    products: dict[str, Product],
    stack_entries: dict[str, StackEntry],
    substances: dict[str, Substance],
) -> dict[str, DashboardReviewEntryWithMembers]:
    dashboard_files = sorted(paths.dashboards.glob("*.yaml")) if paths.dashboards.exists() else []
    review_data = cast(
        DashboardReviewResult,
        build_dashboard_review(
            dashboard_files=dashboard_files,
            products=products,
            stack_entries=stack_entries,
            substances=substances,
        ),
    )
    seen: dict[str, DashboardReviewEntryWithMembers] = {}
    for entry in review_data["benefits"] + review_data["risks"]:
        seen.setdefault(entry["name"], entry)
    return seen
