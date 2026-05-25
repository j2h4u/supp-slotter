"""Text renderer for the full `review` command."""

from __future__ import annotations

import textwrap
from typing import Any, cast

from planner.engine.review_model import ConcernEntry, ReviewModel

SEPARATOR = "─" * 41
_WRAP_WIDTH = 79
_INDENT = "    "

_HEADERS: dict[str, str] = {
    "safety": "Safety",
    "data_quality": "Data Quality",
    "model_gap": "Model Gaps",
}

_RELATION_STATUS_DESC: dict[str, str] = {
    "actionable_now": "relation semantics fire for the current stack",
    "active_pair_present": "both endpoints active; no absence warning",
    "latent_one_side_present": "one endpoint active; relation does not fire",
    "inactive": "both endpoints absent",
}

_CONCERN_STATUS_ORDER: dict[str, int] = {
    "active": 0,
    "inactive": 1,
    "tracked-unassigned": 2,
    "knowledge-only": 3,
}


def render_review(model: ReviewModel) -> None:
    _print_review_brief(model)
    _print_concerns(model)
    _print_relations(model)
    _print_index_section(
        "Risk flags",
        model.risk_index,
        "No risk flags on active substances.",
    )
    _print_index_section(
        "Pathway memberships",
        model.pathway_index,
        "No pathway memberships on active substances.",
    )
    _print_dashboard_summary(model)


def _print_review_brief(model: ReviewModel) -> None:
    active_concerns_by_kind = {
        kind: [
            entry
            for entry in model.concerns_by_kind[kind]
            if entry.status == "active"
        ]
        for kind in _HEADERS
    }
    active_concerns_total = sum(len(entries) for entries in active_concerns_by_kind.values())
    risk_total = sum(len(names) for names in model.risk_index.values())
    dashboard_current_count = _dashboard_views_with_current_members(model)
    dashboard_zero_current_count = len(model.dashboard_summary) - dashboard_current_count

    print("Review brief")
    print(SEPARATOR)
    print(
        "  Active concerns: "
        f"{active_concerns_total} "
        f"(safety {len(active_concerns_by_kind['safety'])}, "
        f"data_quality {len(active_concerns_by_kind['data_quality'])}, "
        f"model_gap {len(active_concerns_by_kind['model_gap'])})"
    )
    print(
        "  Relation review: "
        f"{len(model.relations_by_status['actionable_now'])} actionable now, "
        f"{len(model.relations_by_status['active_pair_present'])} active context"
    )
    print(
        "  Risk flags: "
        f"{risk_total} active memberships across {len(model.risk_index)} risk groups"
    )
    print(
        "  Dashboard coverage: "
        f"{dashboard_current_count} views with current members, "
        f"{dashboard_zero_current_count} with zero current members"
    )
    print("  Data-quality drilldown: run `planner audit --full` for active product source/identity gaps.")
    print()


def _print_concerns(model: ReviewModel) -> None:
    any_output = False
    for kind, header in _HEADERS.items():
        entries = model.concerns_by_kind[kind]
        if not entries:
            continue
        if any_output:
            print()
        print(f"{header} ({len(entries)})")
        print(SEPARATOR)
        for entry in sorted(entries, key=_concern_sort_key):
            print(f"  {entry.name} [{entry.status}]")
            wrapped = textwrap.fill(
                entry.text,
                width=_WRAP_WIDTH,
                initial_indent=_INDENT,
                subsequent_indent=_INDENT,
            )
            print(wrapped)
        any_output = True

    if not any_output:
        print("No concerns recorded.")


def _print_relations(model: ReviewModel) -> None:
    total_relations = sum(len(v) for v in model.relations_by_status.values())
    print()
    print(f"Relations ({total_relations})")
    print(SEPARATOR)
    if total_relations == 0:
        print("  No relations defined.")
        return

    for status in (
        "actionable_now",
        "active_pair_present",
        "latent_one_side_present",
        "inactive",
    ):
        entries = model.relations_by_status[status]
        if not entries:
            continue
        desc = _RELATION_STATUS_DESC.get(status, "")
        suffix = f"  [{desc}]" if desc else ""
        print(f"\n  {status} ({len(entries)}){suffix}")
        for entry in sorted(entries, key=_relation_sort_key):
            relation_type = str(entry.get("type") or "")
            source = str(entry.get("source") or "")
            target = str(entry.get("target") or "")
            reason = str(entry.get("reason") or "")
            presence = str(entry.get("presence") or "")
            line = f"[{relation_type}] {source} -> {target}"
            if presence:
                line += f" [{presence}]"
            if reason:
                line += f": {reason}"
            print(f"    {line}")
            if entry.get("show_matches"):
                _print_relation_match_details(entry)


def _relation_sort_key(entry: dict[str, Any]) -> tuple[str, str]:
    relation_type = str(entry.get("type") or "")
    source = str(entry.get("source") or "")
    return (relation_type, source.casefold())


def _print_relation_match_details(entry: dict[str, Any]) -> None:
    source_matches = _relation_match_names(entry, "source_matches")
    target_matches = _relation_match_names(entry, "target_matches")
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


def _relation_match_names(entry: dict[str, Any], key: str) -> list[str]:
    value = entry.get(key)
    if not isinstance(value, list):
        return []
    items = cast(list[Any], value)
    out: list[str] = []
    for item in items:
        if isinstance(item, str):
            out.append(item)
    return out


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


def _concern_sort_key(entry: ConcernEntry) -> tuple[int, str, str]:
    status_order = _CONCERN_STATUS_ORDER.get(entry.status, 99)
    return (status_order, entry.name.casefold(), entry.text.casefold())


def _print_dashboard_summary(model: ReviewModel) -> None:
    print()
    print(f"Dashboard summary ({len(model.dashboard_summary)})")
    print(SEPARATOR)
    if not model.dashboard_summary:
        print("  No dashboards with benefit or risk blocks found.")
        print("  (Dashboards lacking both benefit: and risk: blocks are excluded from this summary.)")
        return

    for name, entry in sorted(model.dashboard_summary.items(), key=lambda x: x[0].casefold()):
        members = _dashboard_members(entry)
        total = len(members)
        current_count = _count_members_by_usage(members, "current")
        on_shelf_count = _count_members_by_usage(members, "on_shelf")
        knowledge_only_count = _count_members_by_tracking(members, "no_tracked_product")
        unassigned_count = _count_members_by_usage(members, "unassigned")
        print(
            f"  {name}: {total} relevant substances "
            f"(current stack: {current_count}, "
            f"on shelf: {on_shelf_count}, "
            f"knowledge only: {knowledge_only_count}, "
            f"tracked unassigned: {unassigned_count})"
        )


def _dashboard_members(entry: dict[str, Any]) -> list[dict[str, Any]]:
    members = entry.get("members")
    if not isinstance(members, list):
        return []
    result: list[dict[str, Any]] = []
    for member in cast(list[object], members):
        if isinstance(member, dict):
            result.append(cast(dict[str, Any], member))
    return result


def _count_members_by_usage(members: list[dict[str, Any]], state: str) -> int:
    return sum(1 for member in members if _member_usage_state(member) == state)


def _count_members_by_tracking(members: list[dict[str, Any]], state: str) -> int:
    return sum(1 for member in members if _member_product_tracking_state(member) == state)


def _dashboard_views_with_current_members(model: ReviewModel) -> int:
    count = 0
    for entry in model.dashboard_summary.values():
        if _count_members_by_usage(_dashboard_members(entry), "current") > 0:
            count += 1
    return count


def _member_usage_state(member: dict[str, Any]) -> str | None:
    usage_raw = member.get("usage")
    if not isinstance(usage_raw, dict):
        return None
    usage = cast(dict[str, object], usage_raw)
    state = usage.get("state")
    return state if isinstance(state, str) else None


def _member_product_tracking_state(member: dict[str, Any]) -> str | None:
    tracking_raw = member.get("product_tracking")
    if not isinstance(tracking_raw, dict):
        return None
    tracking = cast(dict[str, object], tracking_raw)
    state = tracking.get("state")
    return state if isinstance(state, str) else None
