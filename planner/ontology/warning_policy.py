"""Ontology-driven warning presentation policy."""

from __future__ import annotations

from functools import cache

from planner.ontology.artifacts import OntologyBundle, load_ontology
from planner.ontology.runtime_program import RuntimeProgram
from planner.paths import ROOT


@cache
def _default_bundle() -> OntologyBundle:
    return load_ontology(ROOT / "ontology")


def check_warning_type_references(bundle: OntologyBundle) -> list[str]:
    """Validate warning types emitted by Python glue/runtime rules against ontology warning_types."""

    runtime_rule_warning_types = {rule.warning_type for rule in bundle.runtime_program.relation_warning_rules}
    concern_rule_warning_types = set(bundle.runtime_program.warning_type_by_concern_kind.values())
    referenced_warning_types = (
        emitted_warning_types(bundle.runtime_program) | runtime_rule_warning_types | concern_rule_warning_types
    )
    declared = set(bundle.runtime_program.warning_types_by_type)
    missing = sorted(referenced_warning_types - declared)
    if not missing:
        return []
    return [
        "Runtime-emitted warning types are not declared in ontology warning_types: "
        + ", ".join(repr(warning_type) for warning_type in missing)
    ]


def emitted_warning_types(runtime: RuntimeProgram) -> frozenset[str]:
    """Return warning types emitted by Python glue, as declared by ontology runtime policy."""

    return frozenset(row.warning_type for row in runtime.warning_emitters)


def warning_type_for_emitter(runtime: RuntimeProgram, emitter: str) -> str:
    """Return the ontology-authored warning type for a Python glue emitter."""

    policy = runtime.warning_emitters_by_emitter.get(emitter)
    if policy is None:
        raise ValueError(f"warning emitter {emitter!r} is not declared in ontology warning_emitters")
    return policy.warning_type


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
