"""Shared test helpers: in-process planner runner with data-root patching."""

from __future__ import annotations

import contextlib
import io as _io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

ROOT = Path(__file__).resolve().parents[1]

# All planner modules that bind path constants imported from planner.io.
_MODULES = [
    "planner.io",
    "planner.cards.dashboards",
    "planner.cards.product",
    "planner.cards.relations",
    "planner.cards.stacks",
    "planner.cards.substance",
    "planner.engine.check",
    "planner.engine.doctor",
    "planner.engine.plan",
    "planner.engine.review",
    "planner.engine.show",
    "planner.maintenance",
]

# Attributes to redirect when the data root changes.
# SCHEMA_DIR is intentionally absent — schema files are static and always read
# from the real repo regardless of which data directory a test uses.
def _new_attrs(new_root: Path) -> dict[str, Path]:
    d = new_root / "data"
    return {
        "ROOT": new_root,
        "DATA_DIR": d,
        "SUBSTANCES_DIR": d / "substances",
        "PRODUCTS_DIR": d / "products",
        "DASHBOARDS_DIR": d / "dashboards",
        "STACKS_PATH": d / "stacks.yaml",
        "RELATIONS_PATH": d / "relations.yaml",
        "SCHEDULE_PATH": new_root / "schedule.yaml",
        "MAINTENANCE_LOCK_DIR": new_root / ".planner-maintenance.lock",
    }


@contextlib.contextmanager
def patch_planner_root(new_root: Path) -> Generator[None, None, None]:
    attrs = _new_attrs(new_root)
    saved: dict[tuple[str, str], object] = {}
    for mod_name in _MODULES:
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        for attr, val in attrs.items():
            if hasattr(mod, attr):
                saved[(mod_name, attr)] = getattr(mod, attr)
                setattr(mod, attr, val)
    try:
        yield
    finally:
        for (mod_name, attr), old in saved.items():
            mod = sys.modules.get(mod_name)
            if mod is not None:
                setattr(mod, attr, old)


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
        with patch_planner_root(root), \
             contextlib.redirect_stdout(stdout_buf), \
             contextlib.redirect_stderr(stderr_buf):
            try:
                main()
            except SystemExit as e:
                returncode = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        sys.argv = old_argv
    return RunResult(returncode=returncode, stdout=stdout_buf.getvalue(), stderr=stderr_buf.getvalue())
