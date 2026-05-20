"""Data builder for the full `review` command."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from planner.cards.dashboards import build_dashboard_review
from planner.cards.product import format_product_name, load_product_registry
from planner.cards.relations import check_global_relations, load_global_relations
from planner.cards.substance import format_substance_name, load_substance_registry
from planner.cards.traits import load_traits
from planner.contracts import CardLoadError, Product, Substance
from planner.paths import Paths
from planner.query_model import build_stack_read_model, stacks_for_read_model
from planner.yaml_io import load_yaml

ReviewRelationRows = dict[str, list[dict[str, str]]]

_CONCERN_KINDS = ("safety", "data_quality", "model_gap")


@dataclass(frozen=True, slots=True)
class ReviewModel:
    concerns_by_kind: dict[str, list[tuple[str, str]]]
    relations_by_status: ReviewRelationRows
    risk_index: dict[str, list[str]]
    pathway_index: dict[str, list[str]]
    dashboard_summary: dict[str, dict[str, Any]]


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
    read_model = build_stack_read_model(
        substances,
        global_relations,
        products,
        stacks_data=stacks_for_read_model(paths) if paths.stacks_file.exists() else None,
    )
    active_substances = read_model.active_substance_ids()
    inactive_substances = read_model.inactive_substance_ids()

    return (
        ReviewModel(
            concerns_by_kind=_concerns_by_kind(substances, products),
            relations_by_status=read_model.classify_relations(active_substances),
            risk_index=_risk_index(active_substances, substances),
            pathway_index=_pathway_index(active_substances, substances),
            dashboard_summary=_dashboard_summary(
                paths,
                active_substances,
                inactive_substances,
                substances,
            ),
        ),
        [],
    )


def _concerns_by_kind(
    substances: dict[str, Substance],
    products: dict[str, Product],
) -> dict[str, list[tuple[str, str]]]:
    by_kind: dict[str, list[tuple[str, str]]] = {kind: [] for kind in _CONCERN_KINDS}
    for substance in sorted(substances.values(), key=lambda item: item.name.casefold()):
        for concern in substance.concerns:
            by_kind[concern.kind].append((format_substance_name(substance), concern.text))
    for product in sorted(products.values(), key=lambda item: item.name.casefold()):
        for concern in product.concerns:
            by_kind[concern.kind].append((format_product_name(product), concern.text))
    return by_kind


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
    active_substances: set[str],
    inactive_substances: set[str],
    substances: dict[str, Substance],
) -> dict[str, dict[str, Any]]:
    dashboard_files = sorted(paths.dashboards.glob("*.yaml")) if paths.dashboards.exists() else []
    review_data = build_dashboard_review(
        dashboard_files=dashboard_files,
        active_substances=active_substances,
        inactive_substances=inactive_substances,
        substances=substances,
    )
    seen: dict[str, dict[str, Any]] = {}
    for entry in review_data["benefits"] + review_data["risks"]:
        seen.setdefault(entry["name"], entry)
    return seen
