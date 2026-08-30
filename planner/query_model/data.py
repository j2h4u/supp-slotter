"""Command-scoped data used by the planner read-model facade."""

from __future__ import annotations

from dataclasses import dataclass

from planner.contracts import Product, Substance


@dataclass(frozen=True, slots=True)
class RelationEndpoint:
    """Resolved relation endpoint used by review-only queries."""

    key: str
    display: str
    substance_ids: tuple[str, ...]
    member_names: tuple[str, ...]
    selector_form: str


@dataclass(frozen=True, slots=True)
class RelationQuery:
    """Typed review metadata for one resolved ontology assertion."""

    relation_type: str
    source: RelationEndpoint
    target: RelationEndpoint
    reason: str
    research_state: str
    sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReadModelData:
    """Plain immutable command data; no database or query language involved."""

    substances: dict[str, Substance]
    products: dict[str, Product]
    stacks: dict[str, list[str]]
    relations: tuple[RelationQuery, ...]
