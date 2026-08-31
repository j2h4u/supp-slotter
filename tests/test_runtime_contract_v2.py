"""Focused acceptance for the closed, portable online runtime contract."""

from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from functools import cache
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
import yaml
from planner.cards.dashboards import build_dashboard_review
from planner.contracts import KnowledgeAssertion, Product, ProductComponent, Substance
from planner.engine import review_model
from planner.engine.review_model import _ConcernFilterContext
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import (
    IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY,
    IMPLEMENTED_DOMAIN_FEASIBILITY,
    IMPLEMENTED_ENGINE_CONTRACT_PROTOCOL,
    IMPLEMENTED_PRESSURE_IDENTITY,
    IMPLEMENTED_PRESSURE_SATISFACTION_STRATEGY,
    IMPLEMENTED_PRIMARY_OBJECTIVE,
    IMPLEMENTED_PUBLICATION_STATUSES,
    IMPLEMENTED_SECONDARY_OBJECTIVE,
    IMPLEMENTED_TIE_BREAK,
    decode_runtime_program,
)
from planner.paths import Paths
from planner.query_model.data import ReadModelData, RelationEndpoint, RelationQuery
from planner.query_model.read_model import StackReadModel
from planner.query_model.relations import classify_relations
from scripts.ontology_compiler import compile_ontology

from tests.helpers import ontology_bundle

ROOT = Path(__file__).resolve().parents[1]


@cache
def _compiled_payload() -> str:
    artifacts = compile_ontology(ROOT / "ontology")
    return artifacts[Path("runtime-program.json")].decode("utf-8")


def _payload() -> dict[str, object]:
    return cast(dict[str, object], json.loads(deepcopy(_compiled_payload())))


def _blank_first_canonical_fact_id(payload: dict[str, object]) -> None:
    projection = cast(dict[str, object], payload["projection"])
    scheduling = cast(dict[str, object], projection["canonical_scheduling"])
    facts = cast(list[dict[str, object]], scheduling["facts"])
    facts[0]["id"] = "   "


def _pad_first_canonical_fact_id(payload: dict[str, object]) -> None:
    projection = cast(dict[str, object], payload["projection"])
    scheduling = cast(dict[str, object], projection["canonical_scheduling"])
    facts = cast(list[dict[str, object]], scheduling["facts"])
    facts[0]["id"] = f" {facts[0]['id']}"


def test_v2_contract_decodes_exactly_and_excludes_retired_objective_inputs() -> None:
    payload = _payload()
    runtime = decode_runtime_program(payload)
    contract = runtime.engine_contract

    assert contract.protocol_version == IMPLEMENTED_ENGINE_CONTRACT_PROTOCOL
    assert contract.pressure_identity == IMPLEMENTED_PRESSURE_IDENTITY
    assert contract.applicability_expansion_strategy == IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY
    assert contract.pressure_satisfaction_strategy == IMPLEMENTED_PRESSURE_SATISFACTION_STRATEGY
    assert contract.domain_feasibility == IMPLEMENTED_DOMAIN_FEASIBILITY
    assert contract.primary_objective == IMPLEMENTED_PRIMARY_OBJECTIVE
    assert contract.secondary_objective == IMPLEMENTED_SECONDARY_OBJECTIVE
    assert contract.tie_break == IMPLEMENTED_TIE_BREAK
    assert contract.publication_statuses == IMPLEMENTED_PUBLICATION_STATUSES
    projection = cast(dict[str, object], payload["projection"])
    assert "effect_scoring" not in projection
    assert "constraint_execution_policies" not in projection


def test_authored_stack_partition_is_closed_and_reproduces_active_membership() -> None:
    payload = _payload()
    runtime = decode_runtime_program(payload)
    partition = runtime.glue_contract.stack_partition

    assert partition.routable_stack_names == ("daily", "training")
    assert partition.excluded_stack_names == ("inactive",)
    assert partition.tracked_unassigned_partition_name == "tracked_unassigned"
    assert not (set(partition.routable_stack_names) & set(partition.excluded_stack_names))

    projection = cast(dict[str, object], payload["projection"])
    glue = cast(dict[str, object], projection["glue_contract"])
    partition_payload = cast(dict[str, object], glue["stack_partition"])
    partition_payload["excluded_stack_names"] = ["daily"]
    with pytest.raises(OntologyInfrastructureError, match="disjoint"):
        decode_runtime_program(payload)


def test_second_excluded_partition_cannot_enter_current_review_or_relation_inputs(  # noqa: PLR0914
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Only runtime-declared routable partitions contribute to active views."""
    bundle = ontology_bundle()
    runtime = bundle.runtime_program
    partition = replace(
        runtime.glue_contract.stack_partition,
        excluded_stack_names=(*runtime.glue_contract.stack_partition.excluded_stack_names, "archived"),
    )
    runtime = replace(runtime, glue_contract=replace(runtime.glue_contract, stack_partition=partition))
    test_bundle = SimpleNamespace(runtime_program=runtime)

    active = Substance("sub_aaaaaaaaaa", "Active")
    excluded = Substance(
        "sub_bbbbbbbbbb",
        "Archived",
        knowledge_assertions=(KnowledgeAssertion("context", "vascular_health"),),
    )
    active_product = Product(
        "prd_aaaaaaaaaa", "Active product", (ProductComponent(active.id, "cmp_prd_aaaaaaaaaa__sub_aaaaaaaaaa"),)
    )
    excluded_product = Product(
        "prd_bbbbbbbbbb", "Archived product", (ProductComponent(excluded.id, "cmp_prd_bbbbbbbbbb__sub_bbbbbbbbbb"),)
    )
    products = {active_product.id: active_product, excluded_product.id: excluded_product}
    substances = {active.id: active, excluded.id: excluded}
    stacks = {"daily": [active_product.id], "inactive": [], "archived": [excluded_product.id], "training": []}

    query_model = StackReadModel(
        ReadModelData(substances=substances, products=products, stacks=stacks, relations=()),
        test_bundle,  # type: ignore[arg-type]
    )
    active_ids = query_model.active_substance_ids()
    assert active_ids == {active.id}

    relation = RelationQuery(
        relation_type="co_use_context",
        source=RelationEndpoint("excluded", "Archived", (excluded.id,), ("Archived",), "entity_id"),
        target=RelationEndpoint("active", "Active", (active.id,), ("Active",), "entity_id"),
        reason="excluded membership must not become active relation evidence",
        research_state="unassessed",
        sources=(),
    )
    rows = classify_relations((relation,), active_ids, runtime)
    assert rows[0]["source_matches"] == []
    assert rows[0]["target_matches"] == ["Active"]

    dashboard = tmp_path / "data" / "dashboards" / "archived.yaml"
    dashboard.parent.mkdir(parents=True)
    dashboard.write_text(
        yaml.safe_dump(
            {
                "id": "archived_dashboard",
                "name": "Archived dashboard",
                "description": "Second excluded partition regression",
                "benefit": {"description": "Archived benefit"},
                "selectors": [{"category": "context", "term": "vascular_health"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    dashboard_review = build_dashboard_review(
        dashboard_files=[dashboard],
        products=products,
        stack_entries={
            product_id: {"product": product_id, "stack": stack}
            for stack, product_ids in stacks.items()
            for product_id in product_ids
        },
        substances=substances,
        bundle=SimpleNamespace(
            root=bundle.root,
            decoded=bundle.decoded,
            runtime_program=runtime,
            runtime_vocabulary=bundle.runtime_vocabulary,
        ),  # type: ignore[arg-type]
    )
    dashboard_benefit = cast(list[dict[str, object]], dashboard_review["benefits"])[0]
    dashboard_member = cast(list[dict[str, object]], dashboard_benefit["members"])[0]
    usage = cast(dict[str, object], dashboard_member["usage"])
    assert usage["state"] == "on_shelf"
    assert usage["state"] != "current"
    assert usage["stacks"] == ["archived"]

    captured: dict[str, _ConcernFilterContext] = {}
    monkeypatch.setattr(review_model, "load_substance_registry", lambda *_args: substances)
    monkeypatch.setattr(review_model, "load_product_registry", lambda *_args: products)
    monkeypatch.setattr(review_model, "load_yaml", lambda _path: {})
    monkeypatch.setattr(review_model, "check_global_relations", lambda *_args: [])
    monkeypatch.setattr(review_model, "load_global_relations", lambda *_args: [])
    monkeypatch.setattr(review_model, "stacks_for_read_model", lambda *_args: stacks)
    monkeypatch.setattr(review_model, "build_stack_read_model", lambda *_args, **_kwargs: query_model)
    monkeypatch.setattr(review_model, "_dashboard_summary", lambda *_args: {})

    def capture_concerns(
        context: _ConcernFilterContext, _order: tuple[str, ...]
    ) -> dict[str, list[review_model.ConcernEntry]]:
        captured["context"] = context
        return {}

    monkeypatch.setattr(review_model, "_concerns_by_kind", capture_concerns)
    model, errors = review_model.build_review_model(Paths.from_root(tmp_path), test_bundle)  # type: ignore[arg-type]

    assert errors == []
    assert model is not None
    assert set(captured["context"].substances) == {active.id}
    assert set(captured["context"].products) == {active_product.id}


def test_v1_contract_is_rejected_without_compatibility_fallback() -> None:
    payload = _payload()
    projection = cast(dict[str, object], payload["projection"])
    contract = cast(dict[str, object], projection["engine_contract"])
    contract["protocol_version"] = "supp-slotter.engine-contract/v1"

    with pytest.raises(OntologyInfrastructureError, match="not implemented"):
        decode_runtime_program(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("applicability_expansion_strategy", "all_roles"),
        ("pressure_satisfaction_strategy", "anchor_contains_value"),
    ),
)
def test_engine_semantic_strategies_are_closed_exact_values(field: str, value: str) -> None:
    payload = _payload()
    projection = cast(dict[str, object], payload["projection"])
    contract = cast(dict[str, object], projection["engine_contract"])
    contract[field] = value

    with pytest.raises(OntologyInfrastructureError, match="not an admitted value"):
        decode_runtime_program(payload)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda payload: cast(dict[str, object], payload["provenance"]).__setitem__("source", "runtime-policy.yaml"),
        lambda payload: cast(dict[str, object], payload["provenance"]).__setitem__("source_sha256", "A" * 64),
        lambda payload: cast(dict[str, object], payload["provenance"]).__setitem__("manifest_schema_version", "3"),
        lambda payload: payload.__setitem__("source_hash", " "),
        _blank_first_canonical_fact_id,
        _pad_first_canonical_fact_id,
    ),
)
def test_runtime_envelope_and_canonical_ids_fail_closed(mutate: Callable[[dict[str, object]], None]) -> None:
    payload = _payload()
    mutate(payload)

    with pytest.raises(OntologyInfrastructureError):
        decode_runtime_program(payload)


@pytest.mark.parametrize(
    "retired_field",
    [
        "highest_maximum_score",
        "float_epsilon",
        "weight",
        "bonus",
        "penalty",
        "advisory",
        "pair_mode",
        "blocks_slots",
        "constraint_execution_policies",
    ],
)
def test_retired_objective_and_pair_fields_are_rejected(retired_field: str) -> None:
    payload = _payload()
    projection = cast(dict[str, object], payload["projection"])
    contract = cast(dict[str, object], projection["engine_contract"])
    contract[retired_field] = False

    with pytest.raises(OntologyInfrastructureError, match="invalid closed shape"):
        decode_runtime_program(payload)
