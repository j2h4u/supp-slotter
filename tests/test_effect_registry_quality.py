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
    "methylxanthine_context",
    "omega3_source",
    "phytonutrient_blend_context",
    "sleep_onset_context",
    "sleep_timing_support",
    "vitamin_c_food_matrix_context",
    "wound_healing_context",
}

ENRICHED_EFFECT_SLUGS = {
    "anti_inflammatory_context",
    "antioxidant_context",
    "blood_pressure_context",
    "blood_clotting_context",
    "bone_mineral_metabolism_support",
    "calming_context",
    "capillary_support_context",
    "cholinergic_support",
    "digestive_enzyme_context",
    "dna_synthesis_support",
    "energy_production_support",
    "essential_amino_acid_context",
    "fatty_acid_metabolism_support",
    "fibrinolytic",
    "glucose_metabolism_context",
    "glycosaminoglycan_context",
    "homocysteine_metabolism_support",
    "immune_function_support",
    "joint_comfort_context",
    "nerve_muscle_function",
    "ocular_retina_context",
    "pde5_inhibition",
    "platelet_aggregation_modulation",
    "protein_synthesis_context",
    "red_blood_cell_support",
    "redox_metabolism_support",
    "skin_barrier_context",
    "sleep_context",
    "sleep_onset_support",
    "stress_resilience_context",
    "vascular_polyphenol_context",
    "vasodilator",
    "wound_healing_support",
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


def test_enriched_effects_are_not_placeholder_descriptions() -> None:
    registry = _effect_registry()

    for slug in ENRICHED_EFFECT_SLUGS:
        description = registry[slug]["description"]
        applies_when = registry[slug]["applies_when"]
        assert not description.startswith("Reviewer-only effect axis for"), slug
        assert not applies_when.startswith("Use when a substance should be surfaced"), slug
