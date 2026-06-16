from __future__ import annotations

from pathlib import Path
from typing import TypedDict, cast

import yaml

from planner.engine import cmd_check, cmd_plan, cmd_review
from tests.planner_fixture import PlannerFixtureInput, find_card_path_by_id, write_minimal_planner_fixture


class _ProductComponent(TypedDict):
    substance: str


class _ProductCard(TypedDict):
    components: list[_ProductComponent]


class _RelationEntry(TypedDict, total=False):
    source_name: str
    source_substance: str
    source_class: str
    source_trait: str
    target_name: str
    target_substance: str
    target_class: str
    target_trait: str
    reason: str
    severity: str
    action: str


Relations = dict[str, list[_RelationEntry]]


def _write_relation_fixture(tmp_path: Path) -> Path:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={
                "prd_trace00001": {"stack": "daily"},
                "prd_tadal00001": {"stack": "daily"},
                "prd_nac0000001": {"stack": "inactive"},
                "prd_selenium01": {"stack": "inactive"},
            },
            products={
                "prd_trace00001": [
                    ("sub_zinc000001", ["is:mineral", "timing:wake"]),
                    ("sub_copper0001", ["is:mineral", "timing:wake"]),
                    ("sub_dthree0001", ["is:fat_soluble", "timing:wake"]),
                    ("sub_citrulline", ["effect:nitric_oxide_support", "timing:wake"]),
                ],
                "prd_tadal00001": [("sub_tadal00001", ["effect:pde5_inhibition", "timing:wake"])],
                "prd_nac0000001": [
                    ("sub_nac0000001", ["timing:wake"]),
                    ("sub_selenium01", ["timing:wake"]),
                ],
                "prd_selenium01": [("sub_selenium01", ["timing:wake"])],
            },
            traits={
                "is:mineral": {
                    "label": "Mineral",
                    "description": "Fixture mineral class.",
                    "applies_when": "Fixture only.",
                },
                "is:fat_soluble": {
                    "label": "Fat-soluble",
                    "description": "Fixture fat-soluble class.",
                    "applies_when": "Fixture only.",
                },
                "effect:nitric_oxide_support": {
                    "label": "Nitric Oxide Support",
                    "description": "Fixture nitric oxide effect.",
                    "applies_when": "Fixture only.",
                },
                "effect:pde5_inhibition": {
                    "label": "PDE5 Inhibition",
                    "description": "Fixture PDE5 effect.",
                    "applies_when": "Fixture only.",
                },
                "timing:wake": {
                    "label": "Wake",
                    "description": "Fixture wake timing.",
                    "applies_when": "Fixture only.",
                },
            },
        ),
    )
    temp_data = tmp_path / "data"
    _rename_substance(temp_data, "sub_zinc000001", "Zinc")
    _rename_substance(temp_data, "sub_copper0001", "Copper")
    _rename_substance(temp_data, "sub_dthree0001", "Vitamin D")
    _rename_substance(temp_data, "sub_citrulline", "L-Citrulline")
    _rename_substance(temp_data, "sub_tadal00001", "Tadalafil")
    _rename_substance(temp_data, "sub_nac0000001", "N-Acetyl Cysteine")
    _rename_substance(temp_data, "sub_selenium01", "Selenium")
    relations: Relations = {
        "balance": [
            {
                "source_name": "Zinc",
                "target_name": "Copper",
                "severity": "medium",
                "reason": "Fixture balance relation.",
                "action": "Review fixture balance.",
            }
        ],
        "supports": [
            {
                "source_name": "Selenium",
                "target_name": "N-Acetyl Cysteine",
                "reason": "Fixture support relation.",
            }
        ],
        "competes": [
            {
                "source_class": "mineral",
                "target_class": "fat_soluble",
                "reason": "Fixture class relation.",
            }
        ],
        "review_with": [
            {
                "source_trait": "effect:nitric_oxide_support",
                "target_trait": "effect:pde5_inhibition",
                "severity": "medium",
                "reason": "Fixture additive blood-pressure lowering review.",
                "action": "Review fixture NO/PDE5 overlap.",
            }
        ],
    }
    (temp_data / "relations.yaml").write_text(yaml.safe_dump(relations, sort_keys=False))
    return temp_data


def _rename_substance(temp_data: Path, substance_id: str, name: str) -> None:
    substance_path = find_card_path_by_id(temp_data / "substances", substance_id)
    substance = cast(dict[str, object], yaml.safe_load(substance_path.read_text()))
    substance["name"] = name
    substance_path.write_text(yaml.safe_dump(substance, sort_keys=False))


def test_balance_relation_warns_when_related_substance_missing(tmp_path: Path) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    trace_product_path = find_card_path_by_id(
        temp_data / "products",
        "prd_trace00001",
    )
    trace_product = cast(_ProductCard, yaml.safe_load(trace_product_path.read_text()))
    trace_product["components"] = [
        component for component in trace_product["components"] if component["substance"] != "sub_copper0001"
    ]
    trace_product_path.write_text(yaml.safe_dump(trace_product, sort_keys=False))

    review_result = cmd_review(data_root=tmp_path)

    assert review_result.exit_code == 0
    assert "actionable_now" in review_result.output
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
    temp_data = _write_relation_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relations["supports"].append({
        "source_name": "Definitely Missing",
        "target_name": "N-Acetyl Cysteine",
        "reason": "Fixture relation.",
    })
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    assert "source_name 'Definitely Missing' has no matching substance name" in "\n".join(result.errors)


def test_relation_validation_rejects_unregistered_class(tmp_path: Path) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relations.setdefault("competes", []).append({
        "source_class": "minearl",
        "target_class": "fat_soluble",
        "reason": "Fixture relation with misspelled class slug.",
    })
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    error_text = "\n".join(result.errors)
    assert result.exit_code != 0
    assert "source_class 'minearl' is not a registered is: trait" in error_text
    assert "target_class 'fat_soluble'" not in error_text


def test_relation_validation_rejects_class_endpoint_outside_competes(
    tmp_path: Path,
) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relations.setdefault("supports", []).append({
        "source_class": "mineral",
        "target_class": "fat_soluble",
        "reason": "Fixture class endpoint on non-competes relation.",
    })
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    assert "source_class/target_class endpoints are only supported for competes" in ("\n".join(result.errors))


def test_relation_validation_explains_endpoint_strategy_conflicts(
    tmp_path: Path,
) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relations.setdefault("supports", []).append({
        "source_name": "Zinc",
        "source_substance": "sub_zinc000001",
        "target_name": "Copper",
        "reason": "Fixture relation with mixed source endpoint strategy.",
    })
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)
    error_text = "\n".join(result.errors)

    assert result.exit_code != 0
    assert "relation endpoints must choose exactly one source endpoint" in error_text
    assert "source endpoints: source_name, source_substance" in error_text
    assert "is valid under each" not in error_text


def test_class_relation_resolves_for_review_status(tmp_path: Path) -> None:
    _write_relation_fixture(tmp_path)

    review_result = cmd_review(data_root=tmp_path)

    assert review_result.exit_code == 0, review_result.stderr
    relation_line = "[competes] Mineral (is:mineral) -> Fat-soluble (is:fat_soluble)"
    assert relation_line in review_result.output
    actionable_section = review_result.output.split("actionable_now", maxsplit=1)[1].split(
        "active_pair_present", maxsplit=1
    )[0]
    assert relation_line in actionable_section


def test_relation_validation_rejects_unregistered_trait(tmp_path: Path) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relations.setdefault("review_with", []).append({
        "source_trait": "effect:not_real",
        "target_name": "Tadalafil",
        "reason": "Fixture relation with misspelled trait slug.",
    })
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    assert "source_trait 'effect:not_real' is not a registered trait" in "\n".join(result.errors)


def test_trait_relation_endpoint_warns_by_matching_trait(tmp_path: Path) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relations.setdefault("review_with", []).append({
        "source_trait": "effect:nitric_oxide_support",
        "target_name": "Tadalafil",
        "severity": "low",
        "reason": "Fixture trait endpoint relation.",
        "action": "Review fixture trait endpoint.",
    })
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_plan(data_root=tmp_path)

    assert result.exit_code == 0, result
    assert any(
        warning.get("type") == "review_with_substance_present"
        and warning.get("source_substance") == "effect:nitric_oxide_support"
        and warning.get("source_name") == "Nitric Oxide Support (effect:nitric_oxide_support)"
        and warning.get("target_name") == "Tadalafil"
        for warning in result.warnings
    )


def test_nitric_oxide_pde5_trait_relation_warns_for_active_stack(
    tmp_path: Path,
) -> None:
    _write_relation_fixture(tmp_path)

    result = cmd_plan(data_root=tmp_path)

    assert result.exit_code == 0, result
    assert any(
        warning.get("type") == "review_with_substance_present"
        and warning.get("source_substance") == "effect:nitric_oxide_support"
        and warning.get("source_name") == "Nitric Oxide Support (effect:nitric_oxide_support)"
        and warning.get("target_substance") == "effect:pde5_inhibition"
        and warning.get("target_name") == "PDE5 Inhibition (effect:pde5_inhibition)"
        and warning.get("severity") == "medium"
        and "additive blood-pressure lowering" in str(warning.get("reason"))
        for warning in result.warnings
    )


def test_support_relation_warns_when_supporter_missing(tmp_path: Path) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    _remove_component_from_product(
        temp_data,
        product_id="prd_nac0000001",
        substance_id="sub_selenium01",
    )
    stacks_path = temp_data / "stacks.yaml"
    stacks = cast(dict[str, list[object]], yaml.safe_load(stacks_path.read_text()))
    stacks["inactive"].remove("prd_nac0000001")
    stacks["daily"].append("prd_nac0000001")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    review_result = cmd_review(data_root=tmp_path)

    assert review_result.exit_code == 0
    assert "actionable_now" in review_result.output
    assert "Selenium" in review_result.output
    assert "N-Acetyl Cysteine" in review_result.output


def test_support_relation_accepts_active_supporter_from_another_product(
    tmp_path: Path,
) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    _remove_component_from_product(
        temp_data,
        product_id="prd_nac0000001",
        substance_id="sub_selenium01",
    )
    stacks_path = temp_data / "stacks.yaml"
    stacks = cast(dict[str, list[object]], yaml.safe_load(stacks_path.read_text()))
    stacks["inactive"].remove("prd_nac0000001")
    stacks["inactive"].remove("prd_selenium01")
    stacks["daily"].append("prd_nac0000001")
    stacks["daily"].append("prd_selenium01")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    review_result = cmd_review(data_root=tmp_path)

    assert review_result.exit_code == 0, review_result.output
    relations_output = review_result.output.split("Relations", maxsplit=1)[1].split(
        "Risk flags",
        maxsplit=1,
    )[0]
    selenium_nac_line = "[supports] Selenium -> N-Acetyl Cysteine"
    assert selenium_nac_line in relations_output
    active_pair_section = relations_output.split("active_pair_present", maxsplit=1)[1].split(
        "latent_one_side_present",
        maxsplit=1,
    )[0]
    assert selenium_nac_line in active_pair_section


def _remove_component_from_product(
    temp_data: Path,
    *,
    product_id: str,
    substance_id: str,
) -> None:
    product_path = find_card_path_by_id(temp_data / "products", product_id)
    product = cast(_ProductCard, yaml.safe_load(product_path.read_text()))
    product["components"] = [component for component in product["components"] if component["substance"] != substance_id]
    product_path.write_text(yaml.safe_dump(product, sort_keys=False))
