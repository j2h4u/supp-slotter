"""Cluster 2 acceptance tests for the logical slot topology boundary."""

from __future__ import annotations

from pathlib import Path

import pytest
from planner.cards.pillboxes import load_pillboxes
from planner.contracts import CardLoadError

ROOT = Path(__file__).resolve().parents[1]


def test_authored_topology_has_exact_six_migrated_slots() -> None:
    pillboxes = load_pillboxes(ROOT / "data" / "pillboxes.yaml", None)  # type: ignore[arg-type]

    assert {
        slot_id: (slot.meal_context, slot.circadian_anchor, slot.exercise_anchor)
        for pillbox in pillboxes.values()
        for slot_id, slot in pillbox.slots.items()
    } == {
        "morning_empty": ("without_food", "wake", None),
        "morning_food": ("with_food", None, None),
        "day_food": ("with_food", None, None),
        "evening_empty": ("without_food", "sleep", None),
        "pre_workout": ("without_food", None, "before"),
        "post_workout": ("without_food", None, "after"),
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

    slot = load_pillboxes(path, None)["daily"].slots["arbitrary_name"]  # type: ignore[arg-type]

    assert (slot.meal_context, slot.circadian_anchor, slot.exercise_anchor) == (None, None, None)


@pytest.mark.parametrize("field", ("near", "food", "capacity", "dose", "count", "physical_fit"))
def test_legacy_and_physical_slot_fields_are_rejected(tmp_path: Path, field: str) -> None:
    path = tmp_path / f"pillboxes-{field}.yaml"
    path.write_text(
        f"daily:\n  label: Daily\n  stack: daily\n  slots:\n    morning:\n      label: Morning\n      order: 1\n      {field}: wake\n",
        encoding="utf-8",
    )

    with pytest.raises(CardLoadError, match=field):
        load_pillboxes(path, None)  # type: ignore[arg-type]


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

    with pytest.raises(CardLoadError, match="duplicate global slot id"):
        load_pillboxes(path, None)  # type: ignore[arg-type]


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

    with pytest.raises(CardLoadError, match="duplicate slot order"):
        load_pillboxes(path, None)  # type: ignore[arg-type]
