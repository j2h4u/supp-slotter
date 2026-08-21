"""Text renderer for the full `review` command."""

from __future__ import annotations

import textwrap

from planner.engine._types import RelationReviewRow
from planner.engine.review_model import ConcernEntry, ReviewModel
from planner.schedule_types import DashboardMember, DashboardReviewEntryWithMembers

SEPARATOR = "─" * 41
_WRAP_WIDTH = 79
_INDENT = "    "


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
    print(
        "  Relation outcomes: "
        f"{sum(1 for rows in model.relations_by_status.values() for row in rows if row['warning_type'])} warnings, "
        f"{sum(len(rows) for rows in model.relations_by_status.values())} authored relations"
    )
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
    any_output = False
    for kind in model.concerns_by_kind:
        header = _concern_label(model, kind)
        entries = model.concerns_by_kind[kind]
        if not entries:
            continue
        if any_output:
            print()
        print(f"{header} ({len(entries)})")
        print(SEPARATOR)
        ordered = sorted(entries, key=_concern_sort_key)
        shown = ordered[:12]
        for entry in shown:
            print(f"  {entry.name} ({entry.record.subject_kind}:{entry.record.subject_id})")
            wrapped = textwrap.fill(
                entry.text,
                width=_WRAP_WIDTH,
                initial_indent=_INDENT,
                subsequent_indent=_INDENT,
            )
            print(wrapped)
        if len(ordered) > len(shown):
            print(f"  … {len(ordered) - len(shown)} more concerns; inspect source cards for the full catalog.")
        any_output = True

    if not any_output:
        print("No concerns recorded.")


def _concern_label(model: ReviewModel, kind: str) -> str:
    label = model.concern_kind_labels.get(kind)
    if not isinstance(label, str) or not label.strip():
        raise ValueError(f"ontology concern kind {kind!r} has no authored presentation label")
    return label


def _print_relations(model: ReviewModel) -> None:
    warning_entries = [
        entry for entries in model.relations_by_status.values() for entry in entries if entry["warning_type"]
    ]
    print()
    print(f"Actionable relation warnings ({len(warning_entries)})")
    print(SEPARATOR)
    if not warning_entries:
        print("  No active relation warnings.")
        return

    for entry in sorted(warning_entries, key=lambda item: _relation_sort_key(item, model.relation_type_order)):
        relation_type = _relation_type_label(model, entry["type"])
        line = f"  [{relation_type}] {entry['source']} -> {entry['target']}"
        print(f"{line} [warning: {entry['warning_type']}]")
        if entry["reason"]:
            print(f"      {entry['reason']}")
        _print_relation_metadata(entry)
        action = entry.get("action")
        if action:
            print(f"      action: {action}")


def _relation_sort_key(entry: RelationReviewRow, relation_type_order: tuple[str, ...]) -> tuple[int, str]:
    relation_type = entry["type"]
    source = entry["source"]
    try:
        order = relation_type_order.index(relation_type)
    except ValueError as error:
        raise ValueError(f"ontology relation type {relation_type!r} has no authored presentation order") from error
    return (order, source.casefold())


def _relation_type_label(model: ReviewModel, relation_type: str) -> str:
    label = model.relation_type_labels.get(relation_type)
    if not isinstance(label, str) or not label.strip():
        raise ValueError(f"ontology relation type {relation_type!r} has no authored presentation label")
    return label


def _print_relation_metadata(entry: RelationReviewRow) -> None:
    if "severity" in entry:
        print(f"      severity: {entry['severity']}")
    if "action" in entry:
        print(f"      action: {entry['action']}")


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


def _print_index_section(
    title: str,
    entries: dict[str, list[str]],
    empty_message: str,
) -> None:
    total = sum(len(v) for v in entries.values())
    print()
    print(f"{title} ({total})")
    print(SEPARATOR)
    if not entries:
        print(f"  {empty_message}")
        return

    for slug in sorted(entries):
        names = entries[slug]
        print(f"  {slug} ({len(names)})")
        for name in names:
            print(f"    - {name}")


def _print_knowledge_index(model: ReviewModel) -> None:
    for namespace in model.knowledge_index_order:
        entries = model.knowledge_index.get(namespace, {})
        title = _knowledge_namespace_label(model, namespace)
        _print_index_section(
            title,
            entries,
            f"No {title.casefold()} on active substances.",
        )


def _knowledge_namespace_label(model: ReviewModel, namespace: str) -> str:
    label = model.knowledge_namespace_labels.get(namespace)
    if not isinstance(label, str) or not label.strip():
        raise ValueError(f"ontology knowledge namespace {namespace!r} has no authored presentation label")
    return label


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
        1 for entry in model.dashboard_summary.values()
        if any(_member_usage_state(member) == primary_usage_state.state for member in _dashboard_members(entry))
    )
    print(f"  {with_current} with {primary_usage_state.label} members; {len(model.dashboard_summary) - with_current} without.")


def _dashboard_members(entry: DashboardReviewEntryWithMembers) -> list[DashboardMember]:
    members = entry.get("members")
    if members is None:
        return []
    return members


def _count_members_by_usage(members: list[DashboardMember], state: str) -> int:
    return sum(1 for member in members if _member_usage_state(member) == state)


def _count_members_by_tracking(members: list[DashboardMember], state: str) -> int:
    return sum(1 for member in members if _member_product_tracking_state(member) == state)


def _dashboard_views_with_usage_state(model: ReviewModel, state: str) -> int:
    count = 0
    for entry in model.dashboard_summary.values():
        if _count_members_by_usage(_dashboard_members(entry), state) > 0:
            count += 1
    return count


def _member_usage_state(member: DashboardMember) -> str | None:
    return member["usage"]["state"]


def _member_product_tracking_state(member: DashboardMember) -> str | None:
    return member["product_tracking"]["state"]
