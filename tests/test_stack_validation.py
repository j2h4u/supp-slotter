from __future__ import annotations

from pathlib import Path

import yaml

from tests.planner_fixture import check_in_temp_dir, copy_data_tree, write_yaml


def test_malformed_stack_entry_reports_schema_error(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    stacks_path = temp_data / "stacks.yaml"
    stack_items = yaml.safe_load(stacks_path.read_text())
    stack_items["daily"][0] = {"product": "sub_2476bf9d4b"}
    write_yaml(stacks_path, stack_items)

    result = check_in_temp_dir(tmp_path)

    assert result.exit_code != 0
    combined_output = "\n".join(result.errors + result.info)
    assert "stacks" in combined_output
    assert "sub_2476bf9d4b" in combined_output
    assert "AttributeError" not in combined_output
    assert "Traceback" not in combined_output
