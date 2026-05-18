"""Substance card loading, naming, and registry helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

from planner.cards._common import load_card_mapping, normalize_filename_part
from planner.contracts import CardLoadError, Concern, Substance
from planner.paths import Paths
from planner.schema_validation import schema_errors


def load_substance(path: Path) -> Substance:
    """Load a substance card into a Substance dataclass."""
    data = load_card_mapping(path, "substance")
    errors = schema_errors(data, "substance", path)
    if errors:
        raise CardLoadError(path, errors[0])
    sched: dict[str, Any] = cast(dict[str, Any], data.get("schedule") or {})
    know: dict[str, Any] = cast(dict[str, Any], data.get("knowledge") or {})
    try:
        return Substance(
            id=data["id"],
            name=data["name"],
            form=data.get("form"),
            aliases=tuple(data.get("aliases") or ()),
            notes=data.get("notes"),
            concerns=tuple(
                Concern(kind=cast(dict[str, Any], c)["kind"], text=cast(dict[str, Any], c)["text"])
                for c in cast(list[Any], data.get("concerns") or [])
                if isinstance(c, dict)
            ),
            intake=tuple(cast(list[Any], sched.get("intake") or ())),
            timing=tuple(cast(list[Any], sched.get("timing") or ())),
            activity=tuple(cast(list[Any], sched.get("activity") or ())),
            prefer_with=tuple(cast(list[Any], sched.get("prefer_with") or ())),
            is_=tuple(cast(list[Any], know.get("is") or ())),
            effect=tuple(cast(list[Any], know.get("effect") or ())),
            risk=tuple(cast(list[Any], know.get("risk") or ())),
            context=tuple(cast(list[Any], know.get("context") or ())),
            pathway=tuple(cast(list[Any], know.get("pathway") or ())),
        )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e


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
            f"warning: loaded {len(substances)}/{len(substance_files)} "
            f"substance cards; {skipped} skipped",
            file=sys.stderr,
        )
    return substances


def format_substance_name(substance: Substance) -> str:
    name = substance.name or substance.id or "unknown"
    if substance.form:
        return f"{name} ({substance.form})"
    return name
