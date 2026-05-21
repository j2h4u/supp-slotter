from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from planner.engine import cmd_find
from tests.helpers import ROOT
from tests.planner_fixture import copy_data_tree


def test_find_searches_multiple_fuzzy_words() -> None:
    result = cmd_find(["magnesium", "bisglycinate"], data_root=ROOT)

    assert result.exit_code == 0
    substance_names = [label for _score, _card_id, label, _path in result.substances]
    product_names = [label for _score, _card_id, label, _path in result.products]
    assert "Magnesium (glycinate)" in substance_names
    assert "Vitamir - Magnesium glycinate" in product_names
    magnesium_idx = substance_names.index("Magnesium (glycinate)")
    assert "Glycine" in substance_names
    glycine_idx = substance_names.index("Glycine")
    assert magnesium_idx < glycine_idx
    assert substance_names or product_names


def test_find_supports_partial_word_matches() -> None:
    result = cmd_find(["citrul", "malat"], data_root=ROOT)

    assert result.exit_code == 0
    substance_names = [label for _score, _card_id, label, _path in result.substances]
    product_names = [label for _score, _card_id, label, _path in result.products]
    assert "L-Citrulline (malate)" in substance_names
    assert "L-Citrulline Malate" in product_names


def test_find_does_not_run_maintenance_on_draft_cards(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    draft_path = temp_data / "substances" / "draft_probe.yaml"
    draft_path.write_text(yaml.safe_dump({"name": "Draft Probe"}, sort_keys=False))

    result = cmd_find(["draft", "probe"], data_root=tmp_path)

    assert result.exit_code != 0
    draft_card = cast(dict[str, Any], yaml.safe_load(draft_path.read_text()))
    assert "id" not in draft_card
    assert draft_path.exists()
