"""Data builder for `review-substance`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from planner.cards.relations import load_global_relations
from planner.cards.substance import load_substance, load_substance_registry
from planner.contracts import CardLoadError, SchedulingPolicy, Substance
from planner.engine._types import SubstanceRelationMatchRow
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.glue_capabilities import ONTOLOGY_COMPOSITE_KEY_SEPARATOR
from planner.ontology.policies import load_scheduling_policies
from planner.ontology.presentation import load_relation_type_order, load_review_presentation
from planner.paths import ROOT, Paths, display_path, strip_root_prefix
from planner.query_model import build_stack_read_model
from planner.query_model.surreal import SurrealLoadContext

SubstanceRelationMatch = tuple[SubstanceRelationMatchRow, list[str]]


@dataclass(frozen=True, slots=True)
class SubstanceReviewModel:
    path: Path
    substance: Substance
    policies: dict[str, SchedulingPolicy]
    namespace_order: tuple[str, ...]
    substance_slugs_by_namespace: dict[str, set[str]]
    current_traits: set[str]
    relation_matches: list[SubstanceRelationMatch]
    relation_type_order: tuple[str, ...]


def resolve_substance_review_path(target: str, paths: Paths) -> tuple[Path | None, str | None]:
    path = Path(target)
    if not path.is_absolute():
        path = ROOT / path

    if not path.exists():
        return None, f"{display_path(path)}: file not found"

    resolved = path.resolve()
    substances_root = paths.substances.resolve()
    if not resolved.is_relative_to(substances_root):
        return (
            None,
            f"{display_path(path)}: review-substance only accepts paths inside {display_path(paths.substances)}/",
        )

    if resolved.suffix != ".yaml":
        return None, f"{display_path(path)}: review-substance only accepts .yaml files"

    return resolved, None


def build_substance_review_model(
    path: Path,
    paths: Paths,
    bundle: OntologyBundle,
) -> tuple[SubstanceReviewModel | None, list[str]]:
    try:
        substance = load_substance(path, bundle)
    except CardLoadError as e:
        return None, [strip_root_prefix(e.message)]

    try:
        policies = load_scheduling_policies(bundle)
    except CardLoadError as e:
        return None, [strip_root_prefix(e.message)]
    if not policies:
        return None, ["canonical ontology has no scheduling policies"]

    substance_slugs = _substance_slugs_by_namespace(substance, bundle)
    current_traits = {
        f"{namespace}{ONTOLOGY_COMPOSITE_KEY_SEPARATOR}{slug}"
        for namespace, slugs in substance_slugs.items()
        for slug in slugs
    }
    review_substances = load_substance_registry(paths, bundle)
    relation_type_order = load_relation_type_order(bundle)
    try:
        global_relations = load_global_relations(paths, bundle, review_substances)
    except CardLoadError as e:
        return None, [strip_root_prefix(e.message)]
    read_model = build_stack_read_model(
        review_substances,
        global_relations,
        context=SurrealLoadContext(
            policies=policies,
            stacks_data=None,
            pillbox_stack_names=None,
            dashboards=None,
        ),
        ontology_bundle=bundle,
    )

    return (
        SubstanceReviewModel(
            path=path,
            substance=substance,
            policies=policies,
            namespace_order=load_review_presentation(bundle).namespace_order,
            substance_slugs_by_namespace=substance_slugs,
            current_traits=current_traits,
            relation_matches=cast(
                list[SubstanceRelationMatch],
                read_model.substance_relation_matches(
                    substance.id,
                    substance.name,
                ),
            ),
            relation_type_order=relation_type_order,
        ),
        [],
    )


def _substance_slugs_by_namespace(substance: Substance, bundle: OntologyBundle) -> dict[str, set[str]]:
    slugs_by_namespace: dict[str, set[str]] = {}
    del bundle
    for assertion in substance.schedule_assertions:
        slugs_by_namespace.setdefault(assertion.axis, set()).add(assertion.value)
    for assertion in substance.knowledge_assertions:
        slugs_by_namespace.setdefault(assertion.category, set()).add(assertion.value)
    return slugs_by_namespace
