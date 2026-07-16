"""Frozen-tree provenance and accounting for the LinkML cutover."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).parents[1]
BASELINE = ROOT / "tests/fixtures/linkml_cutover/wave_a_baseline.json"


def _git(*args: str, text: bool = False) -> bytes | str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=text)


def _frozen(path: str) -> bytes:
    return _git("show", f"{_baseline()['origin']['commit']}:{path}")  # type: ignore[return-value]


def _baseline() -> dict[str, Any]:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _yaml(path: str) -> dict[str, Any]:
    value = yaml.safe_load(_frozen(path))
    assert isinstance(value, dict)
    return value


def _inventory() -> tuple[list[str], list[str], list[dict[str, object]], list[dict[str, str]]]:
    commit = _baseline()["origin"]["commit"]
    paths = str(_git("ls-tree", "-r", "--name-only", commit, "--", "data", text=True)).splitlines()
    substances: list[str] = []
    products: list[str] = []
    edges: list[dict[str, object]] = []
    facts: list[dict[str, str]] = []
    for path in sorted(path for path in paths if path.endswith(".yaml")):
        card = _yaml(path)
        if path.startswith("data/substances/"):
            substances.append(card["id"])
            for category, values in sorted((card.get("knowledge") or {}).items()):
                facts.extend({"subject": card["id"], "category": category, "value": value} for value in values)
        elif path.startswith("data/products/"):
            products.append(card["id"])
            for index, component in enumerate(card.get("components", [])):
                authority = component.get("authority", "primary" if index == 0 else "secondary")
                edges.append({
                    "product_id": card["id"],
                    "index": index,
                    "substance_id": component["substance"],
                    "authority": authority,
                })
    return substances, products, edges, facts


def _score_rows(layout: dict[str, Any], phase: str) -> list[dict[str, object]]:
    return [
        {"product_id": product_id, **row}
        for product_id, product in sorted(layout[phase]["products"].items())
        for row in product.get("slot_scores", [])
    ]


def test_baseline_is_reconstructible_from_frozen_ancestor() -> None:
    baseline = _baseline()
    assert baseline["format_version"] == "wave-a-baseline-v2"
    commit = baseline["origin"]["commit"]
    assert str(_git("rev-parse", f"{commit}^{{tree}}", text=True)).strip() == baseline["origin"]["tree"]
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT, check=True)
    substances, products, edges, facts = _inventory()
    assert baseline["stable_ids"] == {
        "substances": len(substances),
        "products": len(products),
        "sha256": _digest({"substances": substances, "products": products}),
    }
    assert baseline["product_component_edges"] == {
        "count": len(edges),
        "authority_values": sorted({str(edge["authority"]) for edge in edges}),
        "sha256": _digest(edges),
    }
    assert baseline["canonical_domain_facts"] == {"count": len(facts), "sha256": _digest(facts)}


def test_relations_and_policy_sources_are_frozen_blob_accounted() -> None:
    baseline = _baseline()
    relations_raw = _frozen("data/relations.yaml")
    relations = _yaml("data/relations.yaml")
    expected = baseline["canonical_relations"]
    assert (
        expected["source_blob"]
        == str(_git("rev-parse", f"{baseline['origin']['commit']}:data/relations.yaml", text=True)).strip()
    )
    assert expected["source_sha256"] == hashlib.sha256(relations_raw).hexdigest()
    assert expected["count"] == len(relations["relations"])
    assert expected["multiset_sha256"] == _digest(relations["relations"])
    assert expected["document_sha256"] == _digest(relations)
    for source in baseline["policy_sources"]:
        raw = _frozen(source["path"])
        assert (
            source["blob"]
            == str(_git("rev-parse", f"{baseline['origin']['commit']}:{source['path']}", text=True)).strip()
        )
        assert source["sha256"] == hashlib.sha256(raw).hexdigest()


def test_decision_surrogate_accounts_for_every_exposed_datum() -> None:
    baseline = _baseline()
    surrogate = baseline["decision_surrogate"]
    raw = _frozen(surrogate["fixture_path"])
    assert (
        surrogate["fixture_blob"]
        == str(_git("rev-parse", f"{baseline['origin']['commit']}:{surrogate['fixture_path']}", text=True)).strip()
    )
    assert surrogate["fixture_sha256"] == hashlib.sha256(raw).hexdigest()
    layout = yaml.safe_load(raw)
    for phase in ("pre", "post"):
        rows = _score_rows(layout, phase)
        actual = {
            "placements": len(layout[phase]["placement"]),
            "placement_sha256": _digest(layout[phase]["placement"]),
            "score_rows": len(rows),
            "score_rows_sha256": _digest(rows),
            "blocked": sum(bool(row["blocked"]) for row in rows),
            "diagnostics": sum(len(row.get("diagnostics", [])) for row in rows),
            "assignment_refs": sum(len(row.get("assignment_ids", [])) for row in rows),
            "score_multiset": {
                str(score): count for score, count in sorted(Counter(row["score"] for row in rows).items())
            },
        }
        assert surrogate[phase] == actual
    assert surrogate["post"]["placement_sha256"] == "5a60619dbb9a5c6add6f2ccc7cdcb7939257eeb9d2782170aa8d1e06d0c85728"
    assert surrogate["normalized_decision_trace"] == "unavailable_pre_cutover"
    assert set(surrogate["missing_wave_e_fields"]) == {
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
    feasibility = _baseline()["feasibility_start"]
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
