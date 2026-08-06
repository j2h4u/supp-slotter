"""Ontology-driven warning presentation policy."""

from __future__ import annotations

from functools import cache

from planner.ontology.artifacts import OntologyBundle, load_ontology
from planner.paths import ROOT


@cache
def _default_bundle() -> OntologyBundle:
    return load_ontology(ROOT / "ontology")


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
