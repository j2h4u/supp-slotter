#!/usr/bin/env python3
"""Validate the finite legacy-atom migration closure and write its receipt.

The full row-level crosswalk deliberately lives only in a temporary directory.
Git object ``3c6cc44...`` is the immutable forensic source; the checked-in YAML
is a compact, deterministic receipt of the successful reconstruction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final, cast

import yaml
from planner.yaml_io import YamlValue, safe_load_yaml

RECEIPT_FORMAT: Final = "canonical-migration-provenance-closure-v1"
PRE_DELETION_COMMIT: Final = "9050ca70ea2eaff6c92dc86612219634a985fb90"
SOURCE_HEAD: Final = PRE_DELETION_COMMIT
ORIGINAL_LEDGER_BLOB: Final = "3c6cc44f361547d273c43bb8108dfe8d1960800c"
LEDGER_PATH: Final = "docs/migrations/legacy-atom-ledger.yaml"
ORIGINAL_ATOM_COUNT: Final = 2161
ORIGINAL_SOL_COUNT: Final = 1786
SCHEDULE_AXIS_INDEX: Final = 1
FACT_FAMILIES: Final = (
    ("food_effects", "intake"),
    ("acute_alertness_effects", "timing"),
    ("acute_sleep_effects", "timing"),
    ("pre_exercise_performance_effects", "activity"),
    ("post_exercise_recovery_effects", "activity"),
)
ALLOWED_DISPOSITIONS: Final = frozenset({
    "retained_unchanged",
    "typed_fact",
    "raw_quotation",
    "source_metadata",
    "explicit_exclusion",
})
EXCLUSION_RULES: Final = {
    "schedule_assertion": "operational_presentation_prose",
    "scheduling_assessment": "operational_presentation_prose",
    "schedule_prefer_with": "stored_pair_answer",
    "pair_constraint": "superseded_runtime_mechanism",
    "policy_runtime_semantics": "superseded_runtime_mechanism",
    "relation_semantics": "superseded_runtime_mechanism",
    "prescribed_action_or_generated_wording": "generated_action_not_canonical_evidence",
    "substance_notes": "operational_presentation_prose",
    "product_notes": "operational_presentation_prose",
    "component_notes": "operational_presentation_prose",
    "concern_text": "operational_presentation_prose",
}


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def _narrow(value: object, *, source: str) -> YamlValue:
    if value is None or isinstance(value, (bool, float, int, str)):
        return value
    if isinstance(value, list):
        return [_narrow(item, source=source) for item in cast(list[object], value)]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {cast(str, key): _narrow(item, source=source) for key, item in cast(dict[object, object], value).items()}
    raise RuntimeError(f"{source}: unsupported YAML value")


def _mapping(value: YamlValue | None, *, source: str) -> dict[str, YamlValue]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{source} must be a mapping")
    return value


def _list(value: YamlValue | None, *, source: str) -> list[YamlValue]:
    if not isinstance(value, list):
        raise RuntimeError(f"{source} must be a list")
    return value


def _string(value: YamlValue | None, *, source: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{source} must be a non-empty string")
    return value


def _canonical(value: object) -> YamlValue:
    value = _narrow(value, source="canonical value")
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    return value


def _sha256(value: object) -> str:
    encoded = json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _blob_document(root: Path) -> dict[str, YamlValue]:
    actual_blob = _git(root, "rev-parse", f"{PRE_DELETION_COMMIT}:{LEDGER_PATH}").strip()
    if actual_blob != ORIGINAL_LEDGER_BLOB:
        raise RuntimeError(f"pre-deletion ledger blob drifted: {actual_blob}")
    raw = _git(root, "cat-file", "-p", ORIGINAL_LEDGER_BLOB)
    return _mapping(
        _narrow(safe_load_yaml(raw, path=ORIGINAL_LEDGER_BLOB), source=ORIGINAL_LEDGER_BLOB), source="ledger"
    )


def _decode_pointer(pointer: str) -> tuple[str | int, ...]:
    if not pointer.startswith("/"):
        raise RuntimeError(f"invalid JSON pointer: {pointer}")
    return tuple(
        int(token) if token.isdecimal() else token.replace("~1", "/").replace("~0", "~")
        for token in pointer.removeprefix("/").split("/")
    )


_MISSING = object()


def _at_pointer(document: YamlValue, pointer: str) -> YamlValue | object:
    current: YamlValue = document
    for token in _decode_pointer(pointer):
        if isinstance(current, dict):
            if not isinstance(token, str) or token not in current:
                return _MISSING
            current = current[token]
            continue
        if isinstance(current, list):
            if not isinstance(token, int) or token >= len(current):
                return _MISSING
            current = current[token]
            continue
        if current is None or isinstance(current, (bool, float, int, str)):
            return _MISSING
    return current


def _working_document(root: Path, cache: dict[str, YamlValue | object], path: str) -> YamlValue | object:
    if path not in cache:
        candidate = root / path
        cache[path] = (
            _narrow(safe_load_yaml(candidate.read_text(encoding="utf-8"), path=path), source=path)
            if candidate.is_file()
            else _MISSING
        )
    return cache[path]


def _unchanged(root: Path, cache: dict[str, YamlValue | object], row: dict[str, YamlValue]) -> bool:
    document = _working_document(root, cache, _string(row.get("source_path"), source="atom path"))
    if document is _MISSING:
        return False
    value = _at_pointer(cast(YamlValue, document), _string(row.get("pointer"), source="atom pointer"))
    return value is not _MISSING and _sha256(cast(YamlValue, value)) == _string(
        row.get("exact_value_sha256"), source="atom hash"
    )


def _tree_document(root: Path, path: str) -> dict[str, YamlValue]:
    source = f"{PRE_DELETION_COMMIT}:{path}"
    return _mapping(_narrow(safe_load_yaml(_git(root, "show", source), path=source), source=source), source=source)


def _fact_targets(root: Path) -> tuple[dict[tuple[str, str], str], set[str], set[str]]:
    path = root / "ontology/canonical-facts.yaml"
    current_catalog = _mapping(
        _narrow(safe_load_yaml(path.read_text(encoding="utf-8"), path=str(path)), source=str(path)),
        source="canonical fact catalog",
    )
    reference_catalog = _tree_document(root, "ontology/canonical-facts.yaml")
    roles = {
        _string(_mapping(item, source="role").get("id"), source="role id"): _string(
            _mapping(item, source="role").get("substance"), source="role substance"
        )
        for item in _list(reference_catalog.get("composition_roles"), source="composition_roles")
    }
    targets: dict[tuple[str, str], str] = {}
    expected_fact_ids: set[str] = set()
    current_fact_ids: set[str] = set()
    quotations: set[str] = set()
    for family, axis in FACT_FAMILIES:
        for item in _list(reference_catalog.get(family), source=family):
            fact = _mapping(item, source=f"{family} fact")
            fact_id = _string(fact.get("id"), source=f"{family} fact id")
            subject = _mapping(fact.get("subject"), source=f"{family} subject")
            role = subject.get("composition_role")
            substance = subject.get("substance") or (roles.get(role) if isinstance(role, str) else None)
            if not isinstance(substance, str):
                raise RuntimeError(f"{fact_id}: unresolved fact subject")
            targets[(substance, axis)] = fact_id
            expected_fact_ids.add(fact_id)
        for item in _list(current_catalog.get(family), source=f"current {family}"):
            fact = _mapping(item, source=f"current {family} fact")
            fact_id = _string(fact.get("id"), source=f"current {family} fact id")
            current_fact_ids.add(fact_id)
            for provenance in _list(fact.get("provenance"), source=f"{fact_id} provenance"):
                quotation = _mapping(provenance, source=f"{fact_id} provenance").get("quotation")
                if isinstance(quotation, str):
                    quotations.add(_sha256(quotation))
    if not expected_fact_ids <= current_fact_ids:
        raise RuntimeError("a pre-deletion canonical fact target is absent from the current catalog")
    return targets, current_fact_ids, quotations


def _substance_id(root: Path, cache: dict[str, str], path: str) -> str:
    if path not in cache:
        cache[path] = _string(_tree_document(root, path).get("id"), source=f"{path} id")
    return cache[path]


def _classify(  # noqa: PLR0913, PLR0917
    root: Path,
    working_cache: dict[str, YamlValue | object],
    substance_cache: dict[str, str],
    fact_targets: dict[tuple[str, str], str],
    quotation_hashes: set[str],
    row: dict[str, YamlValue],
) -> dict[str, YamlValue]:
    atom_id = _string(row.get("atom_id"), source="atom id")
    category = _string(row.get("category"), source=f"{atom_id} category")
    source_path = _string(row.get("source_path"), source=f"{atom_id} path")
    pointer = _string(row.get("pointer"), source=f"{atom_id} pointer")
    result: dict[str, YamlValue] = {
        "atom_id": atom_id,
        "category": category,
        "source_path": source_path,
        "pointer": pointer,
        "exact_value_sha256": _string(row.get("exact_value_sha256"), source=f"{atom_id} hash"),
    }
    if _unchanged(root, working_cache, row):
        result["disposition"] = "retained_unchanged"
        return result
    if category == "source_metadata":
        result["disposition"] = "source_metadata"
        return result
    if category == "schedule_assertion":
        tokens = _decode_pointer(pointer)
        axis: str | None = None
        if len(tokens) > SCHEDULE_AXIS_INDEX and tokens[0] == "schedule":
            candidate_axis = tokens[SCHEDULE_AXIS_INDEX]
            if isinstance(candidate_axis, str):
                axis = candidate_axis
        fact_id = fact_targets.get((_substance_id(root, substance_cache, source_path), axis)) if axis else None
        if fact_id:
            result.update({"disposition": "typed_fact", "target_id": fact_id, "scheduling_receipt": "axis-disposition"})
            return result
    if (
        category in {"substance_notes", "product_notes", "component_notes", "concern_text"}
        and result["exact_value_sha256"] in quotation_hashes
    ):
        result.update({"disposition": "raw_quotation", "scheduling_receipt": "quoted-evidence"})
        return result
    exclusion = EXCLUSION_RULES.get(category)
    if exclusion is None:
        raise RuntimeError(f"{atom_id}: no closed rule for {category}")
    result.update({"disposition": "explicit_exclusion", "exclusion": exclusion})
    if category in {"schedule_assertion", "scheduling_assessment", "schedule_prefer_with"}:
        result["scheduling_receipt"] = "axis-disposition"
    return result


def _ruleset() -> dict[str, YamlValue]:
    return {
        "unchanged": "same path and exact canonical value hash in target working tree",
        "source_metadata": "preserve selected source URLs and locators as non-causal metadata",
        "typed_fact": "only pre-deletion canonical-facts subject and axis targets",
        "raw_quotation": "only quotations already carried by canonical-fact provenance",
        "explicit_exclusion": dict(sorted(EXCLUSION_RULES.items())),
    }


def _write_crosswalk(rows: list[dict[str, YamlValue]]) -> tuple[int, str]:
    with TemporaryDirectory(prefix="supp-slotter-migration-crosswalk-") as temporary:
        path = Path(temporary) / "crosswalk.jsonl"
        digest = hashlib.sha256()
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                line = json.dumps(_canonical(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                handle.write(line)
                digest.update(line.encode("utf-8"))
        if len(rows) != len({cast(str, row["atom_id"]) for row in rows}) or not path.stat().st_size:
            raise RuntimeError("crosswalk failed uniqueness or completeness validation")
        return len(rows), digest.hexdigest()


def _validate(rows: list[dict[str, YamlValue]], fact_ids: set[str]) -> None:
    if len(rows) != ORIGINAL_ATOM_COUNT or len({cast(str, row["atom_id"]) for row in rows}) != ORIGINAL_ATOM_COUNT:
        raise RuntimeError("original atoms are not complete and unique")
    if sum(row["original_disposition"] == "sol_adjudication" for row in rows) != ORIGINAL_SOL_COUNT:
        raise RuntimeError("original Sol atoms are not complete")
    if any(row["disposition"] not in ALLOWED_DISPOSITIONS for row in rows):
        raise RuntimeError("unapproved final disposition")
    if any(row["disposition"] == "typed_fact" and row.get("target_id") not in fact_ids for row in rows):
        raise RuntimeError("missing canonical fact target")
    if any(row["disposition"] == "explicit_exclusion" and "exclusion" not in row for row in rows):
        raise RuntimeError("unclosed explicit exclusion")


def build_document(root: Path) -> dict[str, YamlValue]:  # noqa: PLR0914
    root = root.resolve()
    _git(root, "cat-file", "-e", f"{PRE_DELETION_COMMIT}^{{commit}}")
    original = _blob_document(root)
    if original.get("ledger_format") != "legacy-atom-ledger-v2":
        raise RuntimeError("unexpected original ledger format")
    fact_targets, fact_ids, quotation_hashes = _fact_targets(root)
    working_cache: dict[str, YamlValue | object] = {}
    substance_cache: dict[str, str] = {}
    crosswalk: list[dict[str, YamlValue]] = []
    for old_row in _list(original.get("atoms"), source="original atoms"):
        row = _classify(
            root,
            working_cache,
            substance_cache,
            fact_targets,
            quotation_hashes,
            _mapping(old_row, source="original atom"),
        )
        row["original_disposition"] = _string(
            _mapping(old_row, source="original atom").get("disposition"), source="original disposition"
        )
        crosswalk.append(row)
    crosswalk.sort(key=lambda row: cast(str, row["atom_id"]))
    _validate(crosswalk, fact_ids)
    row_count, crosswalk_hash = _write_crosswalk(crosswalk)
    dispositions = Counter(cast(str, row["disposition"]) for row in crosswalk)
    exclusions = Counter(cast(str, row["exclusion"]) for row in crosswalk if row["disposition"] == "explicit_exclusion")
    categories = Counter(cast(str, row["category"]) for row in crosswalk)
    metadata = [row for row in crosswalk if row["disposition"] == "source_metadata"]
    scheduling = [
        row
        for row in crosswalk
        if cast(str, row["category"]) in {"schedule_assertion", "scheduling_assessment", "schedule_prefer_with"}
    ]
    typed_fact_ids = sorted(cast(str, row["target_id"]) for row in crosswalk if row["disposition"] == "typed_fact")
    ruleset = _ruleset()
    return {
        "receipt_format": RECEIPT_FORMAT,
        "acceptance": "complete",
        "forensic_inputs": {
            "pre_deletion_commit": PRE_DELETION_COMMIT,
            "original_ledger_blob": ORIGINAL_LEDGER_BLOB,
            "original_ledger_source_head": _string(original.get("source_head"), source="original source head"),
        },
        "coverage": {
            "original_atom_count": row_count,
            "original_sol_adjudication_count": ORIGINAL_SOL_COUNT,
            "original_atom_id_sha256": _sha256(sorted(cast(str, row["atom_id"]) for row in crosswalk)),
            "crosswalk_sha256": crosswalk_hash,
            "classification_rules_sha256": _sha256(ruleset),
            "category_counts": dict(sorted(categories.items())),
            "final_disposition_counts": dict(sorted(dispositions.items())),
            "closed_exclusion_counts": dict(sorted(exclusions.items())),
        },
        "canonical_fact_links": {"count": len(typed_fact_ids), "fact_ids_sha256": _sha256(typed_fact_ids)},
        "source_metadata": {
            "count": len(metadata),
            "assessment_url_occurrence_count": len(metadata),
            "rows_sha256": _sha256(metadata),
        },
        "scheduling_disposition_link": {
            "format": "canonical-scheduling-migration-v1",
            "covered_original_atom_count": len(scheduling),
            "final_disposition_counts": dict(
                sorted(Counter(cast(str, row["disposition"]) for row in scheduling).items())
            ),
            "rows_sha256": _sha256(scheduling),
        },
        "ruleset": ruleset,
        "temporary_crosswalk": "generated in a TemporaryDirectory, validated, hashed, and removed before receipt emission",
    }


def _dump(document: dict[str, YamlValue]) -> str:
    return yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=120)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="Write the compact receipt here; omit for stdout")
    args = parser.parse_args(argv)
    root = cast(Path, args.root).resolve()
    output = cast(Path | None, args.output)
    try:
        rendered = _dump(build_document(root))
    except (KeyError, OSError, RuntimeError, subprocess.CalledProcessError, TypeError, yaml.YAMLError) as error:
        print(f"migration closure failed closed: {error}", file=sys.stderr)
        return 2
    if output is None:
        sys.stdout.write(rendered)
    else:
        destination = output if output.is_absolute() else root / output
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
