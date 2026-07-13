"""The pre-cutover fixture must be bound to immutable Git, never this worktree."""

from __future__ import annotations

from scripts.ontology_inventory import DEFAULT_BASELINE, verify


def test_pre_cutover_baseline_has_immutable_git_provenance() -> None:
    verify(DEFAULT_BASELINE)
