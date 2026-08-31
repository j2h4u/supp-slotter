"""Data builder for the full `review` command."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple, cast

from planner.cards.dashboards import build_dashboard_review
from planner.cards.product import format_product_name, load_product_registry
from planner.cards.relations import check_global_relations, load_global_relations
from planner.cards.substance import format_substance_name, load_substance_registry
from planner.contracts import CardLoadError, ConcernRecord, Product, StackEntry, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.presentation import RelationPresentation, authored_relation_presentation, authored_term_label
from planner.ontology.runtime_program import RuntimeDashboardStateCatalog
from planner.paths import Paths
from planner.query_model import build_stack_read_model, stacks_for_read_model
from planner.query_model.types import RelationReviewRow
from planner.schedule_types import DashboardReviewEntryWithMembers, DashboardReviewResult
from planner.yaml_io import load_yaml

ReviewRelationRows = list[RelationReviewRow]


@dataclass(frozen=True, slots=True)
class ReviewModel:
    concerns_by_kind: dict[str, list[ConcernEntry]]
    concern_kind_labels: dict[str, str]
    relation_rows: ReviewRelationRows
    relation_type_presentations: dict[str, RelationPresentation]
    relation_type_order: tuple[str, ...]
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
        stacks_data = stacks_for_read_model(paths, bundle.runtime_program)
        stack_entries: dict[str, StackEntry] = {
            product_id: {"product": product_id, "stack": stack}
            for stack, product_ids in stacks_data.items()
            for product_id in product_ids
        }
    except (CardLoadError, ValueError) as e:
        message = e.message if isinstance(e, CardLoadError) else str(e)
        return None, [f"review: {message}"]
    try:
        read_model = build_stack_read_model(
            substances,
            global_relations,
            products,
            stacks_data,
            ontology_bundle=bundle,
        )
    except ValueError as error:
        return None, [f"review: {error}"]
    active_substances = read_model.active_substance_ids()
    routable_stack_names = set(bundle.runtime_program.glue_contract.stack_partition.routable_stack_names)
    active_products = {
        product_id for product_id, entry in stack_entries.items() if entry["stack"] in routable_stack_names
    }
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
    concerns_by_kind = _concerns_by_kind(
        _ConcernFilterContext(
            substances={key: value for key, value in substances.items() if key in active_substances},
            products={key: value for key, value in products.items() if key in active_products},
        ),
        (),
    )
    relation_rows = read_model.classify_relations(active_substances)
    relation_type_presentations = {
        relation_type: authored_relation_presentation(relation_type, bundle)
        for relation_type in {row["type"] for row in relation_rows}
    }
    relation_type_order = tuple(
        relation_type
        for relation_type, _ in sorted(relation_type_presentations.items(), key=lambda item: item[1].order)
    )
    knowledge_index = _knowledge_index(active_substances, substances, bundle)
    return (
        ReviewModel(
            concerns_by_kind=concerns_by_kind,
            concern_kind_labels={kind: kind for kind in concerns_by_kind},
            relation_rows=relation_rows,
            relation_type_presentations=relation_type_presentations,
            relation_type_order=relation_type_order,
            knowledge_index=knowledge_index,
            knowledge_namespace_labels={namespace: namespace for namespace in knowledge_index},
            knowledge_index_order=tuple(sorted(knowledge_index)),
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
