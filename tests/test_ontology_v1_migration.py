"""Static acceptance checks for the complete v1 data cutover."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml
from scripts.ontology_inventory import DEFAULT_BASELINE, account

ROOT = Path(__file__).resolve().parent.parent


def test_all_substance_knowledge_is_canonical() -> None:
    allowed = {"kind", "role", "quality", "effect", "risk", "pathway", "context"}
    for path in (ROOT / "data/substances").glob("*.yaml"):
        card = cast(object, yaml.safe_load(path.read_text(encoding="utf-8")))
        assert isinstance(card, dict), path
        card_mapping = cast(dict[str, object], card)
        knowledge = card_mapping.get("knowledge", {})
        assert isinstance(knowledge, dict), path
        assert set(cast(dict[str, object], knowledge)) <= allowed, path


def test_relations_use_only_typed_selectors() -> None:
    loaded = cast(object, yaml.safe_load((ROOT / "data/relations.yaml").read_text(encoding="utf-8")))
    assert isinstance(loaded, dict)
    relations = cast(dict[str, object], loaded).get("relations")
    assert isinstance(relations, list)
    relation_records = [cast(dict[str, object], item) for item in relations if isinstance(item, dict)]
    assert len(relation_records) == 36
    mineral_relation = next(item for item in relation_records if item["id"] == "rel_competes_007")
    assert mineral_relation["source_selector"] == {"category": "kind", "term": "mineral"}
    assert mineral_relation["target_selector"] == {"category": "quality", "term": "fat_soluble"}
    for relation in relation_records:
        legacy_endpoint_keys = {key for key in relation if key.startswith(("source_", "target_"))}
        assert legacy_endpoint_keys <= {"source_selector", "target_selector"}, relation["id"]


def test_migration_accounting_has_no_unexplained_identity_or_edge_loss() -> None:
    report = account(DEFAULT_BASELINE)
    assert report["status"] == "ok"
    assert report["substances"] == 253
    assert report["products"] == 59
    assert report["relations"] == 36
