"""Ontology-derived field lists for substance-card projections."""

from __future__ import annotations

from typing import cast

from planner.ontology.artifacts import OntologyBundle


def schedule_assignment_fields(bundle: OntologyBundle) -> tuple[str, ...]:
    """Return substance ``schedule`` fields controlled by assignment axes."""

    return tuple(
        row.assignment_field
        for row in sorted(bundle.runtime_program.assignment_axes, key=lambda row: (row.order, row.id))
    )


def knowledge_category_fields(bundle: OntologyBundle) -> tuple[str, ...]:
    """Return substance ``knowledge`` fields declared by ontology categories."""

    categories = bundle.runtime_vocabulary.get("categories")
    if not isinstance(categories, dict):
        return ()

    fields: list[str] = []
    for category, raw in categories.items():
        if not isinstance(category, str) or not isinstance(raw, dict):
            continue
        category_data = cast(dict[str, object], raw)
        allowed_predicates = category_data.get("allowed_predicates")
        if not isinstance(allowed_predicates, list):
            continue
        for predicate in allowed_predicates:
            if not isinstance(predicate, str) or not predicate.startswith("knowledge."):
                continue
            field = predicate.removeprefix("knowledge.")
            if field == category:
                fields.append(field)

    return tuple(dict.fromkeys(fields))


def substance_trait_fields(bundle: OntologyBundle) -> tuple[tuple[str, str], ...]:
    """Return ``(Substance field, review namespace)`` pairs from the ontology."""

    schedule_fields = tuple((field, field) for field in schedule_assignment_fields(bundle))
    knowledge_fields = tuple((field, field) for field in knowledge_category_fields(bundle))
    return cast(tuple[tuple[str, str], ...], schedule_fields + knowledge_fields)
