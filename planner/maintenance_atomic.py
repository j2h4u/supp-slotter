"""Atomic staged writes for planner auto-maintenance."""

from __future__ import annotations

import contextlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from planner.paths import strip_root_prefix


@dataclass
class EditPlanEntry:
    """A single file mutation within an atomic edit plan."""

    final_path: Path
    """Where the new content must end up after commit."""

    new_content: str
    """yaml.safe_dump output: the desired bytes for final_path."""

    obsolete_path: Path | None
    """Old card path to unlink after commit. None if unchanged."""


class EditPlan:
    """Collect desired mutations in memory, then stage/commit/abort atomically."""

    def __init__(self) -> None:
        self.entries: list[EditPlanEntry] = []
        self._staged: list[tuple[Path, Path]] = []

    def upsert(self, entry: EditPlanEntry) -> None:
        """Add or replace a final-path mutation while preserving rename cleanup."""
        for existing in self.entries:
            if existing.final_path != entry.final_path:
                continue
            existing.new_content = entry.new_content
            if existing.obsolete_path is None:
                existing.obsolete_path = entry.obsolete_path
            return
        self.entries.append(entry)

    def stage(self) -> bool:
        """Write all entries to .tmp siblings and clean up on any write failure."""
        suffix = f".tmp.{os.getpid():x}.{os.urandom(4).hex()}"
        for entry in self.entries:
            tmp_path = entry.final_path.with_name(entry.final_path.name + suffix)
            try:
                tmp_path.write_text(entry.new_content, encoding="utf-8")
            except OSError as e:
                print(
                    f"auto-maintenance: staging failed for {strip_root_prefix(str(entry.final_path))}: {e}",
                    file=sys.stderr,
                )
                self.abort()
                with contextlib.suppress(OSError):
                    tmp_path.unlink(missing_ok=True)
                return False
            self._staged.append((tmp_path, entry.final_path))
        return True

    def commit(self) -> None:
        """Atomically rename staged .tmp files to final paths, then unlink old paths."""
        obsolete: dict[Path, Path] = {}
        for entry in self.entries:
            if entry.obsolete_path is not None and entry.obsolete_path != entry.final_path:
                obsolete[entry.final_path] = entry.obsolete_path

        for tmp_path, final_path in self._staged:
            try:
                tmp_path.replace(final_path)
            except OSError as e:
                self.abort()
                print(
                    f"auto-maintenance: CRITICAL: commit failed for "
                    f"{strip_root_prefix(str(final_path))}: {e}. "
                    f"Some files may be in a partially-renamed state; "
                    f"reconcile data/ manually.",
                    file=sys.stderr,
                )
                raise

        for old_path in obsolete.values():
            if not old_path.exists():
                continue
            try:
                old_path.unlink()
            except OSError as e:
                print(
                    f"warning: could not remove obsolete card {strip_root_prefix(str(old_path))}: {e}",
                    file=sys.stderr,
                )

    def abort(self) -> None:
        """Remove leftover staged .tmp files."""
        for tmp_path, _ in self._staged:
            with contextlib.suppress(OSError):
                tmp_path.unlink(missing_ok=True)
        self._staged.clear()
