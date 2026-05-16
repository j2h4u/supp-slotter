"""Shared test helpers: in-process planner runner."""

from __future__ import annotations

import contextlib
import io as _io
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = ["ROOT", "RunResult", "run_planner"]

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str


def run_planner(*args: str, root: Path = ROOT) -> RunResult:
    from planner.__main__ import main  # noqa: PLC0415

    old_argv = sys.argv[:]
    stdout_buf = _io.StringIO()
    stderr_buf = _io.StringIO()
    returncode = 0
    sys.argv = ["planner", *args]
    try:
        with contextlib.redirect_stdout(stdout_buf), \
             contextlib.redirect_stderr(stderr_buf):
            try:
                main(data_root=root)
            except SystemExit as e:
                returncode = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        sys.argv = old_argv
    return RunResult(returncode=returncode, stdout=stdout_buf.getvalue(), stderr=stderr_buf.getvalue())
