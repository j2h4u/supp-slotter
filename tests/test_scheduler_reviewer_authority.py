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
            products = cast(list[dict[str, str]], entry["products"])
            if any(product["label"] == product_name for product in products):
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


def test_review_only_relation_cannot_change_command_level_schedule(tmp_path: Path) -> None:
    """Review evidence may change review output, never the canonical planner result."""
    base = tmp_path / "base"
    reviewer = tmp_path / "reviewer"
    fixture = PlannerFixtureInput(
        stack_items={"product": {"stack": "daily"}, "active_product": {"stack": "daily"}},
        products={
            "product": [("component", ["effect:nitric_oxide_support"])],
            "active_product": [("epa_component", ["effect:pde5_inhibition"])],
        },
        traits={
            "effect:nitric_oxide_support": {
                "label": "Nitric oxide support",
                "description": "Fixture",
                "applies_when": "Fixture",
            },
            "effect:pde5_inhibition": {
                "label": "PDE5 inhibition",
                "description": "Fixture",
                "applies_when": "Fixture",
            },
        },
    )
    write_minimal_planner_fixture(base, fixture)
    write_minimal_planner_fixture(reviewer, fixture)
    relations_path = reviewer / "data" / "relations.yaml"
    vocabulary = yaml.safe_load((ROOT / "ontology/generated/runtime-vocabulary.yaml").read_text(encoding="utf-8"))
    assert isinstance(vocabulary, dict)
    catalog = cast(dict[str, dict[str, object]], vocabulary["ontology_assertions"])
    relations_path.write_text(
        yaml.safe_dump({"relations": [catalog["rel_co_use_context_001"]]}, sort_keys=False), encoding="utf-8"
    )

    assert cmd_plan(data_root=base).exit_code == 0
    assert cmd_plan(data_root=reviewer).exit_code == 0
    base_schedule = yaml.safe_load((base / "schedule.yaml").read_text(encoding="utf-8"))
    reviewer_schedule = yaml.safe_load((reviewer / "schedule.yaml").read_text(encoding="utf-8"))
    assert isinstance(base_schedule, dict) and isinstance(reviewer_schedule, dict)
    # Both review endpoints are active and routable; review-only metadata must
    # leave the complete published schedule unchanged, not merely one product.
    assert _scheduled_slot(base_schedule, "Product")
    assert _scheduled_slot(base_schedule, "Active Product")
    assert _scheduled_slot(reviewer_schedule, "Product")
    assert _scheduled_slot(reviewer_schedule, "Active Product")
    assert reviewer_schedule == base_schedule

    base_review = cmd_review(data_root=base)
    reviewer_review = cmd_review(data_root=reviewer)
    assert base_review.exit_code == reviewer_review.exit_code == 0
    assert base_review.output != reviewer_review.output
    assert "The convergence is mechanistic" in reviewer_review.output
    assert "The convergence is mechanistic" not in base_review.output
    assert "[Co-use context]" in reviewer_review.output
    assert "[Co-use context]" not in base_review.output
    assert "Evidence relations involving current stack" in reviewer_review.output
    assert "state: mechanistic_only" in reviewer_review.output
    assert "https://pubmed.ncbi.nlm.nih.gov/17662090/" in reviewer_review.output
    assert not any(
        token in reviewer_review.output.casefold()
        for token in ("warning", "severity", "contraindication", "add ", "remove ", "separate ", "consult ")
    )


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
