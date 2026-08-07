"""Implemented planner glue capabilities.

These names are execution grammar, not supplement-domain truth. The authored
ontology may depend on them, but adding a value here requires Python runtime
support for that capability.
"""

from __future__ import annotations

from typing import Final, cast

IMPLEMENTED_SCOPE_FACT_ADAPTERS: Final[tuple[str, ...]] = (
    "capability_scalar",
    "capability_values",
    "dimension_singleton",
    "product_identity",
    "source_formulation",
)
# Predicate namespaces are part of the planner execution grammar.  Keep this
# boundary in the glue capability module so authored vocabulary cannot expand
# the runtime surface merely by introducing a new prefix.
IMPLEMENTED_PREDICATE_NAMESPACES: Final[tuple[str, ...]] = (
    "schedule",
    "knowledge",
)
EFFECT_ROLE_NONE: Final = "none"
EFFECT_ROLE_WARNING: Final = "warning"
EFFECT_ROLE_SCORED: Final = "scored"
EFFECT_ROLE_BLOCKING: Final = "blocking"
IMPLEMENTED_EFFECT_ROLES: Final[tuple[str, ...]] = (
    EFFECT_ROLE_NONE,
    EFFECT_ROLE_WARNING,
    EFFECT_ROLE_SCORED,
    EFFECT_ROLE_BLOCKING,
)
EFFECT_BLOCK_BEHAVIOR_PRESERVE: Final = "preserve"
EFFECT_BLOCK_BEHAVIOR_SUPPRESS: Final = "suppress"
IMPLEMENTED_EFFECT_BLOCK_BEHAVIORS: Final[tuple[str, ...]] = (
    EFFECT_BLOCK_BEHAVIOR_PRESERVE,
    EFFECT_BLOCK_BEHAVIOR_SUPPRESS,
)
RELATION_WARNING_FILTER_ASSERTION_KIND: Final = "assertion_kind"
RELATION_WARNING_FILTER_SEMANTIC_FAMILY: Final = "semantic_family"
IMPLEMENTED_RELATION_WARNING_FILTER_FIELDS: Final[tuple[str, ...]] = (
    RELATION_WARNING_FILTER_ASSERTION_KIND,
    RELATION_WARNING_FILTER_SEMANTIC_FAMILY,
)
IMPLEMENTED_RELATION_WARNING_ACTIVE_SIDES: Final[tuple[str, ...]] = (
    "both",
    "source",
    "target",
)
IMPLEMENTED_RELATION_PRESENCE_ACTIVE_SIDES: Final[tuple[str, ...]] = (
    "both",
    "none",
    "source",
    "target",
)
IMPLEMENTED_RELATION_PRESENCE_TRUTH_TABLE: Final[tuple[tuple[bool, bool], ...]] = (
    (False, False),
    (False, True),
    (True, False),
    (True, True),
)
IMPLEMENTED_RELATION_ENDPOINT_SELECTOR_KINDS: Final[tuple[str, ...]] = (
    "entity",
    "term",
)
WARNING_EMITTER_INTRA_PRODUCT_CONSTRAINT_CONFLICT: Final = "intra_product_constraint_conflict"
WARNING_EMITTER_PREFER_WITH_RESOLVER: Final = "prefer_with_resolver"
WARNING_EMITTER_TRAIT_REVIEW_ASSIGNMENT: Final = "trait_review_assignment"
IMPLEMENTED_WARNING_EMITTER_IDS: Final[tuple[str, ...]] = (
    WARNING_EMITTER_INTRA_PRODUCT_CONSTRAINT_CONFLICT,
    WARNING_EMITTER_PREFER_WITH_RESOLVER,
    WARNING_EMITTER_TRAIT_REVIEW_ASSIGNMENT,
)
# Audit disposition names and checker IDs are execution grammar.  The
# ontology may choose a subset for each authored audit rule, but cannot invent
# a checker that the runtime does not implement.
IMPLEMENTED_AUDIT_DISPOSITION_CHECKS: Final[dict[str, str]] = {
    "governed_assignment": "governed_assignment_exact",
    "reviewed_no_assignment": "reviewed_no_assignment_empty",
}
IMPLEMENTED_AUDIT_DISPOSITION_CHECK_IDS: Final[tuple[str, ...]] = tuple(IMPLEMENTED_AUDIT_DISPOSITION_CHECKS.values())
AUDIT_ASSIGNMENT_CARDINALITY_EXACTLY_ONE: Final = "exactly_one"
AUDIT_ASSIGNMENT_CARDINALITY_ZERO: Final = "zero"
IMPLEMENTED_AUDIT_ASSIGNMENT_CARDINALITIES: Final[tuple[str, ...]] = (
    AUDIT_ASSIGNMENT_CARDINALITY_EXACTLY_ONE,
    AUDIT_ASSIGNMENT_CARDINALITY_ZERO,
)
AUDIT_REQUIRED_COVERAGE_ALL_ASSIGNMENT_AXES: Final = "all_assignment_axes"
AUDIT_REQUIRED_COVERAGE_CURRENT_AXIS: Final = "current_axis"
IMPLEMENTED_AUDIT_REQUIRED_COVERAGES: Final[tuple[str, ...]] = (
    AUDIT_REQUIRED_COVERAGE_ALL_ASSIGNMENT_AXES,
    AUDIT_REQUIRED_COVERAGE_CURRENT_AXIS,
)
ONTOLOGY_COMPOSITE_KEY_SEPARATOR: Final = ":"
AUDIT_GOVERNANCE_KEY_SEPARATOR: Final = ONTOLOGY_COMPOSITE_KEY_SEPARATOR
IMPLEMENTED_PREFER_WITH_SOURCE_FIELDS: Final[tuple[str, ...]] = ("prefer_with",)
IMPLEMENTED_PREFER_WITH_TARGET_RESOLUTIONS: Final[tuple[str, ...]] = ("exactly_one_active_item",)
IMPLEMENTED_PREFER_WITH_PAIR_MODES: Final[tuple[str, ...]] = ("undirected_same_slot_bonus",)
ONTOLOGY_ASSERTION_FILTER_COLUMNS: Final[dict[str, str]] = {
    field: field for field in IMPLEMENTED_RELATION_WARNING_FILTER_FIELDS
}
IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS: Final[dict[str, tuple[str, ...]]] = {
    "scope_fact_adapters": IMPLEMENTED_SCOPE_FACT_ADAPTERS,
    "relation_warning_filter_fields": IMPLEMENTED_RELATION_WARNING_FILTER_FIELDS,
    "relation_warning_active_sides": IMPLEMENTED_RELATION_WARNING_ACTIVE_SIDES,
    "relation_presence_active_sides": IMPLEMENTED_RELATION_PRESENCE_ACTIVE_SIDES,
    "relation_endpoint_selector_kinds": IMPLEMENTED_RELATION_ENDPOINT_SELECTOR_KINDS,
    "warning_emitter_ids": IMPLEMENTED_WARNING_EMITTER_IDS,
    "prefer_with_source_fields": IMPLEMENTED_PREFER_WITH_SOURCE_FIELDS,
    "prefer_with_target_resolutions": IMPLEMENTED_PREFER_WITH_TARGET_RESOLUTIONS,
    "prefer_with_pair_modes": IMPLEMENTED_PREFER_WITH_PAIR_MODES,
}
IMPLEMENTED_GLUE_CONTRACT_AUTHORED_SEQUENCE_FIELDS: Final[tuple[str, ...]] = (
    "source_kinds",
    "source_kind_roles",
    "component_authority_outcomes",
    "component_authority_primary_values",
    "relation_review_status_ids",
    "concern_membership_roles",
)
IMPLEMENTED_GLUE_CONTRACT_SCALAR_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "inactive_stack_name",
    "active_concern_role",
    "inactive_concern_role",
    "product_concern_fallback_role",
    "substance_concern_fallback_role",
)
IMPLEMENTED_GLUE_CONTRACT_STRUCTURED_FIELDS: Final[tuple[str, ...]] = ("relation_presence_truth_table",)
IMPLEMENTED_GLUE_CONTRACT_FIELD_NAMES: Final[tuple[str, ...]] = (
    "id",
    "inactive_stack_name",
    "source_kinds",
    "source_kind_roles",
    "scope_fact_adapters",
    "component_authority_outcomes",
    "component_authority_primary_values",
    "relation_warning_filter_fields",
    "relation_warning_active_sides",
    "relation_presence_active_sides",
    "relation_presence_truth_table",
    "relation_review_status_ids",
    "relation_endpoint_selector_kinds",
    "concern_membership_roles",
    "active_concern_role",
    "inactive_concern_role",
    "product_concern_fallback_role",
    "substance_concern_fallback_role",
    "warning_emitter_ids",
    "prefer_with_source_fields",
    "prefer_with_target_resolutions",
    "prefer_with_pair_modes",
)


def relation_endpoint_selector_kind(selector: object) -> str:
    if not isinstance(selector, dict):
        raise ValueError("relation selector projection must be a mapping")
    selector_mapping = cast(dict[str, object], selector)
    kind = selector_mapping.get("kind")
    if not isinstance(kind, str) or kind not in IMPLEMENTED_RELATION_ENDPOINT_SELECTOR_KINDS:
        raise ValueError(f"relation selector projection has unsupported kind {kind!r}")
    return kind


def ontology_assertion_filter_value(filter_field: str, *, assertion_kind: str, semantic_family: str) -> str:
    if filter_field not in ONTOLOGY_ASSERTION_FILTER_COLUMNS:
        raise ValueError(f"ontology relation_warning_rules has unsupported filter_field {filter_field!r}")
    if filter_field == RELATION_WARNING_FILTER_ASSERTION_KIND:
        return assertion_kind
    if filter_field == RELATION_WARNING_FILTER_SEMANTIC_FAMILY:
        return semantic_family
    raise ValueError(f"ontology relation_warning_rules has unresolved filter_field {filter_field!r}")
