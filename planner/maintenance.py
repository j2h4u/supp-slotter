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
    display_message,
    load_yaml,
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
        traits=tuple(data.get("traits") or ()),
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
            print(f"ERROR: {display_message(e.message)}", file=sys.stderr)
            return None

        old_id = data.get("id")
        generated_id = not isinstance(old_id, str)
        if generated_id:
            data["id"] = generate_stable_id(id_prefix)

        new_path = cards_dir / canonical_fn(data)

        if generated_id:
            renames[str(path.stem)] = data["id"]

        if path != new_path:
            file_moves.append((path, new_path))

        if generated_id:
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
                data["id"] = old_id  # restore before returning
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
                f"{display_message(str(destination))}",
                file=sys.stderr,
            )
            return None

    for source, destination in file_moves:
        source.rename(destination)

    return renames, len(file_moves)


def process_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True

def read_lock_pid(lock_dir: Path) -> int | None:
    owner_path = lock_dir / "pid"
    try:
        raw_pid = owner_path.read_text().strip()
    except OSError:
        return None
    if not raw_pid.isdigit():
        return None
    return int(raw_pid)

def clear_stale_lock(lock_dir: Path) -> None:
    pid = read_lock_pid(lock_dir)
    if pid is not None and process_is_running(pid):
        return
    try:
        (lock_dir / "pid").unlink(missing_ok=True)
        lock_dir.rmdir()
    except OSError as e:
        print(f"warning: could not clear stale lock at {lock_dir}: {e}", file=sys.stderr)
        return

def acquire_maintenance_lock(lock_dir: Path = MAINTENANCE_LOCK_DIR) -> bool:
    try:
        lock_dir.mkdir()
    except FileExistsError:
        clear_stale_lock(lock_dir)
        try:
            lock_dir.mkdir()
        except FileExistsError:
            pid = read_lock_pid(lock_dir)
            owner = f" by pid {pid}" if pid is not None else ""
            print(
                "auto-maintenance skipped: another planner process is running"
                f"{owner}",
                file=sys.stderr,
            )
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

def rewrite_substance_refs(data_dir: Path, substance_renames: dict[str, str]) -> None:
    if not substance_renames:
        return

    products_dir = data_dir / "products"
    for path in sorted(products_dir.glob("*.yaml")):
        try:
            product = load_card_mapping(path, "product")
        except CardLoadError:
            continue
        changed = False
        for component_obj in cast(list[Any], product.get("components") or []):
            if not isinstance(component_obj, dict):
                continue
            component = cast(dict[str, Any], component_obj)
            old_ref = cast(str | None, component.get("substance"))
            if isinstance(old_ref, str) and old_ref in substance_renames:
                component["substance"] = substance_renames[old_ref]
                changed = True
        if changed:
            try:
                path.write_text(
                    yaml.safe_dump(
                        product,
                        sort_keys=False,
                        default_flow_style=False,
                        allow_unicode=True,
                    )
                )
            except OSError as e:
                print(f"warning: could not write {path}: {e}", file=sys.stderr)
                continue

    dashboards_dir = data_dir / "dashboards"
    if dashboards_dir.exists():
        for path in sorted(dashboards_dir.glob("*.yaml")):
            try:
                dashboard = load_card_mapping(path, "dashboard")
            except CardLoadError:
                continue
            changed = False
            for member_list_name in ("taking", "candidates", "declined"):
                for member_obj in cast(list[Any], dashboard.get(member_list_name) or []):
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
                            dashboard,
                            sort_keys=False,
                            default_flow_style=False,
                            allow_unicode=True,
                        )
                    )
                except OSError as e:
                    print(f"warning: could not write {path}: {e}", file=sys.stderr)
                    continue

    substances_dir = data_dir / "substances"
    for path in sorted(substances_dir.glob("*.yaml")):
        try:
            substance = load_card_mapping(path, "substance")
        except CardLoadError:
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

def normalize_substances(data_dir: Path) -> tuple[dict[str, str], int] | None:
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

def auto_maintenance_needed(data_dir: Path = DATA_DIR) -> bool:
    """Detect whether normalize_* would do work.

    Operates on raw dict mappings rather than typed dataclasses because
    the whole point of normalize_* is to fix on-disk cards that don't
    yet conform — a missing id is the signal to run maintenance, not a
    reason to bail out of the check.
    """
    substances_dir = data_dir / "substances"
    products_dir = data_dir / "products"

    for path in sorted(substances_dir.glob("*.yaml")):
        try:
            substance = load_card_mapping(path, "substance")
        except CardLoadError:
            return False
        if not isinstance(substance.get("id"), str):
            return True
        if path != substances_dir / canonical_substance_filename(
            _substance_from_mapping(substance)
        ):
            return True

    for path in sorted(products_dir.glob("*.yaml")):
        try:
            product = load_card_mapping(path, "product")
        except CardLoadError:
            return False
        if not isinstance(product.get("id"), str):
            return True
        if path != products_dir / canonical_product_filename(
            _product_from_mapping(product)
        ):
            return True

    return False

def run_auto_maintenance(data_dir: Path = DATA_DIR, *, quiet: bool = False) -> int:
    lock_acquired = False
    if auto_maintenance_needed(data_dir):
        if not acquire_maintenance_lock(data_dir.parent / MAINTENANCE_LOCK_DIR.name):
            return 1
        lock_acquired = True

    try:
        return run_auto_maintenance_unlocked(data_dir, quiet=quiet)
    finally:
        if lock_acquired:
            release_maintenance_lock(data_dir.parent / MAINTENANCE_LOCK_DIR.name)

def run_auto_maintenance_unlocked(
    data_dir: Path = DATA_DIR, *, quiet: bool = False
) -> int:
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
            stacks_path.write_text(
                yaml.safe_dump(
                    stacks_data,
                    sort_keys=False,
                    default_flow_style=False,
                    allow_unicode=True,
                )
            )

    changed = (
        len(substance_renames)
        + substance_file_moves
        + len(product_renames)
        + product_file_moves
    )
    if changed and not quiet:
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
