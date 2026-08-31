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
IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS: Final[dict[str, tuple[str, ...]]] = {
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
