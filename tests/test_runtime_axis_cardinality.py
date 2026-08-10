"""Executable cardinality contract for authored schedule axes."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.cards.substance import load_substance
from planner.contracts import CardLoadError, Product, ProductComponent, ScheduleAssertion, Substance
from planner.engine._scheduling import project_schedule_assignments
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import decode_runtime_program
from scripts.ontology_compiler import compile_ontology

from tests.helpers import ontology_bundle
from tests.test_ontology_artifacts import _copy_repository_shape

ROOT = Path(__file__).resolve().parents[1]


def _payload() -> dict[str, object]:
    return cast(dict[str, object], json.loads((ROOT / "ontology/generated/runtime-program.json").read_text()))


def _axis_row(payload: dict[str, object], index: int = 0) -> dict[str, object]:
    projection = cast(dict[str, object], payload["projection"])
    axes = cast(list[dict[str, object]], projection["assignment_axes"])
    return axes[index]


def _bundle_with_runtime(runtime: object):
    base = copy.copy(ontology_bundle())
    object.__setattr__(base, "_runtime_program", runtime)
    return base


def test_runtime_axis_decodes_authored_cardinality() -> None:
    runtime = ontology_bundle().runtime_program
    axis = runtime.assignment_axes[0]
    assert axis.minimum_cardinality == 0
    assert axis.maximum_cardinality == 1


def test_runtime_decode_rejects_removed_parallel_rule_and_table_sections() -> None:
    payload = _payload()
    payload["rules"] = []
    payload["tables"] = []
    with pytest.raises(OntologyInfrastructureError, match="top-level shape"):
        decode_runtime_program(payload)


def test_runtime_decode_rejects_unknown_projection_target() -> None:
    payload = _payload()
    projection = cast(dict[str, object], payload["projection"])
    projection["rules"] = []
    with pytest.raises(OntologyInfrastructureError, match="closed shape"):
        decode_runtime_program(payload)


def test_compiler_rejects_unknown_projection_target(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    policy_path = root / "runtime-policy.yaml"
    source = cast(dict[str, object], yaml.safe_load(policy_path.read_text(encoding="utf-8")))
    projections = cast(list[dict[str, object]], source["runtime_projection"])
    projections.append({"id": "removed_rules", "target": "rules", "source": "rules"})
    policy_path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError, match="not executable"):
        compile_ontology(root)


@pytest.mark.parametrize(
    ("minimum", "maximum"),
    [(2, 1), (-1, 1), (0, -1)],
)
def test_runtime_axis_rejects_invalid_cardinality_contract(minimum: int, maximum: int) -> None:
    payload = _payload()
    row = _axis_row(payload)
    row["minimum_cardinality"] = minimum
    row["maximum_cardinality"] = maximum
    with pytest.raises(OntologyInfrastructureError, match="cardinality"):
        decode_runtime_program(payload)


@pytest.mark.parametrize(
    ("minimum", "maximum", "message"),
    [(2, 2, "at least 2"), (0, 0, "at most 0")],
)
def test_card_loader_enforces_mutated_axis_cardinality(
    tmp_path: Path, minimum: int, maximum: int, message: str
) -> None:
    payload = _payload()
    row = _axis_row(payload)
    row["minimum_cardinality"] = minimum
    row["maximum_cardinality"] = maximum
    runtime = decode_runtime_program(payload)
    bundle = _bundle_with_runtime(runtime)
    card = {
        "id": "sub_aaaaaaaaaa",
        "name": "A",
        "schedule": {"intake": ["food_preferred"]},
    }
    path = tmp_path / "a__sub_aaaaaaaaaa.yaml"
    path.write_text(yaml.safe_dump(card, sort_keys=False), encoding="utf-8")
    with pytest.raises(CardLoadError, match=message):
        load_substance(path, bundle)


def test_scheduler_enforces_axis_cardinality_even_for_typed_mutation() -> None:
    runtime = ontology_bundle().runtime_program
    axis = runtime.assignment_axes[0]
    mutated = replace(runtime, assignment_axes=(replace(axis, maximum_cardinality=0), *runtime.assignment_axes[1:]))
    product = Product("prd_a", "A", (ProductComponent("sub_a"),))
    substance = Substance("sub_a", "A", (), schedule_assertions=(ScheduleAssertion("intake", "food_preferred"),))
    with pytest.raises(OntologyInfrastructureError, match="at most 0"):
        project_schedule_assignments(mutated, product, {substance.id: substance}, {})
