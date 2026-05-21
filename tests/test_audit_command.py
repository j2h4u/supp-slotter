from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from planner.engine import cmd_audit
from tests.planner_fixture import copy_data_tree


def test_audit_lists_knowledge_only_substances_and_cleanup_candidates(
    tmp_path: Path,
) -> None:
    temp_data = copy_data_tree(tmp_path)

    orphan_substance: dict[str, Any] = {
        "id": "sub_0000000003",
        "name": "Orphan Substance",
    }
    (temp_data / "substances/orphan_substance__sub_0000000003.yaml").write_text(
        yaml.safe_dump(orphan_substance, sort_keys=False)
    )

    orphan_product = {
        "id": "prd_0000000004",
        "name": "Orphan Product",
        "components": [{"substance": "sub_877c24aad4"}],
    }
    (temp_data / "products/unknown__orphan_product__prd_0000000004.yaml").write_text(
        yaml.safe_dump(orphan_product, sort_keys=False)
    )

    traits_path = temp_data / "traits" / "risks.yaml"
    traits = yaml.safe_load(traits_path.read_text())
    traits_dict = cast(dict[str, Any], traits)
    risk_dict = cast(dict[str, Any], traits_dict["risk"])
    risk_dict["orphan_trait"] = {
        "label": "Orphan Trait",
        "description": "Unused fixture trait.",
        "applies_when": "Fixture only.",
    }
    traits_path.write_text(yaml.safe_dump(traits_dict, sort_keys=False))

    schedule_traits_path = temp_data / "traits" / "schedule.yaml"
    schedule_traits = yaml.safe_load(schedule_traits_path.read_text())
    schedule_traits_dict = cast(dict[str, Any], schedule_traits)
    timing_dict = cast(dict[str, Any], schedule_traits_dict["timing"])
    timing_dict["fixture_unused_scheduler_trait"] = {
        "label": "Fixture Unused Scheduler Trait",
        "description": "Unused planner capability.",
        "applies_when": "Fixture only.",
    }
    schedule_traits_path.write_text(yaml.safe_dump(schedule_traits_dict, sort_keys=False))

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.cleanup
    assert any(
        "Orphan Substance (sub_0000000003)" == entry
        for entry in result.cleanup["substances.knowledge_only"]
    )
    assert "prd_0000000004" in result.cleanup["products.without_stack"]
    assert "risk:orphan_trait" in result.cleanup["traits.unused"]
    assert "timing:fixture_unused_scheduler_trait" not in result.cleanup["traits.unused"]


def test_audit_lists_similar_substance_cards(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)

    duplicate_like_substance: dict[str, Any] = {
        "id": "sub_0000000005",
        "name": "Magnesium Bisglycinate",
    }
    (temp_data / "substances/magnesium_bisglycinate__sub_0000000005.yaml").write_text(
        yaml.safe_dump(duplicate_like_substance, sort_keys=False)
    )

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.cleanup
    similar = result.cleanup["substances.similar_names"]
    combined = "\n".join(similar)
    assert "sub_0000000005 Magnesium Bisglycinate" in combined
    assert "sub_7e02eab0d1 Magnesium (glycinate)" in combined


def test_audit_does_not_flag_distinct_substances_sharing_a_form(
    tmp_path: Path,
) -> None:
    temp_data = copy_data_tree(tmp_path)

    fixture_substances = {
        "fixture_calcium_shared_form__sub_0000000010.yaml": {
            "id": "sub_0000000010",
            "name": "Calcium",
            "form": "Shared Extract Matrix",
        },
        "fixture_magnesium_shared_form__sub_0000000011.yaml": {
            "id": "sub_0000000011",
            "name": "Magnesium",
            "form": "Shared Extract Matrix",
        },
    }
    for filename, data in fixture_substances.items():
        (temp_data / "substances" / filename).write_text(
            yaml.safe_dump(data, sort_keys=False)
        )

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.cleanup
    similar = result.cleanup["substances.similar_names"]
    assert not any(
        "sub_0000000010 Calcium (Shared Extract Matrix)" in cluster
        and "sub_0000000011 Magnesium (Shared Extract Matrix)" in cluster
        for cluster in similar
    )


def test_full_audit_uses_digestive_enzyme_intake_rules(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)

    systemic_enzyme: dict[str, Any] = {
        "id": "sub_0000000006",
        "name": "Fixture Systemic Enzyme",
        "schedule": {"intake": ["food_preferred"]},
        "knowledge": {"is": ["enzyme"]},
    }
    (temp_data / "substances/fixture_systemic_enzyme__sub_0000000006.yaml").write_text(
        yaml.safe_dump(systemic_enzyme, sort_keys=False)
    )

    result = cmd_audit(data_root=tmp_path, full=True)

    assert result.exit_code == 0, result.full
    intake_review = "\n".join(result.full["full.intake_review"])
    assert "Fixture Systemic Enzyme" in intake_review
    assert "Alpha amylase" not in intake_review
    assert "Bromelain" not in intake_review
    assert "Lipase" not in intake_review
    assert "Papain" not in intake_review


def test_full_audit_accepts_soft_food_preferences_for_fats_and_minerals(
    tmp_path: Path,
) -> None:
    temp_data = copy_data_tree(tmp_path)

    fixture_substances = {
        "fixture_fat_oil__sub_0000000007.yaml": {
            "id": "sub_0000000007",
            "name": "Fixture Fat Oil",
            "schedule": {"intake": ["food_preferred"]},
            "knowledge": {"is": ["fat_soluble"]},
        },
        "fixture_neutral_mineral__sub_0000000008.yaml": {
            "id": "sub_0000000008",
            "name": "Fixture Neutral Mineral",
            "schedule": {"intake": ["food_neutral"]},
            "knowledge": {"is": ["mineral"]},
        },
    }
    for filename, data in fixture_substances.items():
        (temp_data / "substances" / filename).write_text(
            yaml.safe_dump(data, sort_keys=False)
        )

    result = cmd_audit(data_root=tmp_path, full=True)

    assert result.exit_code == 0, result.full
    intake_review = "\n".join(result.full["full.intake_review"])
    assert "Fixture Fat Oil" not in intake_review
    assert "Flaxseed oil" not in intake_review
    assert "Fixture Neutral Mineral" in intake_review


def test_full_audit_lists_active_product_source_gaps(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    product_path = temp_data / "products" / "fixture_source_gap__prd_0000000023.yaml"
    product_path.write_text(
        yaml.safe_dump(
            {
                "id": "prd_0000000023",
                "name": "Fixture Source Gap",
                "components": [
                    {
                        "substance": "sub_877c24aad4",
                        "label": "Fixture Component",
                    }
                ],
            },
            sort_keys=False,
        )
    )
    stacks_path = temp_data / "stacks.yaml"
    stacks = yaml.safe_load(stacks_path.read_text())
    stacks["daily"].append("prd_0000000023")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    result = cmd_audit(data_root=tmp_path, full=True)

    assert result.exit_code == 0, result.full
    source_gaps = "\n".join(result.full["full.active_product_source"])
    assert "Fixture Source Gap (prd_0000000023)" in source_gaps
    assert "no brand" in source_gaps
    assert "no urls" in source_gaps
    assert "components without amount: Fixture Component (no component note)" in source_gaps


def test_audit_warns_empty_cluster(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)

    traits_path = temp_data / "traits" / "context.yaml"
    traits_dict: dict[str, Any] = {"context": {}}
    cast(dict[str, Any], traits_dict["context"])["empty_cluster_probe_xyz"] = {
        "label": "Empty Cluster Probe",
        "description": "Fixture trait for empty_cluster test.",
        "applies_when": "Fixture only.",
    }
    traits_path.write_text(yaml.safe_dump(traits_dict, sort_keys=False))

    dashboards_dir = temp_data / "dashboards"
    dashboards_dir.mkdir(exist_ok=True)
    (dashboards_dir / "empty_cluster_probe_xyz.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "Empty Cluster Probe Dashboard",
                "description": "Fixture.",
                "from_traits": {"context": ["empty_cluster_probe_xyz"]},
                "benefit": {"description": "Fixture benefit."},
            },
            sort_keys=False,
        )
    )

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.cleanup
    empty_cluster_entries = result.cleanup["dashboard.empty_cluster"]
    assert len(empty_cluster_entries) >= 1
    combined = "\n".join(empty_cluster_entries)
    assert "empty_cluster_probe_xyz" in combined
    assert "union resolution" in combined
    assert "Resolution:" in combined


def test_audit_lists_effect_overlap_review_hints(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)

    traits_path = temp_data / "traits" / "effects.yaml"
    traits = yaml.safe_load(traits_path.read_text())
    traits_dict = cast(dict[str, Any], traits)
    effect_dict = cast(dict[str, Any], traits_dict["effect"])
    effect_dict["fixture_overlap_context"] = {
        "label": "Fixture Overlap Context",
        "description": "Fixture effect overlap context.",
        "applies_when": "Fixture only.",
    }
    effect_dict["fixture_overlap_support"] = {
        "label": "Fixture Overlap Support",
        "description": "Fixture effect overlap support.",
        "applies_when": "Fixture only.",
    }
    traits_path.write_text(yaml.safe_dump(traits_dict, sort_keys=False))

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.cleanup
    effect_overlap_entries = result.cleanup["effects.overlap_review"]
    combined = "\n".join(effect_overlap_entries)
    assert "fixture_overlap_context" in combined
    assert "fixture_overlap_support" in combined
    assert "Review whether these are distinct facts" in combined


def test_audit_lists_relation_name_endpoint_fanout(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    for card_id, form in (
        ("sub_0000000021", "Form A"),
        ("sub_0000000022", "Form B"),
    ):
        substance_path = (
            temp_data
            / "substances"
            / f"fixture_shared_{form.lower().replace(' ', '_')}__{card_id}.yaml"
        )
        substance_path.write_text(
            yaml.safe_dump(
                {"id": card_id, "name": "Fixture Shared", "form": form},
                sort_keys=False,
            )
        )
    relations_path = temp_data / "relations.yaml"
    relations = yaml.safe_load(relations_path.read_text())
    relations.setdefault("supports", []).append(
        {
            "source_name": "Fixture Shared",
            "target_name": "N-Acetyl Cysteine",
            "reason": "Fixture all-form relation.",
        }
    )
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.cleanup
    fanout = "\n".join(result.cleanup["relations.name_fanout"])
    assert "supports source_name 'Fixture Shared' matches 2 substance cards" in fanout
    assert "otherwise use source_substance" in fanout


def test_audit_suppresses_two_substance_effect_usage_overlap(
    tmp_path: Path,
) -> None:
    temp_data = copy_data_tree(tmp_path)

    traits_path = temp_data / "traits" / "effects.yaml"
    traits = yaml.safe_load(traits_path.read_text())
    traits_dict = cast(dict[str, Any], traits)
    effect_dict = cast(dict[str, Any], traits_dict["effect"])
    effect_dict["fixture_alpha_context"] = {
        "label": "Fixture Alpha Context",
        "description": "Fixture alpha context.",
        "applies_when": "Fixture only.",
    }
    effect_dict["fixture_beta_signal"] = {
        "label": "Fixture Beta Signal",
        "description": "Fixture beta signal.",
        "applies_when": "Fixture only.",
    }
    traits_path.write_text(yaml.safe_dump(traits_dict, sort_keys=False))

    for card_id, name in (
        ("sub_0000000012", "Fixture Usage A"),
        ("sub_0000000013", "Fixture Usage B"),
    ):
        (temp_data / "substances" / f"{name.lower().replace(' ', '_')}__{card_id}.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": card_id,
                    "name": name,
                    "knowledge": {
                        "effect": [
                            "fixture_alpha_context",
                            "fixture_beta_signal",
                        ]
                    },
                },
                sort_keys=False,
            )
        )

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.cleanup
    effect_overlap_entries = result.cleanup["effects.overlap_review"]
    combined = "\n".join(effect_overlap_entries)
    assert "Same effect usage across 2 substances" not in combined
