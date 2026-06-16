"""Substance-card validation for `planner check`."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from planner.cards._common import load_card_mapping
from planner.cards.substance import canonical_substance_filename
from planner.contracts import CardLoadError, Substance
from planner.paths import Paths
from planner.schema_validation import schema_errors


def check_substances(
    substance_files: list[Path],
    trait_ids: set[str],
    paths: Paths,
    *,
    prefer_with_registry: dict[str, Path] | None = None,
) -> tuple[list[str], list[str], dict[str, Path]]:
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

        errors.extend(schema_errors(substance, "substance", sf))
        _validate_substance_identity(sf, substance, seen_ids, errors)
        sid_raw = substance.get("id")
        if not isinstance(sid_raw, str):
            continue

        sched_raw: dict[str, Any] = cast(dict[str, Any], substance.get("schedule") or {})
        know_raw: dict[str, Any] = cast(dict[str, Any], substance.get("knowledge") or {})
        _collect_prefer_with_refs(sf, sid_raw, sched_raw, prefer_with_refs, errors)
        _validate_schedule_traits(sf, sched_raw, trait_ids, errors)
        _validate_review_traits(sf, know_raw, trait_ids, paths, errors)

    target_ids = prefer_with_registry or seen_ids
    for sf, _source, target in prefer_with_refs:
        if target not in target_ids:
            errors.append(f"{sf}: prefer_with target '{target}' has no matching substance card")
    return errors, info, seen_ids


def _validate_substance_identity(
    path: Path,
    substance: dict[str, Any],
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
    schedule: dict[str, Any],
    prefer_with_refs: list[tuple[Path, str, str]],
    errors: list[str],
) -> None:
    prefer_with_raw: Any = schedule.get("prefer_with") or []
    prefer_with_list = cast(list[Any], prefer_with_raw)
    for other in prefer_with_list:
        if other == substance_id:
            errors.append(f"{path}: prefer_with references self ('{substance_id}')")
        elif isinstance(other, str):
            prefer_with_refs.append((path, substance_id, other))


def _validate_schedule_traits(
    path: Path,
    schedule: dict[str, Any],
    trait_ids: set[str],
    errors: list[str],
) -> None:
    for namespace in ("intake", "timing", "activity"):
        ns_raw: Any = schedule.get(namespace) or []
        ns_list = cast(list[Any], ns_raw)
        for slug in ns_list:
            if not isinstance(slug, str):
                continue
            _validate_registered_trait(path, namespace, slug, trait_ids, errors)


def _validate_review_traits(
    path: Path,
    knowledge: dict[str, Any],
    trait_ids: set[str],
    paths: Paths,
    errors: list[str],
) -> None:
    for namespace in ("is", "effect", "risk", "pathway", "context"):
        ns_raw: Any = knowledge.get(namespace) or []
        ns_list = cast(list[Any], ns_raw)
        for slug in ns_list:
            if not isinstance(slug, str):
                continue
            if namespace == "context":
                _validate_context_dashboard(path, slug, paths, errors)
            else:
                _validate_registered_trait(path, namespace, slug, trait_ids, errors)


def _validate_registered_trait(
    path: Path,
    namespace: str,
    slug: str,
    trait_ids: set[str],
    errors: list[str],
) -> None:
    full_id = f"{namespace}:{slug}"
    if full_id in trait_ids:
        return
    errors.append(
        f"{path}: Unknown trait '{slug}' under namespace '{namespace}:' "
        f"— register it in data/traits/ under '{namespace}:' first "
        f"(with label and description)."
    )


def _validate_context_dashboard(
    path: Path,
    slug: str,
    paths: Paths,
    errors: list[str],
) -> None:
    if (paths.dashboards / f"{slug}.yaml").exists():
        return
    errors.append(f"{path}: Unknown review context '{slug}' — create data/dashboards/{slug}.yaml first.")
