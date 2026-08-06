"""Ontology-driven warning presentation policy."""

from __future__ import annotations

from functools import cache

from planner.ontology.artifacts import OntologyBundle, load_ontology
from planner.paths import ROOT

AMBIGUOUS_PREFER_WITH_WARNING = "ambiguous_prefer_with"
INTRA_PRODUCT_SCHEDULING_CONSTRAINT_CONFLICT_WARNING = "intra_product_scheduling_constraint_conflict"
SAFETY_CONCERN_WARNING = "safety_concern"
TRAIT_REVIEW_WARNING = "trait_review"

PYTHON_CREATED_WARNING_TYPES = frozenset({
    AMBIGUOUS_PREFER_WITH_WARNING,
    INTRA_PRODUCT_SCHEDULING_CONSTRAINT_CONFLICT_WARNING,
    SAFETY_CONCERN_WARNING,
    TRAIT_REVIEW_WARNING,
})


@cache
def _default_bundle() -> OntologyBundle:
    return load_ontology(ROOT / "ontology")


def check_warning_type_references(bundle: OntologyBundle) -> list[str]:
    """Validate warning types emitted by Python glue/runtime rules against ontology warning_types."""

    runtime_rule_warning_types = {rule.warning_type for rule in bundle.runtime_program.relation_warning_rules}
    referenced_warning_types = PYTHON_CREATED_WARNING_TYPES | runtime_rule_warning_types
    declared = set(bundle.runtime_program.warning_types_by_type)
    missing = sorted(referenced_warning_types - declared)
    if not missing:
        return []
    return [
        "Python-emitted warning types are not declared in ontology warning_types: "
        + ", ".join(repr(warning_type) for warning_type in missing)
    ]


def warning_category_label(warning_type: str, bundle: OntologyBundle | None = None) -> str:
    """Return the ontology-authored label for a warning type."""

    policy = (bundle or _default_bundle()).runtime_program.warning_types_by_type.get(warning_type)
    if policy is None:
        raise ValueError(f"warning type {warning_type!r} is not declared in ontology warning_types")
    return policy.label


def warning_action(
    warning_type: str,
    trait_id: str,
    relation_type: str,
    bundle: OntologyBundle | None = None,
) -> str:
    """Return the ontology-authored default operator action for a warning."""

    runtime = (bundle or _default_bundle()).runtime_program
    if trait_id:
        trait_policy = runtime.warning_trait_actions_by_trait.get(trait_id)
        if trait_policy is not None:
            return trait_policy.action_text
    type_policy = runtime.warning_types_by_type.get(warning_type)
    if type_policy is not None:
        return type_policy.action_text
    raise ValueError(f"warning type {warning_type!r} is not declared in ontology warning_types")
