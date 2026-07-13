from __future__ import annotations

from pathlib import Path

import pytest
from planner.cards.traits import load_scheduling_policies, readable_traits
from planner.contracts import CardLoadError, SchedulingPolicy


def _write_trait_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_load_scheduling_policies_reads_split_directory(tmp_path: Path) -> None:
    traits_dir = tmp_path / "traits"
    _write_trait_file(
        traits_dir / "classes.yaml",
        "is:\n  mineral:\n    label: Mineral\n    description: Fixture class.\n    applies_when: Fixture only.\n",
    )
    _write_trait_file(
        traits_dir / "risks.yaml",
        "risk:\n"
        "  manual_review:\n"
        "    label: Manual review\n"
        "    description: Fixture risk.\n"
        "    applies_when: Fixture only.\n",
    )

    policies = load_scheduling_policies(traits_dir)

    assert set(policies) == {"is:mineral", "risk:manual_review"}


def test_load_scheduling_policies_rejects_duplicate_namespace(tmp_path: Path) -> None:
    traits_dir = tmp_path / "traits"
    _write_trait_file(
        traits_dir / "one.yaml",
        "risk:\n  one:\n    label: One\n    description: Fixture.\n    applies_when: Fixture only.\n",
    )
    _write_trait_file(
        traits_dir / "two.yaml",
        "risk:\n  two:\n    label: Two\n    description: Fixture.\n    applies_when: Fixture only.\n",
    )

    with pytest.raises(CardLoadError, match="namespace 'risk' is already defined"):
        load_scheduling_policies(traits_dir)


def test_load_scheduling_policies_rejects_single_file_registry(tmp_path: Path) -> None:
    traits_file = tmp_path / "traits.yaml"
    traits_file.write_text(
        "risk:\n"
        "  manual_review:\n"
        "    label: Manual review\n"
        "    description: Fixture.\n"
        "    applies_when: Fixture only.\n",
        encoding="utf-8",
    )

    with pytest.raises(CardLoadError, match="expected trait directory"):
        load_scheduling_policies(traits_file)


def test_readable_traits_filters_internal_namespaces_and_uses_labels() -> None:
    policies = {
        "intake:with_food": SchedulingPolicy(
            id="intake:with_food",
            namespace="intake",
            short_name="with_food",
            label="With food",
            description="Fixture.",
            applies_when="Fixture.",
        ),
        "activity:workout": SchedulingPolicy(
            id="activity:workout",
            namespace="activity",
            short_name="workout",
            label="Workout",
            description="Fixture.",
            applies_when="Fixture.",
        ),
    }

    labels = readable_traits(
        {
            "activity:workout",
            "context:review",
            "intake:with_food",
            "is:mineral",
            "pathway:methylation",
            "risk:manual_review",
            "timing:wake",
            "unknown:raw",
        },
        policies,
    )

    assert labels == ["unknown:raw", "With food", "Workout"]
