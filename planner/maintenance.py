"""Auto-maintenance: file-rename helpers, normalization, lock management.

Maintenance reads via load_card_mapping (raw dict) for the rewrite paths so
yaml.safe_dump preserves on-disk key order. Read-only checks use the typed
dataclass loaders.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import yaml

from planner.cards._common import generate_stable_id, load_card_mapping
from planner.cards.product import canonical_product_filename
from planner.cards.substance import canonical_substance_filename
from planner.contracts import CardLoadError, Product, Substance
from planner.io import (
    DATA_DIR,
    MAINTENANCE_LOCK_DIR,
    load_yaml,
    strip_root_prefix,
)


def _substance_from_mapping(data: dict[str, Any]) -> Substance:
    """Build a Substance from a partially-validated raw mapping.

    Used by maintenance to compute canonical filenames without forcing the
    yaml file through full schema validation (auto-maintenance runs before
    check, on data that may still need normalisation).
    """
    name_raw = data.get("name")
    form_raw = data.get("form")
    return Substance(
        id=str(data["id"]),
        name=name_raw if isinstance(name_raw, str) else "",
        form=form_raw if isinstance(form_raw, str) else None,
    )


def _product_from_mapping(data: dict[str, Any]) -> Product:
    name_raw = data.get("name")
    brand_raw = data.get("brand")
    return Product(
        id=str(data["id"]),
        name=name_raw if isinstance(name_raw, str) else "",
        components=(),
        brand=brand_raw if isinstance(brand_raw, str) else None,
    )


def _normalize_card_dir(
    cards_dir: Path,
    canonical_fn: Callable[[Any], str],
    id_prefix: str,
) -> tuple[dict[str, str], int] | None:
    """Normalize filenames and assign stable IDs for all YAML cards in cards_dir.

    Returns (renames, file_move_count) where renames maps old stem → new id
    for cards that received a generated id. Returns None on any error that
    should abort auto-maintenance.
    """
    renames: dict[str, str] = {}
    file_moves: list[tuple[Path, Path]] = []

    for path in sorted(cards_dir.glob("*.yaml")):
        try:
            data = load_card_mapping(path, cards_dir.name)
        except CardLoadError as e:
            print(f"ERROR: {strip_root_prefix(e.message)}", file=sys.stderr)
            return None

        old_id = data.get("id")
        needs_new_id = not isinstance(old_id, str)
        if needs_new_id:
            data["id"] = generate_stable_id(id_prefix)

        new_path = cards_dir / canonical_fn(data)

        if needs_new_id:
            renames[str(path.stem)] = data["id"]

        if path != new_path:
            file_moves.append((path, new_path))

        if needs_new_id:
            try:
                path.write_text(
                    yaml.safe_dump(
                        data,
                        sort_keys=False,
                        default_flow_style=False,
                        allow_unicode=True,
                    )
                )
            except OSError as e:
                data["id"] = old_id
                print(
                    f"warning: could not write {cards_dir.name} id to {path}: {e}",
                    file=sys.stderr,
                )
                return None

    destinations = [destination for _source, destination in file_moves]
    if len(set(destinations)) != len(destinations):
        print(
            f"auto-maintenance aborted: duplicate {cards_dir.name} filename destination",
            file=sys.stderr,
        )
        return None

    for source, destination in file_moves:
        if destination.exists() and destination != source:
            print(
                "auto-maintenance aborted: destination exists: "
                f"{strip_root_prefix(str(destination))}",
                file=sys.stderr,
            )
            return None

    for source, destination in file_moves:
        source.rename(destination)

    return renames, len(file_moves)


def process_is_running(pid: int) -> bool:
    """Use kill(pid, 0) as a portable liveness probe; PermissionError means the process exists but we lack signal rights."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True

def read_lock_pid(lock_dir: Path) -> int | None:
    """Return the integer pid recorded in `<lock_dir>/pid`, or None on any IOError or non-numeric content (callers treat None as no owner)."""
    owner_path = lock_dir / "pid"
    try:
        raw_pid = owner_path.read_text().strip()
    except OSError:
        return None
    if not raw_pid.isdigit():
        return None
    return int(raw_pid)

def clear_stale_lock(lock_dir: Path) -> None:
    """Clear the lock directory iff its owning pid is dead; returns silently without clearing if the owner is still alive."""
    pid = read_lock_pid(lock_dir)
    if pid is not None and process_is_running(pid):
        return
    try:
        (lock_dir / "pid").unlink(missing_ok=True)
        lock_dir.rmdir()
    except OSError as e:
        print(f"warning: could not clear stale lock at {lock_dir}: {e}", file=sys.stderr)
        return

def acquire_maintenance_lock(
    lock_dir: Path = MAINTENANCE_LOCK_DIR,
    collect_errors: list[str] | None = None,
) -> bool:
    """mkdir-based lock: atomic on POSIX; clears a stale lock (dead pid) before retrying once."""
    try:
        lock_dir.mkdir()
    except FileExistsError:
        clear_stale_lock(lock_dir)
        try:
            lock_dir.mkdir()
        except FileExistsError:
            pid = read_lock_pid(lock_dir)
            owner = f" by pid {pid}" if pid is not None else ""
            msg = f"auto-maintenance skipped: another planner process is running{owner}"
            print(msg, file=sys.stderr)
            if collect_errors is not None:
                collect_errors.append(msg)
            return False
    try:
        (lock_dir / "pid").write_text(f"{os.getpid()}\n")
    except OSError as e:
        print(f"warning: could not write maintenance lock pid: {e}", file=sys.stderr)
        try:
            lock_dir.rmdir()
        except OSError:
            pass
        return False
    return True

def release_maintenance_lock(lock_dir: Path = MAINTENANCE_LOCK_DIR) -> None:
    try:
        (lock_dir / "pid").unlink(missing_ok=True)
        lock_dir.rmdir()
    except OSError as e:
        print(f"warning: could not release maintenance lock at {lock_dir}: {e}", file=sys.stderr)

def rewrite_stack_product_refs(
    stacks_data: dict[str, Any], product_renames: dict[str, str]
) -> None:
    for stack_name, items in stacks_data.items():
        if not isinstance(items, list):
            continue
        items_list = cast(list[Any], items)
        new_items: list[Any] = []
        for item in items_list:
            if isinstance(item, str):
                new_items.append(product_renames.get(item, item))
            else:
                new_items.append(item)
        stacks_data[stack_name] = new_items

def _rewrite_dict_refs_in_files(
    cards_dir: Path,
    card_kind: str,
    member_lists: tuple[str, ...],
    substance_renames: dict[str, str],
) -> None:
    """Iterate cards_dir/*.yaml; for each file, walk every list named in
    member_lists; for each dict member, replace `substance` field via
    substance_renames. Writes back only if any field changed.

    Used for products (member_lists=("components",)) and dashboards
    (member_lists=("taking", "candidates", "declined")).
    """
    if not cards_dir.exists():
        return
    for path in sorted(cards_dir.glob("*.yaml")):
        try:
            card = load_card_mapping(path, card_kind)
        except CardLoadError as e:
            print(f"warning: skipping {path}: {strip_root_prefix(e.message)}", file=sys.stderr)
            continue
        changed = False
        for list_name in member_lists:
            for member_obj in cast(list[Any], card.get(list_name) or []):
                if not isinstance(member_obj, dict):
                    continue
                member = cast(dict[str, Any], member_obj)
                old_ref = cast(str | None, member.get("substance"))
                if isinstance(old_ref, str) and old_ref in substance_renames:
                    member["substance"] = substance_renames[old_ref]
                    changed = True
        if changed:
            try:
                path.write_text(
                    yaml.safe_dump(
                        card,
                        sort_keys=False,
                        default_flow_style=False,
                        allow_unicode=True,
                    )
                )
            except OSError as e:
                print(f"warning: could not write {path}: {e}", file=sys.stderr)
                continue


def _rewrite_prefer_with_in_substances(
    substances_dir: Path,
    substance_renames: dict[str, str],
) -> None:
    """Rewrite each substance card's prefer_with list-of-strings via
    substance_renames. Writes only if the list changed.
    """
    for path in sorted(substances_dir.glob("*.yaml")):
        try:
            substance = load_card_mapping(path, "substance")
        except CardLoadError as e:
            print(f"warning: skipping {path}: {strip_root_prefix(e.message)}", file=sys.stderr)
            continue
        prefer_with = substance.get("prefer_with")
        if not isinstance(prefer_with, list):
            continue
        prefer_with_list = cast(list[Any], prefer_with)
        rewritten: list[Any] = []
        for item in prefer_with_list:
            if isinstance(item, str):
                rewritten.append(substance_renames.get(item, item))
            else:
                rewritten.append(item)
        if rewritten != prefer_with:
            substance["prefer_with"] = rewritten
            try:
                path.write_text(
                    yaml.safe_dump(
                        substance,
                        sort_keys=False,
                        default_flow_style=False,
                        allow_unicode=True,
                    )
                )
            except OSError as e:
                print(f"warning: could not write {path}: {e}", file=sys.stderr)
                continue


def rewrite_substance_refs(data_dir: Path, substance_renames: dict[str, str]) -> None:
    if not substance_renames:
        return
    _rewrite_dict_refs_in_files(
        data_dir / "products", "product", ("components",), substance_renames,
    )
    _rewrite_dict_refs_in_files(
        data_dir / "dashboards", "dashboard",
        ("taking", "candidates", "declined"), substance_renames,
    )
    _rewrite_prefer_with_in_substances(data_dir / "substances", substance_renames)

def normalize_substances(data_dir: Path) -> tuple[dict[str, str], int] | None:
    """Assign stable ids and canonical filenames to substance cards, then rewrite all cross-file substance refs to match."""
    result = _normalize_card_dir(
        data_dir / "substances",
        lambda d: canonical_substance_filename(_substance_from_mapping(d)),
        "sub",
    )
    if result is None:
        return None
    substance_renames, substance_file_moves = result
    rewrite_substance_refs(data_dir, substance_renames)
    return substance_renames, substance_file_moves

def auto_maintenance_needed(data_dir: Path | None = None) -> bool | None:
    """Detect whether normalize_* would do work.

    Returns:
        True  — at least one card needs renaming or id assignment.
        False — all cards conform; no work needed.
        None  — a CardLoadError was raised while reading a card; this is an
                error, not evidence that maintenance is unnecessary.  Callers
                must treat None as a hard error and abort rather than treating
                it as equivalent to False.

    Operates on raw dict mappings rather than typed dataclasses because
    the whole point of normalize_* is to fix on-disk cards that don't
    yet conform — a missing id is the signal to run maintenance, not a
    reason to bail out of the check.
    """
    if data_dir is None:
        data_dir = DATA_DIR
    substances_dir = data_dir / "substances"
    products_dir = data_dir / "products"

    for path in sorted(substances_dir.glob("*.yaml")):
        try:
            substance = load_card_mapping(path, "substance")
        except CardLoadError as e:
            print(
                f"auto-maintenance: could not read {path}: {strip_root_prefix(e.message)}",
                file=sys.stderr,
            )
            return None
        if not isinstance(substance.get("id"), str):
            return True
        if path != substances_dir / canonical_substance_filename(
            _substance_from_mapping(substance)
        ):
            return True

    for path in sorted(products_dir.glob("*.yaml")):
        try:
            product = load_card_mapping(path, "product")
        except CardLoadError as e:
            print(
                f"auto-maintenance: could not read {path}: {strip_root_prefix(e.message)}",
                file=sys.stderr,
            )
            return None
        if not isinstance(product.get("id"), str):
            return True
        if path != products_dir / canonical_product_filename(
            _product_from_mapping(product)
        ):
            return True

    return False

def run_auto_maintenance(
    data_dir: Path | None = None,
    *,
    suppress_output: bool = False,
    collect_errors: list[str] | None = None,
) -> int:
    """Acquire the maintenance lock only when work is actually needed, then delegate to the unlocked worker."""
    if data_dir is None:
        data_dir = DATA_DIR
    lock_acquired = False
    needs = auto_maintenance_needed(data_dir)
    if needs is None:
        return 1
    if needs:
        if not acquire_maintenance_lock(
            data_dir.parent / MAINTENANCE_LOCK_DIR.name,
            collect_errors=collect_errors,
        ):
            return 1
        lock_acquired = True

    try:
        return run_auto_maintenance_unlocked(data_dir, suppress_output=suppress_output)
    finally:
        if lock_acquired:
            release_maintenance_lock(data_dir.parent / MAINTENANCE_LOCK_DIR.name)

def run_auto_maintenance_unlocked(
    data_dir: Path | None = None, *, suppress_output: bool = False
) -> int:
    """Normalise substances and products in place; caller is responsible for holding the maintenance lock."""
    if data_dir is None:
        data_dir = DATA_DIR
    stacks_path = data_dir / "stacks.yaml"

    substance_result = normalize_substances(data_dir)
    if substance_result is None:
        return 1
    substance_renames, substance_file_moves = substance_result

    product_result = _normalize_card_dir(
        data_dir / "products",
        lambda d: canonical_product_filename(_product_from_mapping(d)),
        "prd",
    )
    if product_result is None:
        return 1
    product_renames, product_file_moves = product_result

    if stacks_path.exists() and product_renames:
        stacks_data = load_yaml(stacks_path)
        if isinstance(stacks_data, dict):
            rewrite_stack_product_refs(cast(dict[str, Any], stacks_data), product_renames)
            try:
                stacks_path.write_text(
                    yaml.safe_dump(
                        stacks_data,
                        sort_keys=False,
                        default_flow_style=False,
                        allow_unicode=True,
                    )
                )
            except OSError as e:
                print(
                    f"auto-maintenance: failed to write {strip_root_prefix(str(stacks_path))} "
                    f"after product renames committed; reconcile stacks.yaml manually: {e}",
                    file=sys.stderr,
                )
                return 1

    changed = (
        len(substance_renames)
        + substance_file_moves
        + len(product_renames)
        + product_file_moves
    )
    if changed:
        if suppress_output:
            print(f"auto-maintenance: renamed {changed} file(s)", file=sys.stderr)
        else:
            print(
                "normalized substances: "
                f"{len(substance_renames)} ids, {substance_file_moves} filenames"
            )
            for old_id, new_id in sorted(substance_renames.items()):
                print(f"  {old_id} -> {new_id}")
            print(
                "normalized products: "
                f"{len(product_renames)} ids, {product_file_moves} filenames"
            )
            for old_id, new_id in sorted(product_renames.items()):
                print(f"  {old_id} -> {new_id}")
    return 0
