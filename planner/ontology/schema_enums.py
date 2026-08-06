"""Generated ontology schema enum accessors."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from planner.contracts import CardLoadError
from planner.ontology.artifacts import OntologyBundle
from planner.paths import ROOT


def schema_enum_values(bundle: OntologyBundle, enum_name: str) -> tuple[str, ...]:
    """Return enum values from verified generated schema.json."""

    schema = bundle.decoded.get("schema.json")
    if not isinstance(schema, Mapping):
        raise CardLoadError(ROOT / "ontology", "verified ontology bundle has no generated schema")
    schema_mapping = cast(Mapping[str, object], schema)
    definitions = schema_mapping.get("$defs")
    if not isinstance(definitions, Mapping):
        raise CardLoadError(ROOT / "ontology", "generated schema has no definitions")
    definitions_mapping = cast(Mapping[str, object], definitions)
    enum_definition = definitions_mapping.get(enum_name)
    if not isinstance(enum_definition, Mapping):
        raise CardLoadError(ROOT / "ontology", f"generated schema has no {enum_name} enum")
    enum_mapping = cast(Mapping[str, object], enum_definition)
    values = enum_mapping.get("enum")
    if not isinstance(values, list) or not values or any(not isinstance(value, str) for value in values):
        raise CardLoadError(ROOT / "ontology", f"generated schema {enum_name} enum is malformed")
    return tuple(cast(list[str], values))
