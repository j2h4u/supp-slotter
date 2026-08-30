from __future__ import annotations

from pathlib import Path
from typing import TypedDict, cast

import yaml
from planner.cards.substance import canonical_substance_filename
from planner.contracts import Substance
from planner.engine import cmd_check, cmd_review

from tests.planner_fixture import PlannerFixtureInput, find_card_path_by_id, write_minimal_planner_fixture

ROOT = Path(__file__).resolve().parents[1]


class _ProductComponent(TypedDict):
    substance: str


class _ProductCard(TypedDict):
    components: list[_ProductComponent]


Relations = dict[str, list[dict[str, object]]]


def _write_relation_fixture(tmp_path: Path) -> Path:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={
                "prd_trace00001": {"stack": "daily"},
                "prd_tadal00001": {"stack": "daily"},
                "prd_nac0000001": {"stack": "inactive"},
                "prd_selenium01": {"stack": "inactive"},
            },
            products={
                "prd_trace00001": [
                    ("sub_zinc000001", ["kind:mineral"]),
                    ("sub_copper0001", ["kind:mineral"]),
                    ("sub_dthree0001", ["quality:fat_soluble"]),
                    ("sub_citrulline", ["effect:nitric_oxide_support"]),
                ],
                "prd_tadal00001": [("sub_tadal00001", ["role:pharmaceutical", "effect:pde5_inhibition"])],
                "prd_nac0000001": [
                    ("sub_d997f98e03", ["kind:amino"]),
                    ("sub_selenium01", ["kind:mineral"]),
                ],
                "prd_selenium01": [("sub_selenium01", ["kind:mineral"])],
            },
            traits={},
        ),
    )
    temp_data = tmp_path / "data"
    _rename_substance(temp_data, "sub_zinc000001", "Zinc")
    _rename_substance(temp_data, "sub_copper0001", "Copper")
    _rename_substance(temp_data, "sub_dthree0001", "Vitamin D")
    _rename_substance(temp_data, "sub_citrulline", "L-Citrulline")
    _rename_substance(temp_data, "sub_tadal00001", "Tadalafil")
    _rename_substance(temp_data, "sub_d997f98e03", "N-Acetyl Cysteine")
    _rename_substance(temp_data, "sub_selenium01", "Selenium")
    vocabulary = cast(
        dict[str, object], yaml.safe_load((ROOT / "ontology/generated/runtime-vocabulary.yaml").read_text())
    )
    catalog = cast(dict[str, dict[str, object]], vocabulary["ontology_assertions"])
    relations: Relations = {
        "relations": [
            catalog["rel_balance_001"],
            catalog["rel_supports_001"],
            catalog["rel_co_use_context_001"],
        ]
    }
    (temp_data / "relations.yaml").write_text(yaml.safe_dump(relations, sort_keys=False))
    return temp_data


def _rename_substance(temp_data: Path, substance_id: str, name: str) -> None:
    substance_path = find_card_path_by_id(temp_data / "substances", substance_id)
    substance = cast(dict[str, object], yaml.safe_load(substance_path.read_text()))
    substance["name"] = name
    substance_path.write_text(yaml.safe_dump(substance, sort_keys=False))
    substance_path.replace(
        substance_path.with_name(
            canonical_substance_filename(
                Substance(id=substance_id, name=name, form=cast(str | None, substance.get("form")))
            )
        )
    )


def test_balance_relation_is_visible_when_related_substance_is_missing(tmp_path: Path) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    trace_product_path = find_card_path_by_id(
        temp_data / "products",
        "prd_trace00001",
    )
    trace_product = cast(_ProductCard, yaml.safe_load(trace_product_path.read_text()))
    trace_product["components"] = [
        component for component in trace_product["components"] if component["substance"] != "sub_copper0001"
    ]
    trace_product_path.write_text(yaml.safe_dump(trace_product, sort_keys=False))

    review_result = cmd_review(data_root=tmp_path)

    assert review_result.exit_code == 0
    assert "Unassessed relation leads" in review_result.output
    assert "Zinc" in review_result.output and "Copper" in review_result.output


def test_relation_validation_rejects_unknown_substance_name(tmp_path: Path) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relations["relations"].append({
        "id": "rel_missing_source",
        "relation_type": "supports",
        "assertion_kind": "ontology_assertion",
        "semantic_family": "biochemical_mechanism_assertion",
        "research_state": "unassessed",
        "sources": [],
        "source_selector": {"entity": {"name": "Definitely Missing"}},
        "target_selector": {"entity": {"name": "N-Acetyl Cysteine"}},
        "reason": "Fixture relation.",
    })
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    assert "source_selector.entity.name 'Definitely Missing' has no matching substance name" in "\n".join(result.errors)


def test_relation_validation_accepts_typed_term_endpoint_for_supports(
    tmp_path: Path,
) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relations["relations"].append({
        "id": "rel_cross_category_support",
        "relation_type": "supports",
        "assertion_kind": "ontology_assertion",
        "semantic_family": "biochemical_mechanism_assertion",
        "research_state": "unassessed",
        "sources": [],
        "source_selector": {"category": "kind", "term": "mineral"},
        "target_selector": {"category": "quality", "term": "fat_soluble"},
        "reason": "Fixture category endpoint relation.",
    })
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code == 0, "\n".join(result.errors)


def test_relation_validation_rejects_invalid_selector_shape(
    tmp_path: Path,
) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relations["relations"].append({
        "id": "rel_invalid_selector",
        "relation_type": "supports",
        "assertion_kind": "ontology_assertion",
        "semantic_family": "biochemical_mechanism_assertion",
        "research_state": "unassessed",
        "sources": [],
        "source_selector": {"entity": {"entity_id": "sub_zinc000001"}, "category": "kind", "term": "mineral"},
        "target_selector": {"entity": {"name": "Copper"}},
        "reason": "Fixture relation with mixed source endpoint strategy.",
    })
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)
    error_text = "\n".join(result.errors)

    assert result.exit_code != 0
    assert "relation endpoints must choose exactly one source endpoint and exactly one target endpoint" in error_text
    assert "found source endpoints: category, entity, term" in error_text
    assert "Use the canonical selector shape {entity: {entity_id|name}} or {category, term} on each side." in error_text


def test_typed_selector_relation_is_valid_against_the_complete_canonical_corpus(tmp_path: Path) -> None:
    _write_relation_fixture(tmp_path)

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code == 0, result


def test_relation_validation_rejects_unregistered_trait(tmp_path: Path) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relations["relations"].append({
        "id": "rel_unknown_effect",
        "relation_type": "co_use_context",
        "assertion_kind": "co_use_evidence",
        "semantic_family": "co_use_evidence",
        "research_state": "unassessed",
        "sources": [],
        "source_selector": {"category": "effect", "term": "not_real"},
        "target_selector": {"entity": {"name": "Tadalafil"}},
        "reason": "Fixture relation with misspelled trait slug.",
    })
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    assert "source_selector term 'effect:not_real' is not in canonical ontology vocabulary" in "\n".join(result.errors)


def test_support_relation_is_visible_when_supporter_is_missing(tmp_path: Path) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    _remove_component_from_product(
        temp_data,
        product_id="prd_nac0000001",
        substance_id="sub_selenium01",
    )
    stacks_path = temp_data / "stacks.yaml"
    stacks = cast(dict[str, list[object]], yaml.safe_load(stacks_path.read_text()))
    stacks["inactive"].remove("prd_nac0000001")
    stacks["daily"].append("prd_nac0000001")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    review_result = cmd_review(data_root=tmp_path)

    assert review_result.exit_code == 0
    assert "Unassessed relation leads" in review_result.output
    assert "Selenium" in review_result.output
    assert "N-Acetyl Cysteine" in review_result.output


def test_support_relation_accepts_active_supporter_from_another_product(
    tmp_path: Path,
) -> None:
    temp_data = _write_relation_fixture(tmp_path)
    _remove_component_from_product(
        temp_data,
        product_id="prd_nac0000001",
        substance_id="sub_selenium01",
    )
    stacks_path = temp_data / "stacks.yaml"
    stacks = cast(dict[str, list[object]], yaml.safe_load(stacks_path.read_text()))
    stacks["inactive"].remove("prd_nac0000001")
    stacks["inactive"].remove("prd_selenium01")
    stacks["daily"].append("prd_nac0000001")
    stacks["daily"].append("prd_selenium01")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    review_result = cmd_review(data_root=tmp_path)

    assert review_result.exit_code == 0, review_result.output
    relations_output = review_result.output.split("Unassessed relation leads", maxsplit=1)[1].split(
        "Dashboard coverage",
        maxsplit=1,
    )[0]
    assert "Selenium -> N-Acetyl Cysteine" in relations_output


def _remove_component_from_product(
    temp_data: Path,
    *,
    product_id: str,
    substance_id: str,
) -> None:
    product_path = find_card_path_by_id(temp_data / "products", product_id)
    product = cast(_ProductCard, yaml.safe_load(product_path.read_text()))
    product["components"] = [component for component in product["components"] if component["substance"] != substance_id]
    product_path.write_text(yaml.safe_dump(product, sort_keys=False))
