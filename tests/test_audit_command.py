# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml
from planner.engine import cmd_audit

from tests.planner_fixture import write_yaml as _write_yaml


def write_yaml(path: Path, data: dict[str, object]) -> None:
    """Write a synthetic card using direct schedule assignments."""
    _write_yaml(path, data)


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
                "stack": "daily",
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
                "stack": "training",
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
    constraint_anchors = {
        "sub_vvmld46dbz": {"name": "Calcium", "form": "calcium ascorbate"},
        "sub_ses5czfzi1": {"name": "Iron", "form": "Ferrochel ferrous bisglycinate chelate"},
        "sub_8554n79hve": {"name": "Zinc", "form": "citrate"},
        "sub_844a0cc551": {"name": "Copper", "form": "bisglycinate"},
        "sub_844a87d72b": {"name": "Vitamin E", "form": "tocopherol"},
        "sub_5723eafac4": {"name": "Vitamin E", "form": "tocotrienols"},
    }
    for substance_id, fields in constraint_anchors.items():
        write_yaml(
            temp_data / f"substances/constraint_{substance_id}__{substance_id}.yaml",
            {"id": substance_id, **fields},
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
            "kind": {
                "mineral": {
                    "label": "Mineral",
                    "description": "Fixture mineral class.",
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
        temp_data / "traits/qualities.yaml",
        {
            "quality": {
                "fat_soluble": {
                    "label": "Fat-soluble",
                    "description": "Fixture fat-soluble quality.",
                    "applies_when": "Fixture only.",
                }
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
            },
            "timing": {
                "energy_like": {
                    "label": "Energy-like",
                    "description": "Fixture energy-like timing.",
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


def test_audit_uses_flattened_diagnostics_contract(tmp_path: Path) -> None:
    _write_audit_fixture(tmp_path)

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 0
    assert set(result.cleanup) == {"diagnostics"}


def test_audit_fails_closed_on_unknown_relation_entity(tmp_path: Path) -> None:
    data_root = _write_audit_fixture(tmp_path)
    write_yaml(
        data_root / "relations.yaml",
        {
            "relations": [
                {
                    "id": "rel_unknown_entity",
                    "relation_type": "supports",
                    "assertion_kind": "ontology_assertion",
                    "semantic_family": "test",
                    "source_selector": {"entity": {"entity_id": "sub_missing000"}},
                    "target_selector": {"entity": {"entity_id": "sub_0000000100"}},
                    "reason": "unknown relation entity must fail closed",
                }
            ]
        },
    )

    result = cmd_audit(data_root=tmp_path)

    assert result.exit_code == 1
    assert result.full == {}
