"""Vertical tests for the bounded, read-only enrichment queue."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import yaml
from planner.contracts import Product, ProductComponent
from planner.engine import cmd_grooming_next
from planner.engine.grooming import _product_ids_by_substance

from tests.helpers import ontology_bundle
from tests.planner_fixture import (
    PlannerFixtureInput,
    find_card_path_by_id,
    plan_in_temp_dir,
    write_minimal_planner_fixture,
)


def _write_grooming_fixture(tmp_path: Path) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={
                "prd_alpha00001": {"stack": "daily"},
                "prd_beta000001": {"stack": "training"},
                "prd_inactive01": {"stack": "inactive"},
            },
            products={
                "prd_alpha00001": [("sub_alpha00001", [])],
                "prd_alpha00002": [("sub_alpha00001", [])],
                "prd_beta000001": [("sub_beta000001", [])],
                "prd_inactive01": [("sub_inactive01", [])],
            },
            traits={},
        ),
    )
    names = {
        "sub_alpha00001": "zeta",
        "sub_beta000001": "Alpha",
        "sub_inactive01": "Inactive",
    }
    for substance_id, name in names.items():
        path = find_card_path_by_id(tmp_path / "data/substances", substance_id)
        data = cast(dict[str, object], yaml.safe_load(path.read_text()))
        data["name"] = name
        path.write_text(yaml.safe_dump(data, sort_keys=False))
    (tmp_path / "data/substances/orphan__sub_orphan0001.yaml").write_text(
        yaml.safe_dump(
            {"id": "sub_orphan0001", "name": "Orphan registry card"},
            sort_keys=False,
        )
    )


def test_grooming_next_default_limit_counts_products_and_renders_total(tmp_path: Path) -> None:
    _write_grooming_fixture(tmp_path)

    result = cmd_grooming_next(data_root=tmp_path)

    assert result.exit_code == 0
    assert result.limit == 1
    assert result.total_remaining == 2
    assert result.shown == 1
    assert result.output.startswith("Grooming queue: 2 remaining, showing 1\n")
    assert [candidate.name for candidate in result.candidates] == ["zeta"]
    assert (result.candidates[0].total_product_count, result.candidates[0].active_product_count) == (2, 1)
    assert all(candidate.id != "sub_inactive01" for candidate in result.candidates)
    assert all(candidate.id != "sub_orphan0001" for candidate in result.candidates)
    assert "zeta" in result.output and "Alpha" not in result.output
    limited = cmd_grooming_next(limit=1, data_root=tmp_path)
    assert limited.total_remaining == 2
    assert limited.shown == 1
    assert limited.output.startswith("Grooming queue: 2 remaining, showing 1\n")


def test_grooming_next_orders_active_count_before_total_count(tmp_path: Path) -> None:
    _write_grooming_fixture(tmp_path)
    stacks_path = tmp_path / "data/stacks.yaml"
    stacks = cast(dict[str, list[str]], yaml.safe_load(stacks_path.read_text()))
    stacks["training"].append("prd_alpha00002")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))
    for product_id in ("prd_beta000002", "prd_beta000003"):
        (tmp_path / f"data/products/{product_id}.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": product_id,
                    "name": product_id,
                    "components": [{"substance": "sub_beta000001"}],
                },
                sort_keys=False,
            )
        )

    result = cmd_grooming_next(limit=2, data_root=tmp_path)

    assert [candidate.id for candidate in result.candidates] == ["sub_alpha00001", "sub_beta000001"]
    assert (result.candidates[0].active_product_count, result.candidates[0].total_product_count) == (2, 2)
    assert (result.candidates[1].active_product_count, result.candidates[1].total_product_count) == (1, 3)


def test_grooming_next_uses_authored_metric_order_without_code_change(tmp_path: Path, monkeypatch) -> None:
    _write_grooming_fixture(tmp_path)
    stacks_path = tmp_path / "data/stacks.yaml"
    stacks = cast(dict[str, list[str]], yaml.safe_load(stacks_path.read_text()))
    stacks["training"].append("prd_alpha00002")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))
    for product_id in ("prd_beta000002", "prd_beta000003"):
        (tmp_path / f"data/products/{product_id}.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": product_id,
                    "name": product_id,
                    "components": [{"substance": "sub_beta000001"}],
                },
                sort_keys=False,
            )
        )
    bundle = ontology_bundle()
    policy = replace(
        bundle.runtime_program.semantic_enrichment_grooming,
        roi_order_desc=("total_unique_product_count", "active_unique_product_count"),
    )
    runtime = replace(bundle.runtime_program, semantic_enrichment_grooming=policy)
    object.__setattr__(bundle, "_runtime_program", runtime)
    monkeypatch.setattr("planner.engine.grooming.load_ontology", lambda _root: bundle)

    result = cmd_grooming_next(limit=2, data_root=tmp_path)

    assert [candidate.id for candidate in result.candidates] == ["sub_beta000001", "sub_alpha00001"]


def test_grooming_next_counts_duplicate_stack_membership_once(tmp_path: Path) -> None:
    _write_grooming_fixture(tmp_path)
    stacks_path = tmp_path / "data/stacks.yaml"
    stacks = cast(dict[str, list[str]], yaml.safe_load(stacks_path.read_text()))
    stacks["training"].append("prd_alpha00001")
    stacks_path.write_text(yaml.safe_dump(stacks, sort_keys=False))

    result = cmd_grooming_next(data_root=tmp_path)

    alpha = next(candidate for candidate in result.candidates if candidate.id == "sub_alpha00001")
    assert alpha.total_product_count == 2
    assert alpha.active_product_count == 1


def test_grooming_product_count_deduplicates_repeated_components() -> None:
    product = Product(
        "prd_duplicate01",
        "Duplicate component product",
        (ProductComponent("sub_alpha00001"), ProductComponent("sub_alpha00001")),
    )

    assert _product_ids_by_substance({product.id: product}) == {"sub_alpha00001": {product.id}}


def test_grooming_next_casefold_ties_use_id_order_and_repeat_exactly(tmp_path: Path) -> None:
    _write_grooming_fixture(tmp_path)
    for substance_id, name in (("sub_alpha00001", "ALPHA"), ("sub_beta000001", "alpha")):
        path = find_card_path_by_id(tmp_path / "data/substances", substance_id)
        data = cast(dict[str, object], yaml.safe_load(path.read_text()))
        data["name"] = name
        path.write_text(yaml.safe_dump(data, sort_keys=False))
    for product_id, substance_id in (("prd_beta000002", "sub_beta000001"),):
        (tmp_path / f"data/products/{product_id}.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": product_id,
                    "name": product_id,
                    "components": [{"substance": substance_id}],
                },
                sort_keys=False,
            )
        )

    first = cmd_grooming_next(limit=2, data_root=tmp_path)
    second = cmd_grooming_next(limit=2, data_root=tmp_path)

    first_ids = [candidate.id for candidate in first.candidates]
    second_ids = [candidate.id for candidate in second.candidates]
    assert first.exit_code == second.exit_code == 0
    assert len(first_ids) == len(second_ids) == 2
    assert first_ids == second_ids == sorted(first_ids)


def test_grooming_next_excludes_dated_cards_and_applies_positive_limit(tmp_path: Path) -> None:
    _write_grooming_fixture(tmp_path)
    dated_path = find_card_path_by_id(tmp_path / "data/substances", "sub_alpha00001")
    dated = cast(dict[str, object], yaml.safe_load(dated_path.read_text()))
    dated["semantic_enrichment_attempted_on"] = "2026-08-12"
    dated_path.write_text(yaml.safe_dump(dated, sort_keys=False))

    result = cmd_grooming_next(limit=1, data_root=tmp_path)

    assert result.exit_code == 0
    assert [candidate.id for candidate in result.candidates] == ["sub_beta000001"]


def test_grooming_next_zero_queue_header_is_truthful(tmp_path: Path) -> None:
    _write_grooming_fixture(tmp_path)
    for substance_id in ("sub_alpha00001", "sub_beta000001"):
        path = find_card_path_by_id(tmp_path / "data/substances", substance_id)
        data = cast(dict[str, object], yaml.safe_load(path.read_text()))
        data["semantic_enrichment_attempted_on"] = "2026-08-12"
        path.write_text(yaml.safe_dump(data, sort_keys=False))

    result = cmd_grooming_next(data_root=tmp_path)

    assert result.exit_code == 0
    assert result.total_remaining == result.shown == 0
    assert result.output == "Grooming queue: 0 remaining, showing 0\n  none\n"


def test_grooming_marker_does_not_change_scheduling_output(tmp_path: Path) -> None:
    _write_grooming_fixture(tmp_path)
    before = plan_in_temp_dir(tmp_path)
    dated_path = find_card_path_by_id(tmp_path / "data/substances", "sub_alpha00001")
    dated = cast(dict[str, object], yaml.safe_load(dated_path.read_text()))
    dated["semantic_enrichment_attempted_on"] = "2026-08-12"
    dated_path.write_text(yaml.safe_dump(dated, sort_keys=False))

    after = plan_in_temp_dir(tmp_path)

    assert before == after
