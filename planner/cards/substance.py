"""Substance card loading, naming, and registry helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping, normalize_filename_part
from planner.contracts import CardLoadError, Concern, ConcernKind, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.schema_enums import schema_enum_values
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
        schedule_values = _string_tuple_fields(sched, schedule_assignment_fields(bundle))
        knowledge_values = _string_tuple_fields(know, knowledge_category_fields(bundle))
        return Substance(
            id=cast(str, data["id"]),
            name=cast(str, data["name"]),
            form=cast(str | None, data.get("form")),
            aliases=_string_tuple(data.get("aliases") or ()),
            notes=cast(str | None, data.get("notes")),
            concerns=_concerns(data.get("concerns"), path, bundle),
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


def _string_tuple_fields(data: dict[str, object], fields: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    return {field: _string_tuple(data.get(field) or ()) for field in fields}


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
