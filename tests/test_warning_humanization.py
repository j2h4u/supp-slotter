"""Unit tests for warning humanization."""

from __future__ import annotations

from dataclasses import replace

import pytest
from planner.cards.safety_warnings import SafetyConcernInput, collect_active_safety_concerns
from planner.cards.substance import format_substance_name
from planner.cards.warnings import humanize_warning
from planner.contracts import Concern
from planner.ontology.glue_capabilities import IMPLEMENTED_WARNING_EMITTER_IDS
from planner.ontology.warning_policy import check_warning_type_references, emitted_warning_types

from tests.helpers import ontology_bundle
from tests.scheduling_fixtures import make_product, make_substance


def warning_payload(**kwargs: object) -> dict[str, object]:
    return kwargs


def test_humanize_warning_missing_balance_known_substances() -> None:
    sub_src = make_substance("sub_src", "Magnesium")
    sub_tgt = make_substance("sub_tgt", "Calcium")
    substances = {"sub_src": sub_src, "sub_tgt": sub_tgt}

    warning = warning_payload(
        type="missing_balance_substance",
        source_substance="sub_src",
        source_name="Magnesium",
        target_substance="sub_tgt",
        target_name="Calcium",
        reason="balance pair",
        action="",
    )

    result = humanize_warning(warning, products={}, substances=substances, ontology_bundle=ontology_bundle())

    assert result["category"] == "Missing balancing substance"
    concern = result["concern"]
    assert isinstance(concern, str)
    assert "missing" in concern.casefold()


def test_humanize_warning_missing_support_uses_conditional_review_policy() -> None:
    warning = warning_payload(type="missing_support_substance")

    result = humanize_warning(warning, products={}, substances={}, ontology_bundle=ontology_bundle())

    assert result["category"] == "Conditional support review"
    assert result["action"] == (
        "Review whether this support relationship is applicable in context; absence from the tracked stack alone "
        "does not establish a need to add or supplement it."
    )


def test_humanize_warning_unknown_type_fails_closed() -> None:
    warning = warning_payload(type="totally_unknown_xyz", reason="something weird")

    with pytest.raises(ValueError, match="not declared in ontology warning_types"):
        humanize_warning(warning, products={}, substances={}, ontology_bundle=ontology_bundle())


def test_emitted_warning_types_are_declared_in_ontology() -> None:
    runtime = ontology_bundle().runtime_program
    declared_warning_types = set(runtime.warning_types_by_type)
    runtime_rule_warning_types = {rule.warning_type for rule in runtime.relation_warning_rules}
    concern_catalog_warning_types = set(runtime.concern_warning_catalog_by_kind.values())

    assert (
        declared_warning_types
        >= emitted_warning_types(runtime) | runtime_rule_warning_types | concern_catalog_warning_types
    )
    assert set(runtime.warning_emitters_by_emitter) == set(IMPLEMENTED_WARNING_EMITTER_IDS)
    assert runtime.concern_warning_catalog_by_kind == {"safety": "safety_concern"}
    assert check_warning_type_references(ontology_bundle()) == []


def test_active_concern_warnings_follow_authored_concern_catalog() -> None:
    runtime = ontology_bundle().runtime_program
    product = replace(
        make_product("prd_x", "Formula"),
        concerns=(
            Concern(kind="safety", text="Review safety."),
            Concern(kind="model_gap", text="Annotation only."),
        ),
    )

    warnings = collect_active_safety_concerns(
        SafetyConcernInput(
            active_order=["item_x"],
            active_components={"item_x": []},
            item_products={"item_x": "prd_x"},
            products={"prd_x": product},
            runtime_program=runtime,
            substances={},
        )
    )

    assert [warning["type"] for warning in warnings] == ["safety_concern"]
    assert [warning["message"] for warning in warnings] == ["Review safety."]


def test_concern_projection_skips_missing_subjects_without_affecting_warning_collection() -> None:
    runtime = ontology_bundle().runtime_program
    warnings = collect_active_safety_concerns(
        SafetyConcernInput(
            active_order=["item_x"],
            active_components={"item_x": ["sub_missing"]},
            item_products={"item_x": "prd_missing"},
            products={},
            runtime_program=runtime,
            substances={},
        )
    )

    assert warnings == []


def test_trait_review_warning_uses_ontology_policy_with_bundle() -> None:
    warning = warning_payload(type="trait_review", trait="risk:narrow_therapeutic_window", action="")

    result = humanize_warning(warning, products={}, substances={}, ontology_bundle=ontology_bundle())

    assert result["category"] == "Trait review"
    assert result["action"] == "Review total daily amount across products and avoid accidental stacking."


def test_humanize_warning_operator_attention_message_omits_note() -> None:
    warning = warning_payload(type="safety_concern", message="This requires operator attention to resolve.")

    result = humanize_warning(warning, products={}, substances={}, ontology_bundle=ontology_bundle())

    assert "note" not in result


def test_humanize_warning_resolves_known_product_id_to_display_name() -> None:
    prd = make_product("prd_x", "Omega Formula", brand="Brand")
    warning = warning_payload(type="safety_concern", product="prd_x")

    result = humanize_warning(warning, products={"prd_x": prd}, substances={}, ontology_bundle=ontology_bundle())

    assert result["product"] == "Brand - Omega Formula"


def test_humanize_warning_keeps_raw_product_id_when_unknown() -> None:
    warning = warning_payload(type="safety_concern", product="prd_x")

    result = humanize_warning(warning, products={}, substances={}, ontology_bundle=ontology_bundle())

    assert result["product"] == "prd_x"


def test_humanize_warning_resolves_known_substance_id_to_display_name() -> None:
    sub = make_substance("sub_x", "Magnesium")
    warning = warning_payload(type="safety_concern", substance="sub_x")

    result = humanize_warning(warning, products={}, substances={"sub_x": sub}, ontology_bundle=ontology_bundle())

    assert result["substance"] == format_substance_name(sub)


def test_humanize_warning_source_target_fall_back_to_name_when_substance_absent() -> None:
    warning = warning_payload(
        type="missing_balance_substance",
        source_substance="sub_missing",
        source_name="Magnesium",
        target_substance="sub_also_missing",
        target_name="Calcium",
    )

    result = humanize_warning(warning, products={}, substances={}, ontology_bundle=ontology_bundle())

    assert result["source"] == "Magnesium"
    assert result["target"] == "Calcium"


def test_humanize_warning_trait_drives_concern_text() -> None:
    warning = warning_payload(type="trait_review", trait="risk:bleeding_med_interaction")

    result = humanize_warning(warning, products={}, substances={}, ontology_bundle=ontology_bundle())

    assert result["concern"] == "Bleeding medication interaction"


def test_humanize_warning_relation_drives_concern_text_when_no_trait() -> None:
    warning = warning_payload(type="trait_review", relation="supports")

    result = humanize_warning(warning, products={}, substances={}, ontology_bundle=ontology_bundle())

    assert result["concern"] == "Support relationship"


def test_humanize_warning_unknown_relation_label_fails_closed() -> None:
    warning = warning_payload(type="trait_review", relation="competes_for_absorption")

    with pytest.raises(ValueError, match="has no authored label"):
        humanize_warning(warning, products={}, substances={}, ontology_bundle=ontology_bundle())


def test_humanize_warning_explicit_action_overrides_default_lookup() -> None:
    warning = warning_payload(type="safety_concern", action="Custom action text")

    result = humanize_warning(warning, products={}, substances={}, ontology_bundle=ontology_bundle())

    assert result["action"] == "Custom action text"


def test_humanize_warning_default_action_used_when_warning_lacks_action() -> None:
    warning = warning_payload(type="safety_concern")

    result = humanize_warning(warning, products={}, substances={}, ontology_bundle=ontology_bundle())

    assert result["action"] == ("Review this safety concern before treating the schedule as final.")


def test_humanize_warning_non_string_message_does_not_emit_note() -> None:
    warning = warning_payload(type="trait_review", message={"nested": "dict"})

    result = humanize_warning(warning, products={}, substances={}, ontology_bundle=ontology_bundle())

    assert "note" not in result
