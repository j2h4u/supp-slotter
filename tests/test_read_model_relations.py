"""Focused acceptance coverage for typed read-model relation queries."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from planner.contracts import (
    KnowledgeAssertion,
    OntologyAssertion,
    Product,
    ProductComponent,
    Relation,
    RelationSelector,
    Substance,
)
from planner.query_model import build_stack_read_model

from tests.helpers import ontology_bundle


@dataclass(frozen=True, slots=True)
class _RepresentativeQueryFixture:
    substances: dict[str, Substance]
    products: dict[str, Product]
    stacks: dict[str, list[str]]
    relations: list[Relation]


@pytest.fixture()
def representative_query_fixture() -> _RepresentativeQueryFixture:
    fact = (KnowledgeAssertion("context", "vascular_health"),)
    active_alpha = Substance("sub_active_alpha", "Alpha", knowledge_assertions=fact)
    active_zeta = Substance("sub_active_zeta", "Zeta", knowledge_assertions=fact)
    inactive = Substance("sub_inactive", "Inactive", knowledge_assertions=fact)
    support = Substance("sub_support", "Support")
    unassigned = Substance("sub_unassigned", "Unassigned", knowledge_assertions=fact)
    substances = {item.id: item for item in (active_alpha, active_zeta, inactive, support, unassigned)}
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
        "prd_unassigned": Product(
            "prd_unassigned", "Unassigned", (ProductComponent(unassigned.id, "cmp_prd_unassigned__sub_unassigned"),)
        ),
    }
    relations = [
        Relation(
            "rel_support_one",
            "supports",
            "support reason",
            RelationSelector(entity_id=support.id),
            RelationSelector(entity_id=active_zeta.id),
            action="support action",
            severity="low",
            assertion_kind="ontology_assertion",
            semantic_family="biochemical_mechanism_assertion",
        ),
        Relation(
            "rel_support_duplicate",
            "supports",
            "duplicate support reason",
            RelationSelector(entity_id=support.id),
            RelationSelector(entity_id=active_zeta.id),
            action="duplicate support action",
            severity="low",
            assertion_kind="ontology_assertion",
            semantic_family="biochemical_mechanism_assertion",
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
        ),
    ]
    return _RepresentativeQueryFixture(
        substances=substances,
        products=products,
        stacks={"daily": ["prd_active_zeta", "prd_active_alpha"], "inactive": ["prd_inactive"]},
        relations=relations,
    )


def _fixture_assertions(relations: list[Relation], _bundle: object) -> tuple[OntologyAssertion, ...]:
    assertions: list[OntologyAssertion] = []
    for relation in relations:
        if relation.assertion_kind is None or relation.semantic_family is None:
            raise ValueError(f"fixture relation {relation.id!r} requires explicit semantics")
        assertions.append(
            OntologyAssertion(
                id=relation.id,
                relation_type=relation.type,
                assertion_kind=relation.assertion_kind,
                semantic_family=relation.semantic_family,
                reason=relation.reason,
                source_selector=relation.source_selector,
                target_selector=relation.target_selector,
                action=relation.action,
                severity=relation.severity,
            )
        )
    return tuple(assertions)


def _build_fixture_read_model(
    monkeypatch: pytest.MonkeyPatch,
    fixture: _RepresentativeQueryFixture,
):
    monkeypatch.setattr("planner.query_model.read_model.project_ontology_assertions", _fixture_assertions)
    return build_stack_read_model(
        fixture.substances,
        fixture.relations,
        fixture.products,
        fixture.stacks,
        ontology_bundle=ontology_bundle(),
    )


def test_typed_read_model_projects_complete_partition_facts_relations_and_warnings(
    monkeypatch: pytest.MonkeyPatch,
    representative_query_fixture: _RepresentativeQueryFixture,
) -> None:
    read_model = _build_fixture_read_model(monkeypatch, representative_query_fixture)

    active = read_model.active_substance_ids()
    inactive = read_model.inactive_substance_ids()
    assert active == {"sub_active_alpha", "sub_active_zeta"}
    assert inactive == {"sub_inactive"}
    assert set(representative_query_fixture.substances) - active - inactive == {"sub_support", "sub_unassigned"}
    assert read_model.active_fact_index(
        item_id_sequence=["item_zeta", "item_alpha"],
        item_products={"item_zeta": "prd_active_zeta", "item_alpha": "prd_active_alpha"},
    ) == [
        {
            "namespace": "context",
            "fact": "vascular_health",
            "label": "Vascular Health",
            "product_count": 2,
            "products": ["Alpha", "Zeta"],
        }
    ]

    relation_rows = read_model.classify_relations(active)
    assert [(row["type"], row["source_matches"], row["target_matches"]) for row in relation_rows["both_active"]] == [
        ("review_with", ["Alpha"], ["Zeta"])
    ]
    assert [(row["type"], row["reason"], row["action"]) for row in relation_rows["missing_source"]] == [
        ("supports", "support reason", "support action"),
        ("supports", "duplicate support reason", "duplicate support action"),
    ]
    assert [
        (row["relation"], row["source_substance"], row["target_substance"])
        for row in read_model.collect_relation_warnings(active)
    ] == [
        ("review_with", "sub_active_alpha", "sub_active_zeta"),
        ("supports", "sub_support", "sub_active_zeta"),
    ]


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("stack_product", "stack 'daily'\\[0\\] references missing product 'prd_missing'"),
        (
            "component_substance",
            "product 'prd_active_alpha'\\.components\\[0\\] references missing substance 'sub_missing'",
        ),
        ("missing_item_product", "no product mapping for item 'item_missing'"),
        ("unknown_item_product", "references missing product 'prd_missing'"),
        ("relation_reference", "rel_support_one.*unresolved source endpoint: unsupported_selector"),
        ("relation_endpoint", "rel_support_one.*unresolved source endpoint: malformed_selector"),
    ],
)
def test_typed_read_model_rejects_every_incomplete_reference(
    monkeypatch: pytest.MonkeyPatch,
    representative_query_fixture: _RepresentativeQueryFixture,
    mutation: str,
    match: str,
) -> None:
    fixture = representative_query_fixture
    if mutation == "stack_product":
        fixture = _RepresentativeQueryFixture(
            fixture.substances,
            fixture.products,
            {"daily": ["prd_missing"], "inactive": ["prd_inactive"]},
            fixture.relations,
        )
    elif mutation == "component_substance":
        products = dict(fixture.products)
        products["prd_active_alpha"] = Product(
            "prd_active_alpha", "Alpha", (ProductComponent("sub_missing", "cmp_prd_active_alpha__sub_missing"),)
        )
        fixture = _RepresentativeQueryFixture(fixture.substances, products, fixture.stacks, fixture.relations)
    elif mutation in {"relation_reference", "relation_endpoint"}:
        relations = list(fixture.relations)
        relations[0] = Relation(
            fixture.relations[0].id,
            fixture.relations[0].type,
            fixture.relations[0].reason,
            RelationSelector(entity_id="sub_missing") if mutation == "relation_reference" else RelationSelector(),
            fixture.relations[0].target_selector,
            action=fixture.relations[0].action,
            severity=fixture.relations[0].severity,
            assertion_kind=fixture.relations[0].assertion_kind,
            semantic_family=fixture.relations[0].semantic_family,
        )
        fixture = _RepresentativeQueryFixture(fixture.substances, fixture.products, fixture.stacks, relations)

    if mutation == "missing_item_product":
        with pytest.raises(ValueError, match=match):
            _build_fixture_read_model(monkeypatch, fixture).active_fact_index(
                item_id_sequence=["item_missing"], item_products={}
            )
        return
    if mutation == "unknown_item_product":
        with pytest.raises(ValueError, match=match):
            _build_fixture_read_model(monkeypatch, fixture).active_fact_index(
                item_id_sequence=["item_missing"], item_products={"item_missing": "prd_missing"}
            )
        return

    with pytest.raises(ValueError, match=match):
        _build_fixture_read_model(monkeypatch, fixture)
