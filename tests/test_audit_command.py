from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from planner.engine import cmd_audit
from tests.planner_fixture import copy_data_tree


def test_audit_lists_reference_only_substances_and_cleanup_candidates(
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
    assert "sub_0000000003" in result.cleanup["substances.reference_only"]
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
