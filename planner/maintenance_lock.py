"""Lock management for planner auto-maintenance."""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path


def process_is_running(pid: int) -> bool:
    """Use kill(pid, 0) as a liveness probe."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_lock_pid(lock_dir: Path) -> int | None:
    """Return the integer pid recorded in `<lock_dir>/pid`, or None."""
    owner_path = lock_dir / "pid"
    try:
        raw_pid = owner_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw_pid.isdigit():
        return None
    return int(raw_pid)


def clear_stale_lock(lock_dir: Path) -> None:
    """Clear the lock directory only if its owning pid is dead."""
    pid = read_lock_pid(lock_dir)
    if pid is not None and process_is_running(pid):
        return
    try:
        (lock_dir / "pid").unlink(missing_ok=True)
        lock_dir.rmdir()
    except OSError as e:
        print(f"warning: could not clear stale lock at {lock_dir}: {e}", file=sys.stderr)


def acquire_maintenance_lock(
    lock_dir: Path,
    collect_errors: list[str] | None = None,
) -> bool:
    """Acquire a mkdir-based lock, clearing a stale lock before one retry."""
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
        (lock_dir / "pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
    except OSError as e:
        print(f"warning: could not write maintenance lock pid: {e}", file=sys.stderr)
        with contextlib.suppress(OSError):
            lock_dir.rmdir()
        return False
    return True


def release_maintenance_lock(lock_dir: Path) -> None:
    """Release a lock acquired by acquire_maintenance_lock."""
    try:
        (lock_dir / "pid").unlink(missing_ok=True)
        lock_dir.rmdir()
    except OSError as e:
        print(f"warning: could not release maintenance lock at {lock_dir}: {e}", file=sys.stderr)
