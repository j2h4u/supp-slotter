"""Auto-maintenance change detection."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping
from planner.cards.product import canonical_product_filename
from planner.cards.substance import canonical_substance_filename
from planner.contracts import CardLoadError
from planner.maintenance_mapping import product_from_mapping, substance_from_mapping
from planner.maintenance_substance_resolution import (
    MaintenanceContract,
    has_draft_reference,
)
from planner.paths import Paths, strip_root_prefix


def auto_maintenance_needed(
    paths: Paths,
    *,
    contract: MaintenanceContract | None = None,
) -> bool | None:
    if contract is None:
        print("auto-maintenance: verified ontology maintenance contract is required", file=sys.stderr)
        return None
    substance_dir = paths.root / contract.substance_path
    product_dir = paths.root / contract.product_path
    substance_result = _cards_need_maintenance(
        substance_dir,
        lambda path, data: path != substance_dir / canonical_substance_filename(substance_from_mapping(data)),
    )
    if substance_result is not False:
        return substance_result

    return _cards_need_maintenance(
        product_dir,
        lambda path, data: (
            path != product_dir / canonical_product_filename(product_from_mapping(data))
            or has_draft_reference(data, contract.product_substance)
        ),
    )


def _cards_need_maintenance(
    cards_dir: Path,
    path_is_noncanonical: Callable[[Path, dict[str, object]], bool],
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
        card_data = cast(dict[str, object], card)
        if not isinstance(card_data.get("id"), str):
            return True
        if path_is_noncanonical(path, card_data):
            return True
    return False
