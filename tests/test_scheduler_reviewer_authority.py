"""Review-only knowledge must not become a scheduling input."""

import json
import time
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import planner.ontology.artifacts as artifacts
import pytest
import yaml
from planner.engine import cmd_find, cmd_plan, cmd_review
from planner.paths import ROOT

from tests.planner_fixture import (
    PlannerFixtureInput,
    PlannerFixtureOptions,
    plan_in_temp_dir,
    write_minimal_planner_fixture,
)


def _scheduled_slot(schedule: dict[str, object], product_name: str) -> str:
    pillboxes = schedule["pillboxes"]
    assert isinstance(pillboxes, dict)
    for pillbox in pillboxes.values():
        assert isinstance(pillbox, dict)
        slots = pillbox["slots"]
        assert isinstance(slots, dict)
        for slot_id, entry in cast(Mapping[str, object], slots).items():
            assert isinstance(entry, dict)
            products = cast(list[str], entry["products"])
            if product_name in products:
                return str(slot_id)
    raise AssertionError(f"product {product_name!r} was not scheduled")


def test_reviewer_only_knowledge_does_not_change_slot_assignment(tmp_path: Path) -> None:
    base = tmp_path / "base"
    reviewer = tmp_path / "reviewer"
    fixture = PlannerFixtureInput(
        stack_items={"product": {"stack": "daily"}, "active_product": {"stack": "daily"}},
        products={
            "product": [("component", ["effect:circulation_support"])],
            "active_product": [
                ("epa_component", ["risk:bleeding_med_interaction", "effect:platelet_aggregation_modulation"])
            ],
        },
        traits={
            "effect:circulation_support": {
                "label": "Circulation support",
                "description": "Fixture",
                "applies_when": "Fixture",
            },
            "risk:bleeding_med_interaction": {
                "label": "Bleeding medication interaction",
                "description": "Fixture",
                "applies_when": "Fixture",
            },
            "effect:platelet_aggregation_modulation": {
                "label": "Platelet aggregation modulation",
                "description": "Fixture",
                "applies_when": "Fixture",
            },
        },
    )
    write_minimal_planner_fixture(base, fixture)
    write_minimal_planner_fixture(
        reviewer,
        PlannerFixtureInput(
            stack_items=fixture.stack_items,
            products={
                "product": [("component", ["effect:circulation_support", "risk:manual_review"])],
                "active_product": fixture.products["active_product"],
            },
            traits={
                **fixture.traits,
                "risk:manual_review": {"label": "Review only", "description": "Fixture", "applies_when": "Fixture"},
            },
        ),
    )
    base_slot = _scheduled_slot(plan_in_temp_dir(base), "Product")
    reviewer_schedule = plan_in_temp_dir(reviewer)
    reviewer_slot = _scheduled_slot(reviewer_schedule, "Product")
    assert base_slot == reviewer_slot
    active_fact_index = cast(list[dict[str, object]], reviewer_schedule["active_fact_index"])
    assert active_fact_index == []


def test_review_only_relation_cannot_change_command_level_schedule(tmp_path: Path) -> None:
    """Review evidence may change review output, never the canonical planner result."""
    base = tmp_path / "base"
    reviewer = tmp_path / "reviewer"
    fixture = PlannerFixtureInput(
        stack_items={"product": {"stack": "daily"}, "active_product": {"stack": "inactive"}},
        products={
            "product": [("component", ["effect:circulation_support"])],
            "active_product": [("epa_component", ["effect:platelet_aggregation_modulation"])],
        },
        traits={
            "effect:circulation_support": {
                "label": "Circulation support",
                "description": "Fixture",
                "applies_when": "Fixture",
            },
            "effect:platelet_aggregation_modulation": {
                "label": "Platelet aggregation modulation",
                "description": "Fixture",
                "applies_when": "Fixture",
            },
        },
    )
    write_minimal_planner_fixture(base, fixture)
    write_minimal_planner_fixture(
        reviewer,
        fixture,
        PlannerFixtureOptions(
            substance_relations={
                "component": [
                    {
                        "relation_type": "balance",
                        "substances": ["epa_component"],
                        "reason": "Fixture review-only relation.",
                    }
                ]
            }
        ),
    )
    relations_path = reviewer / "data" / "relations.yaml"
    relations = yaml.safe_load(relations_path.read_text(encoding="utf-8"))
    assert isinstance(relations, dict)
    relation = cast(list[dict[str, object]], relations["relations"])[0]
    relation["assertion_kind"] = "clinical_review_signal"
    relation["semantic_family"] = "nutrient_balance_review_signal"
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False), encoding="utf-8")

    assert cmd_plan(data_root=base).exit_code == 0
    assert cmd_plan(data_root=reviewer).exit_code == 0
    base_schedule = yaml.safe_load((base / "schedule.yaml").read_text(encoding="utf-8"))
    reviewer_schedule = yaml.safe_load((reviewer / "schedule.yaml").read_text(encoding="utf-8"))
    assert isinstance(base_schedule, dict) and isinstance(reviewer_schedule, dict)
    for field in ("status", "objective", "assignments", "pressure_matches", "domain_loads", "optimizer_proof"):
        assert reviewer_schedule[field] == base_schedule[field]
    assert reviewer_schedule["canonical_explanations"] == base_schedule["canonical_explanations"]

    base_review = cmd_review(data_root=base)
    reviewer_review = cmd_review(data_root=reviewer)
    assert base_review.exit_code == reviewer_review.exit_code == 0
    assert base_review.output != reviewer_review.output
    assert "Fixture review-only relation." in reviewer_review.output
    assert "Fixture review-only relation." not in base_review.output


@pytest.mark.parametrize("command", ("plan", "find", "review"))
def test_runtime_commands_read_only_declared_runtime_outputs_and_command_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    """The 20-second ceiling catches accidental formal-runtime work without microbenchmarking."""
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={"product": {"stack": "daily"}},
            products={"product": [("component", [])]},
            traits={},
        ),
    )
    runtime_root = ROOT / "ontology" / "generated"
    runtime_lock = runtime_root / "runtime-lock.json"
    lock = json.loads(runtime_lock.read_text(encoding="utf-8"))
    output_names = {record["path"] for record in lock["outputs"]}
    assert len(output_names) == 9
    allowed_runtime_reads = {runtime_lock, *(runtime_root / name for name in output_names)}
    artifact_reads: list[Path] = []
    text_reads: list[Path] = []
    original_artifact_read = artifacts._read_bytes
    original_read_text = Path.read_text

    def record_artifact_read(path: Path, *, code: str) -> bytes:
        artifact_reads.append(path)
        return original_artifact_read(path, code=code)

    def record_read_text(path: Path, *args: object, **kwargs: object) -> str:
        text_reads.append(path)
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(artifacts, "_read_bytes", record_artifact_read)
    monkeypatch.setattr(Path, "read_text", record_read_text)
    started = time.perf_counter()
    if command == "plan":
        result = cmd_plan(data_root=tmp_path)
        assert result.exit_code == 0, result.errors
    elif command == "find":
        result = cmd_find(["product"], data_root=tmp_path)
        assert result.exit_code == 0
    else:
        result = cmd_review(data_root=tmp_path)
        assert result.exit_code == 0, result.stderr
    elapsed = time.perf_counter() - started

    assert elapsed < 20.0, f"{command} crossed the 20-second runtime boundary: {elapsed:.2f}s"
    assert set(artifact_reads) == allowed_runtime_reads
    assert all(path in allowed_runtime_reads or path.is_relative_to(tmp_path / "data") for path in text_reads)
    forbidden_names = {"artifact-lock.json", "context.json", "ontology.ttl", "projection-map.json", "shapes.ttl"}
    assert forbidden_names.isdisjoint(path.name for path in [*artifact_reads, *text_reads])
