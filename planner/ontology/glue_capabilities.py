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
IMPLEMENTED_RELATION_WARNING_FILTER_FIELDS: Final[tuple[str, ...]] = (
    "assertion_kind",
    "semantic_family",
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
DEFAULT_RELATION_ENDPOINT_SELECTOR_KIND: Final = "entity"
IMPLEMENTED_PREFER_WITH_SOURCE_FIELDS: Final[tuple[str, ...]] = ("prefer_with",)
IMPLEMENTED_PREFER_WITH_TARGET_RESOLUTIONS: Final[tuple[str, ...]] = ("exactly_one_active_item",)
IMPLEMENTED_PREFER_WITH_PAIR_MODES: Final[tuple[str, ...]] = ("undirected_same_slot_bonus",)
ONTOLOGY_ASSERTION_FILTER_COLUMNS: Final[dict[str, str]] = {
    "assertion_kind": "assertion_kind",
    "semantic_family": "semantic_family",
}


def relation_endpoint_selector_kind(selector: object) -> str:
    if not isinstance(selector, dict):
        return DEFAULT_RELATION_ENDPOINT_SELECTOR_KIND
    selector_mapping = cast(dict[str, object], selector)
    kind = selector_mapping.get("kind")
    return kind if isinstance(kind, str) else DEFAULT_RELATION_ENDPOINT_SELECTOR_KIND
