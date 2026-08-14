"""Fail-closed uniqueness contracts for authored source cards."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.cards.dashboards import load_dashboard
from planner.cards.product import load_product
from planner.cards.relations import load_global_relations
from planner.cards.substance import load_substance
from planner.contracts import CardLoadError, Relation, RelationSelector, Substance
from planner.paths import Paths
from planner.query_model import build_stack_read_model
from planner.query_model.surreal_records import relation_record
from planner.schema_validation import schema_errors

from tests.helpers import ontology_bundle


def test_product_components_are_unique_by_substance_reference() -> None:
    duplicate = {
        "id": "prd_aaaaaaaaaa",
        "name": "Duplicate component probe",
        "components": [
            {"substance": "sub_aaaaaaaaaa", "label": "first"},
            {"substance": "sub_aaaaaaaaaa", "label": "second"},
        ],
    }
    distinct = {**duplicate, "components": [{"substance": "sub_aaaaaaaaaa"}, {"substance": "sub_bbbbbbbbbb"}]}

    errors = schema_errors(duplicate, "product", Path("product.yaml"), ontology_bundle())
    assert any("duplicate value 'sub_aaaaaaaaaa'" in error for error in errors)
    assert any("components.1.substance" in error for error in errors)
    assert schema_errors(distinct, "product", Path("product.yaml"), ontology_bundle()) == []


def test_product_loader_rejects_duplicate_component_substance(tmp_path: Path) -> None:
    path = tmp_path / "product.yaml"
    path.write_text(
        "id: prd_aaaaaaaaaa\nname: Duplicate component probe\ncomponents:\n"
        "  - substance: sub_aaaaaaaaaa\n    label: first\n"
        "  - substance: sub_aaaaaaaaaa\n    label: second\n",
        encoding="utf-8",
    )

    with pytest.raises(CardLoadError, match="duplicate value 'sub_aaaaaaaaaa'"):
        load_product(path, ontology_bundle())


def test_knowledge_assertion_values_are_unique_within_category(tmp_path: Path) -> None:
    duplicate = {
        "id": "sub_aaaaaaaaaa",
        "name": "Duplicate knowledge probe",
        "knowledge": {"kind": ["amino", "amino"]},
    }
    distinct = {**duplicate, "knowledge": {"kind": ["amino", "mineral"]}}

    errors = schema_errors(duplicate, "substance", Path("substance.yaml"), ontology_bundle())
    assert any("knowledge" in error and "amino" in error for error in errors)
    assert schema_errors(distinct, "substance", Path("substance.yaml"), ontology_bundle()) == []

    path = tmp_path / "substance.yaml"
    path.write_text(
        "id: sub_aaaaaaaaaa\nname: Duplicate knowledge probe\nknowledge:\n  kind: [amino, amino]\n",
        encoding="utf-8",
    )
    with pytest.raises(CardLoadError, match="knowledge"):
        load_substance(path, ontology_bundle())


def test_dashboard_selector_and_declared_context_values_are_unique() -> None:
    duplicate_selector = {
        "id": "dashboard_probe",
        "name": "Dashboard probe",
        "description": "duplicate selector probe",
        "benefit": {"description": "duplicate selector probe"},
        "selectors": [
            {"category": "context", "term": "vascular_health"},
            {"category": "context", "term": "vascular_health"},
        ],
    }
    duplicate_context = {
        **duplicate_selector,
        "selectors": [{"category": "context", "term": "vascular_health"}],
        "declares_context": ["vascular_health", "vascular_health"],
    }
    distinct = {
        **duplicate_selector,
        "selectors": [
            {"category": "context", "term": "vascular_health"},
            {"category": "context", "term": "connective_tissue_support"},
        ],
        "declares_context": ["vascular_health", "connective_tissue_support"],
    }

    selector_errors = schema_errors(duplicate_selector, "dashboard", Path("dashboard.yaml"), ontology_bundle())
    context_errors = schema_errors(duplicate_context, "dashboard", Path("dashboard.yaml"), ontology_bundle())
    assert any("selectors" in error and "unique" in error for error in selector_errors)
    assert any("declares_context" in error and "unique" in error for error in context_errors)
    assert schema_errors(distinct, "dashboard", Path("dashboard.yaml"), ontology_bundle()) == []


def test_dashboard_loader_rejects_duplicate_selector(tmp_path: Path) -> None:
    path = tmp_path / "dashboard.yaml"
    path.write_text(
        "id: dashboard_probe\nname: Dashboard probe\ndescription: duplicate selector probe\n"
        "benefit:\n  description: duplicate selector probe\n"
        "\n"
        "selectors:\n  - category: context\n    term: vascular_health\n"
        "  - category: context\n    term: vascular_health\n",
        encoding="utf-8",
    )

    with pytest.raises(CardLoadError, match="selectors"):
        load_dashboard(path, ontology_bundle())


def _relation_entry(identifier: str, *, reason: str = "relation identity probe") -> dict[str, object]:
    return {
        "id": identifier,
        "relation_type": "supports",
        "assertion_kind": "ontology_assertion",
        "semantic_family": "test",
        "reason": reason,
        "source_selector": {"category": "context", "term": "vascular_health"},
        "target_selector": {"category": "context", "term": "vascular_health"},
    }


def test_relation_ids_are_non_empty_and_unique_in_generated_contract() -> None:
    duplicate = {"relations": [_relation_entry("rel_duplicate"), _relation_entry("rel_duplicate", reason="second")]}
    blank = {"relations": [_relation_entry("")]}

    duplicate_errors = schema_errors(duplicate, "relations", Path("relations.yaml"), ontology_bundle())
    blank_errors = schema_errors(blank, "relations", Path("relations.yaml"), ontology_bundle())

    assert any("duplicate value 'rel_duplicate'" in error and "relations.1.id" in error for error in duplicate_errors)
    assert any("relations/0/id" in error for error in blank_errors)
    assert schema_errors({"relations": []}, "relations", Path("relations.yaml"), ontology_bundle()) == []


def test_relation_loader_rejects_duplicate_ids_before_projection(tmp_path: Path) -> None:
    path = tmp_path / "data" / "relations.yaml"
    path.parent.mkdir()
    path.write_text(
        yaml.safe_dump(
            {"relations": [_relation_entry("rel_duplicate"), _relation_entry("rel_duplicate", reason="second")]},
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(CardLoadError, match=r"duplicate value 'rel_duplicate'.*relations\.1\.id"):
        load_global_relations(Paths.from_root(tmp_path), ontology_bundle(), {})


def test_relation_loader_rejects_cross_form_entity_duplicate(tmp_path: Path) -> None:
    path = tmp_path / "data" / "relations.yaml"
    path.parent.mkdir()
    common = {
        "relation_type": "review_with",
        "assertion_kind": "clinical_review_signal",
        "semantic_family": "test",
        "reason": "cross-form identity probe",
        "target_selector": {"entity": {"entity_id": "sub_other000"}},
    }
    path.write_text(
        yaml.safe_dump(
            {
                "relations": [
                    {
                        **common,
                        "id": "rel_cross_form_a",
                        "source_selector": {"entity": {"entity_id": "sub_known000"}},
                    },
                    {
                        **common,
                        "id": "rel_cross_form_b",
                        "source_selector": {"entity": {"name": "Known"}},
                    },
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    substances = {
        "sub_known000": Substance(id="sub_known000", name="Known"),
        "sub_other000": Substance(id="sub_other000", name="Other"),
    }
    with pytest.raises(CardLoadError, match="non-directional relation type 'review_with'"):
        load_global_relations(Paths.from_root(tmp_path), ontology_bundle(), substances)


def test_name_selector_resolves_new_same_name_form_in_runtime_record(tmp_path: Path) -> None:
    path = tmp_path / "data" / "relations.yaml"
    path.parent.mkdir()
    path.write_text(
        yaml.safe_dump(
            {
                "relations": [
                    {
                        "id": "rel_name_family",
                        "relation_type": "supports",
                        "assertion_kind": "ontology_assertion",
                        "semantic_family": "test",
                        "reason": "name family runtime probe",
                        "source_selector": {"entity": {"name": "Known"}},
                        "target_selector": {"entity": {"entity_id": "sub_other000"}},
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    substances = {
        "sub_known000": Substance(id="sub_known000", name="Known"),
        "sub_knownform": Substance(id="sub_knownform", name="Known", form="second form"),
        "sub_other000": Substance(id="sub_other000", name="Other"),
    }

    [relation] = load_global_relations(Paths.from_root(tmp_path), ontology_bundle(), substances)
    record = relation_record(relation, substances, ontology_bundle())

    assert relation.source_selector == RelationSelector(entity_name="Known")
    assert record["src_substances"] == ["sub_known000", "sub_knownform"]
    assert record["src_member_names"] == ["Known", "Known (second form)"]
    assert record["src_selector"] == {"form": "name", "kind": "entity", "id": None, "name": "Known"}


@pytest.mark.parametrize(
    ("selector", "expected_form", "expected_kind", "expected_details"),
    [
        (RelationSelector(entity_id="sub_known000"), "entity_id", "entity", False),
        (RelationSelector(entity_name="Known"), "name", "entity", True),
        (RelationSelector(category="kind", term="mineral"), "term", "term", True),
    ],
)
def test_selector_form_capabilities_are_semantic_not_cardinality(
    selector: RelationSelector,
    expected_form: str,
    expected_kind: str,
    expected_details: bool,
) -> None:
    runtime = ontology_bundle().runtime_program
    capability = runtime.selector_form_capabilities_by_form[expected_form]
    assert capability.endpoint_kind == expected_kind
    assert capability.show_match_details is expected_details

    substances = {
        "sub_known000": Substance(id="sub_known000", name="Known"),
        "sub_other000": Substance(id="sub_other000", name="Other"),
    }
    relation = Relation(
        id="rel_selector_capability",
        type="supports",
        assertion_kind="ontology_assertion",
        semantic_family="biochemical_mechanism_assertion",
        reason="selector capability probe",
        source_selector=selector,
        target_selector=RelationSelector(entity_id="sub_other000"),
    )
    record = relation_record(relation, substances, ontology_bundle())
    source_selector = cast(dict[str, object], record["src_selector"])
    assert source_selector["form"] == expected_form
    assert source_selector["kind"] == ("term" if expected_form == "term" else "entity")


@pytest.mark.parametrize(
    ("substances", "expected_matches"),
    [
        (
            {
                "sub_known000": Substance(id="sub_known000", name="Known"),
                "sub_other000": Substance(id="sub_other000", name="Other"),
            },
            ["Known"],
        ),
        (
            {
                "sub_known000": Substance(id="sub_known000", name="Known"),
                "sub_knownform": Substance(id="sub_knownform", name="Known", form="second form"),
                "sub_other000": Substance(id="sub_other000", name="Other"),
            },
            ["Known", "Known (second form)"],
        ),
    ],
)
def test_name_family_review_always_shows_match_details(
    substances: dict[str, Substance], expected_matches: list[str]
) -> None:
    relation = Relation(
        id="rel_name_family_review",
        type="supports",
        assertion_kind="ontology_assertion",
        semantic_family="biochemical_mechanism_assertion",
        reason="name family review probe",
        source_selector=RelationSelector(entity_name="Known"),
        target_selector=RelationSelector(entity_id="sub_other000"),
    )
    model = build_stack_read_model(substances, [relation], ontology_bundle=ontology_bundle())
    rows = model.classify_relations(set(substances))
    row = next(row for entries in rows.values() for row in entries)
    assert row["show_matches"] is True
    assert row["source_matches"] == expected_matches


def test_relation_schema_rejects_unknown_top_level_field() -> None:
    assert any(
        "Additional properties" in error and "bogus" in error
        for error in schema_errors(
            {"relations": [], "bogus": True}, "relations", Path("relations.yaml"), ontology_bundle()
        )
    )


def test_read_model_rejects_duplicate_typed_relation_ids() -> None:
    relation = Relation(
        id="rel_duplicate",
        type="supports",
        assertion_kind="ontology_assertion",
        semantic_family="test",
        reason="duplicate typed relation",
        source_selector=RelationSelector(category="context", term="vascular_health"),
        target_selector=RelationSelector(category="context", term="vascular_health"),
    )

    with pytest.raises(ValueError, match=r"relations\[1\]\.id duplicates 'rel_duplicate'"):
        build_stack_read_model({}, [relation, relation], ontology_bundle=ontology_bundle())
