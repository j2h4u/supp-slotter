from planner.cards._common import connected_components, similarity_score
from planner.cards.substance_similarity import (
    _is_expected_form_variant_pair,
    collect_similar_substances,
    substance_similarity_terms,
)
from planner.contracts import Substance


def _substance(identifier: str, name: str, *, form: str | None = None, aliases: tuple[str, ...] = ()) -> Substance:
    return Substance(id=identifier, name=name, form=form, aliases=aliases)


def test_similarity_score_prioritizes_primary_exact_matches_and_ignores_alias_only_matches() -> None:
    assert similarity_score([("x", True)], [("y", True)]) == 0.0
    assert similarity_score([("magnesium", False)], [("magnesium", False)]) == 0.0
    assert similarity_score([("magnesium", True)], [("magnesium", False)]) == 1.0
    assert similarity_score([("magnesium glycinate", True)], [("magnesium glycine", True)]) > 0.86


def test_connected_components_drops_singletons_and_returns_stable_members() -> None:
    assert connected_components({"z": {"y"}, "y": {"z", "x"}, "x": {"y"}, "solo": set()}) == [["x", "y", "z"]]


def test_similarity_terms_normalize_form_and_deduplicate_repeated_aliases() -> None:
    substance = _substance("sub_a", "Vitamin C", form="Ascorbic-acid", aliases=("Vit C", "vit c", ""))

    assert substance_similarity_terms(substance) == [
        ("vitamin c ascorbic acid", True),
        ("vit c", False),
    ]


def test_collect_similar_substances_clusters_duplicate_names_but_keeps_expected_forms_separate() -> None:
    substances = {
        "sub_a": _substance("sub_a", "Magnesium", aliases=("Mg",)),
        "sub_b": _substance("sub_b", "Magnesium", aliases=("Mg",)),
        "sub_c": _substance("sub_c", "Magnesium", form="citrate"),
        "sub_d": _substance("sub_d", "Magnesium", form="glycinate"),
    }

    clusters = collect_similar_substances(substances)

    assert len(clusters) == 1
    assert "sub_a Magnesium" in clusters[0]
    assert "sub_b Magnesium" in clusters[0]
    assert "sub_c Magnesium (citrate)" not in clusters[0]
    assert "sub_d Magnesium (glycinate)" not in clusters[0]


def test_expected_form_variant_detection_requires_two_forms_and_a_matching_base_name() -> None:
    citrate = _substance("sub_a", "Magnesium", form="citrate")
    glycinate = _substance("sub_b", "Magnesium", form="glycinate")
    near_name = _substance("sub_c", "Magnesiu", form="bisglycinate")
    unrelated = _substance("sub_e", "Iron", form="bisglycinate")

    assert _is_expected_form_variant_pair(citrate, glycinate)
    assert not _is_expected_form_variant_pair(citrate, _substance("sub_d", "Magnesium"))
    assert not _is_expected_form_variant_pair(citrate, near_name)
    assert _is_expected_form_variant_pair(citrate, unrelated)
