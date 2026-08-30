"""Typed query result records shared by read-model and review rendering."""

from __future__ import annotations

from typing import TypedDict


class RelationReviewRow(TypedDict):
    type: str
    source: str
    target: str
    reason: str
    research_state: str
    sources: list[str]
    source_matches: list[str]
    target_matches: list[str]
    show_matches: bool
