from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml

from tests.planner_fixture import PlannerFixtureInput, check_in_temp_dir, write_minimal_planner_fixture, write_yaml


def test_malformed_stack_entry_reports_schema_error(tmp_path: Path) -> None:
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
    temp_data = tmp_path / "data"
    stacks_path = temp_data / "stacks.yaml"
    stack_items = cast(dict[str, list[object]], yaml.safe_load(stacks_path.read_text()))
    stack_items["daily"][0] = {"product": "sub_aaa0000001"}
    write_yaml(stacks_path, stack_items)

    result = check_in_temp_dir(tmp_path)

    assert result.exit_code != 0
    combined_output = "\n".join(result.errors + result.info)
    assert "stacks" in combined_output
    assert "sub_aaa0000001" in combined_output
    assert "AttributeError" not in combined_output
    assert "Traceback" not in combined_output
