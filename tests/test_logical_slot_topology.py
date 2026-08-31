"""Cluster 2 acceptance tests for the logical slot topology boundary."""

from __future__ import annotations

from pathlib import Path

import pytest
from planner.cards.pillboxes import load_pillboxes
from planner.contracts import CardLoadError

from tests.helpers import ontology_bundle

ROOT = Path(__file__).resolve().parents[1]


def test_authored_topology_has_exact_six_migrated_slots() -> None:
    pillboxes = load_pillboxes(ROOT / "data" / "pillboxes.yaml", ontology_bundle())

    assert {slot_id: slot.anchors for pillbox in pillboxes.values() for slot_id, slot in pillbox.slots.items()} == {
        "morning_empty": {"meal_context": "without_food", "circadian_anchor": "wake", "exercise_anchor": None},
        "morning_food": {"meal_context": "with_food", "circadian_anchor": None, "exercise_anchor": None},
        "day_food": {"meal_context": "with_food", "circadian_anchor": None, "exercise_anchor": None},
        "evening_empty": {"meal_context": "without_food", "circadian_anchor": "sleep", "exercise_anchor": None},
        "pre_workout": {"meal_context": "without_food", "circadian_anchor": None, "exercise_anchor": "before"},
        "post_workout": {"meal_context": "without_food", "circadian_anchor": None, "exercise_anchor": "after"},
    }


def test_topology_axes_are_optional_and_do_not_use_label_or_order(tmp_path: Path) -> None:
    path = tmp_path / "pillboxes.yaml"
    path.write_text(
        """
daily:
  label: Daily
  stack: daily
  slots:
    arbitrary_name:
      label: Wake-like prose, but no anchor
      order: 42
""",
        encoding="utf-8",
    )

    slot = load_pillboxes(path, ontology_bundle())["daily"].slots["arbitrary_name"]

    assert slot.anchors == {"meal_context": None, "circadian_anchor": None, "exercise_anchor": None}


@pytest.mark.parametrize("field", ("near", "food", "capacity", "dose", "count", "physical_fit"))
def test_legacy_and_physical_slot_fields_are_rejected(tmp_path: Path, field: str) -> None:
    path = tmp_path / f"pillboxes-{field}.yaml"
    path.write_text(
        f"daily:\n  label: Daily\n  stack: daily\n  slots:\n    morning:\n      label: Morning\n      order: 1\n      {field}: wake\n",
        encoding="utf-8",
    )

    with pytest.raises(CardLoadError, match=field):
        load_pillboxes(path, ontology_bundle())


def test_duplicate_global_slot_ids_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "pillboxes.yaml"
    path.write_text(
        """
daily:
  label: Daily
  stack: daily
  slots:
    shared:
      label: Daily
      order: 1
training:
  label: Training
  stack: training
  slots:
    shared:
      label: Training
      order: 1
""",
        encoding="utf-8",
    )

    with pytest.raises(CardLoadError, match=r"slot_identity.*duplicate value 'shared'"):
        load_pillboxes(path, ontology_bundle())


def test_duplicate_order_is_rejected_within_one_topology(tmp_path: Path) -> None:
    path = tmp_path / "pillboxes.yaml"
    path.write_text(
        """
daily:
  label: Daily
  stack: daily
  slots:
    first:
      label: First
      order: 1
    second:
      label: Second
      order: 1
""",
        encoding="utf-8",
    )

    with pytest.raises(CardLoadError, match=r"slot_order.*duplicate value 1"):
        load_pillboxes(path, ontology_bundle())


def test_distinct_topologies_keep_distinct_stack_references(tmp_path: Path) -> None:
    path = tmp_path / "pillboxes.yaml"
    path.write_text(
        """
daily:
  label: Daily
  stack: daily
  slots:
    daily_slot:
      label: Daily slot
      order: 1
training:
  label: Training
  stack: training
  slots:
    training_slot:
      label: Training slot
      order: 1
""",
        encoding="utf-8",
    )

    pillboxes = load_pillboxes(path, ontology_bundle())

    assert {pillbox.stack for pillbox in pillboxes.values()} == {"daily", "training"}
