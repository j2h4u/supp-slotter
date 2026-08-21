from __future__ import annotations

from pathlib import Path
from typing import TypedDict, cast

import pytest
import yaml
from planner.engine import cmd_check, cmd_plan, cmd_review
from planner.ontology.runtime_program import RuntimeRelationWarningRule
from planner.query_model.relations import _RelationReviewContext, _warning_type_for_relation

from tests.helpers import ontology_bundle
from tests.planner_fixture import PlannerFixtureInput, find_card_path_by_id, write_minimal_planner_fixture


class _ProductComponent(TypedDict):
    substance: str


class _ProductCard(TypedDict):
    components: list[_ProductComponent]


Relations = dict[str, list[dict[str, object]]]


def test_relation_review_rule_filter_field_fails_closed() -> None:
    runtime = ontology_bundle().runtime_program
    rule = RuntimeRelationWarningRule(
        id="rule_bad_filter",
        relation_kind="supports",
        warning_type="missing_support_substance",
        filter_field="unsupported_field",
        filter_value="biochemical_mechanism_assertion",
        active_side="target",
        reverse_output=False,
    )

    with pytest.raises(ValueError, match="unsupported filter_field"):
        _warning_type_for_relation(
            "supports",
            "ontology_assertion",
            "biochemical_mechanism_assertion",
            "missing_source",
            _RelationReviewContext(
                (rule,),
                runtime.relation_presence_statuses_by_status,
                runtime.relation_presence_statuses_by_active_side,
            ),
        )


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
                    ("sub_zinc000001", ["kind:mineral"]),
                    ("sub_copper0001", ["kind:mineral"]),
                    ("sub_dthree0001", ["quality:fat_soluble"]),
                    ("sub_citrulline", ["effect:nitric_oxide_support"]),
                ],
                "prd_tadal00001": [("sub_tadal00001", ["role:pharmaceutical", "effect:pde5_inhibition"])],
                "prd_nac0000001": [
                    ("sub_nac0000001", ["kind:amino"]),
                    ("sub_selenium01", ["kind:mineral"]),
                ],
                "prd_selenium01": [("sub_selenium01", ["kind:mineral"])],
            },
            traits={},
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
        "relations": [
            {
                "id": "rel_fixture_balance",
                "relation_type": "balance",
                "assertion_kind": "clinical_review_signal",
                "semantic_family": "nutrient_balance_review_signal",
                "source_selector": {"entity": {"name": "Zinc"}},
                "target_selector": {"entity": {"name": "Copper"}},
                "severity": "medium",
                "reason": "Fixture balance relation.",
                "action": "Review fixture balance.",
            },
            {
                "id": "rel_fixture_supports",
                "relation_type": "supports",
                "assertion_kind": "ontology_assertion",
                "semantic_family": "biochemical_mechanism_assertion",
                "source_selector": {"entity": {"name": "Selenium"}},
                "target_selector": {"entity": {"name": "N-Acetyl Cysteine"}},
                "severity": "low",
                "reason": "Fixture support relation.",
                "action": "Review fixture support relationship in context.",
            },
            {
                "id": "rel_fixture_review_with",
                "relation_type": "review_with",
                "assertion_kind": "clinical_review_signal",
                "semantic_family": "clinical_review_signal",
                "source_selector": {"category": "effect", "term": "nitric_oxide_support"},
                "target_selector": {"category": "effect", "term": "pde5_inhibition"},
                "severity": "medium",
                "reason": "Fixture additive blood-pressure lowering review.",
                "action": "Review fixture NO/PDE5 overlap.",
            },
        ]
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
    assert "Relation outcomes:" in review_result.output
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
    relations["relations"].append({
        "id": "rel_missing_source",
        "relation_type": "supports",
        "assertion_kind": "ontology_assertion",
        "semantic_family": "biochemical_mechanism_assertion",
        "source_selector": {"entity": {"name": "Definitely Missing"}},
        "target_selector": {"entity": {"name": "N-Acetyl Cysteine"}},
        "reason": "Fixture relation.",
    })
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    assert "source_selector.entity.name 'Definitely Missing' has no matching substance name" in "\n".join(result.errors)


def test_relation_validation_accepts_typed_term_endpoint_for_supports(
    tmp_path: Path,
) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relations["relations"].append({
        "id": "rel_cross_category_support",
        "relation_type": "supports",
        "assertion_kind": "ontology_assertion",
        "semantic_family": "biochemical_mechanism_assertion",
        "source_selector": {"category": "kind", "term": "mineral"},
        "target_selector": {"category": "quality", "term": "fat_soluble"},
        "reason": "Fixture category endpoint relation.",
    })
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code == 0, "\n".join(result.errors)


def test_relation_validation_rejects_invalid_selector_shape(
    tmp_path: Path,
) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relations["relations"].append({
        "id": "rel_invalid_selector",
        "relation_type": "supports",
        "assertion_kind": "ontology_assertion",
        "semantic_family": "biochemical_mechanism_assertion",
        "source_selector": {"entity": {"entity_id": "sub_zinc000001"}, "category": "kind", "term": "mineral"},
        "target_selector": {"entity": {"name": "Copper"}},
        "reason": "Fixture relation with mixed source endpoint strategy.",
    })
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)
    error_text = "\n".join(result.errors)

    assert result.exit_code != 0
    assert "relation endpoints must choose exactly one source endpoint and exactly one target endpoint" in error_text
    assert "found source endpoints: category, entity, term" in error_text
    assert "Use the canonical selector shape {entity: {entity_id|name}} or {category, term} on each side." in error_text


def test_typed_selector_relation_does_not_create_a_scheduling_conflict(tmp_path: Path) -> None:
    _write_relation_fixture(tmp_path)

    result = cmd_plan(data_root=tmp_path)

    assert result.exit_code == 0, result
    assert not any(warning.get("type") == "intra_product_relation_conflict" for warning in result.warnings)


def test_relation_validation_rejects_unregistered_trait(tmp_path: Path) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relations["relations"].append({
        "id": "rel_unknown_effect",
        "relation_type": "review_with",
        "assertion_kind": "clinical_review_signal",
        "semantic_family": "clinical_review_signal",
        "source_selector": {"category": "effect", "term": "not_real"},
        "target_selector": {"entity": {"name": "Tadalafil"}},
        "reason": "Fixture relation with misspelled trait slug.",
    })
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    assert "source_selector term 'effect:not_real' is not in canonical ontology vocabulary" in "\n".join(result.errors)


def test_trait_relation_endpoint_warns_by_matching_trait(tmp_path: Path) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relations["relations"].append({
        "id": "rel_effect_to_tadalafil",
        "relation_type": "review_with",
        "assertion_kind": "clinical_review_signal",
        "semantic_family": "clinical_review_signal",
        "source_selector": {"category": "effect", "term": "nitric_oxide_support"},
        "target_selector": {"entity": {"name": "Tadalafil"}},
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
        and warning.get("target_name") == "Tadalafil"
        and warning.get("reason") == "Fixture trait endpoint relation."
        and warning.get("action") == "Review fixture trait endpoint."
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
        and warning.get("source_name") == "Nitric Oxide Support"
        and warning.get("target_substance") == "effect:pde5_inhibition"
        and warning.get("target_name") == "PDE5 Inhibition"
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
    assert "Relation outcomes:" in review_result.output
    assert "Selenium" in review_result.output
    assert "N-Acetyl Cysteine" in review_result.output

    plan_result = cmd_plan(data_root=tmp_path)

    assert plan_result.exit_code == 0, plan_result
    support_warnings = [
        warning
        for warning in plan_result.warnings
        if warning.get("type") == "missing_support_substance"
        and warning.get("source_name") == "Selenium"
        and warning.get("target_name") == "N-Acetyl Cysteine"
    ]
    assert len(support_warnings) == 1
    warning = support_warnings[0]
    assert warning["type"] == "missing_support_substance"
    assert warning["source_name"] == "Selenium"
    assert warning["target_name"] == "N-Acetyl Cysteine"
    assert warning["severity"] == "low"
    assert warning["reason"] == "Fixture support relation."
    assert warning["action"] == "Review fixture support relationship in context."


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
        "Dashboard coverage",
        maxsplit=1,
    )[0]
    selenium_nac_line = "[Support relationship] Selenium -> N-Acetyl Cysteine"
    assert selenium_nac_line in relations_output
    assert "both_active" in relations_output


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
