"""Bundle-scoped reuse for immutable ontology presentation decoders."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import cast

import pytest
from planner.ontology.artifacts import load_ontology
from planner.ontology.presentation import (
    load_category_predicates,
    load_ontoclean_profiles,
    load_review_presentation,
    load_term_catalog,
)
from planner.ontology.substance_fields import canonical_terms_by_predicate

from tests.helpers import ontology_bundle

ROOT = Path(__file__).resolve().parents[1]


def test_verified_bundle_reuses_immutable_presentation_decoders() -> None:
    bundle = ontology_bundle()

    decoders = (
        load_category_predicates,
        load_ontoclean_profiles,
        load_term_catalog,
        load_review_presentation,
        canonical_terms_by_predicate,
    )
    for decoder in decoders:
        assert decoder(bundle) is decoder(bundle)

    with pytest.raises(TypeError):
        cast(dict[str, tuple[str, ...]], load_category_predicates(bundle))["kind"] = ()
    with pytest.raises(TypeError):
        cast(dict[str, object], load_term_catalog(bundle)[0])["slug"] = "mutated"


def test_distinct_bundles_do_not_share_presentation_cache_entries() -> None:
    first = ontology_bundle()
    second = load_ontology(ROOT / "ontology")

    assert first is not second
    assert load_category_predicates(first) == load_category_predicates(second)
    assert load_category_predicates(first) is not load_category_predicates(second)
    assert load_term_catalog(first) == load_term_catalog(second)
    assert load_term_catalog(first) is not load_term_catalog(second)


def test_unverified_bundle_is_not_memoized() -> None:
    copied = copy.copy(ontology_bundle())

    assert load_category_predicates(copied) is not load_category_predicates(copied)
    assert load_term_catalog(copied) is not load_term_catalog(copied)
