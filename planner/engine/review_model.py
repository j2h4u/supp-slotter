"""Data builder for the full `review` command."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple, cast

from planner.cards.dashboards import build_dashboard_review
from planner.cards.product import format_product_name, load_product_registry
from planner.cards.relations import check_global_relations, load_global_relations
from planner.cards.stacks import normalize_stack_entries
from planner.cards.substance import format_substance_name, load_substance_registry
from planner.contracts import CardLoadError, ConcernRecord, Product, StackEntry, Substance
from planner.engine._types import RelationReviewRow
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.policies import load_scheduling_policies
from planner.ontology.presentation import ReviewPresentation, load_relation_type_order, load_review_presentation
from planner.ontology.runtime_program import RuntimeDashboardStateCatalog
from planner.ontology.warning_policy import authored_relation_label, authored_term_label
from planner.paths import Paths
from planner.query_model import build_stack_read_model, stacks_for_read_model
from planner.query_model.surreal import SurrealLoadContext
from planner.schedule_types import DashboardReviewEntryWithMembers, DashboardReviewResult
from planner.yaml_io import load_yaml

ReviewRelationRows = dict[str, list[RelationReviewRow]]


@dataclass(frozen=True, slots=True)
class ReviewModel:
    concerns_by_kind: dict[str, list[ConcernEntry]]
    concern_kind_labels: dict[str, str]
    relations_by_status: ReviewRelationRows
    relation_type_labels: dict[str, str]
    relation_type_order: tuple[str, ...]
    relation_status_order: tuple[str, ...]
    knowledge_index: dict[str, dict[str, list[str]]]
    knowledge_namespace_labels: dict[str, str]
    knowledge_index_order: tuple[str, ...]
    dashboard_summary: dict[str, DashboardReviewEntryWithMembers]
    dashboard_state_catalog: RuntimeDashboardStateCatalog


@dataclass(frozen=True, slots=True)
class ConcernEntry:
    name: str
    record: ConcernRecord

    @property
    def text(self) -> str:
        return self.record.text


class _ConcernFilterContext(NamedTuple):
    substances: dict[str, Substance]
    products: dict[str, Product]


def build_review_model(  # noqa: PLR0914
    paths: Paths, bundle: OntologyBundle
) -> tuple[ReviewModel | None, list[str]]:
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
    global_relations = load_global_relations(paths, bundle, substances)
    try:
        stacks_data = stacks_for_read_model(paths) if paths.stacks_file.exists() else {}
        stack_entries = normalize_stack_entries(cast(dict[str, object], stacks_data))
    except (CardLoadError, ValueError) as e:
        message = e.message if isinstance(e, CardLoadError) else str(e)
        return None, [f"review: {message}"]
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
    presentation = load_review_presentation(bundle)
    relation_type_order = load_relation_type_order(bundle)
    concern_kind_order = presentation.concern_kinds
    knowledge_index_order = presentation.active_fact_namespaces
    try:
        presentation_labels = _review_presentation_labels(
            bundle,
            presentation,
            relation_type_order,
        )
    except ValueError as e:
        return None, [f"review: {e}"]
    try:
        dashboard_summary = _dashboard_summary(
            paths,
            products,
            stack_entries,
            substances,
            bundle,
        )
    except CardLoadError as e:
        return None, [f"review: {e.message}"]
    return (
        ReviewModel(
            concerns_by_kind=_concerns_by_kind(
                _ConcernFilterContext(
                    substances=substances,
                    products=products,
                ),
                concern_kind_order,
            ),
            concern_kind_labels=presentation_labels[0],
            relations_by_status=cast(ReviewRelationRows, read_model.classify_relations(active_substances)),
            relation_type_labels=presentation_labels[2],
            relation_type_order=relation_type_order,
            relation_status_order=tuple(row.status for row in bundle.runtime_program.relation_presence_statuses),
            knowledge_index=_knowledge_index(active_substances, substances, bundle),
            knowledge_namespace_labels=presentation_labels[1],
            knowledge_index_order=knowledge_index_order,
            dashboard_summary=dashboard_summary,
            dashboard_state_catalog=bundle.runtime_program.dashboard_state_catalog,
        ),
        [],
    )


def _concerns_by_kind(
    context: _ConcernFilterContext,
    concern_kind_order: tuple[str, ...],
) -> dict[str, list[ConcernEntry]]:
    by_kind: dict[str, list[ConcernEntry]] = {kind: [] for kind in concern_kind_order}
    for substance in sorted(context.substances.values(), key=lambda item: item.name.casefold()):
        for concern in substance.concerns:
            by_kind.setdefault(concern.kind, []).append(
                ConcernEntry(
                    name=format_substance_name(substance),
                    record=ConcernRecord("substance", substance.id, concern.kind, concern.text),
                )
            )
    for product in sorted(context.products.values(), key=lambda item: item.name.casefold()):
        for concern in product.concerns:
            by_kind.setdefault(concern.kind, []).append(
                ConcernEntry(
                    name=format_product_name(product),
                    record=ConcernRecord("product", product.id, concern.kind, concern.text),
                )
            )
    return by_kind


def _knowledge_index(
    active_substances: set[str],
    substances: dict[str, Substance],
    bundle: OntologyBundle,
) -> dict[str, dict[str, list[str]]]:
    index: dict[str, dict[str, list[str]]] = {}
    for substance_id in sorted(active_substances):
        substance = substances.get(substance_id)
        if substance is None:
            continue
        for assertion in substance.knowledge_assertions:
            term_label = authored_term_label(f"{assertion.category}:{assertion.value}", bundle)
            index.setdefault(assertion.category, {}).setdefault(term_label, []).append(format_substance_name(substance))
    return index


def _review_presentation_labels(
    bundle: OntologyBundle,
    presentation: ReviewPresentation,
    relation_type_order: tuple[str, ...],
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    return (
        {kind: presentation.label("concern_annotations", kind) for kind in presentation.concern_kinds},
        {
            namespace: presentation.label("active_fact_index", namespace)
            for namespace in presentation.active_fact_namespaces
        },
        {relation_type: authored_relation_label(relation_type, bundle) for relation_type in relation_type_order},
    )


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
        seen.setdefault(entry["id"], entry)
    return seen
