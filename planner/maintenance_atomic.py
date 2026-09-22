"""Atomic staged writes for explicit planner normalization."""

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
                    f"normalize: staging failed for {strip_root_prefix(str(entry.final_path))}: {e}",
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

        suffix = f".bak.{os.getpid():x}.{os.urandom(4).hex()}"
        backups = self._replace_staged_files(suffix)

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

        for backup_path, _final_path in backups:
            try:
                backup_path.unlink(missing_ok=True)
            except OSError as e:
                print(
                    f"warning: could not remove temporary backup {strip_root_prefix(str(backup_path))}: {e}",
                    file=sys.stderr,
                )
        self._staged.clear()

    def _replace_staged_files(self, suffix: str) -> list[tuple[Path, Path]]:
        backups: list[tuple[Path, Path]] = []
        replaced: list[Path] = []
        final_path: Path | None = None
        try:
            for tmp_path, final_path in self._staged:
                backup_path = final_path.with_name(final_path.name + suffix)
                if final_path.exists() or final_path.is_symlink():
                    final_path.replace(backup_path)
                    backups.append((backup_path, final_path))
                tmp_path.replace(final_path)
                replaced.append(final_path)
        except OSError as e:
            self._rollback_replacements(backups, replaced)
            self.abort()
            print(
                f"normalize: CRITICAL: commit failed while replacing "
                f"{strip_root_prefix(str(final_path)) if final_path is not None else '<unknown target>'}: {e}",
                file=sys.stderr,
            )
            raise
        return backups

    def _rollback_replacements(self, backups: list[tuple[Path, Path]], replaced: list[Path]) -> None:
        """Restore final paths that were replaced before a later replacement failed."""
        for final_path in reversed(replaced):
            with contextlib.suppress(OSError):
                final_path.unlink(missing_ok=True)
        for backup_path, final_path in reversed(backups):
            with contextlib.suppress(OSError):
                backup_path.replace(final_path)

    def abort(self) -> None:
        """Remove leftover staged .tmp files."""
        for tmp_path, _ in self._staged:
            with contextlib.suppress(OSError):
                tmp_path.unlink(missing_ok=True)
        self._staged.clear()
