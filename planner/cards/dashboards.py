"""Dashboard cluster validation and review-output building."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

from planner.cards._common import load_card_mapping
from planner.cards.substance import format_substance_name
from planner.contracts import (
    CardLoadError,
    Dashboard,
    DashboardBenefit,
    DashboardMember,
    DashboardRisk,
    Substance,
)
from planner.io import schema_errors


def _build_dashboard_member(member: dict[str, Any]) -> DashboardMember:
    return DashboardMember(
        substance=member.get("substance"),
        name=member.get("name"),
        role=member.get("role"),
        note=member.get("note"),
        reason=member.get("reason"),
    )


def load_dashboard(path: Path) -> Dashboard:
    """Load a dashboard card into a Dashboard dataclass.

    Raises CardLoadError on missing file, parse error, schema violation, or
    missing required field.
    """
    data = load_card_mapping(path, "dashboard")
    errors = schema_errors(data, "dashboard", path)
    if errors:
        raise CardLoadError(path, errors[0])
    try:
        benefit_raw = data.get("benefit")
        benefit: DashboardBenefit | None = None
        if isinstance(benefit_raw, dict):
            benefit_dict = cast(dict[str, Any], benefit_raw)
            desc = benefit_dict.get("description")
            if isinstance(desc, str):
                benefit = DashboardBenefit(description=desc)

        risk_raw = data.get("risk")
        risk: DashboardRisk | None = None
        if isinstance(risk_raw, dict):
            risk_dict = cast(dict[str, Any], risk_raw)
            desc = risk_dict.get("description")
            if isinstance(desc, str):
                threshold = risk_dict.get("warning_threshold")
                risk = DashboardRisk(
                    description=desc,
                    warning_threshold=int(threshold or 0),
                    action=risk_dict.get("action"),
                )

        return Dashboard(
            name=data["name"],
            description=data["description"],
            taking=tuple(
                _build_dashboard_member(cast(dict[str, Any], m))
                for m in data.get("taking") or ()
                if isinstance(m, dict)
            ),
            benefit=benefit,
            risk=risk,
            started=data.get("started"),
            candidates=tuple(
                _build_dashboard_member(cast(dict[str, Any], m))
                for m in data.get("candidates") or ()
                if isinstance(m, dict)
            ),
            declined=tuple(
                _build_dashboard_member(cast(dict[str, Any], m))
                for m in data.get("declined") or ()
                if isinstance(m, dict)
            ),
        )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e


def collect_dashboard_substance_refs(dashboard_files: list[Path]) -> set[str]:
    refs: set[str] = set()
    for gf in dashboard_files:
        try:
            dashboard = load_dashboard(gf)
        except CardLoadError as e:
            print(f"warning: skipping dashboard card: {e.message}", file=sys.stderr)
            continue
        for member_list in (dashboard.taking, dashboard.candidates, dashboard.declined):
            for member in member_list:
                if member.substance is not None:
                    refs.add(member.substance)
    return refs


def build_dashboard_review(
    *,
    dashboard_files: list[Path],
    active_substances: set[str],
    inactive_substances: set[str],
    substances: dict[str, Substance],
) -> dict[str, list[dict[str, Any]]]:
    benefits: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def member_label(substance_id: str) -> str:
        substance = substances.get(substance_id)
        if substance is not None:
            return format_substance_name(substance)
        return substance_id

    for dashboard_file in dashboard_files:
        try:
            dashboard = load_dashboard(dashboard_file)
        except CardLoadError as e:
            print(f"warning: skipping dashboard card: {e.message}", file=sys.stderr)
            continue

        taking_substance_count = 0
        active_count = 0
        covered_labels: list[str] = []
        active_substance_ids: list[str] = []
        inactive: list[str] = []
        missing: list[str] = []

        for member in dashboard.taking:
            if member.substance is None:
                continue
            taking_substance_count += 1
            label = member_label(member.substance)
            if member.substance in active_substances:
                active_count += 1
                active_substance_ids.append(member.substance)
                covered_labels.append(label)
            elif member.substance in inactive_substances:
                inactive.append(label)
            else:
                missing.append(label)

        coverage_ratio = active_count / taking_substance_count if taking_substance_count else 0.0
        if dashboard.benefit is not None:
            benefit_entry: dict[str, Any] = {
                "name": dashboard.name,
                "coverage_percent": round(coverage_ratio * 100),
                "covered": sorted(covered_labels, key=str.casefold),
            }
            if inactive:
                benefit_entry["inactive"] = sorted(inactive, key=str.casefold)
            if missing:
                benefit_entry["missing"] = sorted(missing, key=str.casefold)
            benefits.append(benefit_entry)

        if dashboard.risk is not None:
            risk_entry: dict[str, Any] = {
                "name": dashboard.name,
                "active_count": active_count,
                "tracked_count": taking_substance_count,
                "active": sorted(covered_labels, key=str.casefold),
            }
            if inactive:
                risk_entry["inactive"] = sorted(inactive, key=str.casefold)
            if missing:
                risk_entry["missing"] = sorted(missing, key=str.casefold)
            risks.append(risk_entry)
            if active_count >= dashboard.risk.warning_threshold:
                warnings.append(
                    {
                        "type": "risk_cluster_load",
                        "cluster": dashboard.name or dashboard_file.stem,
                        "active": sorted(active_substance_ids, key=lambda sid: member_label(sid).casefold()),
                        "message": dashboard.risk.description,
                        "action": dashboard.risk.action or "",
                    }
                )

    return {"benefits": benefits, "risks": risks, "warnings": warnings}


def check_dashboards(
    dashboard_files: list[Path], substance_ids: dict[str, Path],
    substances: dict[str, Substance],
) -> list[str]:
    """Validate dashboard cards against schema and dashboard substance refs.

    Operates on the raw mapping (rather than `load_dashboard`) so schema
    violations and ref violations are reported together — `load_dashboard`
    bails on the first schema error, which would mask downstream member-ref
    issues that the user expects to see in the same run.
    """
    errors: list[str] = []

    def member_label(member: dict[str, Any]) -> str:
        ref = member.get("substance")
        if isinstance(ref, str):
            substance = substances.get(ref)
            if substance is not None:
                return format_substance_name(substance)
            return ref
        name = member.get("name")
        return str(name or "")

    for gf in dashboard_files:
        try:
            dashboard = load_card_mapping(gf, "dashboard")
        except CardLoadError as e:
            errors.append(e.message)
            continue

        errors.extend(schema_errors(dashboard, "dashboard", gf))

        for list_name in ("taking", "candidates", "declined"):
            members_raw: Any = dashboard.get(list_name) or []
            if not isinstance(members_raw, list):
                continue
            members_raw_list = cast(list[Any], members_raw)
            members: list[dict[str, Any]] = [cast(dict[str, Any], m) for m in members_raw_list if isinstance(m, dict)]
            labels = [member_label(m) for m in members]
            if labels != sorted(labels, key=str.casefold):
                errors.append(f"{gf}: {list_name} must be sorted alphabetically")
            for i, member in enumerate(members):
                ref = member.get("substance")
                if not isinstance(ref, str):
                    continue
                if ref not in substance_ids:
                    errors.append(
                        f"{gf}: {list_name}[{i}].substance '{ref}' "
                        f"has no matching substance card "
                        f"(expected at data/substances/{ref}.yaml)"
                    )
    return errors
