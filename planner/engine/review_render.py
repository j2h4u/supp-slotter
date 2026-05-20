"""Text renderer for the full `review` command."""

from __future__ import annotations

import textwrap

from planner.engine.review_model import ReviewModel

SEPARATOR = "─" * 41
_WRAP_WIDTH = 79
_INDENT = "    "

_HEADERS: dict[str, str] = {
    "safety": "Safety",
    "data_quality": "Data Quality",
    "model_gap": "Model Gaps",
}

_RELATION_STATUS_DESC: dict[str, str] = {
    "missing_source": "target present, source absent",
    "missing_target": "source present, target absent",
    "neither_active": "both absent",
}


def render_review(model: ReviewModel) -> None:
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
        for entry in entries:
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

    for status in ("both_active", "missing_source", "missing_target", "neither_active"):
        entries = model.relations_by_status[status]
        if not entries:
            continue
        desc = _RELATION_STATUS_DESC.get(status, "")
        suffix = f"  [{desc}]" if desc else ""
        print(f"\n  {status} ({len(entries)}){suffix}")
        for entry in sorted(entries, key=lambda e: (e["type"], e["source"].casefold())):
            line = f"[{entry['type']}] {entry['source']} -> {entry['target']}"
            if entry["reason"]:
                line += f": {entry['reason']}"
            print(f"    {line}")


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


def _print_dashboard_summary(model: ReviewModel) -> None:
    print()
    print(f"Dashboard summary ({len(model.dashboard_summary)})")
    print(SEPARATOR)
    if not model.dashboard_summary:
        print("  No dashboards with benefit or risk blocks found.")
        print("  (Dashboards lacking both benefit: and risk: blocks are excluded from this summary.)")
        return

    for name, entry in sorted(model.dashboard_summary.items(), key=lambda x: x[0].casefold()):
        covered: list[str] = list(entry.get("covered") or entry.get("active") or [])
        inactive_list: list[str] = list(entry.get("inactive") or [])
        missing_list: list[str] = list(entry.get("missing") or [])
        total = len(covered) + len(inactive_list) + len(missing_list)
        print(
            f"  {name}: {len(covered)}/{total} covered "
            f"(inactive: {len(inactive_list)}, missing: {len(missing_list)})"
        )
