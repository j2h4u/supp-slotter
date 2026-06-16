from __future__ import annotations

from pathlib import Path
from typing import NotRequired, TypedDict, cast

import yaml

from tests.planner_fixture import (
    PlannerFixtureInput,
    check_in_temp_dir,
    find_card_path_by_id,
    write_minimal_planner_fixture,
    write_yaml,
)


class _ProductComponent(TypedDict):
    substance: str


class _ProductCard(TypedDict):
    components: list[_ProductComponent]
    urls: NotRequired[list[str]]


def _write_product_validation_fixture(tmp_path: Path) -> Path:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={"prd_aaa0000001": {"stack": "daily"}},
            products={"prd_aaa0000001": [("sub_aaa0000001", ["timing:wake"])]},
            traits={
                "timing:wake": {
                    "label": "Wake",
                    "description": "Fixture wake timing.",
                    "applies_when": "Fixture only.",
                }
            },
        ),
    )
    return tmp_path / "data"


def test_product_formula_ref_validator_rejects_missing_substance(
    tmp_path: Path,
) -> None:
    temp_data = _write_product_validation_fixture(tmp_path)
    product_path = find_card_path_by_id(
        temp_data / "products",
        "prd_aaa0000001",
    )
    product = cast(_ProductCard, yaml.safe_load(product_path.read_text()))
    product["components"][0]["substance"] = "sub_deadbeef00"
    write_yaml(product_path, product)

    result = check_in_temp_dir(tmp_path)

    assert result.exit_code != 0
    combined_output = "\n".join(result.errors + result.info)
    assert "sub_deadbeef00" in combined_output
    assert "references unknown substance" in combined_output


def test_product_schema_accepts_description_urls(tmp_path: Path) -> None:
    temp_data = _write_product_validation_fixture(tmp_path)
    product_path = find_card_path_by_id(
        temp_data / "products",
        "prd_aaa0000001",
    )
    product = cast(_ProductCard, yaml.safe_load(product_path.read_text()))
    product["urls"] = ["https://example.com/probe-sub_aaa0000001"]
    write_yaml(product_path, product)

    result = check_in_temp_dir(tmp_path)

    assert result.exit_code == 0, "\n".join(result.errors + result.info)
