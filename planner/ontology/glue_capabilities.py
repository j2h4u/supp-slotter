"""Implemented planner glue capabilities.

These names are execution grammar, not supplement-domain truth. The authored
ontology may depend on them, but adding a value here requires Python runtime
support for that capability.
"""

from __future__ import annotations

from typing import Final, cast

# Predicate namespaces are part of the planner execution grammar.  Keep this
# boundary in the glue capability module so authored vocabulary cannot expand
# the runtime surface merely by introducing a new prefix.
IMPLEMENTED_PREDICATE_NAMESPACES: Final[tuple[str, ...]] = ("knowledge",)
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
IMPLEMENTED_RELATION_PRESENCE_ACTIVE_SIDE_BY_STATE: Final[dict[tuple[bool, bool], str]] = {
    (False, False): "none",
    (False, True): "target",
    (True, False): "source",
    (True, True): "both",
}
IMPLEMENTED_RELATION_ENDPOINT_SELECTOR_KINDS: Final[tuple[str, ...]] = (
    "entity",
    "term",
)
IMPLEMENTED_RELATION_SELECTOR_FORMS: Final[tuple[str, ...]] = (
    "entity_id",
    "name",
    "term",
)
ONTOLOGY_COMPOSITE_KEY_SEPARATOR: Final = ":"
ONTOLOGY_ASSERTION_FILTER_COLUMNS: Final[dict[str, str]] = {
    field: field for field in IMPLEMENTED_RELATION_WARNING_FILTER_FIELDS
}
IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS: Final[dict[str, tuple[str, ...]]] = {
    "relation_warning_filter_fields": IMPLEMENTED_RELATION_WARNING_FILTER_FIELDS,
    "relation_warning_active_sides": IMPLEMENTED_RELATION_WARNING_ACTIVE_SIDES,
    "relation_presence_active_sides": IMPLEMENTED_RELATION_PRESENCE_ACTIVE_SIDES,
    "relation_endpoint_selector_kinds": IMPLEMENTED_RELATION_ENDPOINT_SELECTOR_KINDS,
    "relation_selector_forms": IMPLEMENTED_RELATION_SELECTOR_FORMS,
}


def relation_endpoint_selector_kind(selector: object) -> str:
    if not isinstance(selector, dict):
        raise ValueError("relation selector projection must be a mapping")
    selector_mapping = cast(dict[str, object], selector)
    kind = selector_mapping.get("kind")
    if not isinstance(kind, str) or kind not in IMPLEMENTED_RELATION_ENDPOINT_SELECTOR_KINDS:
        raise ValueError(f"relation selector projection has unsupported kind {kind!r}")
    return kind


def relation_presence_active_side(source_active: bool, target_active: bool) -> str:
    """Return the canonical active-side label for an endpoint truth state."""
    try:
        return IMPLEMENTED_RELATION_PRESENCE_ACTIVE_SIDE_BY_STATE[(source_active, target_active)]
    except KeyError as error:
        raise ValueError(
            "relation presence state is outside the executable truth table: "
            f"source_active={source_active!r}, target_active={target_active!r}"
        ) from error


def ontology_assertion_filter_value(filter_field: str, *, assertion_kind: str, semantic_family: str) -> str:
    if filter_field not in ONTOLOGY_ASSERTION_FILTER_COLUMNS:
        raise ValueError(f"ontology relation_warning_rules has unsupported filter_field {filter_field!r}")
    if filter_field == RELATION_WARNING_FILTER_ASSERTION_KIND:
        return assertion_kind
    if filter_field == RELATION_WARNING_FILTER_SEMANTIC_FAMILY:
        return semantic_family
    raise ValueError(f"ontology relation_warning_rules has unresolved filter_field {filter_field!r}")
