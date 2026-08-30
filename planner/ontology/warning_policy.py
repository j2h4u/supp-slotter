"""Ontology-driven warning presentation policy."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from planner.ontology.artifacts import OntologyBundle
from planner.ontology.presentation import load_term_catalog


def check_warning_type_references(bundle: OntologyBundle) -> list[str]:
    """Validate warning types emitted by Python glue/runtime rules against ontology warning_types."""

    runtime_rule_warning_types = {rule.warning_type for rule in bundle.runtime_program.relation_warning_rules}
    concern_catalog_warning_types = set(bundle.runtime_program.concern_warning_catalog_by_kind.values())
    referenced_warning_types = runtime_rule_warning_types | concern_catalog_warning_types
    declared = set(bundle.runtime_program.warning_types_by_type)
    missing = sorted(referenced_warning_types - declared)
    if not missing:
        return []
    return [
        "Runtime-emitted warning types are not declared in ontology warning_types: "
        + ", ".join(repr(warning_type) for warning_type in missing)
    ]


def warning_category_label(warning_type: str, bundle: OntologyBundle) -> str:
    """Return the ontology-authored label for a warning type."""

    policy = bundle.runtime_program.warning_types_by_type.get(warning_type)
    if policy is None:
        raise ValueError(f"warning type {warning_type!r} is not declared in ontology warning_types")
    return policy.label


def authored_term_label(term_id: str, bundle: OntologyBundle) -> str:
    """Resolve a ``namespace:slug`` term through its authored vocabulary label."""
    namespace, separator, slug = term_id.partition(":")
    if not separator or not namespace or not slug:
        raise ValueError(f"ontology term id {term_id!r} is malformed; raw id is diagnostic only")
    for term in load_term_catalog(bundle):
        if term.get("semantic_category") != namespace or term.get("slug") != slug:
            continue
        label = term.get("label")
        if isinstance(label, str) and label.strip():
            return label
        raise ValueError(f"ontology term {term_id!r} has no authored non-empty label")
    raise ValueError(f"ontology term {term_id!r} has no authored label; raw id is diagnostic only")


def authored_relation_label(relation_type: str, bundle: OntologyBundle) -> str:
    """Resolve a relation type through its authored relation presentation catalog."""
    relation_types = bundle.runtime_vocabulary.get("relation_types")
    if not isinstance(relation_types, Mapping):
        raise ValueError("ontology relation_types presentation catalog is missing")
    raw_relation = cast(Mapping[str, object], relation_types).get(relation_type)
    if not isinstance(raw_relation, Mapping):
        raise ValueError(f"ontology relation type {relation_type!r} has no authored label")
    label = cast(Mapping[str, object], raw_relation).get("label")
    if not isinstance(label, str) or not label.strip():
        raise ValueError(f"ontology relation type {relation_type!r} has no authored non-empty label")
    return label


def warning_concern_label(
    warning_type: str,
    trait_id: str,
    relation_type: str,
    bundle: OntologyBundle,
) -> str:
    """Resolve warning concern text from authored term, relation, or warning catalogs."""
    if trait_id:
        return authored_term_label(trait_id, bundle)
    if relation_type:
        return authored_relation_label(relation_type, bundle)
    return warning_category_label(warning_type, bundle)


def warning_action(
    warning_type: str,
    trait_id: str,
    relation_type: str,
    bundle: OntologyBundle,
) -> str:
    """Return the ontology-authored default operator action for a warning."""

    runtime = bundle.runtime_program
    type_policy = runtime.warning_types_by_type.get(warning_type)
    if type_policy is not None:
        return type_policy.action_text
    raise ValueError(f"warning type {warning_type!r} is not declared in ontology warning_types")
