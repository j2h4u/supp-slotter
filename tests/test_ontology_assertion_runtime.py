"""Runtime parity for generated non-blocking ontology assertions."""

from __future__ import annotations

from planner.query_model import build_stack_read_model

from tests.helpers import ontology_bundle
from tests.scheduling_fixtures import make_substance


def test_assertion_projection_resolves_id_and_name_selectors_without_scheduling_effect() -> None:
    metformin = make_substance("sub_605u9zvqt2", "Metformin")
    b12 = make_substance("sub_b12", "Vitamin B12")

    read_model = build_stack_read_model(
        {metformin.id: metformin, b12.id: b12},
        [],
        ontology_bundle=ontology_bundle(),
    )
    warnings = [
        warning
        for warning in read_model.collect_relation_warnings({metformin.id, b12.id})
        if warning["type"] == "review_with_substance_present"
    ]

    assert len(warnings) == 1
    assert warnings[0]["source_substance"] == metformin.id
    assert warnings[0]["target_substance"] == "Vitamin B12"
    assert warnings[0]["type"] == "review_with_substance_present"


def test_relation_warning_query_does_not_cross_relation_types_with_shared_filter() -> None:
    """A balance assertion must not satisfy the review_with warning rule."""
    zinc = make_substance("sub_zinc", "Zinc")
    copper = make_substance("sub_copper", "Copper")
    read_model = build_stack_read_model(
        {zinc.id: zinc, copper.id: copper},
        [],
        ontology_bundle=ontology_bundle(),
    )

    warnings = read_model.collect_relation_warnings({zinc.id, copper.id})

    assert not [warning for warning in warnings if warning["type"] == "review_with_substance_present"]
