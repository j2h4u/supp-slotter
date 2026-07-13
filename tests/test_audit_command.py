from __future__ import annotations

import contextlib
import io
from pathlib import Path
from typing import cast

import yaml
from planner.engine import cmd_audit

from tests.planner_fixture import write_yaml


def _load_yaml_dict(path: Path) -> dict[str, object]:
    loaded = cast(object, yaml.safe_load(path.read_text(encoding="utf-8")))
    assert isinstance(loaded, dict)
    return cast(dict[str, object], loaded)


def _dict_entry(mapping: dict[str, object], key: str) -> dict[str, object]:
    value = mapping[key]
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _write_audit_fixture(tmp_path: Path) -> Path:
    temp_data = tmp_path / "data"
    write_yaml(
        temp_data / "pillboxes.yaml",
        {
            "daily": {
                "label": "Daily",
                "slots": {
                    "morning_empty": {
                        "label": "Morning empty",
                        "order": 1,
                        "near": "wake",
                        "food": False,
                    }
                },
            },
            "training": {
                "label": "Training",
                "slots": {
                    "pre_workout": {
                        "label": "Pre-workout",
                        "order": 1,
                        "near": "workout_before",
                        "food": False,
                    }
                },
            },
        },
    )
    write_yaml(
        temp_data / "stacks.yaml",
        {"daily": ["prd_0000000100"], "training": [], "inactive": []},
    )
    write_yaml(
        temp_data / "substances/magnesium_glycinate__sub_0000000100.yaml",
        {
            "id": "sub_0000000100",
            "name": "Magnesium",
            "form": "glycinate",
            "schedule": {"timing": ["energy_like"]},
            "knowledge": {"kind": ["mineral"]},
        },
    )
    write_yaml(
        temp_data / "products/fixture_active_product__prd_0000000100.yaml",
        {
            "id": "prd_0000000100",
            "name": "Fixture Active Product",
            "components": [{"substance": "sub_0000000100"}],
        },
    )
    write_yaml(
        temp_data / "traits/classes.yaml",
        {
            "is": {
                "mineral": {
                    "label": "Mineral",
                    "description": "Fixture mineral class.",
                    "applies_when": "Fixture only.",
                },
                "fat_soluble": {
                    "label": "Fat-soluble",
                    "description": "Fixture fat-soluble class.",
                    "applies_when": "Fixture only.",
                },
                "enzyme": {
                    "label": "Enzyme",
                    "description": "Fixture enzyme class.",
                    "applies_when": "Fixture only.",
                },
                "nootropic": {
                    "label": "Nootropic",
                    "description": "Fixture nootropic class.",
                    "applies_when": "Fixture only.",
                },
            }
        },
    )
    write_yaml(
        temp_data / "traits/schedule.yaml",
        {
            "intake": {
                "food_preferred": {
                    "label": "Food preferred",
                    "description": "Fixture food-preferred intake.",
                    "applies_when": "Fixture only.",
                },
                "food_neutral": {
                    "label": "Food neutral",
                    "description": "Fixture neutral intake.",
                    "applies_when": "Fixture only.",
                },
            },
            "timing": {
                "wake": {
                    "label": "Wake",
                    "description": "Fixture wake timing.",
                    "applies_when": "Fixture only.",
                }
            },
        },
    )
    write_yaml(
        temp_data / "traits/risks.yaml",
        {
            "risk": {
                "manual_review": {
                    "label": "Manual Review",
                    "description": "Fixture manual review risk.",
                    "applies_when": "Fixture only.",
                }
            }
        },
    )
    write_yaml(
        temp_data / "traits/effects.yaml",
        {
            "effect": {
                "fixture_baseline_effect": {
                    "label": "Fixture Baseline Effect",
                    "description": "Fixture baseline effect.",
                    "applies_when": "Fixture only.",
                }
            }
        },
    )
    write_yaml(
        temp_data / "traits/context.yaml",
        {
            "context": {
                "fixture_baseline_context": {
                    "label": "Fixture Baseline Context",
                    "description": "Fixture baseline context.",
                    "applies_when": "Fixture only.",
                }
            }
        },
    )
    write_yaml(
        temp_data / "traits/pathways.yaml",
        {
            "pathway": {
                "fixture_pathway": {
                    "label": "Fixture Pathway",
                    "description": "Fixture pathway.",
                    "applies_when": "Fixture only.",
                }
            }
        },
    )
    write_yaml(temp_data / "relations.yaml", {"relations": []})
    (temp_data / "dashboards").mkdir(parents=True, exist_ok=True)
    return temp_data


def test_audit_lists_knowledge_only_substances_and_cleanup_candidates(
    tmp_path: Path,
) -> None:
    temp_data = _write_audit_fixture(tmp_path)

    orphan_substance: dict[str, object] = {
        "id": "sub_0000000003",
        "name": "Orphan Substance",
    }
    (temp_data / "substances/orphan_substance__sub_0000000003.yaml").write_text(
        yaml.safe_dump(orphan_substance, sort_keys=False)
    )

    orphan_product = {
        "id": "prd_0000000004",
        "name": "Orphan Product",
        "brand": "Fixture Brand",
        "components": [{"substance": "sub_0000000100"}],
    }
    (temp_data / "products/unknown__orphan_product__prd_0000000004.yaml").write_text(
        yaml.safe_dump(orphan_product, sort_keys=False)
    )

    traits_path = temp_data / "traits" / "risks.yaml"
    traits_dict = _load_yaml_dict(traits_path)
    risk_dict = _dict_entry(traits_dict, "risk")
    risk_dict["orphan_trait"] = {
        "label": "Orphan Trait",
        "description": "Unused fixture trait.",
        "applies_when": "Fixture only.",
    }
    traits_path.write_text(yaml.safe_dump(traits_dict, sort_keys=False))

    schedule_traits_path = temp_data / "traits" / "schedule.yaml"
    schedule_traits_dict = _load_yaml_dict(schedule_traits_path)
    timing_dict = _dict_entry(schedule_traits_dict, "timing")
    timing_dict["fixture_unused_scheduler_trait"] = {
        "label": "Fixture Unused Scheduler Trait",
        "description": "Unused planner capability.",
        "applies_when": "Fixture only.",
    }
    schedule_traits_path.write_text(yaml.safe_dump(schedule_traits_dict, sort_keys=False))

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.cleanup
    assert any(entry == "Orphan Substance (sub_0000000003)" for entry in result.cleanup["substances.knowledge_only"])
    assert "Fixture Brand - Orphan Product (prd_0000000004)" in result.cleanup["products.without_stack"]
    # Fixture-local trait files no longer affect the canonical policy audit.
    unused_policies = result.cleanup["ontology.policies.unused"]
    assert "risk:orphan_trait" not in unused_policies
    assert "timing:fixture_unused_scheduler_trait" not in unused_policies
    assert "intake:food_preferred" in unused_policies


def test_audit_lists_similar_substance_cards(tmp_path: Path) -> None:
    temp_data = _write_audit_fixture(tmp_path)

    duplicate_like_substance: dict[str, object] = {
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
    assert "sub_0000000100 Magnesium (glycinate)" in combined


def test_audit_does_not_flag_distinct_substances_sharing_a_form(
    tmp_path: Path,
) -> None:
    temp_data = _write_audit_fixture(tmp_path)

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
        (temp_data / "substances" / filename).write_text(yaml.safe_dump(data, sort_keys=False))

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.cleanup
    similar = result.cleanup["substances.similar_names"]
    assert not any(
        "sub_0000000010 Calcium (Shared Extract Matrix)" in cluster
        and "sub_0000000011 Magnesium (Shared Extract Matrix)" in cluster
        for cluster in similar
    )


def test_full_audit_uses_canonical_kind_projection_without_legacy_is_field(tmp_path: Path) -> None:
    """Full audit must query canonical kind, never the removed is_ projection."""
    _write_audit_fixture(tmp_path)

    result = cmd_audit(data_root=tmp_path, full=True)

    assert result.exit_code == 0, result.full
    assert "full.no_classification" in result.full


def test_full_audit_uses_digestive_enzyme_intake_rules(tmp_path: Path) -> None:
    temp_data = _write_audit_fixture(tmp_path)

    systemic_enzyme: dict[str, object] = {
        "id": "sub_0000000006",
        "name": "Fixture Systemic Enzyme",
        "schedule": {"intake": ["food_preferred"]},
        "knowledge": {"kind": ["enzyme"]},
    }
    (temp_data / "substances/fixture_systemic_enzyme__sub_0000000006.yaml").write_text(
        yaml.safe_dump(systemic_enzyme, sort_keys=False)
    )

    result = cmd_audit(data_root=tmp_path, full=True)

    assert result.exit_code == 0, result.full
    intake_review = "\n".join(result.full["full.intake_review"])
    assert "Fixture Systemic Enzyme" in intake_review


def test_full_audit_accepts_soft_food_preferences_for_fats_and_minerals(
    tmp_path: Path,
) -> None:
    temp_data = _write_audit_fixture(tmp_path)

    fixture_substances = {
        "fixture_fat_oil__sub_0000000007.yaml": {
            "id": "sub_0000000007",
            "name": "Fixture Fat Oil",
            "schedule": {"intake": ["food_preferred"]},
            "knowledge": {"quality": ["fat_soluble"]},
        },
        "fixture_neutral_mineral__sub_0000000008.yaml": {
            "id": "sub_0000000008",
            "name": "Fixture Neutral Mineral",
            "schedule": {"intake": ["food_preferred"]},
            "knowledge": {"kind": ["mineral"]},
        },
    }
    for filename, data in fixture_substances.items():
        (temp_data / "substances" / filename).write_text(yaml.safe_dump(data, sort_keys=False))

    result = cmd_audit(data_root=tmp_path, full=True)

    assert result.exit_code == 0, result.full
    intake_review = "\n".join(result.full["full.intake_review"])
    assert "Fixture Fat Oil" not in intake_review
    assert "Fixture Neutral Mineral" not in intake_review


def test_full_audit_no_intake_only_requires_product_components(
    tmp_path: Path,
) -> None:
    temp_data = _write_audit_fixture(tmp_path)
    (temp_data / "substances/fixture_reference__sub_0000000024.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "sub_0000000024",
                "name": "Fixture Reference",
                "knowledge": {"role": ["nootropic"]},
            },
            sort_keys=False,
        )
    )
    (temp_data / "substances/fixture_product_component__sub_0000000025.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "sub_0000000025",
                "name": "Fixture Product Component",
                "knowledge": {"role": ["nootropic"]},
            },
            sort_keys=False,
        )
    )
    (temp_data / "products/fixture_product__prd_0000000026.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "prd_0000000026",
                "name": "Fixture Product",
                "components": [{"substance": "sub_0000000025"}],
            },
            sort_keys=False,
        )
    )

    result = cmd_audit(data_root=tmp_path, full=True)

    assert result.exit_code == 0, result.full
    missing_intake = "\n".join(result.full["full.no_intake"])
    assert "Fixture Reference" not in missing_intake
    assert "Fixture Product Component" in missing_intake


def test_full_audit_lists_active_product_source_gaps(tmp_path: Path) -> None:
    temp_data = _write_audit_fixture(tmp_path)
    product_path = temp_data / "products" / "fixture_source_gap__prd_0000000023.yaml"
    product_path.write_text(
        yaml.safe_dump(
            {
                "id": "prd_0000000023",
                "name": "Fixture Source Gap",
                "components": [
                    {
                        "substance": "sub_0000000100",
                        "label": "Fixture Component",
                    }
                ],
            },
            sort_keys=False,
        )
    )
    stacks_path = temp_data / "stacks.yaml"
    stacks = _load_yaml_dict(stacks_path)
    cast(list[str], stacks["daily"]).append("prd_0000000023")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    result = cmd_audit(data_root=tmp_path, full=True)

    assert result.exit_code == 0, result.full
    source_gaps = "\n".join(result.full["full.active_product_source"])
    assert "Fixture Source Gap (prd_0000000023)" in source_gaps
    assert "no brand" in source_gaps
    assert "no urls" in source_gaps
    assert "components without amount" not in source_gaps


def test_full_audit_prints_active_product_source_gaps_first(tmp_path: Path) -> None:
    _write_audit_fixture(tmp_path)
    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        result = cmd_audit(data_root=tmp_path, full=True)

    output = stdout.getvalue()
    assert result.exit_code == 0
    full_audit = output.split("Full audit", maxsplit=1)[1]
    first_header = full_audit.split("\n  ", maxsplit=2)[1]
    assert first_header.startswith("Active product source/identity gaps")


def test_audit_rejects_invalid_canonical_relation_before_full_audit(tmp_path: Path) -> None:
    temp_data = _write_audit_fixture(tmp_path)
    write_yaml(
        temp_data / "relations.yaml",
        {
            "balance": [
                {
                    "source_name": "Missing Source Name",
                    "target_name": "Missing Target Name",
                    "reason": "Fixture unknown relation names.",
                }
            ],
            "supports": [
                {
                    "source_substance": "sub_missing001",
                    "target_substance": "sub_missing002",
                    "reason": "Fixture unknown relation ids.",
                }
            ],
            "competes": [],
            "review_with": [],
        },
    )

    result = cmd_audit(data_root=tmp_path, full=True)

    assert result.exit_code != 0
    assert result.full == {}


def test_audit_warns_empty_cluster(tmp_path: Path) -> None:
    temp_data = _write_audit_fixture(tmp_path)

    traits_path = temp_data / "traits" / "context.yaml"
    traits_dict: dict[str, object] = {"context": {}}
    cast(dict[str, object], traits_dict["context"])["empty_cluster_probe_xyz"] = {
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
                "id": "empty_cluster_probe",
                "name": "Empty Cluster Probe Dashboard",
                "description": "Fixture.",
                "selectors": [{"category": "context", "term": "connective_tissue_support"}],
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
    assert "empty_cluster_probe" in combined
    assert "selector" in combined
    assert "Resolution:" in combined


def test_audit_warns_context_tags_without_dashboard_selector(tmp_path: Path) -> None:
    temp_data = _write_audit_fixture(tmp_path)

    traits_path = temp_data / "traits" / "context.yaml"
    traits_dict = {
        "context": {
            "fixture_stale_context": {
                "label": "Fixture Stale Context",
                "description": "Fixture context with no dashboard selector.",
                "applies_when": "Fixture only.",
            }
        }
    }
    traits_path.write_text(yaml.safe_dump(traits_dict, sort_keys=False), encoding="utf-8")

    (temp_data / "substances/fixture_stale_context__sub_0000000027.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "sub_0000000027",
                "name": "Fixture Stale Context Substance",
                "knowledge": {"context": ["connective_tissue_support"]},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.cleanup
    entries = result.cleanup["context.without_dashboard_selector"]
    combined = "\n".join(entries)
    assert "context:connective_tissue_support" in combined
    assert "no dashboard selectors selector consumes it" in combined
    assert "Resolution:" in combined


def test_audit_ignores_legacy_effect_registry_files(
    tmp_path: Path,
) -> None:
    temp_data = _write_audit_fixture(tmp_path)

    traits_path = temp_data / "traits" / "effects.yaml"
    traits_dict = _load_yaml_dict(traits_path)
    effect_dict = _dict_entry(traits_dict, "effect")
    effect_dict["fixture_unconsumed_context"] = {
        "label": "Fixture Unconsumed Context",
        "description": "Fixture no-consumer effect context.",
        "applies_when": "Fixture only.",
    }
    traits_path.write_text(yaml.safe_dump(traits_dict, sort_keys=False), encoding="utf-8")

    for index in range(3):
        card_id = f"sub_000000003{index}"
        (temp_data / "substances" / f"fixture_context_effect_{index}__{card_id}.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": card_id,
                    "name": f"Fixture Context Effect {index}",
                    "knowledge": {"effect": ["cholinergic_support"]},
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.cleanup
    entries = result.cleanup["effects.context_without_consumer"]
    combined = "\n".join(entries)
    assert combined == ""


def test_audit_warns_broad_relation_trait_endpoint(tmp_path: Path) -> None:
    temp_data = _write_audit_fixture(tmp_path)

    for index in range(6):
        card_id = f"sub_000000004{index}"
        (temp_data / "substances" / f"fixture_broad_endpoint_{index}__{card_id}.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": card_id,
                    "name": f"Fixture Broad Endpoint {index}",
                    "knowledge": {"kind": ["mineral"]},
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    write_yaml(
        temp_data / "relations.yaml",
        {
            "relations": [
                {
                    "id": "rel_fixture_broad_endpoint",
                    "type": "review_with",
                    "source_selector": {"category": "kind", "term": "mineral"},
                    "target_selector": {"entity": {"name": "Magnesium"}},
                    "reason": "Fixture broad relation endpoint.",
                }
            ]
        },
    )

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0, result.cleanup
    entries = result.cleanup["relations.broad_trait_endpoint"]
    combined = "\n".join(entries)
    assert "review_with kind:mineral -> Magnesium" in combined
    assert "source trait endpoint kind:mineral resolves to 7 substances" in combined
    assert "Resolution:" in combined


def test_audit_ignores_legacy_effect_overlap_registry_entries(tmp_path: Path) -> None:
    temp_data = _write_audit_fixture(tmp_path)

    traits_path = temp_data / "traits" / "effects.yaml"
    traits_dict = _load_yaml_dict(traits_path)
    effect_dict = _dict_entry(traits_dict, "effect")
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
    assert combined == ""


def test_audit_suppresses_two_substance_effect_usage_overlap(
    tmp_path: Path,
) -> None:
    temp_data = _write_audit_fixture(tmp_path)

    traits_path = temp_data / "traits" / "effects.yaml"
    traits_dict = _load_yaml_dict(traits_path)
    effect_dict = _dict_entry(traits_dict, "effect")
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
