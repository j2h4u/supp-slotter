"""Focused acceptance checks for operational canonical-coverage grooming."""

from __future__ import annotations

from pathlib import Path
from shutil import copytree
from types import SimpleNamespace

import planner.engine.grooming as grooming
import pytest
from planner.cards.product import load_product_registry
from planner.cards.substance import load_substance_registry
from planner.contracts import CardLoadError, Product, ProductComponent, Substance
from planner.ontology.artifacts import load_ontology
from planner.paths import ROOT, Paths
from planner.yaml_io import load_yaml


def _write_receipts(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text(
            "format: supp-slotter.grooming-receipts/v1\nassessments: []\n",
            encoding="utf-8",
        )
        return
    assessments = "\n".join(
        f'  - composition_role: {role}\n    assessed_on: "2026-08-30"\n    outcome: {outcome}' for role, outcome in rows
    )
    path.write_text(f"format: supp-slotter.grooming-receipts/v1\nassessments:\n{assessments}\n", encoding="utf-8")


def _bundle(*, substances: set[str] = frozenset(), roles: set[str] = frozenset()) -> SimpleNamespace:
    facts = tuple(
        SimpleNamespace(applicability=SimpleNamespace(substance=substance, composition_role=None))
        for substance in substances
    ) + tuple(SimpleNamespace(applicability=SimpleNamespace(substance=None, composition_role=role)) for role in roles)
    catalog = SimpleNamespace(
        food_effects=facts,
        acute_alertness_effects=(),
        acute_sleep_effects=(),
        pre_exercise_performance_effects=(),
        post_exercise_recovery_effects=(),
    )
    return SimpleNamespace(
        runtime_program=SimpleNamespace(
            canonical_fact_catalog=catalog,
            glue_contract=SimpleNamespace(
                inactive_stack_name="inactive",
                stack_partition=SimpleNamespace(routable_stack_names=("daily", "training")),
            ),
        )
    )


def _fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Paths, SimpleNamespace, str, str]:
    role_a = "cmp_prd_aaaaaaaaaa__sub_aaaaaaaaaa"
    role_b = "cmp_prd_aaaaaaaaaa__sub_bbbbbbbbbb"
    products = {
        "prd_aaaaaaaaaa": Product(
            "prd_aaaaaaaaaa",
            "Active product",
            (ProductComponent("sub_aaaaaaaaaa", id=role_a), ProductComponent("sub_bbbbbbbbbb", id=role_b)),
        )
    }
    substances = {
        "sub_aaaaaaaaaa": Substance("sub_aaaaaaaaaa", "Alpha"),
        "sub_bbbbbbbbbb": Substance("sub_bbbbbbbbbb", "Beta"),
    }
    monkeypatch.setattr(grooming, "load_product_registry", lambda _paths, _bundle: products)
    monkeypatch.setattr(grooming, "load_substance_registry", lambda _paths, _bundle: substances)
    monkeypatch.setattr(grooming, "_active_role_ids", lambda _paths, _products, _bundle: {role_a, role_b})
    return Paths.from_root(tmp_path), _bundle(substances={"sub_aaaaaaaaaa"}), role_a, role_b


def test_receipt_catalog_closes_the_real_active_queue(tmp_path: Path) -> None:
    bundle = load_ontology(ROOT / "ontology")
    copytree(ROOT / "data", tmp_path / "data")
    paths = Paths.from_root(tmp_path)
    products = load_product_registry(paths, bundle)
    substances = load_substance_registry(paths, bundle)
    all_roles = grooming._component_roles(products, substances)
    active_role_ids = grooming._active_role_ids(paths, products, bundle)
    fact_role_ids = grooming._canonical_fact_role_ids(bundle, all_roles)
    receipts = grooming._load_receipts(
        paths.data / "grooming-receipts.yaml",
        known_role_ids=set(all_roles),
        fact_role_ids=fact_role_ids,
    )

    assert len(active_role_ids) == 45
    assert len(active_role_ids & fact_role_ids) == 4
    assert len(fact_role_ids) >= 6
    assert len(receipts) == 41
    assert sum(receipt.outcome == "no_supported_fact" for receipt in receipts) == 41
    assert not (active_role_ids - fact_role_ids - {receipt.composition_role for receipt in receipts})


def test_queue_is_stable_under_receipt_permutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths, bundle, _role_a, role_b = _fixture(monkeypatch, tmp_path)
    _write_receipts(paths.data / "grooming-receipts.yaml", [(role_b, "no_supported_fact")])

    selected, eligible = grooming._select_work_items(paths, bundle)
    _write_receipts(paths.data / "grooming-receipts.yaml", [(role_b, "no_supported_fact")])
    selected_reordered, eligible_reordered = grooming._select_work_items(paths, bundle)

    assert (selected, eligible) == ((), 0)
    assert (selected_reordered, eligible_reordered) == ((), 0)


def test_removing_then_restoring_an_active_receipt_reopens_then_closes_its_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, bundle, _role_a, role_b = _fixture(monkeypatch, tmp_path)
    _write_receipts(paths.data / "grooming-receipts.yaml", [(role_b, "no_supported_fact")])
    selected, eligible = grooming._select_work_items(paths, bundle)
    assert not selected and eligible == 0

    _write_receipts(paths.data / "grooming-receipts.yaml", [])
    selected, eligible = grooming._select_work_items(paths, bundle)
    assert selected[0].id == role_b and eligible == 1

    _write_receipts(paths.data / "grooming-receipts.yaml", [(role_b, "no_supported_fact")])
    selected, eligible = grooming._select_work_items(paths, bundle)
    assert not selected and eligible == 0


def test_inactive_receipt_does_not_queue_until_the_role_is_activated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, bundle, role_a, role_b = _fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(grooming, "_active_role_ids", lambda _paths, _products, _bundle: {role_a})
    _write_receipts(paths.data / "grooming-receipts.yaml", [])
    selected, eligible = grooming._select_work_items(paths, bundle)
    assert not selected and eligible == 0

    monkeypatch.setattr(grooming, "_active_role_ids", lambda _paths, _products, _bundle: {role_a, role_b})
    selected, eligible = grooming._select_work_items(paths, bundle)
    assert selected[0].id == role_b and eligible == 1

    _write_receipts(paths.data / "grooming-receipts.yaml", [(role_b, "no_supported_fact")])
    selected, eligible = grooming._select_work_items(paths, bundle)
    assert not selected and eligible == 0


@pytest.mark.parametrize(
    ("rows", "fact_role_ids", "match"),
    [
        (
            [
                ("cmp_prd_aaaaaaaaaa__sub_aaaaaaaaaa", "no_supported_fact"),
                ("cmp_prd_aaaaaaaaaa__sub_aaaaaaaaaa", "no_supported_fact"),
            ],
            {"cmp_prd_aaaaaaaaaa__sub_aaaaaaaaaa"},
            "duplicate",
        ),
        ([("cmp_unknown", "no_supported_fact")], set(), "unknown"),
        (
            [("cmp_prd_aaaaaaaaaa__sub_aaaaaaaaaa", "no_supported_fact")],
            {"cmp_prd_aaaaaaaaaa__sub_aaaaaaaaaa"},
            "newly covered",
        ),
    ],
)
def test_receipt_loader_rejects_duplicate_unknown_and_incoherent_rows(
    tmp_path: Path, rows: list[tuple[str, str]], fact_role_ids: set[str], match: str
) -> None:
    path = tmp_path / "grooming-receipts.yaml"
    _write_receipts(path, rows)

    with pytest.raises(CardLoadError, match=match):
        grooming._load_receipts(
            path,
            known_role_ids={"cmp_prd_aaaaaaaaaa__sub_aaaaaaaaaa"},
            fact_role_ids=fact_role_ids,
        )


@pytest.mark.parametrize(
    ("assessed_on", "match"),
    [("2026-02-28", "quoted YYYY-MM-DD"), ('"2026-02-30"', "valid calendar date")],
)
def test_receipt_loader_rejects_unquoted_or_invalid_dates(tmp_path: Path, assessed_on: str, match: str) -> None:
    path = tmp_path / "grooming-receipts.yaml"
    path.write_text(
        "format: supp-slotter.grooming-receipts/v1\nassessments:\n"
        "  - composition_role: cmp_prd_aaaaaaaaaa__sub_aaaaaaaaaa\n"
        f"    assessed_on: {assessed_on}\n"
        "    outcome: no_supported_fact\n",
        encoding="utf-8",
    )

    with pytest.raises(CardLoadError, match=match):
        grooming._load_receipts(path, known_role_ids={"cmp_prd_aaaaaaaaaa__sub_aaaaaaaaaa"}, fact_role_ids=set())


def test_receipts_are_operational_and_not_a_plan_runtime_input() -> None:
    assert "grooming-receipts" not in (ROOT / "ontology" / "manifest.yaml").read_text(encoding="utf-8")
    for path in (ROOT / "planner" / "engine" / "_plan_inputs.py", ROOT / "planner" / "engine" / "plan.py"):
        assert "grooming-receipts" not in path.read_text(encoding="utf-8")
    assert load_yaml(ROOT / "data" / "grooming-receipts.yaml") is not None
