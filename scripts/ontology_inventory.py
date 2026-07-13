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
    arguments = parser.parse_args()
    try:
        if arguments.command == "capture":
            baseline = capture(arguments.ref)
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            verify(arguments.baseline, head=arguments.head)
    except BaselineError as error:
        print(f"ontology inventory: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
