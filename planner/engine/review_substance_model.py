"""Data builder for `review-substance`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from planner.cards.relations import load_global_relations
from planner.cards.substance import load_substance, load_substance_registry
from planner.contracts import CardLoadError, SchedulingPolicy, Substance
from planner.engine._types import SubstanceRelationMatchRow
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.policies import load_scheduling_policies
from planner.ontology.substance_fields import substance_trait_fields
from planner.paths import ROOT, Paths, display_path, strip_root_prefix
from planner.query_model import build_stack_read_model
from planner.query_model.surreal import SurrealLoadContext

SubstanceRelationMatch = tuple[SubstanceRelationMatchRow, list[str]]
ContextDashboardDetails = dict[str, tuple[str, str] | None]


@dataclass(frozen=True, slots=True)
class SubstanceReviewModel:
    path: Path
    substance: Substance
    policies: dict[str, SchedulingPolicy]
    namespace_order: tuple[str, ...]
    substance_slugs_by_namespace: dict[str, set[str]]
    current_traits: set[str]
    relation_matches: list[SubstanceRelationMatch]
    context_dashboards: ContextDashboardDetails


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
    current_traits = {f"{namespace}:{slug}" for namespace, slugs in substance_slugs.items() for slug in slugs}
    review_substances = load_substance_registry(paths, bundle)
    read_model = build_stack_read_model(
        review_substances,
        load_global_relations(paths),
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
            namespace_order=_namespace_order(bundle),
            substance_slugs_by_namespace=substance_slugs,
            current_traits=current_traits,
            relation_matches=cast(
                list[SubstanceRelationMatch],
                read_model.substance_relation_matches(
                    substance.id,
                    substance.name,
                ),
            ),
            context_dashboards=_context_dashboards(paths, substance_slugs),
        ),
        [],
    )


def _substance_slugs_by_namespace(substance: Substance, bundle: OntologyBundle) -> dict[str, set[str]]:
    slugs_by_namespace: dict[str, set[str]] = {}
    for field, namespace in substance_trait_fields(bundle):
        slugs_by_namespace[namespace] = set(cast(tuple[str, ...], getattr(substance, field)))
    return slugs_by_namespace


def _namespace_order(bundle: OntologyBundle) -> tuple[str, ...]:
    categories = bundle.runtime_vocabulary.get("categories")
    if not isinstance(categories, dict):
        return tuple(
            row.axis for row in sorted(bundle.runtime_program.assignment_axes, key=lambda row: (row.order, row.id))
        )
    order: list[str] = []
    assignment_axes = tuple(
        row.axis for row in sorted(bundle.runtime_program.assignment_axes, key=lambda row: (row.order, row.id))
    )
    for category in categories:
        if not isinstance(category, str):
            continue
        if category == "schedule_rule":
            order.extend(assignment_axes)
        else:
            order.append(category)
    return tuple(dict.fromkeys(order))


def _context_dashboards(
    paths: Paths,
    slugs_by_namespace: dict[str, set[str]],
) -> ContextDashboardDetails:
    details: ContextDashboardDetails = {}
    for slug in slugs_by_namespace.get("context", set()):
        yaml_path = paths.dashboards / f"{slug}.yaml"
        if not yaml_path.exists():
            details[slug] = None
            continue
        raw_data = cast(object, yaml.safe_load(yaml_path.read_text(encoding="utf-8")))
        if not isinstance(raw_data, dict):
            details[slug] = (slug, "")
            continue
        data = cast(dict[str, object], raw_data)
        name = data.get("name", slug)
        desc = data.get("description", "")
        details[slug] = (
            name if isinstance(name, str) else slug,
            desc if isinstance(desc, str) else "",
        )
    return details
