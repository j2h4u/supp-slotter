from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.cards.stacks import normalize_stack_entries, validate_stacks
from planner.ontology.artifacts import load_ontology
from planner.paths import ROOT, Paths

from tests.planner_fixture import PlannerFixtureInput, check_in_temp_dir, write_minimal_planner_fixture, write_yaml


def test_normalization_rejects_product_assigned_to_active_and_inactive_stacks() -> None:
    with pytest.raises(ValueError, match=r"prd_aaa0000001.*multiple stacks"):
        normalize_stack_entries({"daily": ["prd_aaa0000001"], "inactive": ["prd_aaa0000001"]})


def test_malformed_stack_entry_reports_schema_error(tmp_path: Path) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={"prd_aaa0000001": {"stack": "daily"}},
            products={"prd_aaa0000001": [("sub_aaa0000001", ["timing:energy_like"])]},
            traits={"timing:energy_like": {"label": "Energy-like", "description": "Fixture.", "applies_when": "Fixture."}},
        ),
    )
    stacks_path = tmp_path / "data" / "stacks.yaml"
    stack_items = cast(dict[str, list[object]], yaml.safe_load(stacks_path.read_text()))
    stack_items["daily"][0] = {"product": "sub_aaa0000001"}
    write_yaml(stacks_path, stack_items)
    result = check_in_temp_dir(tmp_path)
    combined_output = "\n".join(result.errors + result.info)
    assert result.exit_code != 0
    assert "stacks" in combined_output and "sub_aaa0000001" in combined_output
    assert "AttributeError" not in combined_output and "Traceback" not in combined_output


def test_inactive_stack_is_exempt_but_routable_stack_requires_pillbox(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "stacks.yaml").write_text("inactive: []\ndaily: []\n", encoding="utf-8")
    (data / "pillboxes.yaml").write_text("{}\n", encoding="utf-8")

    errors, info = validate_stacks(Paths.from_root(tmp_path), {}, load_ontology(ROOT / "ontology"))

    assert errors == []
    assert any("stack 'daily' has no pillbox" in message for message in info)
    assert not any("stack 'inactive' has no pillbox" in message for message in info)
