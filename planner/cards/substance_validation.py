"""Substance-card validation for `planner check`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping
from planner.cards.substance import canonical_substance_filename
from planner.contracts import CardLoadError, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.substance_fields import (
    canonical_terms_by_predicate,
    knowledge_category_fields,
    schedule_assignment_fields,
)
from planner.paths import Paths
from planner.schema_validation import schema_errors
from planner.yaml_io import YamlValue


@dataclass(frozen=True, slots=True)
class _CanonicalTermContext:
    terms_by_predicate: Mapping[str, frozenset[str]]
    schedule_fields: tuple[str, ...]
    knowledge_fields: tuple[str, ...]
    schedule_axis_by_field: tuple[tuple[str, str], ...]


def check_substances(
    substance_files: list[Path],
    trait_ids: set[str],
    paths: Paths,
    bundle: OntologyBundle,
    *,
    prefer_with_registry: dict[str, Path] | None = None,
) -> tuple[list[str], list[str], dict[str, Path]]:
    canonical_terms: _CanonicalTermContext | None = None
    errors: list[str] = []
    info: list[str] = []
    seen_ids: dict[str, Path] = {}
    prefer_with_refs: list[tuple[Path, str, str]] = []

    for sf in substance_files:
        try:
            substance = load_card_mapping(sf, "substance")
        except CardLoadError as e:
            errors.append(e.message)
            continue

        if canonical_terms is None:
            canonical_terms = _canonical_term_context(bundle)

        errors.extend(schema_errors(substance, "substance", sf, bundle))
        _validate_substance_identity(sf, substance, seen_ids, errors)
        sid_raw = substance.get("id")
        if not isinstance(sid_raw, str):
            continue

        sched_raw = substance.get("schedule") or {}
        know_raw = substance.get("knowledge") or {}
        sched_raw = cast(dict[str, YamlValue], sched_raw) if isinstance(sched_raw, dict) else {}
        know_raw = cast(dict[str, YamlValue], know_raw) if isinstance(know_raw, dict) else {}
        _collect_prefer_with_refs(sf, sid_raw, sched_raw, prefer_with_refs, errors)
        _validate_canonical_terms(sf, sched_raw, know_raw, canonical_terms, errors)

    target_ids = prefer_with_registry or seen_ids
    for sf, _source, target in prefer_with_refs:
        if target not in target_ids:
            errors.append(f"{sf}: prefer_with target '{target}' has no matching substance card")
    return errors, info, seen_ids


def _validate_substance_identity(
    path: Path,
    substance: dict[str, YamlValue],
    seen_ids: dict[str, Path],
    errors: list[str],
) -> None:
    sid_raw = substance.get("id")
    if not isinstance(sid_raw, str):
        return

    name_raw = substance.get("name")
    form_raw = substance.get("form")
    expected_filename = canonical_substance_filename(
        Substance(
            id=sid_raw,
            name=name_raw if isinstance(name_raw, str) else "",
            form=form_raw if isinstance(form_raw, str) else None,
        )
    )
    if path.name != expected_filename:
        errors.append(f"{path}: substance filename must be '{expected_filename}'")
    if sid_raw in seen_ids:
        errors.append(f"{path}: duplicate id '{sid_raw}' (also in {seen_ids[sid_raw]})")
    else:
        seen_ids[sid_raw] = path


def _collect_prefer_with_refs(
    path: Path,
    substance_id: str,
    schedule: dict[str, YamlValue],
    prefer_with_refs: list[tuple[Path, str, str]],
    errors: list[str],
) -> None:
    prefer_with_raw = schedule.get("prefer_with") or []
    if not isinstance(prefer_with_raw, list):
        return
    for other in prefer_with_raw:
        if other == substance_id:
            errors.append(f"{path}: prefer_with references self ('{substance_id}')")
        elif isinstance(other, str):
            prefer_with_refs.append((path, substance_id, other))


def _validate_canonical_terms(
    path: Path,
    schedule: dict[str, YamlValue],
    knowledge: dict[str, YamlValue],
    context: _CanonicalTermContext,
    errors: list[str],
) -> None:
    schedule_axis_by_field = dict(context.schedule_axis_by_field)
    for field in context.schedule_fields:
        axis = schedule_axis_by_field.get(field)
        if axis is None:
            continue
        _append_unknown_schedule_term_errors(
            path, axis, schedule.get(field), context.terms_by_predicate.get(f"schedule.{axis}", frozenset()), errors
        )
    for category in context.knowledge_fields:
        _append_unknown_term_errors(
            path,
            category,
            knowledge.get(category),
            context.terms_by_predicate.get(f"knowledge.{category}", frozenset()),
            errors,
        )


def _canonical_term_context(bundle: OntologyBundle) -> _CanonicalTermContext:
    assignment_axes = tuple(
        (row.assignment_field, row.axis)
        for row in sorted(bundle.runtime_program.assignment_axes, key=lambda row: (row.order, row.id))
    )
    return _CanonicalTermContext(
        terms_by_predicate=canonical_terms_by_predicate(bundle),
        schedule_fields=schedule_assignment_fields(bundle),
        knowledge_fields=knowledge_category_fields(bundle),
        schedule_axis_by_field=assignment_axes,
    )


def _append_unknown_schedule_term_errors(
    path: Path,
    axis: str,
    values: YamlValue | None,
    known: frozenset[str],
    errors: list[str],
) -> None:
    if not isinstance(values, list):
        return
    errors.extend(
        f"{path}: term '{axis}:{term}' is not in canonical ontology vocabulary"
        for term in values
        if isinstance(term, str) and term not in known
    )


def _append_unknown_term_errors(
    path: Path, category: str, values: YamlValue | None, known: frozenset[str], errors: list[str]
) -> None:
    if not isinstance(values, list):
        return
    errors.extend(
        f"{path}: term '{category}:{term}' is not in canonical ontology vocabulary"
        for term in values
        if isinstance(term, str) and term not in known
    )
