"""Direct loader contracts for malformed cards and canonical references."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from planner.cards import relations as relation_cards
from planner.cards.dashboards import build_dashboard_review, load_dashboard
from planner.cards.relations import load_global_relations
from planner.cards.substance import load_substance
from planner.contracts import CardLoadError, Substance
from planner.ontology.selector import load_relation_type_contracts
from planner.paths import Paths
from planner.query_model.loaders import dashboards_for_read_model
from planner.query_model.surreal_records import dashboard_record

from tests.helpers import ontology_bundle


@pytest.mark.parametrize(
    ("selectors", "message"),
    [
        (None, "selectors"),
        ({"category": "context", "term": "foo"}, "selectors"),
        (["not a selector"], r"selectors\[0\]"),
        ([{"category": "context"}], r"selectors\[0\]"),
    ],
)
def test_dashboard_loader_rejects_missing_non_list_and_invalid_selectors(
    tmp_path: Path, selectors: object, message: str
) -> None:
    card = {
        "id": "dash_invalid",
        "name": "Invalid dashboard",
        "description": "invalid",
        "selectors": selectors,
    }
    if selectors is None:
        del card["selectors"]
    path = tmp_path / "dashboard.yaml"
    path.write_text(yaml.safe_dump(card), encoding="utf-8")

    with pytest.raises(CardLoadError, match=message):
        load_dashboard(path, ontology_bundle())


def test_dashboard_loader_preserves_canonical_identity_and_declared_context(tmp_path: Path) -> None:
    path = tmp_path / "identity_probe.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "id": "identity_probe",
                "name": "Identity probe",
                "description": "dashboard identity/context preservation",
                "benefit": {"description": "benefit"},
                "selectors": [{"category": "context", "term": "vascular_health"}],
                "declares_context": ["vascular_health"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    dashboard = load_dashboard(path, ontology_bundle())

    assert dashboard.id == "identity_probe"
    assert dashboard.declares_context == ("vascular_health",)
    record = dashboard_record(dashboard, ontology_bundle())
    assert record["id"] == "identity_probe"
    assert "slug" not in record
    assert record["declares_context"] == ["vascular_health"]
    assert record["declares_context_labels"] == ["Vascular Health"]


def test_dashboard_rename_preserves_authored_identity_and_behavior(tmp_path: Path) -> None:
    path = tmp_path / "identity_probe.yaml"
    renamed_path = tmp_path / "renamed_dashboard_source.yaml"
    card = {
        "id": "stable_dashboard_id",
        "name": "Identity probe",
        "description": "dashboard identity is path-independent",
        "benefit": {"description": "benefit"},
        "selectors": [{"category": "context", "term": "vascular_health"}],
    }
    path.write_text(
        yaml.safe_dump(card, sort_keys=False),
        encoding="utf-8",
    )
    before = load_dashboard(path, ontology_bundle())
    before_review = build_dashboard_review(
        dashboard_files=[path],
        products={},
        stack_entries={},
        substances={},
        bundle=ontology_bundle(),
    )
    path.rename(renamed_path)
    after = load_dashboard(renamed_path, ontology_bundle())
    after_review = build_dashboard_review(
        dashboard_files=[renamed_path],
        products={},
        stack_entries={},
        substances={},
        bundle=ontology_bundle(),
    )

    assert before == after
    assert after.id == "stable_dashboard_id"
    assert after.source_path == renamed_path
    assert before_review == after_review


def test_dashboard_registry_rejects_duplicate_authored_ids(tmp_path: Path) -> None:
    dashboards_dir = tmp_path / "data" / "dashboards"
    dashboards_dir.mkdir(parents=True)
    card = {
        "id": "stable_dashboard_id",
        "name": "Duplicate probe",
        "description": "duplicate authored id",
        "benefit": {"description": "duplicate authored id"},
        "selectors": [{"category": "context", "term": "vascular_health"}],
    }
    for filename in ("first_source.yaml", "renamed_source.yaml"):
        (dashboards_dir / filename).write_text(yaml.safe_dump(card, sort_keys=False), encoding="utf-8")

    with pytest.raises(CardLoadError, match="duplicate dashboard id"):
        dashboards_for_read_model(Paths.from_root(tmp_path), ontology_bundle())


def test_dashboard_loader_rejects_unknown_declared_context(tmp_path: Path) -> None:
    path = tmp_path / "identity_probe.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "id": "identity_probe",
                "name": "Identity probe",
                "description": "dashboard context mismatch",
                "benefit": {"description": "benefit"},
                "selectors": [{"category": "context", "term": "vascular_health"}],
                "declares_context": ["unknown_context"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(CardLoadError, match=r"declares_context\[0\].*canonical ontology vocabulary"):
        load_dashboard(path, ontology_bundle())


@pytest.mark.parametrize("document", [[], {"other": []}])
def test_relation_loader_rejects_malformed_top_level(tmp_path: Path, document: object) -> None:
    path = tmp_path / "data" / "relations.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(CardLoadError, match=r"top-level|missing required"):
        load_global_relations(Paths.from_root(tmp_path), ontology_bundle(), {})


def test_relation_loader_rejects_non_list_and_invalid_selector_entry(tmp_path: Path) -> None:
    path = tmp_path / "data" / "relations.yaml"
    path.parent.mkdir()
    relation_type = next(iter(ontology_bundle().runtime_vocabulary["relation_types"]))
    path.write_text(
        yaml.safe_dump({
            "relations": [
                {
                    "id": "rel_invalid",
                    "relation_type": relation_type,
                    "source_selector": {"category": "context"},
                    "target_selector": {"category": "context", "term": "foo"},
                    "reason": "invalid selector",
                }
            ]
        }),
        encoding="utf-8",
    )

    with pytest.raises(CardLoadError, match=r"relations\[0\].source_selector"):
        load_global_relations(Paths.from_root(tmp_path), ontology_bundle(), {})

    path.write_text(yaml.safe_dump({"relations": {"not": "a list"}}), encoding="utf-8")
    with pytest.raises(CardLoadError, match="relations must be a list"):
        load_global_relations(Paths.from_root(tmp_path), ontology_bundle(), {})


@pytest.mark.parametrize("side", ["source", "target"])
def test_relation_loader_enforces_per_side_selector_forms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, side: str) -> None:
    bundle = ontology_bundle()
    contracts = dict(load_relation_type_contracts(bundle))
    supports = contracts["supports"]
    contracts["supports"] = replace(
        supports,
        source_selector_forms=frozenset({"term"}) if side == "source" else supports.source_selector_forms,
        target_selector_forms=frozenset({"term"}) if side == "target" else supports.target_selector_forms,
    )
    monkeypatch.setattr(relation_cards, "load_relation_type_contracts", lambda _bundle: contracts)
    path = tmp_path / "data" / "relations.yaml"
    path.parent.mkdir()
    path.write_text(
        yaml.safe_dump(
            {
                "relations": [
                    {
                        "id": "rel_selector_form_probe",
                        "relation_type": "supports",
                        "assertion_kind": "ontology_assertion",
                        "semantic_family": "test",
                        "source_selector": {"entity": {"name": "Known"}},
                        "target_selector": (
                            {"category": "context", "term": "vascular_health"}
                            if side == "source"
                            else {"entity": {"name": "Known"}}
                        ),
                        "reason": "selector form probe",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(CardLoadError, match="uses selector form 'entity'"):
        load_global_relations(Paths.from_root(tmp_path), bundle, {"sub_known000": Substance("sub_known000", "Known")})


def test_relation_loader_rejects_reversed_directionless_duplicate(tmp_path: Path) -> None:
    path = tmp_path / "data" / "relations.yaml"
    path.parent.mkdir()
    common = {
        "relation_type": "review_with",
        "assertion_kind": "clinical_review_signal",
        "semantic_family": "test",
        "reason": "direction probe",
    }
    path.write_text(
        yaml.safe_dump(
            {
                "relations": [
                    {
                        **common,
                        "id": "rel_direction_probe_a",
                        "source_selector": {"entity": {"name": "Known"}},
                        "target_selector": {"entity": {"name": "Other"}},
                    },
                    {
                        **common,
                        "id": "rel_direction_probe_b",
                        "source_selector": {"entity": {"name": "Other"}},
                        "target_selector": {"entity": {"name": "Known"}},
                    },
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    substances = {
        "sub_known000": Substance("sub_known000", "Known"),
        "sub_other000": Substance("sub_other000", "Other"),
    }
    with pytest.raises(CardLoadError, match="non-directional relation type 'review_with'"):
        load_global_relations(Paths.from_root(tmp_path), ontology_bundle(), substances)


@pytest.mark.parametrize(
    ("selector", "message"),
    [
        (
            {"entity": {"entity_id": "sub_missing000"}},
            "no matching substance card",
        ),
        (
            {"entity": {"name": "Missing substance"}},
            "no matching substance name",
        ),
        (
            {"category": "context", "term": "mineral"},
            "not in canonical ontology vocabulary",
        ),
    ],
)
def test_relation_loader_rejects_unresolved_selector_references(
    tmp_path: Path,
    selector: dict[str, object],
    message: str,
) -> None:
    path = tmp_path / "data" / "relations.yaml"
    path.parent.mkdir()
    path.write_text(
        yaml.safe_dump(
            {
                "relations": [
                    {
                        "id": "rel_unresolved_selector",
                        "relation_type": "supports",
                        "assertion_kind": "ontology_assertion",
                        "semantic_family": "test",
                        "source_selector": selector,
                        "target_selector": {"entity": {"entity_id": "sub_known000"}},
                        "reason": "unresolved selector must not be omitted",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    substances = {"sub_known000": Substance(id="sub_known000", name="Known substance")}
    with pytest.raises(CardLoadError, match=message):
        load_global_relations(Paths.from_root(tmp_path), ontology_bundle(), substances)


@pytest.mark.parametrize(
    ("section", "field", "predicate"),
    [
        ("knowledge", "effect", "knowledge.effect"),
        ("schedule", "intake", "schedule.intake"),
    ],
)
def test_substance_loader_rejects_unknown_canonical_terms(
    tmp_path: Path, section: str, field: str, predicate: str
) -> None:
    path = tmp_path / "probe.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "id": "sub_zz0000zzzz",
                "name": "Unknown term probe",
                section: {field: ["not_a_registered_term"]},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        CardLoadError, match=rf"term '{predicate}:not_a_registered_term'.*canonical ontology vocabulary"
    ):
        load_substance(path, ontology_bundle())


def test_substance_loader_accepts_known_and_registered_unused_terms(tmp_path: Path) -> None:
    path = tmp_path / "probe.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "id": "sub_zz0000zzzz",
                "name": "Known term probe",
                "knowledge": {"kind": ["mineral"]},
                # Authored in the registry but intentionally unused by the
                # repository's current substance cards.
                "schedule": {"intake": ["fat_meal_required"]},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    substance = load_substance(path, ontology_bundle())

    assert substance.knowledge_assertions[0].category == "kind"
    assert substance.knowledge_assertions[0].value == "mineral"
    assert substance.schedule_assertions[0].axis == "intake"
    assert substance.schedule_assertions[0].value == "fat_meal_required"
