from __future__ import annotations

from planner.engine import cmd_find
from tests.helpers import ROOT


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
