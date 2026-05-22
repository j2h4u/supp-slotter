from __future__ import annotations

from typing import Any, cast

import yaml

from planner.paths import ROOT

REMOVED_EFFECT_SLUGS = {
    "ala_source_context",
    "ergogenic",
    "fatty_acid_metabolism_context",
    "food_matrix_context",
    "immune_function_context",
    "lipid_metabolic_context",
    "methylxanthine_context",
    "nerve_muscle_function",
    "omega3_source",
    "phytonutrient_blend_context",
    "protein_synthesis_context",
    "sleep_onset_context",
    "sleep_timing_support",
    "vitamin_c_food_matrix_context",
    "wound_healing_context",
}

def _effect_registry() -> dict[str, dict[str, Any]]:
    loaded = yaml.safe_load(
        (ROOT / "data/traits/effects.yaml").read_text(encoding="utf-8")
    )
    data = cast(dict[str, Any], loaded)
    assert isinstance(data, dict)
    effects_obj = data["effect"]
    assert isinstance(effects_obj, dict)
    return cast(dict[str, dict[str, Any]], effects_obj)


def _substance_effect_slugs() -> set[str]:
    slugs: set[str] = set()
    for path in (ROOT / "data/substances").glob("*.yaml"):
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            continue
        data = cast(dict[str, Any], loaded)
        knowledge_obj = data.get("knowledge")
        if not isinstance(knowledge_obj, dict):
            continue
        knowledge_dict = cast(dict[str, Any], knowledge_obj)
        effects_obj = knowledge_dict.get("effect")
        if not isinstance(effects_obj, list):
            continue
        effects = cast(list[Any], effects_obj)
        slugs.update(slug for slug in effects if isinstance(slug, str))
    return slugs


def test_removed_effect_slugs_do_not_return() -> None:
    registry_slugs = set(_effect_registry())
    substance_slugs = _substance_effect_slugs()

    assert registry_slugs.isdisjoint(REMOVED_EFFECT_SLUGS)
    assert substance_slugs.isdisjoint(REMOVED_EFFECT_SLUGS)


def test_effects_are_not_placeholder_descriptions() -> None:
    registry = _effect_registry()

    for slug, metadata in registry.items():
        description = metadata["description"]
        applies_when = metadata["applies_when"]
        assert not description.startswith("Reviewer-only effect axis for"), slug
        assert not applies_when.startswith("Use when a substance should be surfaced"), slug
