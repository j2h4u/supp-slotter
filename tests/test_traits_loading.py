from __future__ import annotations

from pathlib import Path

from planner.contracts import SchedulingPolicy
from planner.ontology.policies import load_scheduling_policies, readable_policies


def _write_trait_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_load_scheduling_policies_uses_canonical_vocabulary_not_legacy_path(tmp_path: Path) -> None:
    """The historical traits directory is no longer a policy source of truth."""
    traits_dir = tmp_path / "traits"
    _write_trait_file(
        traits_dir / "risks.yaml",
        "risk:\n"
        "  manual_review:\n"
        "    label: Manual review\n"
        "    description: Fixture risk.\n"
        "    applies_when: Fixture only.\n",
    )

    policies = load_scheduling_policies(traits_dir)

    assert policies["risk:manual_review"].label == "Requires manual review"
    assert policies["risk:manual_review"].description != "Fixture risk."


def test_readable_policies_filters_internal_namespaces_and_uses_labels() -> None:
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

    labels = readable_policies(
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
