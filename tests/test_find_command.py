from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml
from planner.engine import cmd_find

from tests.planner_fixture import PlannerFixtureInput, find_card_path_by_id, write_minimal_planner_fixture


def _write_find_fixture(tmp_path: Path) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={
                "prd_magnesium1": {"stack": "daily"},
                "prd_citrulline": {"stack": "training"},
                "prd_glycine000": {"stack": "inactive"},
            },
            products={
                "prd_magnesium1": [("sub_magnesium1", ["timing:wake"])],
                "prd_citrulline": [("sub_citrulline", ["activity:workout"])],
                "prd_glycine000": [("sub_glycine000", ["timing:wake"])],
            },
            traits={
                "timing:wake": {
                    "label": "Wake",
                    "description": "Fixture wake timing.",
                    "applies_when": "Fixture only.",
                },
                "activity:workout": {
                    "label": "Workout",
                    "description": "Fixture workout activity.",
                    "applies_when": "Fixture only.",
                },
            },
        ),
    )
    data_dir = tmp_path / "data"

    magnesium_path = find_card_path_by_id(data_dir / "substances", "sub_magnesium1")
    magnesium = cast(dict[str, object], yaml.safe_load(magnesium_path.read_text()))
    magnesium["name"] = "Magnesium"
    magnesium["form"] = "bisglycinate"
    magnesium_path.write_text(yaml.safe_dump(magnesium, sort_keys=False))

    magnesium_product_path = find_card_path_by_id(data_dir / "products", "prd_magnesium1")
    magnesium_product = cast(dict[str, object], yaml.safe_load(magnesium_product_path.read_text()))
    magnesium_product["name"] = "Magnesium Bisglycinate"
    magnesium_product["brand"] = "Fixture Brand"
    magnesium_product_path.write_text(yaml.safe_dump(magnesium_product, sort_keys=False))

    citrulline_path = find_card_path_by_id(data_dir / "substances", "sub_citrulline")
    citrulline = cast(dict[str, object], yaml.safe_load(citrulline_path.read_text()))
    citrulline["name"] = "L-Citrulline"
    citrulline["form"] = "malate"
    citrulline_path.write_text(yaml.safe_dump(citrulline, sort_keys=False))

    citrulline_product_path = find_card_path_by_id(data_dir / "products", "prd_citrulline")
    citrulline_product = cast(dict[str, object], yaml.safe_load(citrulline_product_path.read_text()))
    citrulline_product["name"] = "L-Citrulline Malate"
    citrulline_product_path.write_text(yaml.safe_dump(citrulline_product, sort_keys=False))

    glycine_path = find_card_path_by_id(data_dir / "substances", "sub_glycine000")
    glycine = cast(dict[str, object], yaml.safe_load(glycine_path.read_text()))
    glycine["name"] = "Magnesium Glycine"
    glycine_path.write_text(yaml.safe_dump(glycine, sort_keys=False))


def test_find_searches_multiple_fuzzy_words(tmp_path: Path) -> None:
    _write_find_fixture(tmp_path)
    result = cmd_find(["magnesium", "bisglycinate"], data_root=tmp_path)

    assert result.exit_code == 0
    substance_names = [label for _score, _card_id, label, _path in result.substances]
    product_names = [label for _score, _card_id, label, _path in result.products]
    assert "Magnesium (bisglycinate)" in substance_names
    assert "Fixture Brand - Magnesium Bisglycinate" in product_names
    magnesium_idx = substance_names.index("Magnesium (bisglycinate)")
    assert "Magnesium Glycine" in substance_names
    glycine_idx = substance_names.index("Magnesium Glycine")
    assert magnesium_idx < glycine_idx
    assert substance_names or product_names


def test_find_supports_partial_word_matches(tmp_path: Path) -> None:
    _write_find_fixture(tmp_path)
    result = cmd_find(["citrul", "malat"], data_root=tmp_path)

    assert result.exit_code == 0
    substance_names = [label for _score, _card_id, label, _path in result.substances]
    product_names = [label for _score, _card_id, label, _path in result.products]
    assert "L-Citrulline (malate)" in substance_names
    assert "L-Citrulline Malate" in product_names


def test_find_does_not_run_maintenance_on_draft_cards(tmp_path: Path) -> None:
    _write_find_fixture(tmp_path)
    temp_data = tmp_path / "data"
    draft_path = temp_data / "substances" / "draft_probe.yaml"
    draft_path.write_text(yaml.safe_dump({"name": "Draft Probe"}, sort_keys=False))

    result = cmd_find(["draft", "probe"], data_root=tmp_path)

    assert result.exit_code != 0
    draft_card = cast(dict[str, object], yaml.safe_load(draft_path.read_text()))
    assert "id" not in draft_card
    assert draft_path.exists()
