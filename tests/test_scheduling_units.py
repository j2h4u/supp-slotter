"""Unit tests for scheduling and warning internals (SI-04 through SI-08).

All fixtures are built inline using dataclass constructors.
No live data directory access — no DATA_DIR reads, no disk YAML.
"""

from __future__ import annotations

from planner.engine._scheduling import compute_slot_score, must_separate
from planner.cards.warnings import humanize_warning, review_context_key
from planner.cards.relations import collect_missing_support_relations
from planner.contracts import (
    Slot,
    Substance,
    TraitDef,
    TraitEffect,
    TraitEffectMatch,
    Relation,
)
from planner.io import WARNING_CATEGORY_LABELS, LEVEL_SCORES

# Shared empty trait_sources sentinel for compute_slot_score tests.
# Tests here do not assert on source attribution in reasons; passing an empty
# dict lets the "or ['unknown']" fallback fire, which is harmless for these assertions.
_NO_SOURCES: dict[str, list[str]] = {}


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _slot(near: str = "breakfast", food: bool = True) -> Slot:
    return Slot(
        slot_id="test_slot",
        label="Test Slot",
        order=1,
        near=near,  # type: ignore[arg-type]
        food=food,
        pillbox="daily",
        pillbox_label="Daily",
        stack="daily",
    )


def _trait_def(
    trait_id: str,
    *,
    effects: tuple[TraitEffect, ...] = (),
    separate_from: tuple[str, ...] = (),
) -> TraitDef:
    return TraitDef(
        id=trait_id,
        namespace="intake",
        short_name=trait_id,
        label=trait_id,
        description="",
        applies_when="always",
        effects=effects,
        separate_from=separate_from,
    )


def _substance(sub_id: str, name: str = "Substance") -> Substance:
    return Substance(id=sub_id, name=name, traits=())


# ---------------------------------------------------------------------------
# SI-04: compute_slot_score
# ---------------------------------------------------------------------------

def test_compute_slot_score_prefer_strong_match() -> None:
    slot = _slot(near="breakfast", food=True)
    match = TraitEffectMatch(near="breakfast", food=True)
    effect = TraitEffect(match=match, level="prefer_strong")
    trait = _trait_def("intake:with_food", effects=(effect,))
    trait_defs = {"intake:with_food": trait}

    score, blocked, _ = compute_slot_score({"intake:with_food"}, slot, trait_defs, _NO_SOURCES)

    assert score == LEVEL_SCORES["prefer_strong"]
    assert score > 0
    assert blocked is False


def test_compute_slot_score_avoid_match() -> None:
    slot = _slot(near="breakfast", food=True)
    match = TraitEffectMatch(near="breakfast")
    effect = TraitEffect(match=match, level="avoid")
    trait = _trait_def("intake:empty_stomach", effects=(effect,))
    trait_defs = {"intake:empty_stomach": trait}

    score, blocked, _ = compute_slot_score({"intake:empty_stomach"}, slot, trait_defs, _NO_SOURCES)

    assert score == LEVEL_SCORES["avoid"]
    assert score < 0
    assert blocked is False


def test_compute_slot_score_block_on_matching_slot() -> None:
    slot = _slot(near="sleep", food=False)
    match = TraitEffectMatch(near="sleep")
    effect = TraitEffect(match=match, block=True)
    trait = _trait_def("effect:stimulant", effects=(effect,))
    trait_defs = {"effect:stimulant": trait}

    score, blocked, _ = compute_slot_score({"effect:stimulant"}, slot, trait_defs, _NO_SOURCES)

    assert blocked is True
    assert score == 0


def test_compute_slot_score_empty_traits() -> None:
    slot = _slot()
    score, blocked, _ = compute_slot_score(set(), slot, {}, _NO_SOURCES)

    assert score == 0
    assert blocked is False


def test_compute_slot_score_no_matching_effects() -> None:
    slot = _slot(near="breakfast", food=True)
    # effect only fires on "sleep"; slot is "breakfast"
    match = TraitEffectMatch(near="sleep")
    effect = TraitEffect(match=match, level="prefer_strong")
    trait = _trait_def("intake:night_only", effects=(effect,))
    trait_defs = {"intake:night_only": trait}

    score, blocked, _ = compute_slot_score({"intake:night_only"}, slot, trait_defs, _NO_SOURCES)

    assert score == 0
    assert blocked is False


def test_compute_slot_score_food_axis_match() -> None:
    # food=False match fires on a food=False slot regardless of near value (wildcard).
    slot = _slot(near="breakfast", food=False)
    match = TraitEffectMatch(near=None, food=False)
    effect = TraitEffect(match=match, level="prefer_strong")
    trait = _trait_def("intake:empty_stomach_food_axis", effects=(effect,))
    trait_defs = {"intake:empty_stomach_food_axis": trait}

    score, blocked, _ = compute_slot_score(
        {"intake:empty_stomach_food_axis"}, slot, trait_defs, _NO_SOURCES
    )

    assert score == LEVEL_SCORES["prefer_strong"]
    assert blocked is False


def test_compute_slot_score_food_axis_mismatch() -> None:
    # food=False effect does not fire on a food=True slot — discriminant blocks accumulation.
    slot = _slot(near="breakfast", food=True)
    match = TraitEffectMatch(near=None, food=False)
    effect = TraitEffect(match=match, level="prefer_strong")
    trait = _trait_def("intake:empty_stomach_food_axis", effects=(effect,))
    trait_defs = {"intake:empty_stomach_food_axis": trait}

    score, blocked, _ = compute_slot_score(
        {"intake:empty_stomach_food_axis"}, slot, trait_defs, _NO_SOURCES
    )

    assert score == 0
    assert blocked is False


def test_compute_slot_score_food_axis_block() -> None:
    # block path fires when food axis matches — blocked is True.
    slot = _slot(near="breakfast", food=False)
    match = TraitEffectMatch(near=None, food=False)
    effect = TraitEffect(match=match, block=True)
    trait = _trait_def("effect:food_blocker", effects=(effect,))
    trait_defs = {"effect:food_blocker": trait}

    _, blocked, _ = compute_slot_score(
        {"effect:food_blocker"}, slot, trait_defs, _NO_SOURCES
    )

    assert blocked is True


# ---------------------------------------------------------------------------
# SI-05: must_separate
# ---------------------------------------------------------------------------

def test_must_separate_t1_declares_against_t2() -> None:
    trait_a = _trait_def("class:trait_a", separate_from=("class:trait_b",))
    trait_defs = {
        "class:trait_a": trait_a,
        "class:trait_b": _trait_def("class:trait_b"),
    }

    result = must_separate({"class:trait_a"}, {"class:trait_b"}, trait_defs)

    assert result is True


def test_must_separate_symmetric_t2_declares_against_t1() -> None:
    trait_b = _trait_def("class:trait_b", separate_from=("class:trait_a",))
    trait_defs = {
        "class:trait_a": _trait_def("class:trait_a"),
        "class:trait_b": trait_b,
    }

    result = must_separate({"class:trait_a"}, {"class:trait_b"}, trait_defs)

    assert result is True


def test_must_separate_neither_declares() -> None:
    trait_defs = {
        "class:trait_a": _trait_def("class:trait_a"),
        "class:trait_b": _trait_def("class:trait_b"),
    }

    result = must_separate({"class:trait_a"}, {"class:trait_b"}, trait_defs)

    assert result is False


# ---------------------------------------------------------------------------
# SI-06: humanize_warning
# ---------------------------------------------------------------------------

def test_humanize_warning_missing_balance_known_substances() -> None:
    sub_src = _substance("sub_src", "Magnesium")
    sub_tgt = _substance("sub_tgt", "Calcium")
    substances = {"sub_src": sub_src, "sub_tgt": sub_tgt}

    warning = {
        "type": "missing_balance_substance",
        "source_substance": "sub_src",
        "source_name": "Magnesium",
        "target_substance": "sub_tgt",
        "target_name": "Calcium",
        "reason": "balance pair",
        "action": "",
    }

    result = humanize_warning(warning, products={}, substances=substances)

    assert result["category"] == WARNING_CATEGORY_LABELS["missing_balance_substance"]
    assert "missing" in result["concern"]


def test_humanize_warning_unknown_type_gets_review_category() -> None:
    warning = {
        "type": "totally_unknown_xyz",
        "reason": "something weird",
    }

    result = humanize_warning(warning, products={}, substances={})

    assert result["category"] == "Review"


def test_humanize_warning_operator_attention_message_omits_note() -> None:
    warning = {
        "type": "unmatched_concern",
        "message": "This requires operator attention to resolve.",
    }

    result = humanize_warning(warning, products={}, substances={})

    assert "note" not in result


# ---------------------------------------------------------------------------
# SI-07: review_context_key
# ---------------------------------------------------------------------------

def test_review_context_key_bleeding() -> None:
    result = review_context_key({"concern": "bleeding risk elevated"})
    assert result == "bleeding_context"


def test_review_context_key_potassium() -> None:
    result = review_context_key({"concern": "potassium elevation possible"})
    assert result == "potassium_medication"


def test_review_context_key_timing_conflict() -> None:
    result = review_context_key({"concern": "timing conflict between slots"})
    assert result == "timing_conflicts"


def test_review_context_key_no_match_returns_none() -> None:
    result = review_context_key({"concern": "general wellness information"})
    assert result is None


# ---------------------------------------------------------------------------
# SI-08: collect_missing_support_relations — non-warning direction
# ---------------------------------------------------------------------------

def test_collect_missing_support_relations_source_active_target_absent_returns_empty() -> None:
    """Only target-active / source-absent triggers the warning.

    When source is active and target is absent, no warning should be emitted.
    """
    sub_src = _substance("sub_src", "Src")
    substances = {"sub_src": sub_src}
    active_substances = {"sub_src"}
    relation = Relation(
        type="supports",
        reason="supports pair",
        source_substance="sub_src",
        target_substance="sub_tgt",
    )

    result = collect_missing_support_relations(
        substances=substances,
        active_substances=active_substances,
        global_relations=[relation],
    )

    assert result == []


def test_collect_missing_support_relations_target_active_source_absent_emits_warning() -> None:
    """Target-active / source-absent direction triggers the missing_support_substance warning."""
    sub_src = _substance("sub_src", "Src Supporter")
    sub_tgt = _substance("sub_tgt", "Tgt Supported")
    substances = {"sub_src": sub_src, "sub_tgt": sub_tgt}
    active_substances = {"sub_tgt"}  # target active, source absent
    relation = Relation(
        type="supports",
        reason="supports pair",
        source_substance="sub_src",
        target_substance="sub_tgt",
    )

    result = collect_missing_support_relations(
        substances=substances,
        active_substances=active_substances,
        global_relations=[relation],
    )

    assert len(result) == 1
    warning = result[0]
    assert warning["type"] == "missing_support_substance"
    assert warning["source_substance"] == "sub_src"
    assert warning["source_name"] == sub_src.name
    assert warning["target_substance"] == "sub_tgt"
    assert warning["target_name"] == sub_tgt.name
    assert warning["reason"] == "supports pair"
