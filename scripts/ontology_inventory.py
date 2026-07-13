#!/usr/bin/env python3
# pyright: reportAny=false, reportUnknownArgumentType=false, reportUnknownMemberType=false
"""Capture and verify the immutable pre-cutover ontology baseline.

The capture path reads only Git blobs reachable from ``main``.  It never reads
the checkout's ``data/`` directory, which makes a baseline credible even when
the feature worktree contains uncommitted migration experiments.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable, Mapping
from hashlib import sha256
from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner.ontology.migration_normalize import NORMALIZER_VERSION, flatten_facts, normalize  # noqa: E402

DEFAULT_BASELINE = ROOT / "tests/fixtures/ontology_migration/pre_cutover_baseline.json"
FORMAT_VERSION = "1"


class BaselineError(RuntimeError):
    """Raised when the immutable migration baseline cannot be trusted."""


def _git(*args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=text,
    )
    if result.returncode:
        stderr = result.stderr if text else result.stderr.decode("utf-8", errors="replace")
        raise BaselineError(f"git {' '.join(args)} failed: {stderr.strip()}")
    return result.stdout


def _tree_files(ref: str) -> list[tuple[str, str]]:
    output = cast(str, _git("ls-tree", "-r", "--full-tree", ref, "--", "data"))
    files: list[tuple[str, str]] = []
    for line in output.splitlines():
        metadata, path = line.split("\t", maxsplit=1)
        mode, kind, blob = metadata.split()
        if kind != "blob" or mode != "100644" or not path.endswith(".yaml"):
            continue
        files.append((path, blob))
    return files


def _blob(blob_id: str) -> bytes:
    return cast(bytes, _git("cat-file", "blob", blob_id, text=False))


def _load_document(path: str, blob_id: str) -> dict[str, object]:
    raw = _blob(blob_id)
    try:
        parsed = yaml.safe_load(raw.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise BaselineError(f"{path} in immutable Git tree is not readable YAML: {error}") from error
    normalized = normalize(parsed)
    entity_id = parsed.get("id") if isinstance(parsed, Mapping) and isinstance(parsed.get("id"), str) else None
    return {
        "path": path,
        "blob": blob_id,
        "sha256": sha256(raw).hexdigest(),
        "entity_id": entity_id,
        "normalized": normalized,
        "facts": flatten_facts(normalized, entity_id=entity_id),
    }


def capture(ref: str) -> dict[str, object]:
    """Build a complete baseline from the ``data/`` subtree of immutable *ref*."""
    origin_commit = cast(str, _git("rev-parse", f"{ref}^{{commit}}")).strip()
    origin_tree = cast(str, _git("rev-parse", f"{origin_commit}^{{tree}}")).strip()
    source_files = _tree_files(origin_commit)
    documents = [_load_document(path, blob) for path, blob in source_files]
    return {
        "format_version": FORMAT_VERSION,
        "normalizer_version": NORMALIZER_VERSION,
        "capture_command": "python scripts/ontology_inventory.py capture --ref main",
        "origin_commit": origin_commit,
        "origin_tree": origin_tree,
        "approved_pre_migration_commit": origin_commit,
        "approved_pre_migration_tree": origin_tree,
        "source_file_count": len(documents),
        "documents": documents,
        "inventory": _inventory(documents),
    }


def _inventory(documents: Iterable[dict[str, object]]) -> dict[str, object]:
    docs = list(documents)
    substances = _ids_for_prefix(docs, "data/substances/", "sub_")
    products = _ids_for_prefix(docs, "data/products/", "prd_")
    components: list[dict[str, object]] = []
    relations: list[dict[str, object]] = []
    dashboards: list[str] = []
    for document in docs:
        path = cast(str, document["path"])
        raw = _restore_mapping(cast(dict[str, object], document["normalized"]))
        if path.startswith("data/products/") and isinstance(raw, dict):
            for index, component in enumerate(cast(list[object], raw.get("components", []))):
                components.append({"product_id": raw.get("id"), "index": index, "component": component})
        if path == "data/relations.yaml" and isinstance(raw, dict):
            relations = cast(list[dict[str, object]], raw.get("relations", []))
        if path.startswith("data/dashboards/") and isinstance(raw, dict) and isinstance(raw.get("id"), str):
            dashboards.append(cast(str, raw["id"]))
    return {
        "substance_ids": substances,
        "product_ids": products,
        "product_components": components,
        "relations": relations,
        "dashboard_ids": sorted(dashboards),
    }


def _ids_for_prefix(documents: Iterable[dict[str, object]], prefix: str, id_prefix: str) -> list[str]:
    ids = [
        cast(str, document["entity_id"])
        for document in documents
        if cast(str, document["path"]).startswith(prefix)
        and isinstance(document.get("entity_id"), str)
        and cast(str, document["entity_id"]).startswith(id_prefix)
    ]
    if len(ids) != len(set(ids)):
        raise BaselineError(f"Duplicate stable IDs in immutable source: {prefix}")
    return sorted(ids)


def _restore_mapping(value: dict[str, object]) -> object:
    """Recover a plain value only for concise inventory summaries."""
    value_type = value["type"]
    if value_type == "mapping":
        return {
            str(key): _restore_mapping(cast(dict[str, object], child))
            for key, child in cast(list[list[object]], value["value"])
        }
    if value_type == "sequence":
        return [_restore_mapping(cast(dict[str, object], child)) for child in cast(list[object], value["value"])]
    if value_type == "null":
        return None
    return value.get("value")


def verify(baseline_path: Path, *, head: str = "HEAD") -> None:
    """Fail closed unless the fixture exactly describes its immutable Git source."""
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BaselineError(f"Cannot read baseline {baseline_path}: {error}") from error
    _require(baseline.get("format_version") == FORMAT_VERSION, "Unsupported baseline format")
    _require(baseline.get("normalizer_version") == NORMALIZER_VERSION, "Normalizer version mismatch")
    origin_commit = _required_string(baseline, "origin_commit")
    origin_tree = _required_string(baseline, "origin_tree")
    _require(
        origin_commit == _required_string(baseline, "approved_pre_migration_commit"),
        "Approved commit differs from origin",
    )
    _require(
        origin_tree == _required_string(baseline, "approved_pre_migration_tree"), "Approved tree differs from origin"
    )
    actual_tree = cast(str, _git("rev-parse", f"{origin_commit}^{{tree}}")).strip()
    _require(actual_tree == origin_tree, "Recorded origin tree does not match origin commit")
    _require(_is_ancestor(origin_commit, head), f"Origin commit {origin_commit} is not an ancestor of {head}")
    expected = capture(origin_commit)
    _require(
        _canonical_json(expected) == _canonical_json(baseline),
        "Baseline source drift: fixture differs from immutable origin tree",
    )


def account(baseline_path: Path) -> dict[str, object]:  # noqa: PLR0914
    """Account for the v1 cutover without accepting a compatibility reader.

    The baseline is immutable Git evidence; current cards must retain stable
    identities and product edges, and every canonical fact must resolve through
    the exhaustive reviewed migration map and vocabulary.  This is intentionally
    strict: an unmapped term, dangling component, changed ID, or relation count
    mismatch is a migration failure rather than a warning.
    """
    verify(baseline_path)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    inventory = cast(dict[str, object], baseline["inventory"])
    source_substances = cast(list[str], inventory["substance_ids"])
    source_products = cast(list[str], inventory["product_ids"])
    current_substances = sorted(
        cast(str, load.get("id"))
        for path in sorted((ROOT / "data/substances").glob("*.yaml"))
        if isinstance((load := yaml.safe_load(path.read_text(encoding="utf-8"))), dict)
        and isinstance(load.get("id"), str)
    )
    current_products = sorted(
        cast(str, load.get("id"))
        for path in sorted((ROOT / "data/products").glob("*.yaml"))
        if isinstance((load := yaml.safe_load(path.read_text(encoding="utf-8"))), dict)
        and isinstance(load.get("id"), str)
    )
    _require(source_substances == current_substances, "Substance stable-ID parity failed")
    _require(source_products == current_products, "Product stable-ID parity failed")
    source_edges = {
        _baseline_component_edge(item) for item in cast(list[dict[str, object]], inventory["product_components"])
    }
    current_edges: set[tuple[str, int, str]] = set()
    for path in (ROOT / "data/products").glob("*.yaml"):
        product = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(product, dict):
            raise BaselineError(f"{path}: product is not a mapping")
        for index, component in enumerate(product.get("components", [])):
            if not isinstance(component, dict) or not isinstance(component.get("substance"), str):
                raise BaselineError(f"{path}: invalid component {index}")
            current_edges.add((str(product["id"]), index, component["substance"]))
    _require(source_edges == current_edges, "Product component-edge parity failed")
    vocabulary = yaml.safe_load((ROOT / "ontology/vocabulary.yaml").read_text(encoding="utf-8"))
    known_terms = {
        (str(term["semantic_category"]), str(term["slug"]))
        for term in vocabulary.get("terms", [])
        if isinstance(term, dict)
    }
    fact_count = 0
    for path in (ROOT / "data/substances").glob("*.yaml"):
        card = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(card, dict):
            raise BaselineError(f"{path}: card is not a mapping")
        for category, terms in card.get("knowledge", {}).items():
            if not isinstance(terms, list):
                raise BaselineError(f"{path}: {category} is not a list")
            for term in terms:
                _require((str(category), str(term)) in known_terms, f"{path}: unknown canonical fact {category}:{term}")
                fact_count += 1
    baseline_relations = _baseline_relation_records(cast(list[dict[str, object]], baseline["documents"]))
    relations = yaml.safe_load((ROOT / "data/relations.yaml").read_text(encoding="utf-8"))
    current_relations = relations.get("relations") if isinstance(relations, dict) else None
    _require(isinstance(current_relations, list), "Canonical relations list is missing")
    typed_relations = cast(list[object], current_relations)
    current_relation_records = [record for record in typed_relations if isinstance(record, dict)]
    _require(
        all(record.get("type") != "competes" for record in current_relation_records),
        "Legacy competes records must be relocated into canonical scheduling constraints",
    )
    constraints_document = yaml.safe_load((ROOT / "ontology/scheduling-constraints.yaml").read_text(encoding="utf-8"))
    constraints_raw = constraints_document.get("scheduling_constraints") if isinstance(constraints_document, dict) else None
    _require(isinstance(constraints_raw, dict), "Canonical scheduling constraints are missing")
    constraints = cast(dict[str, object], constraints_raw)
    _account_relation_relocation(baseline_relations, current_relation_records, constraints)
    _account_ontology_assertions(current_relation_records)
    return {
        "status": "ok",
        "substances": len(current_substances),
        "products": len(current_products),
        "component_edges": len(current_edges),
        "canonical_knowledge_facts": fact_count,
        "relations": len(baseline_relations),
        "ontology_relations": len(current_relation_records),
        "scheduling_constraints": len(constraints),
        "dashboards": len(list((ROOT / "data/dashboards").glob("*.yaml"))),
    }


def _baseline_relation_records(documents: list[dict[str, object]]) -> list[dict[str, object]]:
    """Read grouped legacy records from fixture documents (not the live tree)."""
    document = next((item for item in documents if item.get("path") == "data/relations.yaml"), None)
    if document is None:
        raise BaselineError("Baseline has no data/relations.yaml")
    raw = _restore_mapping(cast(dict[str, object], document["normalized"]))
    if not isinstance(raw, dict):
        raise BaselineError("Baseline relations are not a mapping")
    return [
        record
        for records in raw.values()
        if isinstance(records, list)
        for record in records
        if isinstance(record, dict)
    ]


def _account_relation_relocation(
    baseline_relations: list[dict[str, object]],
    current_relations: list[dict[str, object]],
    constraints: Mapping[str, object],
) -> None:
    """Prove every historical relation survives in its semantic destination."""
    constraint_by_legacy_id = {
        record.get("legacy_relation_id"): record
        for value in constraints.values()
        if isinstance(value, dict)
        for record in [cast(dict[str, object], value)]
        if isinstance(record.get("legacy_relation_id"), str)
    }
    baseline_competes = _baseline_competes_records(baseline_relations)
    expected_ids = {f"rel_competes_{index:03d}" for index in range(1, len(baseline_competes) + 1)}
    _require(len(current_relations) + len(constraints) == len(baseline_relations), "Relation-record parity failed")
    _require(set(constraint_by_legacy_id) == expected_ids, "Scheduling-constraint legacy IDs do not cover every competes record")
    for index, baseline in enumerate(baseline_competes, start=1):
        relation_id = f"rel_competes_{index:03d}"
        constraint = constraint_by_legacy_id[relation_id]
        _require(
            constraint.get("assertion_type") == "clinical_scheduling_constraint"
            and constraint.get("effect") == "separate_slots"
            and constraint.get("enforcement") == "block"
            and constraint.get("legacy_preserved") is True,
            f"Scheduling constraint {relation_id} lost its preserved hard-block semantics",
        )
        _require(constraint.get("source_selector") == _baseline_selector(baseline, "source"), f"Source selector changed for {relation_id}")
        _require(constraint.get("target_selector") == _baseline_selector(baseline, "target"), f"Target selector changed for {relation_id}")
        _require(constraint.get("rationale") == baseline.get("reason"), f"Rationale changed for {relation_id}")
        _require(constraint.get("action") == baseline.get("action"), f"Action changed for {relation_id}")


def _baseline_competes_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    """Identify the eight historical hard separate-slot records without live-tree input."""
    matches = [
        record
        for record in records
        if record.get("source_class") == "mineral"
        or str(record.get("action", "")).startswith(("Keep ", "Separate "))
    ]
    _require(len(matches) == 8, "Baseline does not contain the expected eight hard scheduling constraints")
    return matches


def _account_ontology_assertions(assertions: list[dict[str, object]]) -> None:
    """Prove the 28 non-constraint records have a governed semantic home."""
    expected_by_type = {"balance": 2, "supports": 11, "review_with": 15}
    actual_by_type = {
        relation_type: sum(1 for assertion in assertions if assertion.get("type") == relation_type)
        for relation_type in expected_by_type
    }
    _require(actual_by_type == expected_by_type, "Canonical ontology assertion type counts changed")
    allowed_families = {
        "balance": {"nutrient_balance_review_signal"},
        "supports": {
            "biochemical_mechanism_assertion",
            "absorption_interaction_claim",
            "nutritional_adequacy_advisory",
        },
        "review_with": {"clinical_review_signal"},
    }
    expected_kind = {"balance": "clinical_review_signal", "supports": "ontology_assertion", "review_with": "clinical_review_signal"}
    for assertion in assertions:
        relation_type = assertion.get("type")
        if relation_type not in expected_by_type:
            continue
        _require(
            assertion.get("assertion_kind") == expected_kind[relation_type],
            f"Ontology assertion {assertion.get('id')} has an invalid assertion kind",
        )
        _require(
            assertion.get("semantic_family") in allowed_families[relation_type],
            f"Ontology assertion {assertion.get('id')} has an invalid semantic family",
        )


def _baseline_selector(record: Mapping[str, object], side: str) -> dict[str, object]:
    for source_key, target in ((f"{side}_name", "name"), (f"{side}_substance", "id")):
        value = record.get(source_key)
        if isinstance(value, str):
            return {"entity": {target: value}}
    category = record.get(f"{side}_class")
    if isinstance(category, str):
        # The v1 migration formally separated the former overloaded `is` class:
        # only fat_soluble is a quality; mineral remains a kind.
        return {"category": "quality" if category == "fat_soluble" else "kind", "term": category}
    raise BaselineError(f"Baseline hard scheduling constraint has no {side} selector")


def _baseline_component_edge(item: dict[str, object]) -> tuple[str, int, str]:
    """Validate one normalized baseline component before comparing its edge."""
    product_id = item.get("product_id")
    index = item.get("index")
    component = item.get("component")
    if not isinstance(product_id, str) or not isinstance(index, int) or not isinstance(component, dict):
        raise BaselineError("Baseline contains an invalid product component")
    substance = component.get("substance")
    if not isinstance(substance, str):
        raise BaselineError("Baseline component has no substance ID")
    return product_id, index, substance


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    result = subprocess.run(["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=ROOT, check=False)
    return result.returncode == 0


def _required_string(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise BaselineError(f"Baseline is missing required string {key!r}")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BaselineError(message)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    capture_parser = subcommands.add_parser("capture", help="capture immutable Git-tree baseline")
    capture_parser.add_argument("--ref", default="main")
    capture_parser.add_argument("--output", type=Path, default=DEFAULT_BASELINE)
    verify_parser = subcommands.add_parser("verify", help="verify provenance and immutable source")
    verify_parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    verify_parser.add_argument("--head", default="HEAD")
    account_parser = subcommands.add_parser("account", help="prove v1 ID, edge, vocabulary, and relation parity")
    account_parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    arguments = parser.parse_args()
    try:
        if arguments.command == "capture":
            baseline = capture(arguments.ref)
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        elif arguments.command == "verify":
            verify(arguments.baseline, head=arguments.head)
        else:
            print(json.dumps(account(arguments.baseline), ensure_ascii=False, sort_keys=True))
    except BaselineError as error:
        print(f"ontology inventory: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
