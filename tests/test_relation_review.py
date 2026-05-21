from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from planner.engine import cmd_check, cmd_plan, cmd_review
from tests.planner_fixture import copy_data_tree, find_card_path_by_id


def test_balance_relation_warns_when_related_substance_missing(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    trace_product_path = find_card_path_by_id(
        temp_data / "products",
        "prd_932319251f",
    )
    trace_product = yaml.safe_load(trace_product_path.read_text())
    trace_product["components"] = [
        component
        for component in trace_product["components"]
        if component["substance"] != "sub_844a0cc551"
    ]
    trace_product_path.write_text(yaml.safe_dump(trace_product, sort_keys=False))

    review_result = cmd_review(data_root=tmp_path)

    assert review_result.exit_code == 0
    assert "missing_target" in review_result.output or "missing_source" in review_result.output
    assert "Zinc" in review_result.output and "Copper" in review_result.output

    plan_result = cmd_plan(data_root=tmp_path)

    assert plan_result.exit_code == 0, plan_result
    assert any(
        w.get("type") == "missing_balance_substance"
        and w.get("severity") == "medium"
        and "Zinc" in str(w.get("source_name", ""))
        and "Copper" in str(w.get("target_name", ""))
        and "reason" in w
        and "action" in w
        for w in plan_result.warnings
    ), f"Expected missing_balance_substance warning for Zinc/Copper in: {plan_result.warnings}"


def test_relation_validation_rejects_unknown_substance_name(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = yaml.safe_load(relations_path.read_text())
    relations["supports"].append(
        {
            "source_name": "Definitely Missing",
            "target_name": "N-Acetyl Cysteine",
            "reason": "Fixture relation.",
        }
    )
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    assert "source_name 'Definitely Missing' has no matching substance name" in "\n".join(result.errors)


def test_relation_validation_rejects_unregistered_class(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = yaml.safe_load(relations_path.read_text())
    relations.setdefault("competes", []).append(
        {
            "source_class": "minearl",
            "target_class": "fat_soluble",
            "reason": "Fixture relation with misspelled class slug.",
        }
    )
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    error_text = "\n".join(result.errors)
    assert result.exit_code != 0
    assert "source_class 'minearl' is not a registered is: trait" in error_text
    assert "target_class 'fat_soluble'" not in error_text


def test_relation_validation_rejects_class_endpoint_outside_competes(
    tmp_path: Path,
) -> None:
    temp_data = copy_data_tree(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = yaml.safe_load(relations_path.read_text())
    relations.setdefault("supports", []).append(
        {
            "source_class": "mineral",
            "target_class": "fat_soluble",
            "reason": "Fixture class endpoint on non-competes relation.",
        }
    )
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    assert "source_class/target_class endpoints are only supported for competes" in (
        "\n".join(result.errors)
    )


def test_class_relation_resolves_for_review_status(tmp_path: Path) -> None:
    copy_data_tree(tmp_path)

    review_result = cmd_review(data_root=tmp_path)

    assert review_result.exit_code == 0, review_result.stderr
    relation_line = "[competes] is:mineral -> is:fat_soluble"
    assert relation_line in review_result.output
    both_active_section = review_result.output.split("missing_source", maxsplit=1)[0]
    assert relation_line in both_active_section


def test_relation_validation_rejects_unregistered_trait(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = yaml.safe_load(relations_path.read_text())
    relations.setdefault("review_with", []).append(
        {
            "source_trait": "effect:not_real",
            "target_name": "Tadalafil",
            "reason": "Fixture relation with misspelled trait slug.",
        }
    )
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    assert "source_trait 'effect:not_real' is not a registered trait" in "\n".join(
        result.errors
    )


def test_trait_relation_endpoint_warns_by_matching_trait(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = yaml.safe_load(relations_path.read_text())
    relations.setdefault("review_with", []).append(
        {
            "source_trait": "effect:nitric_oxide_support",
            "target_name": "Tadalafil",
            "severity": "low",
            "reason": "Fixture trait endpoint relation.",
            "action": "Review fixture trait endpoint.",
        }
    )
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_plan(data_root=tmp_path)

    assert result.exit_code == 0, result
    assert any(
        warning.get("type") == "review_with_substance_present"
        and warning.get("source_name") == "effect:nitric_oxide_support"
        and warning.get("target_name") == "Tadalafil"
        for warning in result.warnings
    )


def test_support_relation_warns_when_supporter_missing(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    _remove_component_from_product(
        temp_data,
        product_id="prd_955ea0c9e6",
        substance_id="sub_59bza5s7h0",
    )
    stacks_path = temp_data / "stacks.yaml"
    stacks = yaml.safe_load(stacks_path.read_text())
    stacks["inactive"].remove("prd_955ea0c9e6")
    stacks["daily"].append("prd_955ea0c9e6")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    review_result = cmd_review(data_root=tmp_path)

    assert review_result.exit_code == 0
    assert "missing_source" in review_result.output
    assert "Selenium" in review_result.output
    assert "N-Acetyl Cysteine" in review_result.output


def test_support_relation_accepts_active_supporter_from_another_product(
    tmp_path: Path,
) -> None:
    temp_data = copy_data_tree(tmp_path)
    _remove_component_from_product(
        temp_data,
        product_id="prd_955ea0c9e6",
        substance_id="sub_59bza5s7h0",
    )
    stacks_path = temp_data / "stacks.yaml"
    stacks = yaml.safe_load(stacks_path.read_text())
    stacks["inactive"].remove("prd_955ea0c9e6")
    stacks["inactive"].remove("prd_91a71b69f0")
    stacks["daily"].append("prd_955ea0c9e6")
    stacks["daily"].append("prd_91a71b69f0")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    review_result = cmd_review(data_root=tmp_path)

    assert review_result.exit_code == 0, review_result.output
    relations_output = review_result.output.split("Risk flags", maxsplit=1)[0]
    selenium_nac_line = "[supports] Selenium -> N-Acetyl Cysteine"
    assert selenium_nac_line in relations_output
    both_active_section = relations_output.split("missing_source", maxsplit=1)[0]
    assert selenium_nac_line in both_active_section
    missing_source_section = relations_output.split("missing_source", maxsplit=1)[
        1
    ].split(
        "missing_target",
        maxsplit=1,
    )[0]
    assert selenium_nac_line not in missing_source_section


def _remove_component_from_product(
    temp_data: Path,
    *,
    product_id: str,
    substance_id: str,
) -> None:
    product_path = find_card_path_by_id(temp_data / "products", product_id)
    product = cast(dict[str, Any], yaml.safe_load(product_path.read_text()))
    product["components"] = [
        component
        for component in product["components"]
        if component["substance"] != substance_id
    ]
    product_path.write_text(yaml.safe_dump(product, sort_keys=False))
