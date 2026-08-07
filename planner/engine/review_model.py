"""Data builder for the full `review` command."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple, cast

from planner.cards.dashboards import build_dashboard_review
from planner.cards.product import format_product_name, load_product_registry
from planner.cards.relations import check_global_relations, load_global_relations
from planner.cards.stacks import normalize_stack_entries
from planner.cards.substance import format_substance_name, load_substance_registry
from planner.contracts import CardLoadError, Product, StackEntry, Substance
from planner.engine._types import RelationReviewRow
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.policies import load_scheduling_policies
from planner.ontology.schema_enums import schema_enum_values
from planner.paths import Paths
from planner.query_model import build_stack_read_model, stacks_for_read_model
from planner.query_model.surreal import SurrealLoadContext
from planner.schedule_types import DashboardReviewEntryWithMembers, DashboardReviewResult
from planner.yaml_io import load_yaml

ReviewRelationRows = dict[str, list[RelationReviewRow]]


@dataclass(frozen=True, slots=True)
class ReviewModel:
    concerns_by_kind: dict[str, list[ConcernEntry]]
    concern_status_order: tuple[str, ...]
    relations_by_status: ReviewRelationRows
    relation_status_order: tuple[str, ...]
    relation_status_descriptions: dict[str, str]
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


class _ConcernMembershipStatuses(NamedTuple):
    active: str
    inactive: str
    fallback: str


class _ConcernRoleContract(NamedTuple):
    active: str
    inactive: str
    product_fallback: str
    substance_fallback: str


def build_review_model(paths: Paths, bundle: OntologyBundle) -> tuple[ReviewModel | None, list[str]]:
    substances = load_substance_registry(paths, bundle)
    try:
        policies = load_scheduling_policies(bundle)
    except CardLoadError as e:
        return None, [f"review: {e.message}"]

    relations_data = load_yaml(paths.relations_file)
    relation_errors = check_global_relations(relations_data, substances, paths, bundle)
    if relation_errors:
        return None, [
            *relation_errors,
            "review: refusing — data/relations.yaml has validation errors "
            "(run `planner check` to surface and fix them)",
        ]

    products = load_product_registry(paths, bundle)
    global_relations = load_global_relations(paths, bundle)
    stacks_data = stacks_for_read_model(paths) if paths.stacks_file.exists() else {}
    stack_entries = normalize_stack_entries(cast(dict[str, object], stacks_data))
    read_model = build_stack_read_model(
        substances,
        global_relations,
        products,
        context=SurrealLoadContext(
            policies=policies,
            stacks_data=stacks_data,
            pillbox_stack_names=None,
            dashboards=None,
        ),
        ontology_bundle=bundle,
    )
    active_substances = read_model.active_substance_ids()
    inactive_substances = read_model.inactive_substance_ids()
    inactive_stack_name = bundle.runtime_program.glue_contract.inactive_stack_name
    active_products = {
        product_id
        for stack_name, product_ids in stacks_data.items()
        if stack_name != inactive_stack_name
        for product_id in product_ids
    }
    inactive_products = set(stacks_data.get(inactive_stack_name, []))
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
                ),
                schema_enum_values(bundle, "ConcernKind"),
                {
                    role: policy.status
                    for role, policy in bundle.runtime_program.concern_review_statuses_by_membership_role.items()
                },
                _ConcernRoleContract(
                    active=bundle.runtime_program.glue_contract.active_concern_role,
                    inactive=bundle.runtime_program.glue_contract.inactive_concern_role,
                    product_fallback=bundle.runtime_program.glue_contract.product_concern_fallback_role,
                    substance_fallback=bundle.runtime_program.glue_contract.substance_concern_fallback_role,
                ),
            ),
            concern_status_order=bundle.runtime_program.concern_review_status_order,
            relations_by_status=cast(ReviewRelationRows, read_model.classify_relations(active_substances)),
            relation_status_order=bundle.runtime_program.relation_review_status_order,
            relation_status_descriptions={
                status: row.description
                for status, row in bundle.runtime_program.relation_review_statuses_by_status.items()
            },
            risk_index=_risk_index(active_substances, substances),
            pathway_index=_pathway_index(active_substances, substances),
            dashboard_summary=_dashboard_summary(
                paths,
                products,
                stack_entries,
                substances,
                bundle,
            ),
        ),
        [],
    )


def _concerns_by_kind(
    context: _ConcernFilterContext,
    concern_kind_order: tuple[str, ...],
    concern_statuses_by_role: dict[str, str],
    roles: _ConcernRoleContract,
) -> dict[str, list[ConcernEntry]]:
    by_kind: dict[str, list[ConcernEntry]] = {kind: [] for kind in concern_kind_order}
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
                        _ConcernMembershipStatuses(
                            concern_statuses_by_role[roles.active],
                            concern_statuses_by_role[roles.inactive],
                            concern_statuses_by_role[roles.substance_fallback],
                        ),
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
                        _ConcernMembershipStatuses(
                            concern_statuses_by_role[roles.active],
                            concern_statuses_by_role[roles.inactive],
                            concern_statuses_by_role[roles.product_fallback],
                        ),
                    ),
                )
            )
    return by_kind


def _membership_status(
    item_id: str,
    active_ids: set[str],
    inactive_ids: set[str],
    statuses: _ConcernMembershipStatuses,
) -> str:
    if item_id in active_ids:
        return statuses.active
    if item_id in inactive_ids:
        return statuses.inactive
    return statuses.fallback


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
    bundle: OntologyBundle,
) -> dict[str, DashboardReviewEntryWithMembers]:
    dashboard_files = sorted(paths.dashboards.glob("*.yaml")) if paths.dashboards.exists() else []
    review_data = cast(
        DashboardReviewResult,
        build_dashboard_review(
            dashboard_files=dashboard_files,
            products=products,
            stack_entries=stack_entries,
            substances=substances,
            bundle=bundle,
        ),
    )
    seen: dict[str, DashboardReviewEntryWithMembers] = {}
    for entry in review_data["benefits"] + review_data["risks"]:
        seen.setdefault(entry["name"], entry)
    return seen
