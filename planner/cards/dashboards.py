"""Dashboard cluster validation and review-output building."""

from __future__ import annotations

from pathlib import Path

import yaml

from planner.cards._common import load_card
from planner.cards.substance import format_substance_name
from planner.io import load_yaml, schema_errors


def collect_dashboard_substance_refs(dashboard_files: list[Path]) -> set[str]:
    refs: set[str] = set()
    for gf in dashboard_files:
        dashboard, err = load_card(gf, "dashboard")
        if err:
            continue
        for member_list_name in ("taking", "candidates", "declined"):
            for member in dashboard.get(member_list_name) or []:
                if not isinstance(member, dict):
                    continue
                substance_id = member.get("substance")
                if isinstance(substance_id, str):
                    refs.add(substance_id)
    return refs

def build_dashboard_review(
    *,
    dashboard_files: list[Path],
    active_substances: set[str],
    inactive_substances: set[str],
    substances: dict[str, dict],
) -> dict[str, list[dict]]:
    benefits: list[dict] = []
    risks: list[dict] = []
    warnings: list[dict] = []
    for dashboard_file in dashboard_files:
        dashboard, err = load_card(dashboard_file, "dashboard")
        if err:
            continue
        benefit = dashboard.get("benefit")
        risk = dashboard.get("risk")
        benefit_text = (
            benefit.get("description")
            if isinstance(benefit, dict)
            and isinstance(benefit.get("description"), str)
            else None
        )
        risk_text = (
            risk.get("description")
            if isinstance(risk, dict)
            and isinstance(risk.get("description"), str)
            else None
        )
        taking_total = 0
        active_count = 0
        covered: list[str] = []
        active_ids: list[str] = []
        inactive: list[str] = []
        missing: list[str] = []

        for member in dashboard.get("taking") or []:
            if not isinstance(member, dict):
                continue
            substance_id = member.get("substance")
            if not isinstance(substance_id, str):
                continue
            taking_total += 1
            if substance_id in active_substances:
                active_count += 1
                active_ids.append(substance_id)
                covered.append(
                    format_substance_name(substances.get(substance_id) or {"id": substance_id})
                )
            elif substance_id in inactive_substances:
                inactive.append(
                    format_substance_name(substances.get(substance_id) or {"id": substance_id})
                )
            else:
                missing.append(
                    format_substance_name(substances.get(substance_id) or {"id": substance_id})
                )

        coverage_ratio = active_count / taking_total if taking_total else 0.0
        if benefit_text:
            benefit_entry: dict = {
                "name": dashboard.get("name"),
                "coverage_percent": round(coverage_ratio * 100),
                "covered": sorted(covered, key=str.casefold),
            }
            if inactive:
                benefit_entry["inactive"] = sorted(inactive, key=str.casefold)
            if missing:
                benefit_entry["missing"] = sorted(missing, key=str.casefold)
            benefits.append(benefit_entry)

        if risk_text:
            risk_entry: dict = {
                "name": dashboard.get("name"),
                "active_count": active_count,
                "tracked_count": taking_total,
                "active": sorted(covered, key=str.casefold),
            }
            if inactive:
                risk_entry["inactive"] = sorted(inactive, key=str.casefold)
            if missing:
                risk_entry["missing"] = sorted(missing, key=str.casefold)
            risks.append(risk_entry)
            threshold = risk.get("warning_threshold") if isinstance(risk, dict) else None
            if isinstance(threshold, int) and active_count >= threshold:
                warnings.append(
                    {
                        "type": "risk_cluster_load",
                        "cluster": str(dashboard.get("name") or dashboard_file.stem),
                        "active": sorted(
                            active_ids,
                            key=lambda sid: format_substance_name(
                                substances.get(sid) or {"id": sid}
                            ).casefold(),
                        ),
                        "message": risk_text,
                        "action": risk.get("action", "") if isinstance(risk, dict) else "",
                    }
                )

    return {"benefits": benefits, "risks": risks, "warnings": warnings}

def check_dashboards(dashboard_files: list[Path], substance_ids: dict[str, Path]) -> list[str]:
    """Validate dashboard cards against schema and dashboard substance refs."""
    errors: list[str] = []
    substance_names: dict[str, str] = {}
    for substance_id, path in substance_ids.items():
        try:
            substance = load_yaml(path)
        except yaml.YAMLError:
            continue
        if isinstance(substance, dict):
            substance_names[substance_id] = format_substance_name(substance)

    def member_label(member: dict) -> str:
        ref = member.get("substance")
        if isinstance(ref, str):
            return substance_names.get(ref, ref)
        name = member.get("name")
        return str(name or "")

    for gf in dashboard_files:
        try:
            dashboard = load_yaml(gf)
        except yaml.YAMLError as e:
            errors.append(f"{gf}: yaml parse error: {e}")
            continue
        if dashboard is None:
            errors.append(f"{gf}: empty file")
            continue
        if not isinstance(dashboard, dict):
            errors.append(f"{gf}: top-level must be a mapping")
            continue

        errors.extend(schema_errors(dashboard, "dashboard", gf))
        for list_name in ("taking", "candidates", "declined"):
            members = dashboard.get(list_name) or []
            if not isinstance(members, list):
                continue
            labels = [member_label(member) for member in members if isinstance(member, dict)]
            if labels != sorted(labels, key=str.casefold):
                errors.append(f"{gf}: {list_name} must be sorted alphabetically")
            for i, member in enumerate(members):
                if not isinstance(member, dict):
                    continue
                ref = member.get("substance")
                if ref is None:
                    continue
                if ref not in substance_ids:
                    errors.append(
                        f"{gf}: {list_name}[{i}].substance '{ref}' has no matching substance card "
                        f"(expected at data/substances/{ref}.yaml)"
                    )
    return errors

