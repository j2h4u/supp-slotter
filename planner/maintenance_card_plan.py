"""Card id injection and canonical filename planning."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import yaml

from planner.cards._common import generate_stable_id, load_card_mapping
from planner.contracts import CardLoadError
from planner.maintenance_atomic import EditPlan, EditPlanEntry
from planner.paths import strip_root_prefix


def plan_card_dir(
    cards_dir: Path,
    canonical_fn: Callable[[dict[str, object]], str],
    id_prefix: str,
    plan: EditPlan,
) -> tuple[dict[str, str], int] | None:
    renames: dict[str, str] = {}
    file_moves: list[tuple[Path, Path]] = []
    destination_map: dict[Path, Path] = {}

    for path in sorted(cards_dir.glob("*.yaml")):
        try:
            data = load_card_mapping(path, cards_dir.name)
        except CardLoadError as e:
            print(f"ERROR: {strip_root_prefix(e.message)}", file=sys.stderr)
            return None
        card_data = cast(dict[str, object], dict(data))

        old_id = card_data.get("id")
        needs_new_id = not isinstance(old_id, str)
        if needs_new_id:
            new_id = generate_stable_id(id_prefix)
            card_data["id"] = new_id
        else:
            new_id = old_id

        final_path = cards_dir / canonical_fn(card_data)
        if needs_new_id:
            renames[str(path.stem)] = new_id
        if path != final_path:
            file_moves.append((path, final_path))
        if needs_new_id or path != final_path:
            _append_card_edit(plan, final_path, card_data, path if path != final_path else None)

        if final_path in destination_map and destination_map[final_path] != path:
            print(
                f"auto-maintenance aborted: duplicate {cards_dir.name} filename destination",
                file=sys.stderr,
            )
            return None
        destination_map[final_path] = path

    for source, destination in file_moves:
        if destination.exists() and destination != source:
            print(
                f"auto-maintenance aborted: destination exists: {strip_root_prefix(str(destination))}",
                file=sys.stderr,
            )
            return None

    return renames, len(file_moves)


def _append_card_edit(
    plan: EditPlan,
    final_path: Path,
    data: dict[str, object],
    obsolete_path: Path | None,
) -> None:
    new_content = yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)
    plan.entries.append(
        EditPlanEntry(
            final_path=final_path,
            new_content=new_content,
            obsolete_path=obsolete_path,
        )
    )
