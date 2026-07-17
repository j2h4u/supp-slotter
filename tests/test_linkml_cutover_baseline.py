"""Frozen-tree provenance and accounting for the LinkML cutover."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).parents[1]
BASELINE = ROOT / "tests/fixtures/linkml_cutover/wave_a_baseline.json"


def _git(*args: str, text: bool = False) -> bytes | str:
    result: object = cast(object, subprocess.check_output(["git", *args], cwd=ROOT, text=text))
    if text:
        if not isinstance(result, str):
            raise TypeError("git command did not return text")
    elif not isinstance(result, bytes):
        raise TypeError("git command did not return bytes")
    return result


def _frozen(path: str) -> bytes:
    result = _git("show", f"{_baseline_commit()}:{path}")
    if not isinstance(result, bytes):
        raise TypeError("frozen fixture was not returned as bytes")
    return result


def _git_text(*args: str) -> str:
    result = _git(*args, text=True)
    if not isinstance(result, str):
        raise TypeError("git command did not return text")
    return result


def _baseline() -> dict[str, object]:
    parsed: object = cast(object, json.loads(BASELINE.read_text(encoding="utf-8")))
    return _mapping(parsed, "baseline")


def _baseline_commit() -> str:
    origin = _mapping(_baseline().get("origin"), "origin")
    return _string(origin.get("commit"), "origin.commit")


def _mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError(f"{name} must be a string-keyed object")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, object):
            raise TypeError(f"{name} contains an invalid value")
        result[key] = item
    return result


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value


def _integer(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    return value


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
    return value


def _items(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list")
    items: list[object] = []
    for item in value:
        if not isinstance(item, object):
            raise TypeError(f"{name} contains an invalid value")
        items.append(item)
    return items


def _strings(value: object, name: str) -> list[str]:
    return [_string(item, f"{name}[{index}]") for index, item in enumerate(_items(value, name))]


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _yaml(path: str) -> dict[str, object]:
    value: object = cast(object, yaml.safe_load(_frozen(path)))
    return _mapping(value, path)


def _inventory() -> tuple[list[str], list[str], list[dict[str, object]], list[dict[str, str]]]:
    paths = _git_text("ls-tree", "-r", "--name-only", _baseline_commit(), "--", "data").splitlines()
    substances: list[str] = []
    products: list[str] = []
    edges: list[dict[str, object]] = []
    facts: list[dict[str, str]] = []
    for path in sorted(path for path in paths if path.endswith(".yaml")):
        card = _yaml(path)
        if path.startswith("data/substances/"):
            substance_id = _string(card.get("id"), f"{path}.id")
            substances.append(substance_id)
            knowledge = _mapping(card.get("knowledge", {}), f"{path}.knowledge")
            for category, values_object in sorted(knowledge.items()):
                values = _strings(values_object, f"{path}.knowledge.{category}")
                facts.extend({"subject": substance_id, "category": category, "value": value} for value in values)
        elif path.startswith("data/products/"):
            product_id = _string(card.get("id"), f"{path}.id")
            products.append(product_id)
            for index, component_object in enumerate(_items(card.get("components", []), f"{path}.components")):
                component = _mapping(component_object, f"{path}.components[{index}]")
                authority = _string(component.get("authority", "primary" if index == 0 else "secondary"), "authority")
                edges.append({
                    "product_id": product_id,
                    "index": index,
                    "substance_id": _string(component.get("substance"), "substance"),
                    "authority": authority,
                })
    return substances, products, edges, facts


def _score_rows(layout: dict[str, object], phase: str) -> list[dict[str, object]]:
    phase_data = _mapping(layout.get(phase), f"layout.{phase}")
    products = _mapping(phase_data.get("products"), f"layout.{phase}.products")
    return [
        {"product_id": product_id, **row}
        for product_id, product_object in sorted(products.items())
        for row in _score_rows_for_product(product_object, f"layout.{phase}.products.{product_id}")
    ]


def _score_rows_for_product(value: object, name: str) -> list[dict[str, object]]:
    product = _mapping(value, name)
    return [
        _mapping(row, f"{name}.slot_scores[{index}]")
        for index, row in enumerate(_items(product.get("slot_scores", []), f"{name}.slot_scores"))
    ]


def test_baseline_is_reconstructible_from_frozen_ancestor() -> None:
    baseline = _baseline()
    assert _string(baseline.get("format_version"), "format_version") == "wave-a-baseline-v2"
    origin = _mapping(baseline.get("origin"), "origin")
    commit = _string(origin.get("commit"), "origin.commit")
    tree = _string(origin.get("tree"), "origin.tree")
    assert _git_text("rev-parse", f"{commit}^{{tree}}").strip() == tree
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT, check=True)
    substances, products, edges, facts = _inventory()
    assert _mapping(baseline.get("stable_ids"), "stable_ids") == {
        "substances": len(substances),
        "products": len(products),
        "sha256": _digest({"substances": substances, "products": products}),
    }
    assert _mapping(baseline.get("product_component_edges"), "product_component_edges") == {
        "count": len(edges),
        "authority_values": sorted({str(edge["authority"]) for edge in edges}),
        "sha256": _digest(edges),
    }
    assert _mapping(baseline.get("canonical_domain_facts"), "canonical_domain_facts") == {
        "count": len(facts),
        "sha256": _digest(facts),
    }


def test_relations_and_policy_sources_are_frozen_blob_accounted() -> None:
    baseline = _baseline()
    relations_raw = _frozen("data/relations.yaml")
    relations = _yaml("data/relations.yaml")
    expected = _mapping(baseline.get("canonical_relations"), "canonical_relations")
    origin = _mapping(baseline.get("origin"), "origin")
    commit = _string(origin.get("commit"), "origin.commit")
    relation_blob = _git_text("rev-parse", f"{commit}:data/relations.yaml")
    assert _string(expected.get("source_blob"), "canonical_relations.source_blob") == relation_blob.strip()
    assert (
        _string(expected.get("source_sha256"), "canonical_relations.source_sha256")
        == hashlib.sha256(relations_raw).hexdigest()
    )
    relation_rows = _items(relations.get("relations"), "relations.relations")
    assert _integer(expected.get("count"), "canonical_relations.count") == len(relation_rows)
    assert _string(expected.get("multiset_sha256"), "canonical_relations.multiset_sha256") == _digest(relation_rows)
    assert _string(expected.get("document_sha256"), "canonical_relations.document_sha256") == _digest(relations)
    for index, source_object in enumerate(_items(baseline.get("policy_sources"), "policy_sources")):
        source = _mapping(source_object, f"policy_sources[{index}]")
        source_path = _string(source.get("path"), f"policy_sources[{index}].path")
        raw = _frozen(source_path)
        source_blob = _git_text("rev-parse", f"{commit}:{source_path}")
        assert _string(source.get("blob"), f"policy_sources[{index}].blob") == source_blob.strip()
        assert _string(source.get("sha256"), f"policy_sources[{index}].sha256") == hashlib.sha256(raw).hexdigest()


def test_decision_surrogate_accounts_for_every_exposed_datum() -> None:
    baseline = _baseline()
    surrogate = _mapping(baseline.get("decision_surrogate"), "decision_surrogate")
    fixture_path = _string(surrogate.get("fixture_path"), "decision_surrogate.fixture_path")
    raw = _frozen(fixture_path)
    origin = _mapping(baseline.get("origin"), "origin")
    commit = _string(origin.get("commit"), "origin.commit")
    fixture_blob = _git_text("rev-parse", f"{commit}:{fixture_path}")
    assert _string(surrogate.get("fixture_blob"), "decision_surrogate.fixture_blob") == fixture_blob.strip()
    assert (
        _string(surrogate.get("fixture_sha256"), "decision_surrogate.fixture_sha256") == hashlib.sha256(raw).hexdigest()
    )
    layout: object = cast(object, yaml.safe_load(raw))
    layout_mapping = _mapping(layout, "layout")
    for phase in ("pre", "post"):
        phase_layout = _mapping(layout_mapping.get(phase), f"layout.{phase}")
        placement = _items(phase_layout.get("placement"), f"layout.{phase}.placement")
        rows = _score_rows(layout_mapping, phase)
        actual = {
            "placements": len(placement),
            "placement_sha256": _digest(placement),
            "score_rows": len(rows),
            "score_rows_sha256": _digest(rows),
            "blocked": sum(_boolean(row.get("blocked"), "score.blocked") for row in rows),
            "diagnostics": sum(len(_items(row.get("diagnostics", []), "score.diagnostics")) for row in rows),
            "assignment_refs": sum(len(_items(row.get("assignment_ids", []), "score.assignment_ids")) for row in rows),
            "score_multiset": {
                str(score): count
                for score, count in sorted(Counter(_integer(row.get("score"), "score.score") for row in rows).items())
            },
        }
        assert _mapping(surrogate.get(phase), f"decision_surrogate.{phase}") == actual
    post = _mapping(surrogate.get("post"), "decision_surrogate.post")
    assert (
        _string(post.get("placement_sha256"), "decision_surrogate.post.placement_sha256")
        == "5a60619dbb9a5c6add6f2ccc7cdcb7939257eeb9d2782170aa8d1e06d0c85728"
    )
    assert (
        _string(surrogate.get("normalized_decision_trace"), "decision_surrogate.normalized_decision_trace")
        == "unavailable_pre_cutover"
    )
    assert set(_strings(surrogate.get("missing_wave_e_fields"), "decision_surrogate.missing_wave_e_fields")) == {
        "input_artifact_digest",
        "normalized_selectors",
        "rule_source_keys",
        "exclusions_with_rule_ids",
        "per_rule_deltas",
        "objective_components",
        "ordered_tie_break_chain",
        "final_result_trace",
    }


def test_feasibility_start_is_measurement_not_permanent_failure_contract() -> None:
    feasibility = _mapping(_baseline().get("feasibility_start"), "feasibility_start")
    assert feasibility == {
        "profile": "ubuntu-latest-equivalent",
        "python": "3.14",
        "install": "uv locked",
        "check_seconds": [6.63, 6.81, 6.91],
        "cold_budget_seconds": 10,
        "cold_budget_passes": True,
        "warm_target_seconds": 5,
        "warm_target_passes": False,
        "no_dev_failure_chain": ["artifacts.py", "generate.py", "linkml_runtime"],
        "no_dev_failure_owner": "Wave C",
        "failure_is_not_a_permanent_contract": True,
    }
