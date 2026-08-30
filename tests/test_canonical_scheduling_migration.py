"""Acceptance checks for the compact finite migration-provenance closure."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import scripts.generate_migration_ledger as migration_ledger
import yaml
from jsonschema import Draft202012Validator
from scripts.ontology_compiler import compile_ontology

ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "docs/migrations/legacy-atom-ledger.yaml"
LEGACY_FIELDS = frozenset({"schedule", "prefer_with", "scheduling_assessment"})


def _receipt() -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(LEDGER_PATH.read_text(encoding="utf-8")))


def test_compact_receipt_reconstructs_and_closes_every_original_atom() -> None:
    receipt = _receipt()
    assert receipt == migration_ledger.build_document(ROOT)
    assert receipt["receipt_format"] == "canonical-migration-provenance-closure-v1"
    assert receipt["acceptance"] == "complete"
    assert receipt["forensic_inputs"] == {
        "pre_deletion_commit": migration_ledger.PRE_DELETION_COMMIT,
        "original_ledger_blob": migration_ledger.ORIGINAL_LEDGER_BLOB,
        "original_ledger_source_head": "89b74a0dfe0959b96771a6a68a560f2388e418c6",
    }
    coverage = receipt["coverage"]
    assert coverage["original_atom_count"] == 2161
    assert coverage["original_sol_adjudication_count"] == 1786
    assert len(coverage["crosswalk_sha256"]) == len(coverage["classification_rules_sha256"]) == 64
    assert sum(coverage["final_disposition_counts"].values()) == 2161
    assert coverage["final_disposition_counts"].get("sol_adjudication", 0) == 0
    assert set(coverage["closed_exclusion_counts"]) == {
        "generated_action_not_canonical_evidence",
        "operational_presentation_prose",
        "stored_pair_answer",
        "superseded_runtime_mechanism",
    }
    assert coverage["final_disposition_counts"] == {
        "explicit_exclusion": 771,
        "retained_unchanged": 1129,
        "source_metadata": 255,
        "typed_fact": 6,
    }
    assert coverage["closed_exclusion_counts"]["generated_action_not_canonical_evidence"] == 27
    assert coverage["closed_exclusion_counts"]["stored_pair_answer"] == 1
    assert receipt["canonical_fact_links"]["count"] == 6
    assert receipt["source_metadata"]["count"] == 255
    assert receipt["source_metadata"]["assessment_url_occurrence_count"] == 255
    assert receipt["scheduling_disposition_link"]["format"] == "canonical-scheduling-migration-v1"
    assert receipt["scheduling_disposition_link"]["covered_original_atom_count"] == 383
    assert "atoms" not in receipt and "crosswalk" not in receipt


def test_card_deletion_has_no_collateral_semantic_change() -> None:
    for prefix in ("data/substances", "data/products"):
        paths = migration_ledger._git(
            ROOT, "ls-tree", "-r", "--name-only", migration_ledger.PRE_DELETION_COMMIT, "--", prefix
        )
        for relative_path in paths.splitlines():
            if not relative_path.endswith(".yaml"):
                continue
            source = migration_ledger._tree_document(ROOT, relative_path)
            current = yaml.safe_load((ROOT / relative_path).read_text(encoding="utf-8"))
            expected = copy.deepcopy(source)
            for field in LEGACY_FIELDS:
                expected.pop(field, None)
            assert current == expected, relative_path
            assert LEGACY_FIELDS.isdisjoint(current), relative_path


def test_generated_substance_schema_rejects_every_legacy_field() -> None:
    artifacts = compile_ontology(ROOT / "ontology")
    schema = cast(dict[str, Any], json.loads(artifacts[Path("card.schema.json")]))
    validator = Draft202012Validator(schema)
    base = {"id": "sub_zz0000zzzz", "name": "Migration probe"}
    for field, value in {
        "schedule": {"intake": ["food_preferred"]},
        "prefer_with": ["sub_aaaaaaaaaa"],
        "scheduling_assessment": {"intake": {"conclusion": "insufficient"}},
    }.items():
        assert list(validator.iter_errors({**base, field: value})), field


def test_no_runtime_consumer_reads_the_removed_card_fields() -> None:
    runtime_source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "planner").rglob("*.py"))
    assert "scheduling_assessment" not in runtime_source
    assert "prefer_with" not in runtime_source
