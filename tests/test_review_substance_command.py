from __future__ import annotations

from pathlib import Path
from typing import TypedDict, cast

import yaml
from planner.engine import cmd_review, cmd_review_substance

from tests.helpers import run_planner
from tests.planner_fixture import PlannerFixtureInput, find_card_path_by_id, write_minimal_planner_fixture


class _RelationEntry(TypedDict, total=False):
    source_name: str
    source_substance: str
    source_trait: str
    target_name: str
    target_substance: str
    target_trait: str
    reason: str
    severity: str
    action: str


Relations = dict[str, list[dict[str, object]]]


def _write_review_substance_fixture(tmp_path: Path) -> Path:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={
                "prd_citrulline": {"stack": "training"},
                "prd_bsix000001": {"stack": "daily"},
                "prd_levodopa01": {"stack": "inactive"},
                "prd_creatine01": {"stack": "training"},
            },
            products={
                "prd_citrulline": [("sub_citrulline", ["intake:empty_preferred", "effect:nitric_oxide_support"])],
                "prd_bsix000001": [("sub_bsix000001", ["timing:energy_like"])],
                "prd_levodopa01": [("sub_levodopa01", ["timing:energy_like"])],
                "prd_creatine01": [("sub_creatine01", ["activity:any_workout"])],
            },
            traits={
                "intake:empty_preferred": {
                    "label": "Prefers empty stomach",
                    "description": "Works or absorbs better away from food",
                    "applies_when": "Use for amino acids",
                    "effects": [
                        {"match": {"food": False}, "level": "prefer_strong"},
                        {"match": {"food": True}, "level": "avoid"},
                    ],
                    "warning": True,
                },
                "effect:nitric_oxide_support": {
                    "label": "Nitric Oxide Support",
                    "description": "Fixture nitric oxide effect.",
                    "applies_when": "Fixture only.",
                },
                "timing:energy_like": {
                    "label": "Energy-like",
                    "description": "Fixture energy-like timing.",
                    "applies_when": "Fixture only.",
                },
                "activity:any_workout": {
                    "label": "Workout",
                    "description": "Fixture workout activity.",
                    "applies_when": "Fixture only.",
                },
            },
        ),
    )
    data_dir = tmp_path / "data"

    citrulline_path = find_card_path_by_id(data_dir / "substances", "sub_citrulline")
    citrulline = cast(dict[str, object], yaml.safe_load(citrulline_path.read_text()))
    citrulline["name"] = "L-Citrulline"
    citrulline["form"] = "malate"
    citrulline["concerns"] = [{"kind": "model_gap", "text": "Fixture review concern."}]
    citrulline_path.write_text(yaml.safe_dump(citrulline, sort_keys=False))

    bsix_path = find_card_path_by_id(data_dir / "substances", "sub_bsix000001")
    bsix = cast(dict[str, object], yaml.safe_load(bsix_path.read_text()))
    bsix["name"] = "Vitamin B6"
    bsix["form"] = "pyridoxine HCl"
    bsix_path.write_text(yaml.safe_dump(bsix, sort_keys=False))

    levodopa_path = find_card_path_by_id(data_dir / "substances", "sub_levodopa01")
    levodopa = cast(dict[str, object], yaml.safe_load(levodopa_path.read_text()))
    levodopa["name"] = "Levodopa"
    levodopa_path.write_text(yaml.safe_dump(levodopa, sort_keys=False))

    creatine_path = find_card_path_by_id(data_dir / "substances", "sub_creatine01")
    creatine = cast(dict[str, object], yaml.safe_load(creatine_path.read_text()))
    creatine["name"] = "Creatine"
    creatine_path.write_text(yaml.safe_dump(creatine, sort_keys=False))

    relations: Relations = {
        "relations": [
            {
                "id": "rel_fixture_central",
                "relation_type": "supports",
                "assertion_kind": "ontology_assertion",
                "semantic_family": "biochemical_mechanism_assertion",
                "source_selector": {"entity": {"entity_id": "sub_bsix000001"}},
                "target_selector": {"entity": {"name": "Levodopa"}},
                "reason": "Fixture central relation.",
            }
        ]
    }
    (data_dir / "relations.yaml").write_text(yaml.safe_dump(relations, sort_keys=False))
    return data_dir


def test_review_substance_prints_grouped_trait_checklist(tmp_path: Path) -> None:
    temp_data = _write_review_substance_fixture(tmp_path)
    substance_path = find_card_path_by_id(temp_data / "substances", "sub_citrulline")

    result = cmd_review_substance(str(substance_path), data_root=tmp_path)

    assert result.exit_code == 0, result.output + result.stderr
    assert "Substance review: L-Citrulline (malate)" in result.output
    assert "\nintake\n" in result.output
    assert "  [x] empty_preferred - Prefers empty stomach" in result.output
    assert "Works or absorbs better away from food, without a hard food block." in result.output
    assert "Slot effects: prefer when food=False; avoid when food=True" in result.output
    assert "Output: schedule warning" in result.output
    assert "Concerns" in result.output


def test_review_substance_prints_central_relation_matches(tmp_path: Path) -> None:
    temp_data = _write_review_substance_fixture(tmp_path)
    relation_document = cast(dict[str, object], yaml.safe_load((temp_data / "relations.yaml").read_text()))
    relations = cast(Relations, relation_document)
    assertion = cast(dict[str, object], cast(list[object], relation_document["relations"])[0])
    assert assertion["assertion_kind"] == "ontology_assertion"
    assert assertion["semantic_family"] == "biochemical_mechanism_assertion"
    substance_path = find_card_path_by_id(temp_data / "substances", "sub_bsix000001")

    result = cmd_review_substance(str(substance_path), data_root=tmp_path)

    assert result.exit_code == 0, result.output + result.stderr
    assert "Central relations from data/relations.yaml (read-only)" in result.output
    assert "Edit these in data/relations.yaml, not in this substance card." in result.output
    assert "Matches this substance by id: sub_bsix000001" in result.output
    assert "Matches this substance by exact name: Vitamin B6" in result.output
    assert "supports" in result.output
    assert "Vitamin B6 (pyridoxine HCl) -> Levodopa" in result.output
    assert "matched by: source selector" in result.output

    relations["relations"].append({
        "id": "rel_fixture_review",
        "relation_type": "review_with",
        "assertion_kind": "clinical_review_signal",
        "semantic_family": "clinical_review_signal",
        "source_selector": {"entity": {"entity_id": "sub_bsix000001"}},
        "target_selector": {"entity": {"name": "Levodopa"}},
        "reason": "Synthetic review fixture.",
    })
    relations_path = temp_data / "relations.yaml"
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))
    compact_result = cmd_review_substance(str(substance_path), data_root=tmp_path, compact=True)

    assert compact_result.exit_code == 0, compact_result.output + compact_result.stderr
    assert "review_with" in compact_result.output
    assert "Vitamin B6 (pyridoxine HCl) -> Levodopa" in compact_result.output
    assert "matched by: source selector" in compact_result.output


def test_review_surfaces_share_authored_relation_order(tmp_path: Path) -> None:
    temp_data = _write_review_substance_fixture(tmp_path)
    substance_path = find_card_path_by_id(temp_data / "substances", "sub_citrulline")
    relations = {
        "relations": [
            {
                "id": "rel_fixture_balance",
                "relation_type": "balance",
                "assertion_kind": "ontology_assertion",
                "semantic_family": "biochemical_mechanism_assertion",
                "source_selector": {"entity": {"entity_id": "sub_citrulline"}},
                "target_selector": {"entity": {"entity_id": "sub_creatine01"}},
                "reason": "Fixture balance relation.",
            },
            {
                "id": "rel_fixture_supports",
                "relation_type": "supports",
                "assertion_kind": "ontology_assertion",
                "semantic_family": "biochemical_mechanism_assertion",
                "source_selector": {"entity": {"entity_id": "sub_citrulline"}},
                "target_selector": {"entity": {"entity_id": "sub_bsix000001"}},
                "reason": "Fixture support relation.",
            },
            {
                "id": "rel_fixture_review_with",
                "relation_type": "review_with",
                "assertion_kind": "clinical_review_signal",
                "semantic_family": "clinical_review_signal",
                "source_selector": {"entity": {"entity_id": "sub_citrulline"}},
                "target_selector": {"entity": {"entity_id": "sub_levodopa01"}},
                "reason": "Fixture review relation.",
            },
        ]
    }
    (temp_data / "relations.yaml").write_text(yaml.safe_dump(relations, sort_keys=False))

    full_review = cmd_review(data_root=tmp_path)
    substance_review = cmd_review_substance(str(substance_path), data_root=tmp_path)

    assert full_review.exit_code == 0, full_review.stderr
    assert substance_review.exit_code == 0, substance_review.stderr
    full_positions = [
        full_review.output.index(f"[{label}]")
        for label in ("Balance pairing", "Support relationship", "Review together")
    ]
    substance_positions = [substance_review.output.index(name) for name in ("balance", "supports", "review_with")]
    assert full_positions == sorted(full_positions)
    assert substance_positions == sorted(substance_positions)


def test_review_substance_fails_closed_on_unknown_relation_entity(tmp_path: Path) -> None:
    temp_data = _write_review_substance_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relation = cast(dict[str, object], cast(list[object], relations["relations"])[0])
    relation["source_selector"] = {"entity": {"entity_id": "sub_missing000"}}
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))
    substance_path = find_card_path_by_id(temp_data / "substances", "sub_bsix000001")

    result = cmd_review_substance(str(substance_path), data_root=tmp_path)

    assert result.exit_code == 1
    assert "no matching substance card" in result.stderr


def test_review_substance_prints_trait_relation_matches(tmp_path: Path) -> None:
    temp_data = _write_review_substance_fixture(tmp_path)
    relations_path = temp_data / "relations.yaml"
    relations = cast(Relations, yaml.safe_load(relations_path.read_text()))
    relations["relations"].append({
        "id": "rel_fixture_effect",
        "relation_type": "supports",
        "assertion_kind": "ontology_assertion",
        "semantic_family": "biochemical_mechanism_assertion",
        "source_selector": {"entity": {"name": "Creatine"}},
        "target_selector": {"category": "effect", "term": "nitric_oxide_support"},
        "reason": "Fixture trait endpoint relation.",
    })
    relations_path.write_text(yaml.safe_dump(relations, sort_keys=False))
    substance_path = find_card_path_by_id(temp_data / "substances", "sub_citrulline")

    result = cmd_review_substance(str(substance_path), data_root=tmp_path)

    assert result.exit_code == 0, result.output + result.stderr
    assert "Central relations from data/relations.yaml (read-only)" in result.output
    assert "Creatine -> Nitric Oxide Support" in result.output
    assert "matched by: target selector" in result.output


def test_cli_review_substance_prints_result_output(tmp_path: Path) -> None:
    temp_data = _write_review_substance_fixture(tmp_path)
    substance_path = find_card_path_by_id(temp_data / "substances", "sub_bsix000001")

    result = run_planner("review-substance", str(substance_path), root=tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Substance review: Vitamin B6 (pyridoxine HCl)" in result.stdout
    assert "Central relations from data/relations.yaml (read-only)" in result.stdout


def test_cli_review_substance_compact_prints_current_traits_only(tmp_path: Path) -> None:
    temp_data = _write_review_substance_fixture(tmp_path)
    substance_path = find_card_path_by_id(temp_data / "substances", "sub_bsix000001")

    result = run_planner("review-substance", str(substance_path), "--compact", root=tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Current traits" in result.stdout
    assert "Concerns" in result.stdout
    assert "Before editing traits" not in result.stdout
    assert "  [ ]" not in result.stdout


def test_review_substance_rejects_missing_file(tmp_path: Path) -> None:
    _write_review_substance_fixture(tmp_path)
    nonexistent = tmp_path / "data" / "substances" / "probe__sub_0000000099.yaml"

    result = run_planner("review-substance", str(nonexistent), root=tmp_path)

    assert result.returncode == 1
    assert "file not found" in result.stderr


def test_review_substance_rejects_path_outside_substances_dir(tmp_path: Path) -> None:
    temp_data = _write_review_substance_fixture(tmp_path)
    product_path = next((temp_data / "products").glob("*.yaml"))

    result = run_planner("review-substance", str(product_path), root=tmp_path)

    assert result.returncode == 1
    assert "review-substance only accepts paths inside" in result.stderr


def test_review_substance_rejects_non_yaml_suffix(tmp_path: Path) -> None:
    temp_data = _write_review_substance_fixture(tmp_path)
    probe = temp_data / "substances" / "probe__sub_0000000099.txt"
    probe.write_text("name: Probe\ntraits: []\n")

    result = run_planner("review-substance", str(probe), root=tmp_path)

    assert result.returncode == 1
    assert "review-substance only accepts .yaml files" in result.stderr


def test_review_substance_uses_ontology_bundle_without_traits_directory(tmp_path: Path) -> None:
    temp_data = _write_review_substance_fixture(tmp_path)
    substance_path = next((temp_data / "substances").glob("*.yaml"))

    result = run_planner("review-substance", str(substance_path), root=tmp_path)

    assert result.returncode == 0, result.stderr
