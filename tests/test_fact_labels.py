"""Fail-closed ontology vocabulary checks for the active fact index."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.query_model.facts import _FactLabels


def _bundle(terms: object) -> SimpleNamespace:
    return SimpleNamespace(
        root=Path("ontology"),
        runtime_vocabulary={} if terms is None else {"terms": terms},
    )


@pytest.mark.parametrize(
    ("terms", "message"),
    [
        (None, "terms catalog is missing"),
        ({}, "terms must be a list"),
        ([], "terms must not be empty"),
        ([{}], r"terms\[0\].semantic_category must be a non-empty string"),
        ([{"semantic_category": "risk", "slug": "manual_review", "label": ""}], r"terms\[0\].label"),
    ],
)
def test_fact_labels_reject_malformed_terms_catalog(terms: object, message: str) -> None:
    with pytest.raises(OntologyInfrastructureError, match=message) as raised:
        _FactLabels.from_bundle(_bundle(terms))
    assert raised.value.code == MALFORMED


def test_fact_labels_accept_complete_terms_catalog() -> None:
    labels = _FactLabels.from_bundle(
        _bundle([{"semantic_category": "risk", "slug": "manual_review", "label": "Manual review"}])
    )

    assert labels.label("risk", "manual_review") == "Manual review"
