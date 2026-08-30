"""Generic, fail-closed pillbox projection contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from planner.cards.pillboxes import load_pillboxes
from planner.contracts import CardLoadError
from planner.ontology.runtime_program import decode_runtime_program
from planner.schema_validation import schema_errors

from tests.helpers import ontology_bundle


def _runtime():
    payload = json.loads(
        (Path(__file__).resolve().parents[1] / "ontology/generated/runtime-program.json").read_text(encoding="utf-8")
    )
    return decode_runtime_program(payload)


def _write(path: Path, slot: str) -> None:
    path.write_text(
        "daily:\n  label: Daily\n  stack: daily\n  slots:\n    morning:\n      "
        + slot.replace("\n", "\n      ")
        + "\n",
        encoding="utf-8",
    )


def test_loader_projects_independent_topology_fields(tmp_path: Path) -> None:
    path = tmp_path / "pillboxes.yaml"
    _write(path, "label: Morning\norder: 1\nmeal_context: without_food\ncircadian_anchor: wake")

    slot = load_pillboxes(path, _runtime())["daily"].slots["morning"]

    assert slot.meal_context == "without_food"
    assert slot.circadian_anchor == "wake"
    assert slot.exercise_anchor is None


@pytest.mark.parametrize(
    "slot",
    (
        "order: 1\nmeal_context: without_food",
        "label: ''\norder: 1\nmeal_context: without_food",
        "label: Morning\norder: nope\nmeal_context: without_food",
        "label: Morning\norder: 1\nmeal_context: invalid",
    ),
)
def test_loader_rejects_missing_or_malformed_slot_fields(tmp_path: Path, slot: str) -> None:
    path = tmp_path / "pillboxes.yaml"
    _write(path, slot)

    with pytest.raises(CardLoadError):
        load_pillboxes(path, _runtime())


def test_generated_contract_rejects_global_slot_and_scoped_order_duplicates() -> None:
    data = {
        "daily": {
            "label": "Daily",
            "stack": "daily",
            "slots": {
                "morning": {"label": "Morning", "order": 1, "circadian_anchor": "wake"},
                "evening": {"label": "Evening", "order": 1, "circadian_anchor": "sleep"},
            },
        },
        "training": {
            "label": "Training",
            "stack": "training",
            "slots": {
                "morning": {"label": "Training morning", "order": 2, "circadian_anchor": "wake"},
            },
        },
    }

    errors = schema_errors(data, "pillboxes", Path("pillboxes.yaml"), ontology_bundle())

    assert any("duplicate value 1" in error for error in errors)
    assert any("duplicate value 'morning'" in error for error in errors)


def test_generated_contract_resolves_stack_references_from_validation_context() -> None:
    data = {
        "daily": {
            "label": "Daily",
            "stack": "missing",
            "slots": {"morning": {"label": "Morning", "order": 1, "circadian_anchor": "wake"}},
        }
    }

    errors = schema_errors(
        data,
        "pillboxes",
        Path("pillboxes.yaml"),
        ontology_bundle(),
        reference_values={"Stack": {"daily"}},
    )

    assert any("unknown reference 'missing'" in error for error in errors)
