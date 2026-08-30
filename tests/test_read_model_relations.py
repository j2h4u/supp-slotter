"""Focused acceptance coverage for direct relation classification queries."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from planner.contracts import OntologyAssertion, Product, ProductComponent, Relation, RelationSelector, Substance
from planner.query_model import build_stack_read_model
from planner.query_model.relations import classify_relations, resolve_relation_queries

from tests.helpers import ontology_bundle


@dataclass(frozen=True, slots=True)
class _RepresentativeQueryFixture:
    substances: dict[str, Substance]
    products: dict[str, Product]
    stacks: dict[str, list[str]]
    relations: list[Relation]


@pytest.fixture()
def representative_query_fixture() -> _RepresentativeQueryFixture:
    active_alpha = Substance("sub_active_alpha", "Alpha")
    active_zeta = Substance("sub_active_zeta", "Zeta")
    inactive = Substance("sub_inactive", "Inactive")
    support = Substance("sub_support", "Support")
    substances = {item.id: item for item in (active_alpha, active_zeta, inactive, support)}
    products = {
        "prd_active_alpha": Product(
            "prd_active_alpha", "Alpha", (ProductComponent(active_alpha.id, "cmp_prd_active_alpha__sub_active_alpha"),)
        ),
        "prd_active_zeta": Product(
            "prd_active_zeta", "Zeta", (ProductComponent(active_zeta.id, "cmp_prd_active_zeta__sub_active_zeta"),)
        ),
        "prd_inactive": Product(
            "prd_inactive", "Inactive", (ProductComponent(inactive.id, "cmp_prd_inactive__sub_inactive"),)
        ),
    }
    relations = [
        Relation(
            "rel_support",
            "supports",
            "support reason",
            RelationSelector(entity_id=support.id),
            RelationSelector(entity_id=active_zeta.id),
            action="support action",
            severity="low",
            assertion_kind="ontology_assertion",
            semantic_family="biochemical_mechanism_assertion",
            research_state="unassessed",
            sources=(),
        ),
        Relation(
            "rel_review",
            "review_with",
            "review reason",
            RelationSelector(entity_id=active_alpha.id),
            RelationSelector(entity_id=active_zeta.id),
            action="review action",
            severity="medium",
            assertion_kind="clinical_review_signal",
            semantic_family="clinical_review_signal",
            research_state="unassessed",
            sources=(),
        ),
    ]
    return _RepresentativeQueryFixture(
        substances=substances,
        products=products,
        stacks={"daily": ["prd_active_zeta", "prd_active_alpha"], "inactive": ["prd_inactive"]},
        relations=relations,
    )


def _relation_queries(fixture: _RepresentativeQueryFixture):
    assertions = tuple(
        OntologyAssertion(
            id=relation.id,
            relation_type=relation.type,
            assertion_kind=relation.assertion_kind or "",
            semantic_family=relation.semantic_family or "",
            reason=relation.reason,
            source_selector=relation.source_selector,
            target_selector=relation.target_selector,
            action=relation.action,
            severity=relation.severity,
            research_state=relation.research_state,
            sources=relation.sources,
        )
        for relation in fixture.relations
    )
    return resolve_relation_queries(assertions, fixture.substances, ontology_bundle())


def test_partition_and_direct_relation_classification(
    representative_query_fixture: _RepresentativeQueryFixture,
) -> None:
    fixture = representative_query_fixture
    read_model = build_stack_read_model(
        fixture.substances, [], fixture.products, fixture.stacks, ontology_bundle=ontology_bundle()
    )

    active = read_model.active_substance_ids()
    assert active == {"sub_active_alpha", "sub_active_zeta"}
    assert read_model.inactive_substance_ids() == {"sub_inactive"}

    rows = classify_relations(_relation_queries(fixture), active, ontology_bundle().runtime_program)
    assert [
        (row["type"], row["source_matches"], row["target_matches"], row["warning_type"]) for row in rows["both_active"]
    ] == [("review_with", ["Alpha"], ["Zeta"], "review_with_substance_present")]
    assert [(row["type"], row["reason"], row["action"]) for row in rows["missing_source"]] == [
        ("supports", "support reason", "support action")
    ]


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("stack_product", "stack 'daily'\\[0\\] references missing product 'prd_missing'"),
        (
            "component_substance",
            "product 'prd_active_alpha'\\.components\\[0\\] references missing substance 'sub_missing'",
        ),
        ("relation_reference", "rel_support.*unresolved source endpoint: unsupported_selector"),
        ("relation_endpoint", "rel_support.*unresolved source endpoint: malformed_selector"),
    ],
)
def test_read_model_and_direct_classifier_reject_incomplete_references(
    representative_query_fixture: _RepresentativeQueryFixture,
    mutation: str,
    match: str,
) -> None:
    fixture = representative_query_fixture
    if mutation == "stack_product":
        with pytest.raises(ValueError, match=match):
            build_stack_read_model(
                fixture.substances, [], fixture.products, {"daily": ["prd_missing"]}, ontology_bundle=ontology_bundle()
            )
        return
    if mutation == "component_substance":
        products = dict(fixture.products)
        products["prd_active_alpha"] = Product(
            "prd_active_alpha", "Alpha", (ProductComponent("sub_missing", "cmp_prd_active_alpha__sub_missing"),)
        )
        with pytest.raises(ValueError, match=match):
            build_stack_read_model(fixture.substances, [], products, fixture.stacks, ontology_bundle=ontology_bundle())
        return

    relations = list(fixture.relations)
    relations[0] = Relation(
        id="rel_support",
        type="supports",
        reason="support reason",
        source_selector=RelationSelector(entity_id="sub_missing")
        if mutation == "relation_reference"
        else RelationSelector(),
        target_selector=relations[0].target_selector,
        assertion_kind="ontology_assertion",
        semantic_family="biochemical_mechanism_assertion",
        research_state="unassessed",
        sources=(),
    )
    with pytest.raises(ValueError, match=match):
        _relation_queries(_RepresentativeQueryFixture(fixture.substances, fixture.products, fixture.stacks, relations))
