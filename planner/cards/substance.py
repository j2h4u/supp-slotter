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
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.substance_fields import knowledge_category_fields, schedule_assignment_fields
from planner.paths import Paths
from planner.schema_validation import schema_errors


def load_substance(path: Path, bundle: OntologyBundle) -> Substance:
    """Load a substance card into a Substance dataclass."""
    data = load_card_mapping(path, "substance")
    errors = schema_errors(data, "substance", path, bundle)
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

        governance = _governance(data.get("schedule_governance"), path, bundle)
        schedule_values = _string_tuple_fields(sched, schedule_assignment_fields(bundle))
        knowledge_values = _string_tuple_fields(know, knowledge_category_fields(bundle))
        return Substance(
            id=cast(str, data["id"]),
            name=cast(str, data["name"]),
            form=cast(str | None, data.get("form")),
            aliases=_string_tuple(data.get("aliases") or ()),
            notes=cast(str | None, data.get("notes")),
            concerns=tuple(concerns),
            schedule_governance=governance,
            prefer_with=_string_tuple(sched.get("prefer_with") or ()),
            **schedule_values,
            **knowledge_values,
        )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def _string_tuple_fields(data: dict[str, object], fields: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    return {field: _string_tuple(data.get(field) or ()) for field in fields}


def _scope(raw_scope: object, path: Path, key: str, bundle: OntologyBundle) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw_scope, dict):
        return ()
    scope_values: list[tuple[str, str]] = []
    for raw_key, raw_value in cast(dict[str, object], raw_scope).items():
        scope_key = str(raw_key)
        scope_value = str(raw_value)
        dimension = bundle.runtime_program.scope_by_key.get(scope_key)
        if dimension is None:
            raise CardLoadError(path, f"{path}: schedule_governance[{key}] has unknown scope dimension {scope_key!r}")
        if scope_key != "product" and scope_value not in dimension.values:
            raise CardLoadError(
                path,
                f"{path}: schedule_governance[{key}] has unsupported scope value {scope_key}={scope_value!r}",
            )
        scope_values.append((scope_key, scope_value))
    return tuple(sorted(scope_values))


def _governance(value: object, path: Path, bundle: OntologyBundle) -> dict[str, ScheduleGovernance]:
    if not isinstance(value, dict):
        return {}
    records = cast(dict[str, object], value)
    out: dict[str, ScheduleGovernance] = {}
    for key in sorted(records):
        raw_value = records[key]
        if not isinstance(raw_value, dict):
            raise CardLoadError(path, f"{path}: invalid schedule_governance[{key}]")
        raw = cast(dict[str, object], raw_value)
        scope = _scope(raw.get("scope"), path, key, bundle)
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


def load_substance_registry(paths: Paths, bundle: OntologyBundle) -> dict[str, Substance]:
    substances: dict[str, Substance] = {}
    substance_files = sorted(paths.substances.glob("*.yaml"))
    skipped = 0
    for sf in substance_files:
        try:
            substance = load_substance(sf, bundle)
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
