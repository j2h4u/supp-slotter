"""Unit tests for scheduling and warning internals (SI-04 through SI-08).

All fixtures are built inline using dataclass constructors.
No live data directory access — no DATA_DIR reads, no disk YAML.
"""

from __future__ import annotations

from planner.cards.relations import collect_missing_support_relations
from planner.cards.substance import format_substance_name
from planner.cards.warnings import humanize_warning
from planner.contracts import (
    Product,
    Relation,
    Slot,
    Substance,
    TraitDef,
    TraitEffect,
    TraitEffectMatch,
)
from planner.engine._scheduling import compute_slot_score, must_separate
from planner.io import LEVEL_SCORES, WARNING_CATEGORY_LABELS

# Shared empty trait_sources sentinel for compute_slot_score tests.
# Tests here do not assert on source attribution in reasons; passing an empty
# dict lets the "or ['unknown']" fallback fire, which is harmless for these assertions.
_NO_SOURCES: dict[str, list[str]] = {}


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def make_slot(near: str = "breakfast", food: bool = True) -> Slot:
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


def make_trait_def(
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


def make_substance(sub_id: str, name: str = "Substance") -> Substance:
    return Substance(id=sub_id, name=name)


def make_product(prd_id: str, name: str, brand: str | None = None) -> Product:
    return Product(id=prd_id, name=name, components=(), brand=brand)


# ---------------------------------------------------------------------------
# SI-04: compute_slot_score
# ---------------------------------------------------------------------------

def test_compute_slot_score_prefer_strong_match() -> None:
    slot = make_slot(near="breakfast", food=True)
    match = TraitEffectMatch(near="breakfast", food=True)
    effect = TraitEffect(match=match, level="prefer_strong")
    trait = make_trait_def("intake:with_food", effects=(effect,))
    trait_defs = {"intake:with_food": trait}

    score, blocked, _ = compute_slot_score({"intake:with_food"}, slot, trait_defs, _NO_SOURCES)

    assert score == LEVEL_SCORES["prefer_strong"]
    assert score > 0
    assert blocked is False


def test_compute_slot_score_avoid_match() -> None:
    slot = make_slot(near="breakfast", food=True)
    match = TraitEffectMatch(near="breakfast")
    effect = TraitEffect(match=match, level="avoid")
    trait = make_trait_def("intake:empty_stomach", effects=(effect,))
    trait_defs = {"intake:empty_stomach": trait}

    score, blocked, _ = compute_slot_score({"intake:empty_stomach"}, slot, trait_defs, _NO_SOURCES)

    assert score == LEVEL_SCORES["avoid"]
    assert score < 0
    assert blocked is False


def test_compute_slot_score_block_on_matching_slot() -> None:
    slot = make_slot(near="sleep", food=False)
    match = TraitEffectMatch(near="sleep")
    effect = TraitEffect(match=match, block=True)
    trait = make_trait_def("effect:stimulant", effects=(effect,))
    trait_defs = {"effect:stimulant": trait}

    score, blocked, _ = compute_slot_score({"effect:stimulant"}, slot, trait_defs, _NO_SOURCES)

    assert blocked is True
    assert score == 0


def test_compute_slot_score_empty_traits() -> None:
    slot = make_slot()
    score, blocked, _ = compute_slot_score(set(), slot, {}, _NO_SOURCES)

    assert score == 0
    assert blocked is False


def test_compute_slot_score_no_matching_effects() -> None:
    slot = make_slot(near="breakfast", food=True)
    match = TraitEffectMatch(near="sleep")
    effect = TraitEffect(match=match, level="prefer_strong")
    trait = make_trait_def("intake:night_only", effects=(effect,))
    trait_defs = {"intake:night_only": trait}

    score, blocked, _ = compute_slot_score({"intake:night_only"}, slot, trait_defs, _NO_SOURCES)

    assert score == 0
    assert blocked is False


def test_compute_slot_score_food_axis_match() -> None:
    # food=False match fires on a food=False slot regardless of near value (wildcard).
    slot = make_slot(near="breakfast", food=False)
    match = TraitEffectMatch(near=None, food=False)
    effect = TraitEffect(match=match, level="prefer_strong")
    trait = make_trait_def("intake:empty_stomach_food_axis", effects=(effect,))
    trait_defs = {"intake:empty_stomach_food_axis": trait}

    score, blocked, _ = compute_slot_score(
        {"intake:empty_stomach_food_axis"}, slot, trait_defs, _NO_SOURCES
    )

    assert score == LEVEL_SCORES["prefer_strong"]
    assert blocked is False


def test_compute_slot_score_food_axis_mismatch() -> None:
    # food=False effect does not fire on a food=True slot — discriminant blocks accumulation.
    slot = make_slot(near="breakfast", food=True)
    match = TraitEffectMatch(near=None, food=False)
    effect = TraitEffect(match=match, level="prefer_strong")
    trait = make_trait_def("intake:empty_stomach_food_axis", effects=(effect,))
    trait_defs = {"intake:empty_stomach_food_axis": trait}

    score, blocked, _ = compute_slot_score(
        {"intake:empty_stomach_food_axis"}, slot, trait_defs, _NO_SOURCES
    )

    assert score == 0
    assert blocked is False


def test_compute_slot_score_food_axis_block() -> None:
    # block path fires when food axis matches — blocked is True.
    slot = make_slot(near="breakfast", food=False)
    match = TraitEffectMatch(near=None, food=False)
    effect = TraitEffect(match=match, block=True)
    trait = make_trait_def("effect:food_blocker", effects=(effect,))
    trait_defs = {"effect:food_blocker": trait}

    _, blocked, _ = compute_slot_score(
        {"effect:food_blocker"}, slot, trait_defs, _NO_SOURCES
    )

    assert blocked is True


# ---------------------------------------------------------------------------
# SI-05: must_separate
# ---------------------------------------------------------------------------

def test_must_separate_t1_declares_against_t2() -> None:
    trait_a = make_trait_def("class:trait_a", separate_from=("class:trait_b",))
    trait_defs = {
        "class:trait_a": trait_a,
        "class:trait_b": make_trait_def("class:trait_b"),
    }

    result = must_separate({"class:trait_a"}, {"class:trait_b"}, trait_defs)

    assert result is True


def test_must_separate_symmetric_t2_declares_against_t1() -> None:
    trait_b = make_trait_def("class:trait_b", separate_from=("class:trait_a",))
    trait_defs = {
        "class:trait_a": make_trait_def("class:trait_a"),
        "class:trait_b": trait_b,
    }

    result = must_separate({"class:trait_a"}, {"class:trait_b"}, trait_defs)

    assert result is True


def test_must_separate_neither_declares() -> None:
    trait_defs = {
        "class:trait_a": make_trait_def("class:trait_a"),
        "class:trait_b": make_trait_def("class:trait_b"),
    }

    result = must_separate({"class:trait_a"}, {"class:trait_b"}, trait_defs)

    assert result is False


# ---------------------------------------------------------------------------
# SI-06: humanize_warning
# ---------------------------------------------------------------------------

def test_humanize_warning_missing_balance_known_substances() -> None:
    sub_src = make_substance("sub_src", "Magnesium")
    sub_tgt = make_substance("sub_tgt", "Calcium")
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
        "type": "safety_concern",
        "message": "This requires operator attention to resolve.",
    }

    result = humanize_warning(warning, products={}, substances={})

    assert "note" not in result


def test_humanize_warning_resolves_known_product_id_to_display_name() -> None:
    prd = make_product("prd_x", "Omega Formula", brand="Brand")
    warning = {"type": "safety_concern", "product": "prd_x"}

    result = humanize_warning(warning, products={"prd_x": prd}, substances={})

    assert result["product"] == "Brand - Omega Formula"


def test_humanize_warning_keeps_raw_product_id_when_unknown() -> None:
    warning = {"type": "safety_concern", "product": "prd_x"}

    result = humanize_warning(warning, products={}, substances={})

    assert result["product"] == "prd_x"


def test_humanize_warning_resolves_known_substance_id_to_display_name() -> None:
    sub = make_substance("sub_x", "Magnesium")
    warning = {"type": "safety_concern", "substance": "sub_x"}

    result = humanize_warning(warning, products={}, substances={"sub_x": sub})

    assert result["substance"] == format_substance_name(sub)


def test_humanize_warning_source_target_fall_back_to_name_when_substance_absent() -> None:
    warning = {
        "type": "missing_balance_substance",
        "source_substance": "sub_missing",
        "source_name": "Magnesium",
        "target_substance": "sub_also_missing",
        "target_name": "Calcium",
    }

    result = humanize_warning(warning, products={}, substances={})

    assert result["source"] == "Magnesium"
    assert result["target"] == "Calcium"


def test_humanize_warning_risk_cluster_load_renders_cluster_and_active_members() -> None:
    sub_a = make_substance("sub_a", "EPA")
    sub_b = make_substance("sub_b", "Ginkgo")
    warning = {
        "type": "risk_cluster_load",
        "cluster": "Bleeding Load",
        "active": ["sub_a", "sub_b"],
    }

    result = humanize_warning(
        warning,
        products={},
        substances={"sub_a": sub_a, "sub_b": sub_b},
    )

    assert result["risk"] == "Bleeding Load"
    assert result["concern"] == "Bleeding Load"
    assert result["active"] == [
        format_substance_name(sub_a),
        format_substance_name(sub_b),
    ]


def test_humanize_warning_trait_drives_concern_text() -> None:
    warning = {"type": "review", "trait": "risk:bleeding_load"}

    result = humanize_warning(warning, products={}, substances={})

    assert result["concern"] == "bleeding load"


def test_humanize_warning_relation_drives_concern_text_when_no_trait() -> None:
    warning = {"type": "review", "relation": "competes_for_absorption"}

    result = humanize_warning(warning, products={}, substances={})

    assert result["concern"] == "competes for absorption"


def test_humanize_warning_explicit_action_overrides_default_lookup() -> None:
    warning = {"type": "safety_concern", "action": "Custom action text"}

    result = humanize_warning(warning, products={}, substances={})

    assert result["action"] == "Custom action text"


def test_humanize_warning_default_action_used_when_warning_lacks_action() -> None:
    warning = {"type": "safety_concern"}

    result = humanize_warning(warning, products={}, substances={})

    assert result["action"] == (
        "Review this safety concern before treating the schedule as final."
    )


def test_humanize_warning_non_string_message_does_not_emit_note() -> None:
    warning = {"type": "review", "message": {"nested": "dict"}}

    result = humanize_warning(warning, products={}, substances={})

    assert "note" not in result


# ---------------------------------------------------------------------------
# SI-08: collect_missing_support_relations — directional semantics
# Convention: source = cofactor/enabler, target = primary actor.
# Warning fires only when target (primary) is active and source (cofactor) absent.
# ---------------------------------------------------------------------------

def test_collect_missing_support_relations_source_active_target_absent_no_warning() -> None:
    """Cofactor (source) present but primary actor (target) absent does NOT warn.

    supports is intentionally unidirectional: cofactors have independent functions
    and do not require their primary actor to be present in the stack.
    """
    sub_src = make_substance("sub_src", "Src")
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

    assert len(result) == 0


def test_collect_missing_support_relations_target_active_source_absent_emits_warning() -> None:
    """Target-active / source-absent direction triggers the missing_support_substance warning."""
    sub_src = make_substance("sub_src", "Src Supporter")
    sub_tgt = make_substance("sub_tgt", "Tgt Supported")
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
