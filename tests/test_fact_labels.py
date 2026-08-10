"""Fail-closed ontology vocabulary checks for the active fact index."""

from __future__ import annotations

import copy

import pytest
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.query_model.facts import _FactLabels

from tests.helpers import ontology_bundle


def test_fact_labels_accept_complete_terms_catalog() -> None:
    labels = _FactLabels.from_bundle(ontology_bundle())

    assert labels.label("risk", "manual_review") == "Requires manual review"


def test_fact_labels_reject_copied_bundle_without_verification_provenance() -> None:
    with pytest.raises(OntologyInfrastructureError, match="verified OntologyBundle") as raised:
        _FactLabels.from_bundle(copy.copy(ontology_bundle()))
    assert raised.value.code == MALFORMED


@pytest.mark.parametrize("namespace,slug", [("unknown", "manual_review"), ("risk", "unknown")])
def test_fact_labels_reject_unknown_namespace_or_slug(namespace: str, slug: str) -> None:
    labels = _FactLabels.from_bundle(ontology_bundle())

    with pytest.raises(OntologyInfrastructureError, match="no authored label") as raised:
        labels.label(namespace, slug)
    assert raised.value.code == MALFORMED
