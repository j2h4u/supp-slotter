"""Typed records for generated schedule and review output."""

from __future__ import annotations

from typing import Literal, TypedDict

ProductTrackingState = Literal["tracked_product", "no_tracked_product"]
UsageState = Literal["current", "on_shelf", "unassigned", "not_current"]


class DashboardMatchedTrait(TypedDict):
    namespace: str
    slug: str


class DashboardRelevance(TypedDict):
    matched_traits: list[DashboardMatchedTrait]


class DashboardProductTracking(TypedDict):
    state: ProductTrackingState
    product_count: int


class DashboardUsage(TypedDict):
    state: UsageState
    stacks: list[str]


class DashboardProductPresence(TypedDict):
    product_count: int
    stacks: list[str]


class DashboardMember(TypedDict):
    substance_id: str
    substance: str
    relevance: DashboardRelevance
    product_tracking: DashboardProductTracking
    usage: DashboardUsage


class DashboardReviewEntry(TypedDict):
    name: str


class DashboardReviewEntryWithMembers(DashboardReviewEntry, total=False):
    members: list[DashboardMember]


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


class ActiveFactIndexEntry(TypedDict):
    namespace: str
    fact: str
    label: str
    product_count: int
    products: list[str]


class ScheduleKeptTogether(TypedDict):
    pair: list[str]
    together: bool
    slot: str | None


class ScheduleData(TypedDict):
    summary: ScheduleSummary
    placement_notes: list[SchedulePlacementNote]
    pillboxes: dict[str, SchedulePillbox]
    benefits: list[DashboardReviewEntryWithMembers]
    risks: list[DashboardReviewEntryWithMembers]
    warnings: list[ScheduleWarning]
    active_fact_index: list[ActiveFactIndexEntry]
    kept_together: list[ScheduleKeptTogether]
    explanations: dict[str, ScheduleExplanation]


class DashboardReviewResult(TypedDict):
    benefits: list[DashboardReviewEntryWithMembers]
    risks: list[DashboardReviewEntryWithMembers]
    warnings: list[ScheduleWarning]
