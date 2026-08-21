"""Regression tests for maintenance, io error handling, and auto-maintenance sentinel changes.

Covers:
  - C1: guarded stacks.yaml write in maintenance pipeline
  - EH9: vocal load_global_relations on non-mapping data
  - EH10: auto_maintenance_needed None vs False disambiguation
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import NotRequired, TypedDict, cast

import pytest
import yaml
from planner.contracts import CardLoadError
from planner.maintenance import (
    auto_maintenance_needed,
    run_auto_maintenance,
)
from planner.maintenance_atomic import EditPlan
from planner.maintenance_card_plan import plan_card_dir
from planner.maintenance_substance_resolution import (
    load_maintenance_contract,
    load_reference_resolution,
    rewrite_references,
)
from planner.ontology.errors import OntologyInfrastructureError
from planner.paths import Paths

from tests.helpers import ontology_bundle
from tests.planner_fixture import (
    PlannerFixtureInput,
    check_in_temp_dir,
    find_card_path_by_id,
    fixture_id,
    write_minimal_planner_fixture,
    write_yaml,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Schedule(TypedDict):
    prefer_with: list[str]


class _SubstanceCard(TypedDict):
    id: str
    name: str
    schedule: NotRequired[_Schedule]


class _ProductComponent(TypedDict):
    substance: str


class _ProductCard(TypedDict):
    id: str
    name: str
    components: list[_ProductComponent]


def _write_yaml(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def _minimal_substance(
    sub_id: str = "sub_abc1234567",
    name: str = "Magnesium Glycinate",
) -> dict[str, object]:
    return {"id": sub_id, "name": name, "traits": []}


def _minimal_product(
    prd_id: str = "prd_abc1234567",
    name: str = "Mag Glycinate 400",
    components: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "id": prd_id,
        "name": name,
        "components": components or [{"substance": "sub_abc1234567"}],
    }


def test_auto_maintenance_rewrites_nested_prefer_with_and_product_refs(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    substances_dir = data_dir / "substances"
    products_dir = data_dir / "products"
    substances_dir.mkdir(parents=True)
    products_dir.mkdir(parents=True)

    _write_yaml(
        substances_dir / "source.yaml",
        {"name": "Source", "schedule": {"prefer_with": ["friend"]}},
    )
    _write_yaml(substances_dir / "friend.yaml", {"name": "Friend"})
    _write_yaml(
        products_dir / "source_product.yaml",
        {"name": "Source Product", "components": [{"substance": "source"}]},
    )

    result = run_auto_maintenance(Paths.from_root(tmp_path), suppress_output=True, ontology=ontology_bundle())

    assert result == 0
    source_cards = list(substances_dir.glob("source__sub_*.yaml"))
    friend_cards = list(substances_dir.glob("friend__sub_*.yaml"))
    product_cards = list(products_dir.glob("unknown__source_product__prd_*.yaml"))
    assert len(source_cards) == 1
    assert len(friend_cards) == 1
    assert len(product_cards) == 1

    source = cast(_SubstanceCard, yaml.safe_load(source_cards[0].read_text()))
    friend = cast(_SubstanceCard, yaml.safe_load(friend_cards[0].read_text()))
    product = cast(_ProductCard, yaml.safe_load(product_cards[0].read_text()))

    assert "schedule" in source
    assert source["schedule"]["prefer_with"] == [friend["id"]]
    assert product["components"][0]["substance"] == source["id"]


def test_auto_maintenance_fails_closed_without_verified_bundle(tmp_path: Path) -> None:
    products_dir = tmp_path / "data" / "products"
    products_dir.mkdir(parents=True)
    product = products_dir / "draft.yaml"
    original: dict[str, object] = {"name": "Draft", "components": [{"substance": "source"}]}
    _write_yaml(product, original)

    assert run_auto_maintenance(Paths.from_root(tmp_path), suppress_output=True) == 1
    assert yaml.safe_load(product.read_text()) == original


def test_rewrite_reference_path_is_contract_driven() -> None:
    contract = load_maintenance_contract(ontology_bundle())
    resolution = replace(contract.product_substance, reference_path="ingredients[].substance")
    document: dict[str, object] = {"ingredients": [{"substance": "old"}]}

    assert rewrite_references(document, resolution, {"old": "new"})
    assert document == {"ingredients": [{"substance": "new"}]}


def test_plan_card_dir_adds_ids_and_plans_canonical_renames(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir()
    _write_yaml(cards_dir / "source.yaml", {"name": "Source"})
    _write_yaml(cards_dir / "friend.yaml", {"id": "sub_existing01", "name": "Friend"})
    plan = EditPlan()

    result = plan_card_dir(
        cards_dir,
        lambda card: f"{str(card['name']).lower()}__{card['id']}.yaml",
        "sub",
        plan,
    )

    assert result is not None
    renames, move_count = result
    assert renames["source"].startswith("sub_")
    assert move_count == 2
    assert len(plan.entries) == 2
    assert {entry.obsolete_path.name for entry in plan.entries if entry.obsolete_path} == {
        "friend.yaml",
        "source.yaml",
    }


def test_plan_card_dir_rejects_duplicate_canonical_destination(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir()
    _write_yaml(cards_dir / "one.yaml", {"id": "sub_one000001", "name": "Same"})
    _write_yaml(cards_dir / "two.yaml", {"id": "sub_two000001", "name": "Same"})

    result = plan_card_dir(cards_dir, lambda _card: "same.yaml", "sub", EditPlan())

    assert result is None


def test_check_resolves_product_component_name_to_substance_id(tmp_path: Path) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={"magnesium_product": {"product": "magnesium_product", "stack": "daily"}},
            products={"magnesium_product": [("magnesium_glycinate", [])]},
            traits={
                "kind:mineral": {
                    "label": "Mineral",
                    "description": "Fixture trait for validation.",
                    "applies_when": "Use only in tests.",
                },
            },
        ),
    )
    product_path = find_card_path_by_id(
        tmp_path / "data/products",
        fixture_id("prd", "magnesium_product"),
    )
    product = cast(_ProductCard, yaml.safe_load(product_path.read_text()))
    expected_substance_id = product["components"][0]["substance"]
    product["components"][0]["substance"] = "Magnesium Glycinate"
    write_yaml(product_path, product)

    result = check_in_temp_dir(tmp_path)

    assert result.exit_code == 0, "\n".join(result.errors)
    rewritten = cast(_ProductCard, yaml.safe_load(product_path.read_text()))
    assert rewritten["components"][0]["substance"] == expected_substance_id


def test_auto_maintenance_resolves_component_alias_to_substance_id(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    substances_dir = data_dir / "substances"
    products_dir = data_dir / "products"
    substances_dir.mkdir(parents=True)
    products_dir.mkdir(parents=True)

    _write_yaml(
        substances_dir / "pyridoxal_5_phosphate__sub_abc1234567.yaml",
        {
            "id": "sub_abc1234567",
            "name": "Vitamin B6",
            "form": "pyridoxal 5-phosphate",
            "aliases": ["P5P"],
        },
    )
    _write_yaml(
        products_dir / "b6_product.yaml",
        {
            "id": "prd_abc1234567",
            "name": "B6 Product",
            "components": [{"substance": "P5P"}],
        },
    )

    result = run_auto_maintenance(Paths.from_root(tmp_path), suppress_output=True, ontology=ontology_bundle())

    assert result == 0
    product_cards = list(products_dir.glob("unknown__b6_product__prd_abc1234567.yaml"))
    assert len(product_cards) == 1
    product = cast(_ProductCard, yaml.safe_load(product_cards[0].read_text()))
    assert product["components"][0]["substance"] == "sub_abc1234567"


def test_auto_maintenance_rejects_ambiguous_component_name(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    substances_dir = data_dir / "substances"
    products_dir = data_dir / "products"
    substances_dir.mkdir(parents=True)
    products_dir.mkdir(parents=True)
    errors: list[str] = []

    _write_yaml(
        substances_dir / "magnesium_glycinate__sub_abc1234567.yaml",
        {"id": "sub_abc1234567", "name": "Magnesium", "form": "glycinate"},
    )
    _write_yaml(
        substances_dir / "magnesium_citrate__sub_def1234567.yaml",
        {"id": "sub_def1234567", "name": "Magnesium", "form": "citrate"},
    )
    _write_yaml(
        products_dir / "magnesium_product.yaml",
        {
            "id": "prd_abc1234567",
            "name": "Magnesium Product",
            "components": [{"substance": "Magnesium"}],
        },
    )

    result = run_auto_maintenance(
        Paths.from_root(tmp_path),
        suppress_output=True,
        collect_errors=errors,
        ontology=ontology_bundle(),
    )

    assert result == 1
    assert any("is ambiguous" in error for error in errors)
    assert any("sub_abc1234567 Magnesium (glycinate)" in error for error in errors)
    assert any("sub_def1234567 Magnesium (citrate)" in error for error in errors)


def test_auto_maintenance_rejects_unknown_component_name(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    substances_dir = data_dir / "substances"
    products_dir = data_dir / "products"
    substances_dir.mkdir(parents=True)
    products_dir.mkdir(parents=True)
    errors: list[str] = []

    _write_yaml(
        substances_dir / "magnesium_glycinate__sub_abc1234567.yaml",
        {"id": "sub_abc1234567", "name": "Magnesium", "form": "glycinate"},
    )
    _write_yaml(
        products_dir / "unknown_product.yaml",
        {
            "id": "prd_abc1234567",
            "name": "Unknown Product",
            "components": [{"substance": "Magnesium taurate"}],
        },
    )

    result = run_auto_maintenance(
        Paths.from_root(tmp_path),
        suppress_output=True,
        collect_errors=errors,
        ontology=ontology_bundle(),
    )

    assert result == 1
    assert any("could not be resolved" in error for error in errors)


# ---------------------------------------------------------------------------
# Task 2 — C1: guarded stacks.yaml write
# ---------------------------------------------------------------------------


def _build_rename_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create data/substances/, data/products/, data/stacks.yaml under tmp_path.

    The product references substance sub_old which gets renamed to sub_new,
    so the stacks-write branch is exercised.
    Returns (substances_dir, products_dir, stacks_path).
    """
    data_dir = tmp_path / "data"
    substances_dir = data_dir / "substances"
    substances_dir.mkdir(parents=True)
    products_dir = data_dir / "products"
    products_dir.mkdir(parents=True)

    # Substance card — no id so it gets one assigned and the old stem is tracked as rename
    sub_path = substances_dir / "magnesium_glycinate.yaml"
    _write_yaml(sub_path, {"name": "Magnesium Glycinate", "traits": []})

    # Product card — also no id
    prd_path = products_dir / "mag_glycinate_400.yaml"
    _write_yaml(prd_path, {"name": "Mag Glycinate 400", "components": [{"substance": "magnesium_glycinate"}]})

    stacks_path = data_dir / "stacks.yaml"
    _write_yaml(stacks_path, {"daily": ["mag_glycinate_400"], "training": []})

    return substances_dir, products_dir, stacks_path


def test_run_auto_maintenance_returns_1_when_stacks_write_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from planner.maintenance import run_auto_maintenance

    _build_rename_tree(tmp_path)

    # Make the data dir read-only so writing .tmp siblings inside it raises OSError.
    # Replacing a file depends on directory writability, not target-file writability.
    data_dir = tmp_path / "data"
    data_dir.chmod(0o555)

    try:
        result = run_auto_maintenance(Paths.from_root(tmp_path), ontology=ontology_bundle())
    finally:
        data_dir.chmod(0o755)

    assert result == 1
    captured = capsys.readouterr()
    assert "stacks.yaml" in captured.err


def test_run_auto_maintenance_rolls_back_on_partial_stage_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Partial staging failure leaves the data dir byte-identical and no .tmp orphans."""
    import planner.maintenance as _maint

    _build_rename_tree(tmp_path)

    # Snapshot original state: file paths + byte content
    data_dir = tmp_path / "data"
    snapshot: dict[Path, bytes] = {p: p.read_bytes() for p in data_dir.rglob("*") if p.is_file()}

    # Wrap EditPlan.stage so that the second write_text call inside it raises
    # OSError.  The first .tmp has already been written when the failure fires,
    # which proves that rollback (unlink of already-staged tmps) works correctly.
    original_stage = _maint.EditPlan.stage
    call_count: list[int] = [0]

    def _patched_stage(self: _maint.EditPlan) -> bool:
        orig_write = Path.write_text

        def _failing_write(
            path: Path,
            content: str,
            encoding: str | None = None,
            errors: str | None = None,
            newline: str | None = None,
        ) -> None:
            call_count[0] += 1
            if call_count[0] >= 2:
                raise OSError("injected write failure for atomicity test")
            orig_write(path, content, encoding=encoding, errors=errors, newline=newline)

        monkeypatch.setattr(Path, "write_text", _failing_write)
        result = original_stage(self)
        monkeypatch.setattr(Path, "write_text", orig_write)
        return result

    monkeypatch.setattr(_maint.EditPlan, "stage", _patched_stage)

    result = _maint.run_auto_maintenance(Paths.from_root(tmp_path), ontology=ontology_bundle())

    assert result == 1

    # Every original file must still exist with its original content
    for orig_path, orig_bytes in snapshot.items():
        assert orig_path.exists(), f"original file disappeared: {orig_path}"
        assert orig_path.read_bytes() == orig_bytes, f"original file was mutated: {orig_path}"

    # No orphan .tmp files anywhere under data/
    tmp_orphans = list(data_dir.rglob("*.tmp.*"))
    assert tmp_orphans == [], f"orphan .tmp files left behind: {tmp_orphans}"

    # Lock must be released
    assert not Paths.from_root(tmp_path).maintenance_lock.exists()


# ---------------------------------------------------------------------------
# Task 3 — EH9: load_global_relations ignores non-mapping top-level
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("document", [["a list at top level"], {"balance": []}])
def test_load_global_relations_rejects_malformed_document(tmp_path: Path, document: object) -> None:
    from planner.cards.relations import load_global_relations

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    rel_path = data_dir / "relations.yaml"
    _write_yaml(rel_path, document)
    paths = Paths.from_root(tmp_path)

    with pytest.raises(CardLoadError, match=r"top-level|missing required"):
        load_global_relations(paths, ontology_bundle(), {})


def test_load_global_relations_rejects_unknown_ontology_relation_type(
    tmp_path: Path,
) -> None:
    from planner.cards.relations import load_global_relations

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    rel_path = data_dir / "relations.yaml"
    relations_doc: dict[str, object] = {
        "relations": [
            {
                "id": "rel_unknown",
                "relation_type": "not_in_ontology",
                "source_selector": {"entity": {"entity_id": "sub_src"}},
                "target_selector": {"entity": {"entity_id": "sub_tgt"}},
                "reason": "unknown relation type should not be silently dropped",
            }
        ]
    }
    _write_yaml(rel_path, relations_doc)
    paths = Paths.from_root(tmp_path)

    with pytest.raises(CardLoadError, match="not in ontology relation_types"):
        load_global_relations(paths, ontology_bundle(), {})


# ---------------------------------------------------------------------------
# Task 4 — EH10: auto_maintenance_needed None vs False disambiguation
# ---------------------------------------------------------------------------


def test_auto_maintenance_needed_returns_none_on_card_load_error(
    tmp_path: Path,
) -> None:
    substances_dir = tmp_path / "data" / "substances"
    substances_dir.mkdir(parents=True)
    products_dir = tmp_path / "data" / "products"
    products_dir.mkdir(parents=True)

    # Malformed substance YAML so load_card_mapping raises CardLoadError
    broken = substances_dir / "broken.yaml"
    broken.write_text(":\n  - bad: [")

    from planner.maintenance_substance_resolution import load_maintenance_contract

    result = auto_maintenance_needed(Paths.from_root(tmp_path), contract=load_maintenance_contract(ontology_bundle()))

    assert result is None


def test_run_auto_maintenance_returns_1_without_acquiring_lock_on_load_error(
    tmp_path: Path,
) -> None:
    substances_dir = tmp_path / "data" / "substances"
    substances_dir.mkdir(parents=True)
    products_dir = tmp_path / "data" / "products"
    products_dir.mkdir(parents=True)

    broken = substances_dir / "broken.yaml"
    broken.write_text(":\n  - bad: [")

    paths = Paths.from_root(tmp_path)
    result = run_auto_maintenance(paths, suppress_output=True, ontology=ontology_bundle())

    assert result == 1
    assert not paths.maintenance_lock.exists()


def _metadata_bundle(
    *,
    collection_path: str,
    identity_pattern: str,
    target_class: str = "Entry",
    schema_artifact: str = "schema.json",
    label: str = "Entry",
) -> object:
    base = "https://example.test/"
    projection = {
        "repository_projection": {
            "sources": [
                {
                    "id": "containers",
                    "locator": {"kind": "flat_root", "path": "data/containers"},
                    "root_class": "Container",
                    "documents": {
                        "root_class": "Container",
                        "document_shape": "mapping",
                        "identity": {"source": "id", "predicate": base + "id"},
                        "instructions": [
                            {
                                "kind": "inlined-node",
                                "source": "members[]",
                                "predicate": base + "members",
                                "target": "Member",
                            },
                            {
                                "kind": "reference",
                                "source": "members[].entry",
                                "subject": "members[]",
                                "predicate": base + "entry",
                                "target": target_class,
                            },
                        ],
                    },
                },
                {
                    "id": "entries",
                    "locator": {"kind": "flat_root", "path": collection_path},
                    "root_class": target_class,
                    "documents": {
                        "root_class": target_class,
                        "document_shape": "mapping",
                        "identity": {"source": "id", "predicate": base + "id"},
                        "maintenance": {
                            "role": "target",
                            "label": label,
                            "schema_artifact": schema_artifact,
                        },
                        "instructions": [
                            {"kind": "slot", "source": "form", "predicate": base + "form"},
                            {"kind": "slot", "source": "id", "predicate": base + "id"},
                            {"kind": "alias", "source": "name", "predicate": base + "name"},
                            {"kind": "sequence", "source": "aliases[]", "predicate": base + "aliases"},
                        ],
                    },
                },
            ]
        }
    }
    schema = {
        "$defs": {
            f"{target_class}Card": {
                "properties": {
                    "aliases": {"type": ["array", "null"]},
                    "form": {"type": ["string", "null"]},
                    "id": {"pattern": identity_pattern, "type": "string"},
                    "name": {"type": "string"},
                }
            }
        }
    }
    schema["$ref"] = f"#/$defs/{target_class}Card"
    return SimpleNamespace(projection_map=projection, decoded={schema_artifact: schema})


def test_reference_resolution_rejects_unverified_bundle(tmp_path: Path) -> None:
    bundle = _metadata_bundle(collection_path="data/alternate_entries", identity_pattern=r"^ent_[0-9]{3}$")
    with pytest.raises(OntologyInfrastructureError, match="verified OntologyBundle"):
        load_reference_resolution(bundle)  # type: ignore[arg-type]


def test_reference_resolution_identity_pattern_requires_verified_bundle(tmp_path: Path) -> None:
    with pytest.raises(OntologyInfrastructureError, match="verified OntologyBundle"):
        load_reference_resolution(
            _metadata_bundle(collection_path="data/entries", identity_pattern=r"^item_[0-9]{3}$")  # type: ignore[arg-type]
        )


def test_reference_resolution_follows_renamed_projection_and_schema_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import planner.maintenance_substance_resolution as resolution_module

    monkeypatch.setattr(resolution_module, "_is_verified_bundle", lambda _bundle: True)
    bundle = _metadata_bundle(
        collection_path="data/renamed_entries",
        identity_pattern=r"^ren_[0-9]{3}$",
        target_class="RenamedEntry",
        schema_artifact="renamed.schema.json",
        label="Renamed entry",
    )

    resolution = load_reference_resolution(bundle)  # type: ignore[arg-type]

    assert resolution.target_entity_class == "RenamedEntry"
    assert resolution.entity_label == "Renamed entry"
    assert resolution.source_path == "data/renamed_entries"
    assert resolution.target_schema_artifact == "renamed.schema.json"
    assert resolution.identity_pattern.fullmatch("ren_123") is not None
    assert resolution.identity_pattern.fullmatch("ent_123") is None


def test_reference_resolution_fails_on_missing_or_ambiguous_projection_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import planner.maintenance_substance_resolution as resolution_module

    monkeypatch.setattr(resolution_module, "_is_verified_bundle", lambda _bundle: True)
    missing = _metadata_bundle(collection_path="data/entries", identity_pattern=r"^ent_[0-9]{3}$")
    missing_projection = cast(dict[str, object], missing.projection_map)
    repository = cast(dict[str, object], missing_projection["repository_projection"])
    missing_source = cast(dict[str, object], cast(list[object], repository["sources"])[1])
    cast(dict[str, object], missing_source["documents"]).pop("maintenance")
    with pytest.raises(OntologyInfrastructureError, match="maintenance metadata"):
        load_reference_resolution(missing)  # type: ignore[arg-type]

    ambiguous = _metadata_bundle(collection_path="data/entries", identity_pattern=r"^ent_[0-9]{3}$")
    ambiguous_projection = cast(dict[str, object], ambiguous.projection_map)
    ambiguous_repository = cast(dict[str, object], ambiguous_projection["repository_projection"])
    sources = cast(list[dict[str, object]], ambiguous_repository["sources"])
    duplicate = dict(sources[1])
    duplicate["id"] = "other_entries"
    duplicate["locator"] = {"kind": "flat_root", "path": "data/other_entries"}
    sources.append(duplicate)
    with pytest.raises(OntologyInfrastructureError, match="exactly one source"):
        load_reference_resolution(ambiguous)  # type: ignore[arg-type]
