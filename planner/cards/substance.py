"""Substance card loading, naming, and registry helpers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping, normalize_filename_part
from planner.contracts import CardLoadError, Concern, ConcernKind, KnowledgeAssertion, ScheduleAssertion, Substance
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
            schedule_assertions=_schedule_assertions(schedule, path, bundle),
        )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def _concerns(value: object, path: Path, bundle: OntologyBundle) -> tuple[Concern, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise CardLoadError(path, f"{path}: concerns must be a list")
    concern_kinds = frozenset(schema_enum_values(bundle, "ConcernKind"))
    concerns: list[Concern] = []
    for index, concern in enumerate(cast(list[object] | tuple[object, ...], value)):
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
        predicate = f"knowledge.{category}"
        assertions.extend(
            KnowledgeAssertion(category, term) for term in _canonical_terms(values, path, predicate, canonical_terms)
        )
    return tuple(assertions)


def _schedule_assertions(value: dict[str, object], path: Path, bundle: OntologyBundle) -> tuple[ScheduleAssertion, ...]:
    assertions: list[ScheduleAssertion] = []
    axis_by_field = {row.assignment_field: row for row in bundle.runtime_program.assignment_axes}
    canonical_terms = canonical_terms_by_predicate(bundle)
    for field in schedule_assignment_fields(bundle):
        values = value.get(field) or ()
        if not isinstance(values, (list, tuple)):
            raise CardLoadError(path, f"{path}: schedule.{field} must be a list")
        axis_row = axis_by_field[field]
        violation = axis_cardinality_violation(axis_row, len(values))
        if violation is not None:
            raise CardLoadError(path, f"{path}: schedule.{field} {violation}")
        assertions.extend(
            ScheduleAssertion(axis_row.axis, term)
            for term in _canonical_terms(values, path, f"schedule.{axis_row.axis}", canonical_terms)
        )
    return tuple(assertions)


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
