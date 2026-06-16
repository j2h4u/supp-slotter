"""Typed records shared across planner engine modules."""

from __future__ import annotations

from typing import TypedDict

from planner.cards.dashboards import DashboardMember


class ScheduleWarning(TypedDict, total=False):
    type: str
    item: str
    product: str
    substance: str
    source_substance: str
    source_name: str
    target_substance: str
    target_name: str
    source: str
    target: str
    trait: str
    relation: str
    message: str
    reason: str
    action: str
    severity: str | int
    cluster: str
    active: list[str]
    concern: str
    category: str
    note: str
    candidate_items: list[str]
    source_matches: list[str]
    target_matches: list[str]
    presence: str
    show_matches: bool


class ScheduleSlotEntry(TypedDict):
    label: str
    products: list[str]
    substances: list[str]


class SchedulePillbox(TypedDict):
    label: str
    slots: dict[str, ScheduleSlotEntry]


class SchedulePlacementNote(TypedDict):
    product: str
    pillbox: str
    slot: str
    notes: list[str]


class ScheduleSummary(TypedDict):
    take: dict[str, list[str]]


class ScheduleExplanation(TypedDict):
    components: list[str]
    pillbox: str
    slot: str
    why_here: list[str]
    review_tags: list[str]


class ScheduleData(TypedDict):
    summary: ScheduleSummary
    placement_notes: list[SchedulePlacementNote]
    pillboxes: dict[str, SchedulePillbox]
    benefits: list[DashboardReviewEntryWithMembers]
    risks: list[DashboardReviewEntryWithMembers]
    warnings: list[ScheduleWarning]
    active_fact_index: list[dict[str, object]]
    kept_together: list[ScheduleKeptTogether]
    explanations: dict[str, ScheduleExplanation]


class ScheduleKeptTogether(TypedDict):
    pair: list[str]
    together: bool
    slot: str | None


class DashboardReviewEntry(TypedDict):
    name: str


class DashboardReviewEntryWithMembers(DashboardReviewEntry, total=False):
    members: list[DashboardMember]


class DashboardReviewResult(TypedDict):
    benefits: list[DashboardReviewEntryWithMembers]
    risks: list[DashboardReviewEntryWithMembers]
    warnings: list[ScheduleWarning]


class RelationReviewRow(TypedDict):
    type: str
    source: str
    target: str
    reason: str
    presence: str
    source_matches: list[str]
    target_matches: list[str]
    show_matches: bool


class SubstanceRelationMatchRow(TypedDict):
    type: str
    src_display: str
    tgt_display: str
    reason: str
    action: str
