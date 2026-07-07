"""Repo paths and display-path helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from planner.contracts import CardLoadError

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"


@dataclass(frozen=True, slots=True)
class Paths:
    """Resolved filesystem paths for one planner data root."""

    root: Path
    data: Path
    substances: Path
    products: Path
    dashboards: Path
    traits: Path
    stacks_file: Path
    relations_file: Path
    schedule_file: Path
    maintenance_lock: Path

    @classmethod
    def from_root(cls, root: Path) -> Paths:
        data = root / "data"
        return cls(
            root=root,
            data=data,
            substances=data / "substances",
            products=data / "products",
            dashboards=data / "dashboards",
            traits=data / "traits",
            stacks_file=data / "stacks.yaml",
            relations_file=data / "relations.yaml",
            schedule_file=root / "schedule.yaml",
            maintenance_lock=root / ".planner-maintenance.lock",
        )

    @classmethod
    def default(cls) -> Paths:
        return cls.from_root(ROOT)


def strip_root_prefix(message: str) -> str:
    root = str(ROOT.resolve())
    return message.replace(f"{root}/", "")


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def trait_source_files(path: Path) -> list[Path]:
    """Return trait YAML sources from the split trait directory."""
    if path.is_dir():
        files = sorted(path.glob("*.yaml"))
        if files:
            return files
        raise CardLoadError(path, f"{path}: no traits found")
    if path.exists():
        raise CardLoadError(path, f"{path}: expected trait directory")
    raise CardLoadError(path, f"{path}: directory does not exist")
