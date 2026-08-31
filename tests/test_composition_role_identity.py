"""Focused checks for authored CompositionRole identities."""

from __future__ import annotations

from pathlib import Path

from planner.card_ids import composition_role_id
from planner.cards.product import _product_components
from planner.cards.product_validation import check_product_formulas
from planner.ontology.projection import ProjectionResult, _project_repository_with_projection
from rdflib import URIRef

BASE = "https://example.test/ontology/"


def _product_projection() -> dict[str, object]:
    return {
        "catalogs": [],
        "repository_projection": {
            "format_version": "repository-projection-v1",
            "base_iri": BASE,
            "sources": [
                {
                    "id": "products",
                    "locator": {"kind": "flat_root", "path": "data/products"},
                    "root_class": "Product",
                    "documents": {
                        "document_shape": "mapping",
                        "identity": {"source": "id", "predicate": BASE + "id"},
                        "instructions": [
                            {"kind": "slot", "source": "id", "predicate": BASE + "id"},
                            {"kind": "slot", "source": "name", "predicate": BASE + "label"},
                            {
                                "kind": "inlined-node",
                                "source": "components[]",
                                "predicate": BASE + "components",
                                "target": "ProductComponent",
                            },
                            {
                                "kind": "slot",
                                "source": "components[].id",
                                "subject": "components[]",
                                "predicate": BASE + "id",
                            },
                            {
                                "kind": "slot",
                                "source": "components[].substance",
                                "subject": "components[]",
                                "predicate": BASE + "substance",
                            },
                        ],
                    },
                }
            ],
        },
    }


def _write_product(path: Path, components: str) -> None:
    path.write_text(
        "id: prd_demo\nname: Demo\ncomponents:\n" + components,
        encoding="utf-8",
    )


def _component_nodes(result: ProjectionResult) -> set[URIRef]:
    graph = result.graph
    return set(graph.objects(URIRef(BASE + "product/prd_demo"), URIRef(BASE + "components")))


def test_authored_component_identity_survives_reorder(tmp_path: Path) -> None:
    products = tmp_path / "data/products"
    products.mkdir(parents=True)
    product_path = products / "demo.yaml"
    _write_product(
        product_path,
        "  - id: cmp_prd_demo__sub_a\n    substance: sub_a\n  - id: cmp_prd_demo__sub_b\n    substance: sub_b\n",
    )
    before = _component_nodes(_project_repository_with_projection(tmp_path, _product_projection()))

    _write_product(
        product_path,
        "  - id: cmp_prd_demo__sub_b\n    substance: sub_b\n  - id: cmp_prd_demo__sub_a\n    substance: sub_a\n",
    )
    after = _component_nodes(_project_repository_with_projection(tmp_path, _product_projection()))

    assert (
        before
        == after
        == {
            URIRef(BASE + "productComponent/cmp_prd_demo__sub_a"),
            URIRef(BASE + "productComponent/cmp_prd_demo__sub_b"),
        }
    )


def test_product_formula_validator_rejects_dangling_mismatched_and_duplicate_roles(tmp_path: Path, monkeypatch) -> None:
    import planner.cards.product_validation as validation

    monkeypatch.setattr(validation, "schema_errors", lambda *_args: [])
    first = tmp_path / "unknown__first__prd_first.yaml"
    second = tmp_path / "unknown__second__prd_second.yaml"
    first.write_text(
        "id: prd_first\nname: First\ncomponents:\n"
        "  - id: cmp_prd_first__sub_missing\n    substance: sub_missing\n"
        "  - id: cmp_prd_first__sub_a\n    substance: sub_a\n",
        encoding="utf-8",
    )
    second.write_text(
        "id: prd_second\nname: Second\ncomponents:\n  - id: cmp_prd_first__sub_a\n    substance: sub_a\n",
        encoding="utf-8",
    )

    errors, _, _ = check_product_formulas(
        [first, second],
        {"sub_a": tmp_path / "sub_a.yaml"},
        object(),  # type: ignore[arg-type]
    )

    assert any("sub_missing" in error and "references unknown substance" in error for error in errors)
    assert any("must equal 'cmp_prd_second__sub_a'" in error for error in errors)
    assert any("duplicates" in error and "cmp_prd_first__sub_a" in error for error in errors)


def test_composition_role_id_is_portable_and_deterministic() -> None:
    assert composition_role_id("prd_demo", "sub_a") == "cmp_prd_demo__sub_a"


def test_product_loader_preserves_authored_component_id() -> None:
    loaded = _product_components([{"id": "cmp_prd_demo__sub_a", "substance": "sub_a"}])

    assert loaded[0].id == "cmp_prd_demo__sub_a"
