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
)
from planner.schema_validation import schema_errors
from planner.yaml_io import YamlValue


@dataclass(frozen=True, slots=True)
class _CanonicalTermContext:
    terms_by_predicate: Mapping[str, frozenset[str]]
    knowledge_fields: tuple[str, ...]


def check_substances(
    substance_files: list[Path],
    bundle: OntologyBundle,
) -> tuple[list[str], list[str], dict[str, Path]]:
    canonical_terms: _CanonicalTermContext | None = None
    errors: list[str] = []
    info: list[str] = []
    seen_ids: dict[str, Path] = {}

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

        know_raw = substance.get("knowledge") or {}
        know_raw = cast(dict[str, YamlValue], know_raw) if isinstance(know_raw, dict) else {}
        _validate_canonical_terms(sf, know_raw, canonical_terms, errors)
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


def _validate_canonical_terms(
    path: Path,
    knowledge: dict[str, YamlValue],
    context: _CanonicalTermContext,
    errors: list[str],
) -> None:
    for category in context.knowledge_fields:
        _append_unknown_term_errors(
            path,
            category,
            knowledge.get(category),
            context.terms_by_predicate.get(f"knowledge.{category}", frozenset()),
            errors,
        )


def _canonical_term_context(bundle: OntologyBundle) -> _CanonicalTermContext:
    return _CanonicalTermContext(
        terms_by_predicate=canonical_terms_by_predicate(bundle),
        knowledge_fields=knowledge_category_fields(bundle),
    )


def _append_unknown_term_errors(
    path: Path, category: str, values: YamlValue | None, known: frozenset[str], errors: list[str]
) -> None:
    if not isinstance(values, list):
        return
    for value in values:
        term = value.get("value") if isinstance(value, Mapping) else value
        if isinstance(term, str) and term not in known:
            errors.append(f"{path}: term '{category}:{term}' is not in canonical ontology vocabulary")
