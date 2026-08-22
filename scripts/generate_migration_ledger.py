#!/usr/bin/env python3
"""Generate the deterministic pre-cutover legacy-atom reconciliation ledger.

The default mode writes nothing and emits the ledger to stdout. ``--output``
is the explicit write mode. This inventory reads only clean, tracked
authoritative source cards and policy catalogs; it never reads generated
schedule or ontology output and never imports the planner runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

GENERATOR_VERSION = "legacy-atom-ledger-v2"
ADJUDICATION_BATCH = "sol-20260822-canonical-cutover-v1"
MAX_EXCERPT_LENGTH = 240
MAX_EXCERPT_BODY = MAX_EXCERPT_LENGTH - len("...")
DISPOSITIONS = (
    "typed_fact",
    "raw_quotation",
    "source_metadata",
    "sol_adjudication",
    "explicit_exclusion",
)
AUTO_EXCLUSION_KEYS = frozenset({"action", "action_text", "default_message", "template", "why_here"})
QUOTATION_KEYS = frozenset({"quotation", "quote", "raw_quotation", "raw_quote"})
POLICY_FILES = frozenset({
    "ontology/policies.yaml",
    "ontology/runtime-policy.yaml",
    "ontology/scheduling-constraints.yaml",
})
EXACT_FILES = frozenset({"data/relations.yaml", *POLICY_FILES})
AUTHORITATIVE_PREFIXES = ("data/substances/", "data/products/")
EXCLUDED_SOURCE_FAMILIES = (
    "schedule.yaml (generated projection; intentionally ignored)",
    "ontology/generated/* (generated ontology artifacts; intentionally ignored)",
    "data/stacks.yaml and data/pillboxes.yaml (retained scenario/topology inputs; intentionally ignored)",
    "product urls, retained knowledge assertions and source facts (outside this migration scope)",
    "allowed IDs, labels, order and composition identity/amount fields (retained facts; intentionally ignored)",
)


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _sha256(value: Any) -> str:
    encoded = json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _source_head(root: Path) -> str:
    return _git(root, "rev-parse", "HEAD").strip()


def _pointer(tokens: tuple[str | int, ...]) -> str:
    if not tokens:
        return "/"
    return "/" + "/".join(str(token).replace("~", "~0").replace("/", "~1") for token in tokens)


def _path_text(tokens: tuple[str | int, ...]) -> str:
    path = ""
    for token in tokens:
        if isinstance(token, int):
            path += f"[{token}]"
        elif path:
            path += f".{token}"
        else:
            path = token
    return path


def _excerpt(value: Any) -> str | int | float | bool | None:
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > MAX_EXCERPT_LENGTH:
            return value[:MAX_EXCERPT_BODY] + "..."
        return value
    return None


def _tracked_authoritative_files(root: Path) -> list[Path]:
    tracked = {
        item
        for item in _git(
            root,
            "ls-files",
            "-z",
            "--",
            "data/substances",
            "data/products",
            *sorted(EXACT_FILES),
        ).split("\0")
        if item
    }
    filesystem = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*.yaml")
        if path.is_file()
        and (
            path.relative_to(root).as_posix().startswith(AUTHORITATIVE_PREFIXES)
            or path.relative_to(root).as_posix() in EXACT_FILES
        )
    }
    untracked = sorted(filesystem - tracked)
    if untracked:
        raise RuntimeError("untracked authoritative inputs: " + ", ".join(untracked))
    relevant_status = _git(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        "data/substances",
        "data/products",
        *sorted(EXACT_FILES),
    )
    if relevant_status.strip():
        raise RuntimeError("dirty authoritative inputs:\n" + relevant_status)
    return [root / item for item in sorted(tracked)]


def _iter_leaves(value: Any, tokens: tuple[str | int, ...] = ()) -> Any:
    if isinstance(value, dict):
        for key in sorted(value, key=lambda item: str(item)):
            yield from _iter_leaves(value[key], (*tokens, str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _iter_leaves(item, (*tokens, index))
    else:
        yield tokens, value


def _is_selected(source: str, tokens: tuple[str | int, ...]) -> bool:
    keys = {str(token) for token in tokens if isinstance(token, str)}
    if source.startswith(AUTHORITATIVE_PREFIXES):
        if not tokens:
            return False
        if tokens[0] in {"notes", "concerns", "schedule", "scheduling_assessment"}:
            return True
        return tokens[0] == "components" and "notes" in keys
    if source == "data/relations.yaml":
        return "id" not in keys and bool(
            keys
            & {
                "relations",
                "reason",
                "action",
                "severity",
                "relation_type",
                "assertion_kind",
                "semantic_family",
                "research_state",
                "source_selector",
                "target_selector",
                "sources",
            }
        )
    if source == "ontology/scheduling-constraints.yaml":
        return "id" not in keys
    return "id" not in keys and "label" not in keys and "order" not in keys


def _category(source: str, tokens: tuple[str | int, ...]) -> str:  # noqa: C901, PLR0911
    keys = {str(token) for token in tokens if isinstance(token, str)}
    if "sources" in keys:
        return "source_metadata"
    if keys & QUOTATION_KEYS:
        return "raw_quotation"
    if keys & AUTO_EXCLUSION_KEYS:
        return "prescribed_action_or_generated_wording"
    if source == "data/relations.yaml":
        return "relation_semantics"
    if source == "ontology/scheduling-constraints.yaml":
        return "pair_constraint"
    if source in POLICY_FILES:
        return "policy_runtime_semantics"
    if "prefer_with" in keys:
        return "schedule_prefer_with"
    if "scheduling_assessment" in keys:
        return "scheduling_assessment"
    if "schedule" in keys:
        return "schedule_assertion"
    if "concerns" in keys:
        return "concern_text"
    if "notes" in keys and "components" in keys:
        return "component_notes"
    if "notes" in keys:
        return "substance_notes" if source.startswith("data/substances/") else "product_notes"
    return "legacy_semantic_field"


def _disposition(
    category: str, tokens: tuple[str | int, ...], source: str, pointer: str
) -> tuple[str, str | None, str | None]:
    if category == "source_metadata":
        target = f"source_metadata:{source}#{pointer}"
        return "source_metadata", target, None
    if category == "raw_quotation":
        target = f"raw_quotation:{source}#{pointer}"
        return "raw_quotation", target, None
    if category == "prescribed_action_or_generated_wording":
        return (
            "explicit_exclusion",
            None,
            "prescribed action/template/generated wording is not canonical evidence",
        )
    reasons = {
        "schedule_assertion": "legacy schedule assertion needs closed-fact or exclusion adjudication",
        "schedule_prefer_with": "pair preference is forbidden canonical input and needs disposition adjudication",
        "scheduling_assessment": "assessment outcome/prose is a stored answer and needs evidence adjudication",
        "substance_notes": "substance prose needs evidence-boundary adjudication",
        "product_notes": "product prose needs evidence-boundary adjudication",
        "component_notes": "component prose needs evidence-boundary adjudication",
        "concern_text": "concern prose needs evidence-boundary adjudication",
        "relation_semantics": "relation meaning is outside the closed scheduling fact vocabulary",
        "pair_constraint": "constraint operation/score is a stored answer and needs disposition adjudication",
        "policy_runtime_semantics": "policy/runtime meaning must not become hidden canonical semantics",
        "legacy_semantic_field": "legacy semantic field needs closed-boundary adjudication",
    }
    reason = reasons[category]
    return "sol_adjudication", None, reason


def build_document(root: Path) -> dict[str, Any]:  # noqa: PLR0914
    files = _tracked_authoritative_files(root)
    rows: list[dict[str, Any]] = []
    source_inventory: list[dict[str, Any]] = []
    parse_errors: list[dict[str, str]] = []

    for path in files:
        source = path.relative_to(root).as_posix()
        source_hash = _file_sha256(path)
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            parse_errors.append({"source_path": source, "error": str(error)})
            continue
        selected = [(tokens, value) for tokens, value in _iter_leaves(loaded) if _is_selected(source, tokens)]
        source_inventory.append({
            "source_path": source,
            "source_file_sha256": source_hash,
            "atom_count": len(selected),
        })
        for tokens, value in selected:
            pointer = _pointer(tokens)
            exact_hash = _sha256(value)
            atom_hash = _sha256({"source_path": source, "pointer": pointer, "exact_value_sha256": exact_hash})
            category = _category(source, tokens)
            disposition, target_id, reason = _disposition(category, tokens, source, pointer)
            rows.append({
                "atom_id": f"atom_{atom_hash[:24]}",
                "source_path": source,
                "pointer": pointer,
                "category": category,
                "exact_value_sha256": exact_hash,
                "value_excerpt": _excerpt(value),
                "disposition": disposition,
            })
            if target_id:
                rows[-1]["target_id"] = target_id
            if reason and disposition not in {"source_metadata", "raw_quotation"}:
                rows[-1]["disposition_reason"] = reason

    if parse_errors:
        raise RuntimeError("authoritative YAML parse errors: " + repr(parse_errors))
    rows.sort(key=lambda row: (row["source_path"], row["pointer"], row["atom_id"]))
    counts = Counter(row["disposition"] for row in rows)
    categories = Counter(row["category"] for row in rows)
    return {
        "ledger_format": GENERATOR_VERSION,
        "adjudication_batch": ADJUDICATION_BATCH,
        "source_head": _source_head(root),
        "source_diff_policy": "authoritative files must be git-tracked and clean at generation; regenerate after any source change",
        "scope": {
            "included_source_families": [
                "data/substances/*.yaml: schedule, prefer_with, scheduling_assessment, notes, concerns",
                "data/products/*.yaml: product/component notes and concerns",
                "data/relations.yaml: relation semantic metadata, reason/action/severity/selectors/sources",
                "ontology/scheduling-constraints.yaml: constraint selectors/rationale/action/scores",
                "ontology/policies.yaml and ontology/runtime-policy.yaml: authored semantic prose and stored-answer fields",
            ],
            "excluded_source_families": list(EXCLUDED_SOURCE_FAMILIES),
            "atomization": "Every selected scalar/list leaf receives one row; containers are represented by child pointers.",
        },
        "disposition_enum": list(DISPOSITIONS),
        "coverage": {
            "source_file_count": len(source_inventory),
            "atom_count": len(rows),
            "pending_atom_count": 0,
            "final_disposition_counts": dict(sorted(counts.items())),
            "outstanding_sol_adjudication_count": counts["sol_adjudication"],
            "by_category": dict(sorted(categories.items())),
            "parse_error_count": 0,
            "migration_complete": False,
            "migration_blocker": "outstanding Sol adjudication atoms must receive typed_fact/raw_quotation/source_metadata/explicit_exclusion before deletion",
        },
        "source_inventory": source_inventory,
        "atoms": rows,
    }


def _dump(document: dict[str, Any]) -> str:
    return yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=120)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="Write the ledger here; omitted means stdout only")
    args = parser.parse_args(argv)
    try:
        document = build_document(args.root.resolve())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"migration ledger generation failed closed: {error}", file=sys.stderr)
        return 2
    rendered = _dump(document)
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        output = args.output if args.output.is_absolute() else args.root.resolve() / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
