"""Unit tests for warning humanization."""

from __future__ import annotations

import pytest
from planner.cards.substance import format_substance_name
from planner.cards.warnings import humanize_warning
from planner.ontology.warning_policy import PYTHON_EMITTED_WARNING_TYPES, check_python_emitted_warning_types

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

    result = humanize_warning(warning, products={}, substances=substances)

    assert result["category"] == "Missing balancing substance"
    concern = result["concern"]
    assert isinstance(concern, str)
    assert "missing" in concern


def test_humanize_warning_unknown_type_fails_closed() -> None:
    warning = warning_payload(type="totally_unknown_xyz", reason="something weird")

    with pytest.raises(ValueError, match="not declared in ontology warning_types"):
        humanize_warning(warning, products={}, substances={})


def test_humanize_warning_missing_type_fails_closed() -> None:
    warning = warning_payload(reason="something weird")

    with pytest.raises(ValueError, match="missing required ontology warning type"):
        humanize_warning(warning, products={}, substances={})


def test_humanize_warning_unknown_type_with_bundle_fails_closed() -> None:
    warning = warning_payload(type="totally_unknown_xyz", reason="something weird")

    with pytest.raises(ValueError, match="not declared in ontology warning_types"):
        humanize_warning(warning, products={}, substances={}, ontology_bundle=ontology_bundle())


def test_emitted_warning_types_are_declared_in_ontology() -> None:
    declared_warning_types = set(ontology_bundle().runtime_program.warning_types_by_type)

    assert declared_warning_types >= PYTHON_EMITTED_WARNING_TYPES
    assert check_python_emitted_warning_types(ontology_bundle()) == []


def test_trait_review_warning_uses_ontology_policy_with_bundle() -> None:
    warning = warning_payload(type="trait_review", trait="risk:narrow_therapeutic_window", action="")

    result = humanize_warning(warning, products={}, substances={}, ontology_bundle=ontology_bundle())

    assert result["category"] == "Trait review"
    assert result["action"] == "Review total daily amount across products and avoid accidental stacking."


def test_humanize_warning_operator_attention_message_omits_note() -> None:
    warning = warning_payload(type="safety_concern", message="This requires operator attention to resolve.")

    result = humanize_warning(warning, products={}, substances={})

    assert "note" not in result


def test_humanize_warning_resolves_known_product_id_to_display_name() -> None:
    prd = make_product("prd_x", "Omega Formula", brand="Brand")
    warning = warning_payload(type="safety_concern", product="prd_x")

    result = humanize_warning(warning, products={"prd_x": prd}, substances={})

    assert result["product"] == "Brand - Omega Formula"


def test_humanize_warning_keeps_raw_product_id_when_unknown() -> None:
    warning = warning_payload(type="safety_concern", product="prd_x")

    result = humanize_warning(warning, products={}, substances={})

    assert result["product"] == "prd_x"


def test_humanize_warning_resolves_known_substance_id_to_display_name() -> None:
    sub = make_substance("sub_x", "Magnesium")
    warning = warning_payload(type="safety_concern", substance="sub_x")

    result = humanize_warning(warning, products={}, substances={"sub_x": sub})

    assert result["substance"] == format_substance_name(sub)


def test_humanize_warning_source_target_fall_back_to_name_when_substance_absent() -> None:
    warning = warning_payload(
        type="missing_balance_substance",
        source_substance="sub_missing",
        source_name="Magnesium",
        target_substance="sub_also_missing",
        target_name="Calcium",
    )

    result = humanize_warning(warning, products={}, substances={})

    assert result["source"] == "Magnesium"
    assert result["target"] == "Calcium"


def test_humanize_warning_trait_drives_concern_text() -> None:
    warning = warning_payload(type="trait_review", trait="risk:bleeding_med_interaction")

    result = humanize_warning(warning, products={}, substances={})

    assert result["concern"] == "bleeding med interaction"


def test_humanize_warning_relation_drives_concern_text_when_no_trait() -> None:
    warning = warning_payload(type="trait_review", relation="competes_for_absorption")

    result = humanize_warning(warning, products={}, substances={})

    assert result["concern"] == "competes for absorption"


def test_humanize_warning_explicit_action_overrides_default_lookup() -> None:
    warning = warning_payload(type="safety_concern", action="Custom action text")

    result = humanize_warning(warning, products={}, substances={})

    assert result["action"] == "Custom action text"


def test_humanize_warning_default_action_used_when_warning_lacks_action() -> None:
    warning = warning_payload(type="safety_concern")

    result = humanize_warning(warning, products={}, substances={})

    assert result["action"] == ("Review this safety concern before treating the schedule as final.")


def test_humanize_warning_non_string_message_does_not_emit_note() -> None:
    warning = warning_payload(type="trait_review", message={"nested": "dict"})

    result = humanize_warning(warning, products={}, substances={})

    assert "note" not in result
