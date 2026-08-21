"""Substance card loading, naming, and registry helpers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping, normalize_filename_part
from planner.contracts import (
    CardLoadError,
    Concern,
    ConcernKind,
    KnowledgeAssertion,
    ScheduleAssertion,
    SchedulingAssessment,
    Substance,
)
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.runtime_program import axis_cardinality_violation
from planner.ontology.schema_enums import schema_enum_values
from planner.ontology.substance_fields import (
    canonical_terms_by_predicate,
    knowledge_category_fields,
    schedule_assignment_fields,
)
from planner.paths import Paths
from planner.schema_validation import schema_errors


def load_substance(path: Path, bundle: OntologyBundle) -> Substance:
    """Load a substance card into a Substance dataclass."""
    data = load_card_mapping(path, "substance")
    errors = schema_errors(data, "substance", path, bundle)
    if errors:
        raise CardLoadError(path, errors[0])
    schedule = cast(dict[str, object], data.get("schedule") or {})
    knowledge = cast(dict[str, object], data.get("knowledge") or {})
    schedule_assertions = _schedule_assertions(schedule, path, bundle)
    try:
        return Substance(
            id=cast(str, data["id"]),
            name=cast(str, data["name"]),
            form=cast(str | None, data.get("form")),
            aliases=_string_tuple(data.get("aliases") or ()),
            notes=cast(str | None, data.get("notes")),
            concerns=_concerns(data.get("concerns"), path, bundle),
            prefer_with=_string_tuple(schedule.get("prefer_with") or ()),
            knowledge_assertions=_knowledge_assertions(knowledge, path, bundle),
            schedule_assertions=schedule_assertions,
            scheduling_assessments=_scheduling_assessments(
                data.get("scheduling_assessment"), path, bundle, schedule_assertions
            ),
        )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        values = cast(list[object] | tuple[object, ...], value)
        return tuple(item for item in values if isinstance(item, str))
    return ()


def _concerns(value: object, path: Path, bundle: OntologyBundle) -> tuple[Concern, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise CardLoadError(path, f"{path}: concerns must be a list")
    concerns_raw = cast(list[object] | tuple[object, ...], value)
    concern_kinds = frozenset(schema_enum_values(bundle, "ConcernKind"))
    concerns: list[Concern] = []
    for index, concern in enumerate(concerns_raw):
        if not isinstance(concern, dict):
            raise CardLoadError(path, f"{path}: concerns[{index}] must be a mapping")
        concern_dict = cast(dict[str, object], concern)
        kind = concern_dict.get("kind")
        text = concern_dict.get("text")
        if not isinstance(kind, str) or kind not in concern_kinds:
            raise CardLoadError(path, f"{path}: concerns[{index}].kind is not in ontology ConcernKind")
        if not isinstance(text, str) or not text:
            raise CardLoadError(path, f"{path}: concerns[{index}].text must be non-empty")
        concerns.append(Concern(kind=cast(ConcernKind, kind), text=text))
    return tuple(concerns)


def _knowledge_assertions(
    value: dict[str, object], path: Path, bundle: OntologyBundle
) -> tuple[KnowledgeAssertion, ...]:
    assertions: list[KnowledgeAssertion] = []
    canonical_terms = canonical_terms_by_predicate(bundle)
    for category in knowledge_category_fields(bundle):
        values = value.get(category) or ()
        if not isinstance(values, (list, tuple)):
            raise CardLoadError(path, f"{path}: knowledge.{category} must be a list")
        values = cast(list[object] | tuple[object, ...], values)
        predicate = f"knowledge.{category}"
        known = canonical_terms.get(predicate, frozenset())
        state_values = frozenset(schema_enum_values(bundle, "ResearchState"))
        for index, raw in enumerate(values):
            term, state, sources = _knowledge_record(raw, path, f"{predicate}[{index}]")
            if not isinstance(term, str) or term not in known:
                raise CardLoadError(path, f"{path}: term '{predicate}:{term}' is not in canonical ontology vocabulary")
            if not isinstance(state, str) or state not in state_values:
                raise CardLoadError(
                    path, f"{path}: {predicate}[{index}].research_state is not in ontology ResearchState"
                )
            if state != "unassessed" and not sources:
                raise CardLoadError(path, f"{path}: {predicate}[{index}].sources must be non-empty for {state!r}")
            assertions.append(KnowledgeAssertion(category, term, state, sources))
    return tuple(assertions)


def _knowledge_record(raw: object, path: Path, label: str) -> tuple[object, object, tuple[str, ...]]:
    if isinstance(raw, str):
        return raw, "unassessed", ()
    if not isinstance(raw, Mapping):
        raise CardLoadError(path, f"{path}: {label} must be a string or mapping")
    record = cast(Mapping[str, object], raw)
    if set(record) - {"value", "research_state", "sources"} or "value" not in record:
        raise CardLoadError(path, f"{path}: {label} has unsupported fields")
    state = record.get("research_state", "unassessed")
    raw_sources = record.get("sources", [])
    if not isinstance(raw_sources, list) or any(
        not isinstance(source, str) or not source.strip() for source in raw_sources
    ):
        raise CardLoadError(path, f"{path}: {label}.sources must be a list of non-empty strings")
    return record["value"], state, tuple(cast(list[str], raw_sources))


def _schedule_assertions(value: dict[str, object], path: Path, bundle: OntologyBundle) -> tuple[ScheduleAssertion, ...]:
    assertions: list[ScheduleAssertion] = []
    axis_by_field = {row.assignment_field: row for row in bundle.runtime_program.assignment_axes}
    canonical_terms = canonical_terms_by_predicate(bundle)
    for field in schedule_assignment_fields(bundle):
        values = value.get(field) or ()
        if not isinstance(values, (list, tuple)):
            raise CardLoadError(path, f"{path}: schedule.{field} must be a list")
        values = cast(list[object] | tuple[object, ...], values)
        axis_row = axis_by_field[field]
        violation = axis_cardinality_violation(axis_row, len(values))
        if violation is not None:
            raise CardLoadError(path, f"{path}: schedule.{field} {violation}")
        assertions.extend(
            ScheduleAssertion(axis_row.axis, term)
            for term in _canonical_terms(values, path, f"schedule.{axis_row.axis}", canonical_terms)
        )
    return tuple(assertions)


def _scheduling_assessments(
    value: object,
    path: Path,
    bundle: OntologyBundle,
    schedule_assertions: tuple[ScheduleAssertion, ...],
) -> tuple[SchedulingAssessment, ...]:
    """Load review metadata and join preference policies to same-axis facts."""
    if value is None:
        return ()
    if not isinstance(value, dict):
        raise CardLoadError(path, f"{path}: scheduling_assessment must be a mapping")
    assessment = cast(dict[str, object], value)
    conclusion_values = frozenset(schema_enum_values(bundle, "SchedulingAssessmentConclusion"))
    axis_rows = sorted(bundle.runtime_program.assignment_axes, key=lambda row: (row.order, row.id))
    assertions_by_axis: dict[str, tuple[str, ...]] = {
        row.axis: tuple(item.value for item in schedule_assertions if item.axis == row.axis) for row in axis_rows
    }
    records: list[SchedulingAssessment] = []
    for axis_row in axis_rows:
        raw = assessment.get(axis_row.assignment_field)
        if raw is None:
            continue
        records.append(
            _scheduling_assessment_record(
                raw,
                axis=axis_row.axis,
                path=path,
                conclusion_values=conclusion_values,
                schedule_values=assertions_by_axis.get(axis_row.axis, ()),
            )
        )
    return tuple(records)


def _scheduling_assessment_record(
    value: object,
    *,
    axis: str,
    path: Path,
    conclusion_values: frozenset[str],
    schedule_values: tuple[str, ...],
) -> SchedulingAssessment:
    if not isinstance(value, dict):
        raise CardLoadError(path, f"{path}: scheduling_assessment.{axis} must be a mapping")
    record = cast(dict[str, object], value)
    conclusion = record.get("conclusion")
    if not isinstance(conclusion, str) or conclusion not in conclusion_values:
        raise CardLoadError(path, f"{path}: scheduling_assessment.{axis}.conclusion is not in ontology vocabulary")
    policy = record.get("policy")
    if conclusion == "supports_preference":
        if not isinstance(policy, str) or not policy.strip():
            raise CardLoadError(path, f"{path}: scheduling_assessment.{axis}.policy is required")
        if policy not in schedule_values:
            raise CardLoadError(
                path,
                f"{path}: scheduling_assessment.{axis}.policy {policy!r} has no matching schedule assertion",
            )
    elif policy is not None:
        raise CardLoadError(path, f"{path}: scheduling_assessment.{axis}.policy is forbidden for {conclusion}")
    sources = record.get("sources")
    if (
        not isinstance(sources, list)
        or not sources
        or any(not isinstance(source, str) or not source.strip() for source in sources)
    ):
        raise CardLoadError(path, f"{path}: scheduling_assessment.{axis}.sources must be non-empty")
    summary = record.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise CardLoadError(path, f"{path}: scheduling_assessment.{axis}.summary must be non-empty")
    return SchedulingAssessment(
        axis=axis,
        conclusion=conclusion,
        policy=policy if isinstance(policy, str) else None,
        sources=tuple(cast(list[str], sources)),
        summary=summary,
    )


def _canonical_terms(
    values: list[object] | tuple[object, ...],
    path: Path,
    predicate: str,
    terms_by_predicate: Mapping[str, frozenset[str]],
) -> tuple[str, ...]:
    """Validate assertion slugs against the verified generated registry."""

    known = terms_by_predicate.get(predicate, frozenset())
    terms: list[str] = []
    for term in values:
        if isinstance(term, str) and term:
            if term not in known:
                raise CardLoadError(path, f"{path}: term '{predicate}:{term}' is not in canonical ontology vocabulary")
            terms.append(term)
    return tuple(terms)


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
    errors: list[CardLoadError] = []
    for sf in substance_files:
        try:
            substance = load_substance(sf, bundle)
        except CardLoadError as e:
            errors.append(e)
            continue
        previous = substances.get(substance.id)
        if previous is not None:
            errors.append(CardLoadError(sf, f"{sf}: duplicate substance id {substance.id!r}"))
            continue
        substances[substance.id] = substance
    if errors:
        _raise_registry_errors("substance", paths.substances, errors)
    return substances


def _raise_registry_errors(kind: str, directory: Path, errors: list[CardLoadError]) -> None:
    details = "\n".join(f"- {error.message}" for error in errors)
    raise CardLoadError(directory, f"{directory}: failed to load {len(errors)} {kind} card(s):\n{details}")


def format_substance_name(substance: Substance) -> str:
    name = substance.name or substance.id or "unknown"
    if substance.form:
        return f"{name} ({substance.form})"
    return name
