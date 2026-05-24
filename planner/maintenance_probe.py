"""Auto-maintenance change detection."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from planner.cards._common import load_card_mapping
from planner.cards.product import canonical_product_filename
from planner.cards.substance import canonical_substance_filename
from planner.contracts import CardLoadError
from planner.maintenance_mapping import product_from_mapping, substance_from_mapping
from planner.maintenance_substance_resolution import product_has_draft_component_ref
from planner.paths import Paths, strip_root_prefix


def auto_maintenance_needed(paths: Paths) -> bool | None:
    substance_result = _cards_need_maintenance(
        paths.substances,
        lambda path, data: path != paths.substances / canonical_substance_filename(
            substance_from_mapping(data)
        ),
    )
    if substance_result is not False:
        return substance_result

    return _cards_need_maintenance(
        paths.products,
        lambda path, data: (
            path != paths.products / canonical_product_filename(product_from_mapping(data))
            or product_has_draft_component_ref(data)
        ),
    )


def _cards_need_maintenance(
    cards_dir: Path,
    path_is_noncanonical: Callable[[Path, dict[str, Any]], bool],
) -> bool | None:
    for path in sorted(cards_dir.glob("*.yaml")):
        try:
            card = load_card_mapping(path, cards_dir.name)
        except CardLoadError as e:
            print(
                f"auto-maintenance: could not read {path}: {strip_root_prefix(e.message)}",
                file=sys.stderr,
            )
            return None
        if not isinstance(card.get("id"), str):
            return True
        if path_is_noncanonical(path, card):
            return True
    return False
