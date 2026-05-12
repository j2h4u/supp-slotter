"""Internal: planner root patching for in-process test isolation."""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Generator
from pathlib import Path

# All planner modules that bind path constants imported from planner.io.
_MODULES = [
    "planner.io",
    "planner.cards.dashboards",
    "planner.cards.product",
    "planner.cards.relations",
    "planner.cards.stacks",
    "planner.cards.substance",
    "planner.engine.audit",
    "planner.engine.check",
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
    """Context manager: redirect all module-level path constants to new_root.

    data_root must be a Path the caller already controls (e.g. pytest tmp_path).
    No filesystem escape is possible because the patched paths are constrained
    to whatever Path is passed in.
    """
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


@contextlib.contextmanager
def maybe_patch_root(data_root: Path | None) -> Generator[None, None, None]:
    """Yield inside patch_planner_root when data_root is set, else yield directly."""
    if data_root is not None:
        with patch_planner_root(data_root):
            yield
    else:
        yield
