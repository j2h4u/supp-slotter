"""Text renderer for the full `review` command."""

from __future__ import annotations

import textwrap

from planner.engine.review_model import ConcernEntry, ReviewModel
from planner.ontology.presentation import RelationPresentation
from planner.query_model.types import RelationReviewRow
from planner.schedule_types import DashboardMember, DashboardReviewEntryWithMembers

SEPARATOR = "─" * 41
_WRAP_WIDTH = 79
_CONCERN_EXAMPLES_LIMIT = 3


def render_review(model: ReviewModel) -> None:
    _print_review_brief(model)
    _print_concerns(model)
    _print_relations(model)
    _print_dashboard_summary(model)


def _print_review_brief(model: ReviewModel) -> None:
    concerns_total = sum(len(entries) for entries in model.concerns_by_kind.values())
    knowledge_total = sum(
        len(names)
        for namespace in model.knowledge_index_order
        for names in model.knowledge_index.get(namespace, {}).values()
    )
    primary_usage_state = min(model.dashboard_state_catalog.usage_states, key=lambda state: state.order)
    dashboard_primary_count = _dashboard_views_with_usage_state(model, primary_usage_state.state)
    dashboard_zero_primary = len(model.dashboard_summary) - dashboard_primary_count

    print("Review brief")
    print(SEPARATOR)
    print(
        "  Concerns: "
        f"{concerns_total} ("
        + ", ".join(
            f"{_concern_label(model, kind)} {len(entries)}"
            for kind, entries in model.concerns_by_kind.items()
            if entries
        )
        + ")"
    )
    print(f"  Relations: {len(model.relation_rows)} authored relations")
    print(
        f"  Active knowledge facts: {knowledge_total} memberships across {len(model.knowledge_index_order)} categories"
    )
    print(
        "  Dashboard coverage: "
        f"{dashboard_primary_count} views with {primary_usage_state.label} members, "
        f"{dashboard_zero_primary} with zero {primary_usage_state.label} members"
    )
    print()


def _print_concerns(model: ReviewModel) -> None:
    entries_by_kind = {
        kind: sorted(entries, key=_concern_sort_key) for kind, entries in model.concerns_by_kind.items() if entries
    }
    if not entries_by_kind:
        print("No data quality or model gaps recorded.")
        return
    print(f"Data quality and model gaps ({sum(len(entries) for entries in entries_by_kind.values())})")
    print(SEPARATOR)
    for kind, entries in entries_by_kind.items():
        print(f"  {_concern_label(model, kind)} ({len(entries)})")
        for entry in entries[:_CONCERN_EXAMPLES_LIMIT]:
            print(f"    {entry.name} ({entry.record.subject_kind}:{entry.record.subject_id})")
            print(
                textwrap.fill(
                    entry.text,
                    width=_WRAP_WIDTH,
                    initial_indent="      ",
                    subsequent_indent="      ",
                )
            )
        if len(entries) > _CONCERN_EXAMPLES_LIMIT:
            print(
                f"    … {len(entries) - _CONCERN_EXAMPLES_LIMIT} more entries; inspect source cards for the full catalog."
            )


def _concern_label(model: ReviewModel, kind: str) -> str:
    label = model.concern_kind_labels.get(kind)
    if not isinstance(label, str) or not label.strip():
        raise ValueError(f"ontology concern kind {kind!r} has no authored presentation label")
    return label


def _print_relations(model: ReviewModel) -> None:
    entries = model.relation_rows
    sourced = [entry for entry in entries if entry["sources"]]
    unassessed = [entry for entry in entries if not entry["sources"]]
    _print_relation_section(
        "Evidence relations involving current stack",
        sourced,
        model,
        "No sourced relations involve the current stack.",
    )
    _print_relation_section(
        "Unassessed relation leads",
        unassessed,
        model,
        "No unassessed relation leads involve the current stack.",
    )


def _print_relation_section(
    title: str,
    entries: list[RelationReviewRow],
    model: ReviewModel,
    empty_message: str,
) -> None:
    print()
    print(f"{title} ({len(entries)})")
    print(SEPARATOR)
    if not entries:
        print(f"  {empty_message}")
        return
    for entry in sorted(entries, key=lambda item: _relation_sort_key(item, model.relation_type_order)):
        relation = _relation_type_presentation(model, entry["type"])
        connector = " -> " if relation.directional else " <-> "
        print(f"  [{relation.label}] {entry['source']}{connector}{entry['target']}")
        print(f"      {entry['reason']}")
        print(f"      state: {entry['research_state']}")
        for source in entry["sources"]:
            print(f"      source: {source}")
        if entry["show_matches"]:
            _print_relation_match_details(entry)


def _relation_sort_key(entry: RelationReviewRow, relation_type_order: tuple[str, ...]) -> tuple[int, str]:
    relation_type = entry["type"]
    source = entry["source"]
    try:
        order = relation_type_order.index(relation_type)
    except ValueError as error:
        raise ValueError(f"ontology relation type {relation_type!r} has no authored presentation order") from error
    return (order, source.casefold())


def _relation_type_presentation(model: ReviewModel, relation_type: str) -> RelationPresentation:
    try:
        return model.relation_type_presentations[relation_type]
    except KeyError as error:
        raise ValueError(f"ontology relation type {relation_type!r} has no authored presentation") from error


def _print_relation_match_details(entry: RelationReviewRow) -> None:
    source_matches = entry["source_matches"]
    target_matches = entry["target_matches"]
    if source_matches:
        _print_relation_match_line("matched active sources", source_matches)
    if target_matches:
        _print_relation_match_line("matched active targets", target_matches)


def _print_relation_match_line(label: str, names: list[str]) -> None:
    text = f"{label}: {', '.join(names)}"
    print(
        textwrap.fill(
            text,
            width=_WRAP_WIDTH,
            initial_indent="      ",
            subsequent_indent="      ",
        )
    )


def _concern_sort_key(entry: ConcernEntry) -> tuple[str, str]:
    return (entry.name.casefold(), entry.text.casefold())


def _print_dashboard_summary(model: ReviewModel) -> None:
    print()
    print(f"Dashboard coverage ({len(model.dashboard_summary)})")
    print(SEPARATOR)
    if not model.dashboard_summary:
        print("  No dashboards with benefit or risk blocks found.")
        print("  (Dashboards lacking both benefit: and risk: blocks are excluded from this summary.)")
        return

    primary_usage_state = min(model.dashboard_state_catalog.usage_states, key=lambda state: state.order)
    with_current = sum(
        1
        for entry in model.dashboard_summary.values()
        if any(_member_usage_state(member) == primary_usage_state.state for member in _dashboard_members(entry))
    )
    print(
        f"  {with_current} with {primary_usage_state.label} members; {len(model.dashboard_summary) - with_current} without."
    )


def _dashboard_members(entry: DashboardReviewEntryWithMembers) -> list[DashboardMember]:
    members = entry.get("members")
    if members is None:
        return []
    return members


def _count_members_by_usage(members: list[DashboardMember], state: str) -> int:
    return sum(1 for member in members if _member_usage_state(member) == state)


def _dashboard_views_with_usage_state(model: ReviewModel, state: str) -> int:
    count = 0
    for entry in model.dashboard_summary.values():
        if _count_members_by_usage(_dashboard_members(entry), state) > 0:
            count += 1
    return count


def _member_usage_state(member: DashboardMember) -> str | None:
    return member["usage"]["state"]
