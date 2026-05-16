"""Auto-maintenance: file-rename helpers, normalization, lock management.

Maintenance reads via load_card_mapping (raw dict) for the rewrite paths so
yaml.safe_dump preserves on-disk key order. Read-only checks use the typed
dataclass loaders.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from planner.cards._common import generate_stable_id, load_card_mapping
from planner.cards.product import canonical_product_filename
from planner.cards.substance import canonical_substance_filename
from planner.contracts import CardLoadError, Product, Substance
from planner.io import (
    Paths,
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


# ---------------------------------------------------------------------------
# Atomic edit plan
# ---------------------------------------------------------------------------


@dataclass
class _EditPlanEntry:
    """A single file mutation within an atomic edit plan."""

    final_path: Path
    """Where the new content must end up after commit."""

    new_content: str
    """yaml.safe_dump output — the desired bytes for final_path."""

    obsolete_path: Path | None
    """Old card path to unlink after commit (rename case). None if unchanged."""


class _EditPlan:
    """Collect all desired mutations in memory, then stage/commit/abort atomically.

    Lifecycle:
      1. Build: append _EditPlanEntry objects via .entries.
      2. stage() — write every entry to a .tmp.<hex> sibling; returns False + cleans up on OSError.
      3. commit() — os.replace each .tmp to its final_path; unlink obsolete_path where set.
      4. abort() — idempotent cleanup; unlinks any leftover .tmp files.

    The .tmp.<hex> suffix uses pid + urandom so it never collides with a valid
    card filename (*.yaml) and cannot be picked up by the next planner read.
    """

    def __init__(self) -> None:
        self.entries: list[_EditPlanEntry] = []
        # (tmp_path, final_path) recorded in order as we stage them
        self._staged: list[tuple[Path, Path]] = []

    def stage(self) -> bool:
        """Write all entries to .tmp siblings.  Returns True on full success.

        On any OSError, unlinks every already-staged .tmp and returns False.
        """
        suffix = f".tmp.{os.getpid():x}.{os.urandom(4).hex()}"
        for entry in self.entries:
            tmp_path = entry.final_path.with_name(entry.final_path.name + suffix)
            try:
                tmp_path.write_text(entry.new_content)
            except OSError as e:
                print(
                    f"auto-maintenance: staging failed for {strip_root_prefix(str(entry.final_path))}: {e}",
                    file=sys.stderr,
                )
                # Unlink every .tmp we wrote so far
                for staged_tmp, _ in self._staged:
                    try:
                        staged_tmp.unlink(missing_ok=True)
                    except OSError:
                        pass
                # Also unlink the one that just failed (may have been partially written)
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
                return False
            self._staged.append((tmp_path, entry.final_path))
        return True

    def commit(self) -> None:
        """Atomically rename each staged .tmp to its final_path, then unlink obsolete paths."""
        # Build a map from final_path → obsolete_path for post-rename cleanup
        obsolete: dict[Path, Path] = {}
        for entry in self.entries:
            if entry.obsolete_path is not None and entry.obsolete_path != entry.final_path:
                obsolete[entry.final_path] = entry.obsolete_path

        for tmp_path, final_path in self._staged:
            try:
                os.replace(tmp_path, final_path)
            except OSError as e:
                # Narrow true-partial-failure window: some renames may have landed.
                # Clean up remaining .tmp files (those not yet renamed).
                remaining_tmps = {t for t, _ in self._staged if t.exists()}
                for leftover in remaining_tmps:
                    try:
                        leftover.unlink(missing_ok=True)
                    except OSError:
                        pass
                print(
                    f"auto-maintenance: CRITICAL: commit failed for "
                    f"{strip_root_prefix(str(final_path))}: {e}. "
                    f"Some files may be in a partially-renamed state — "
                    f"reconcile data/ manually.",
                    file=sys.stderr,
                )
                raise

        # Post-commit: unlink obsolete (old) paths for renamed cards
        for _final_path, old_path in obsolete.items():
            if old_path.exists():
                try:
                    old_path.unlink()
                except OSError as e:
                    print(
                        f"warning: could not remove obsolete card {strip_root_prefix(str(old_path))}: {e}",
                        file=sys.stderr,
                    )

    def abort(self) -> None:
        """Idempotent: unlink any leftover .tmp files from a failed stage."""
        for tmp_path, _ in self._staged:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
        self._staged.clear()


# ---------------------------------------------------------------------------
# Plan-building helpers (pure — no writes)
# ---------------------------------------------------------------------------


def _plan_card_dir(
    cards_dir: Path,
    canonical_fn: Callable[[Any], str],
    id_prefix: str,
    plan: _EditPlan,
) -> tuple[dict[str, str], int] | None:
    """Compute desired final state for all YAML cards in cards_dir; append entries to plan.

    Returns (renames, file_move_count) where renames maps old stem → new id
    for cards that received a generated id. Returns None on any error that
    should abort auto-maintenance (CardLoadError, duplicate destination, or
    destination-already-exists collision).

    Does NOT write anything to disk.
    """
    renames: dict[str, str] = {}
    file_moves: list[tuple[Path, Path]] = []
    # Maps final_path → original_path for duplicate-destination check
    destination_map: dict[Path, Path] = {}

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

        final_path = cards_dir / canonical_fn(data)

        if needs_new_id:
            renames[str(path.stem)] = data["id"]

        if path != final_path:
            file_moves.append((path, final_path))

        # Only plan an entry if something actually changes (id injection or rename).
        # Cards that are already canonical are left untouched — no yaml.safe_dump
        # reformat, preserving the no-op byte-identity invariant.
        if needs_new_id or path != final_path:
            new_content = yaml.safe_dump(
                data, sort_keys=False, default_flow_style=False, allow_unicode=True
            )
            obsolete = path if path != final_path else None
            plan.entries.append(
                _EditPlanEntry(final_path=final_path, new_content=new_content, obsolete_path=obsolete)
            )

        # Duplicate-destination check
        if final_path in destination_map and destination_map[final_path] != path:
            print(
                f"auto-maintenance aborted: duplicate {cards_dir.name} filename destination",
                file=sys.stderr,
            )
            return None
        destination_map[final_path] = path

    # Pre-flight existence check: destination exists and is NOT the obsolete source
    for source, destination in file_moves:
        if destination.exists() and destination != source:
            print(
                "auto-maintenance aborted: destination exists: "
                f"{strip_root_prefix(str(destination))}",
                file=sys.stderr,
            )
            return None

    return renames, len(file_moves)


def _plan_substance_ref_rewrites(
    data_dir: Path,
    substance_renames: dict[str, str],
    plan: _EditPlan,
    already_planned: set[Path],
) -> None:
    """Append entries for cards that need substance-ref rewrites.

    Skips paths already present in already_planned (those were handled by
    _plan_card_dir and may carry combined id+rename+ref edits).

    Covers:
      - products (components[].substance)
      - dashboards (taking/candidates/declined[].substance)
      - substances (prefer_with list-of-strings)
    """
    if not substance_renames:
        return

    # Products and dashboards — dict-member refs
    def _rewrite_dict_refs_planned(
        cards_dir: Path,
        card_kind: str,
        member_lists: tuple[str, ...],
    ) -> None:
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
            if changed and path not in already_planned:
                new_content = yaml.safe_dump(
                    card, sort_keys=False, default_flow_style=False, allow_unicode=True
                )
                plan.entries.append(
                    _EditPlanEntry(final_path=path, new_content=new_content, obsolete_path=None)
                )

    _rewrite_dict_refs_planned(data_dir / "products", "product", ("components",))
    _rewrite_dict_refs_planned(
        data_dir / "dashboards",
        "dashboard",
        ("taking", "candidates", "declined"),
    )

    # Substances — prefer_with list-of-strings
    substances_dir = data_dir / "substances"
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
        if rewritten != prefer_with and path not in already_planned:
            substance["prefer_with"] = rewritten
            new_content = yaml.safe_dump(
                substance, sort_keys=False, default_flow_style=False, allow_unicode=True
            )
            plan.entries.append(
                _EditPlanEntry(final_path=path, new_content=new_content, obsolete_path=None)
            )


# ---------------------------------------------------------------------------
# Legacy direct-write helpers (kept callable; bodies delegate to plan helpers)
# ---------------------------------------------------------------------------


def _normalize_card_dir(
    cards_dir: Path,
    canonical_fn: Callable[[Any], str],
    id_prefix: str,
) -> tuple[dict[str, str], int] | None:
    """Normalize filenames and assign stable IDs for all YAML cards in cards_dir.

    Returns (renames, file_move_count) where renames maps old stem → new id
    for cards that received a generated id. Returns None on any error that
    should abort auto-maintenance.

    Writes directly to disk (legacy semantics; kept for individual reuse).
    """
    plan = _EditPlan()
    result = _plan_card_dir(cards_dir, canonical_fn, id_prefix, plan)
    if result is None:
        return None
    renames, file_move_count = result
    if not plan.stage():
        return None
    try:
        plan.commit()
    except OSError:
        return None
    return renames, file_move_count


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
    lock_dir: Path,
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

def release_maintenance_lock(lock_dir: Path) -> None:
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

def auto_maintenance_needed(paths: Paths) -> bool | None:
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
    substances_dir = paths.substances
    products_dir = paths.products

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
    paths: Paths,
    *,
    suppress_output: bool = False,
    collect_errors: list[str] | None = None,
) -> int:
    """Acquire the maintenance lock only when work is actually needed, then delegate to the unlocked worker."""
    lock_acquired = False
    needs = auto_maintenance_needed(paths)
    if needs is None:
        return 1
    if needs:
        if not acquire_maintenance_lock(
            paths.maintenance_lock,
            collect_errors=collect_errors,
        ):
            return 1
        lock_acquired = True

    try:
        return _run_auto_maintenance_unlocked(paths, suppress_output=suppress_output)
    finally:
        if lock_acquired:
            release_maintenance_lock(paths.maintenance_lock)

def _run_auto_maintenance_unlocked(
    paths: Paths, *, suppress_output: bool = False
) -> int:
    """Normalise substances and products atomically via a 4-phase edit plan.

    Phases:
      1. Plan  — compute all desired mutations in memory (no disk writes).
      2. Stage — write .tmp.<hex> siblings for every entry.
      3. Commit — os.replace each .tmp to its final_path; unlink obsolete paths.
      4. Cleanup — handled inside commit() and abort() on failure.

    A failure in the plan or stage phase leaves the data directory
    byte-identical to its pre-call state.  The only window for partial
    mutation is a crash during the commit phase (after at least one
    os.replace has landed); that case prints a loud diagnostic and returns 1.

    Private — `run_auto_maintenance` is the only legitimate caller and it
    holds the maintenance lock around this call.
    """
    data_dir = paths.data
    stacks_path = paths.stacks_file

    # -----------------------------------------------------------------------
    # Phase 1: Plan
    # -----------------------------------------------------------------------
    edit_plan = _EditPlan()

    # Substances
    sub_result = _plan_card_dir(
        data_dir / "substances",
        lambda d: canonical_substance_filename(_substance_from_mapping(d)),
        "sub",
        edit_plan,
    )
    if sub_result is None:
        return 1
    substance_renames, substance_file_moves = sub_result

    # Track the final_paths already planned for substances so we don't
    # double-add them when planning substance-ref rewrites below.
    already_planned: set[Path] = {e.final_path for e in edit_plan.entries}

    # Substance-ref rewrites in products, dashboards, and substances (prefer_with)
    _plan_substance_ref_rewrites(data_dir, substance_renames, edit_plan, already_planned)

    # Update already_planned to include any new ref-rewrite entries
    already_planned = {e.final_path for e in edit_plan.entries}

    # Products
    prd_result = _plan_card_dir(
        data_dir / "products",
        lambda d: canonical_product_filename(_product_from_mapping(d)),
        "prd",
        edit_plan,
    )
    if prd_result is None:
        return 1
    product_renames, product_file_moves = prd_result

    # Stacks rewrite (only if product renames are needed)
    if stacks_path.exists() and product_renames:
        stacks_data = load_yaml(stacks_path)
        if isinstance(stacks_data, dict):
            rewrite_stack_product_refs(cast(dict[str, Any], stacks_data), product_renames)
            stacks_content = yaml.safe_dump(
                stacks_data,
                sort_keys=False,
                default_flow_style=False,
                allow_unicode=True,
            )
            edit_plan.entries.append(
                _EditPlanEntry(
                    final_path=stacks_path,
                    new_content=stacks_content,
                    obsolete_path=None,
                )
            )

    # -----------------------------------------------------------------------
    # Phase 2: Stage
    # -----------------------------------------------------------------------
    if not edit_plan.stage():
        # stage() already printed the error and named the failing path;
        # ensure stacks.yaml appears in stderr for the specific stacks case.
        # (stage() prints the failing final_path which will be stacks.yaml
        # when that entry is the one that fails — no extra print needed.)
        return 1

    # -----------------------------------------------------------------------
    # Phase 3: Commit  (Phase 4 / cleanup is inside commit() and abort())
    # -----------------------------------------------------------------------
    try:
        edit_plan.commit()
    except OSError:
        return 1

    # -----------------------------------------------------------------------
    # Output summary
    # -----------------------------------------------------------------------
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
