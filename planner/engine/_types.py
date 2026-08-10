"""Typed records shared across planner review modules."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class RelationReviewRow(TypedDict):
    type: str
    source: str
    target: str
    reason: str
    action: NotRequired[str]
    severity: NotRequired[str]
    presence: str
    warning_type: str | None
    source_matches: list[str]
    target_matches: list[str]
    show_matches: bool


class SubstanceRelationMatchRow(TypedDict):
    type: str
    src_display: str
    tgt_display: str
    reason: str
    action: str
