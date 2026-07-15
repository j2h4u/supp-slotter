"""Substance card loading, naming, and registry helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping, normalize_filename_part
from planner.contracts import (
    CardLoadError,
    Concern,
    ConcernKind,
    EnforcementCap,
    GovernanceStatus,
    ScheduleGovernance,
    SlotPolicyEvidence,
    Substance,
)
from planner.paths import Paths
from planner.schema_validation import schema_errors


def load_substance(path: Path) -> Substance:
    """Load a substance card into a Substance dataclass."""
    data = load_card_mapping(path, "substance")
    errors = schema_errors(data, "substance", path)
    if errors:
        raise CardLoadError(path, errors[0])
    sched_obj = data.get("schedule") or {}
    know_obj = data.get("knowledge") or {}
    sched = cast(dict[str, object], sched_obj) if isinstance(sched_obj, dict) else {}
    know = cast(dict[str, object], know_obj) if isinstance(know_obj, dict) else {}
    try:
        concerns: list[Concern] = []
        concerns_raw = data.get("concerns") or ()
        if isinstance(concerns_raw, (list, tuple)):
            for concern in concerns_raw:
                if not isinstance(concern, dict):
                    continue
                concern_dict = cast(dict[str, object], concern)
                kind = concern_dict.get("kind")
                text = concern_dict.get("text")
                if isinstance(kind, str) and isinstance(text, str) and kind in {"safety", "model_gap", "data_quality"}:
                    concerns.append(Concern(kind=cast(ConcernKind, kind), text=text))

        def _string_tuple(value: object) -> tuple[str, ...]:
            if isinstance(value, (list, tuple)):
                return tuple(item for item in value if isinstance(item, str))
            return ()

        governance = _governance(data.get("schedule_governance"), path)
        return Substance(
            id=cast(str, data["id"]),
            name=cast(str, data["name"]),
            form=cast(str | None, data.get("form")),
            aliases=_string_tuple(data.get("aliases") or ()),
            notes=cast(str | None, data.get("notes")),
            concerns=tuple(concerns),
            intake=_string_tuple(sched.get("intake") or ()),
            timing=_string_tuple(sched.get("timing") or ()),
            activity=_string_tuple(sched.get("activity") or ()),
            schedule_governance=governance,
            prefer_with=_string_tuple(sched.get("prefer_with") or ()),
            kind=_string_tuple(know.get("kind") or ()),
            role=_string_tuple(know.get("role") or ()),
            quality=_string_tuple(know.get("quality") or ()),
            effect=_string_tuple(know.get("effect") or ()),
            risk=_string_tuple(know.get("risk") or ()),
            context=_string_tuple(know.get("context") or ()),
            pathway=_string_tuple(know.get("pathway") or ()),
        )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e


def _governance(value: object, path: Path) -> dict[str, ScheduleGovernance]:
    if not isinstance(value, dict):
        return {}
    records = cast(dict[str, object], value)
    out: dict[str, ScheduleGovernance] = {}
    for key in sorted(records):
        raw_value = records[key]
        if not isinstance(raw_value, dict):
            raise CardLoadError(path, f"{path}: invalid schedule_governance[{key}]")
        raw = cast(dict[str, object], raw_value)
        raw_scope = raw.get("scope")
        scope = (
            tuple(sorted((str(k), str(v)) for k, v in cast(dict[str, object], raw_scope).items()))
            if isinstance(raw_scope, dict)
            else ()
        )
        evidence: list[SlotPolicyEvidence] = []
        raw_evidence = raw.get("evidence")
        if isinstance(raw_evidence, list):
            for item_value in cast(list[object], raw_evidence):
                if isinstance(item_value, dict):
                    item = cast(dict[str, object], item_value)
                    evidence.append(
                        SlotPolicyEvidence(
                            str(item.get("source", "")), str(item.get("supports", "")), str(item.get("limitations", ""))
                        )
                    )
        out[key] = ScheduleGovernance(
            status=cast(GovernanceStatus, raw.get("status", "approved")),
            enforcement_cap=cast(EnforcementCap, raw.get("enforcement_cap", "none")),
            scope=scope,
            evidence=tuple(evidence),
            owner=str(raw.get("owner", "")),
            review_by=str(raw.get("review_by", "")),
            evidence_gap=cast(str | None, raw.get("evidence_gap")),
            retirement_reason=cast(str | None, raw.get("retirement_reason")),
        )
    return out


def substance_slug(substance: Substance) -> str:
    if substance.form:
        return normalize_filename_part(f"{substance.name} {substance.form}")
    return normalize_filename_part(substance.name)


def canonical_substance_filename(substance: Substance) -> str:
    return f"{substance_slug(substance)}__{substance.id}.yaml"


def substance_names(substances: dict[str, Substance]) -> set[str]:
    return {substance.name for substance in substances.values() if substance.name}


def load_substance_registry(paths: Paths) -> dict[str, Substance]:
    substances: dict[str, Substance] = {}
    substance_files = sorted(paths.substances.glob("*.yaml"))
    skipped = 0
    for sf in substance_files:
        try:
            substance = load_substance(sf)
        except CardLoadError as e:
            print(f"warning: skipping substance card: {e.message}", file=sys.stderr)
            skipped += 1
            continue
        substances[substance.id] = substance
    if skipped:
        print(
            f"warning: loaded {len(substances)}/{len(substance_files)} substance cards; {skipped} skipped",
            file=sys.stderr,
        )
    return substances


def format_substance_name(substance: Substance) -> str:
    name = substance.name or substance.id or "unknown"
    if substance.form:
        return f"{name} ({substance.form})"
    return name
