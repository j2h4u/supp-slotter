"""Closed loader for the source-indexed scheduling candidate catalog.

The candidate catalog is evidence and coverage input.  It is deliberately
kept separate from the canonical ontology: a candidate only becomes a
pressure through an independently authored canonical fact and law path.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from planner.contracts import CardLoadError
from planner.yaml_io import load_yaml

CATALOG_FORMAT = "supp-slotter.scheduling-candidates/v1"
DISPOSITIONS = frozenset({"pressure", "neutral", "unresolved_without_direction", "outside_model"})
_SUBJECT_KINDS = frozenset({"product", "substance", "composition_role"})
_SHA256 = frozenset("0123456789abcdef")
_SHA256_HEX_LENGTH = 64


def _fail(path: Path, label: str, message: str) -> CardLoadError:
    return CardLoadError(path, f"{path}: candidate catalog {label} {message}")


def _map(value: object, path: Path, label: str, keys: set[str] | None = None) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(k, str) for k in value):
        raise _fail(path, label, "must be a mapping with string keys")
    result = cast(Mapping[str, object], value)
    if keys is not None and set(result) != keys:
        missing = ", ".join(sorted(keys - set(result)))
        unknown = ", ".join(sorted(set(result) - keys))
        detail = "; ".join(
            part for part in (f"missing {missing}" if missing else "", f"unknown {unknown}" if unknown else "") if part
        )
        raise _fail(path, label, f"has invalid closed shape ({detail})")
    return result


def _str(value: object, path: Path, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise _fail(path, label, "must be a non-blank, unpadded string")
    return value


def _sha(value: object, path: Path, label: str) -> str:
    result = _str(value, path, label)
    if len(result) != _SHA256_HEX_LENGTH or result.lower() != result or any(c not in _SHA256 for c in result):
        raise _fail(path, label, "must be a lowercase SHA-256 digest")
    return result


def _list(value: object, path: Path, label: str) -> list[object]:
    if not isinstance(value, list):
        raise _fail(path, label, "must be a list")
    return cast(list[object], value)


def _string_list(value: object, path: Path, label: str) -> tuple[str, ...]:
    values = tuple(_str(item, path, f"{label}[{index}]") for index, item in enumerate(_list(value, path, label)))
    if len(values) != len(set(values)):
        raise _fail(path, label, "must not contain duplicates")
    return values


@dataclass(frozen=True, slots=True)
class CandidateScope:
    subject_kind: str
    subject_id: str
    applicability_kind: str | None
    applicability_id: str | None
    active_shelf_reachable: bool
    product_ids: tuple[str, ...] = ()
    composition_role_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidatePressure:
    fact_id: str
    law_id: str
    dimension: str
    value: str
    normalized_item: str


@dataclass(frozen=True, slots=True)
class Candidate:
    id: str
    sequence: int
    candidate_type: str
    scope: CandidateScope
    disposition: str
    provenance: Mapping[str, object]
    pressure: CandidatePressure | None = None
    outside_model_reason: str | None = None


@dataclass(frozen=True, slots=True)
class SourceReceipt:
    path: str
    sha256: str
    record_count: int


@dataclass(frozen=True, slots=True)
class CandidateCatalog:
    path: Path
    sha256: str
    candidates: tuple[Candidate, ...]
    source_receipts: tuple[SourceReceipt, ...]

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(candidate.id for candidate in self.candidates)

    @property
    def by_id(self) -> Mapping[str, Candidate]:
        return {candidate.id: candidate for candidate in self.candidates}

    @property
    def disposition_counts(self) -> Mapping[str, int]:
        return {
            disposition: sum(candidate.disposition == disposition for candidate in self.candidates)
            for disposition in sorted(DISPOSITIONS)
        }


def _scope(raw: object, path: Path, label: str) -> CandidateScope:  # noqa: C901
    raw_mapping = _map(raw, path, label)
    if set(raw_mapping) not in ({"subject", "applicability"}, {"subject", "applicability", "active_shelf_reachable"}):
        raise _fail(path, label, "has invalid closed shape")
    mapping = raw_mapping
    subject = _map(mapping["subject"], path, f"{label}.subject")
    if len(subject) != 1 or next(iter(subject)) not in _SUBJECT_KINDS:
        raise _fail(path, f"{label}.subject", "must select exactly one typed subject")
    subject_kind = next(iter(subject))
    subject_id = _str(subject[subject_kind], path, f"{label}.subject.{subject_kind}")
    applicability = _map(mapping["applicability"], path, f"{label}.applicability")
    typed_keys = set(applicability) & _SUBJECT_KINDS
    if typed_keys:
        if set(applicability) != {subject_kind}:
            raise _fail(path, f"{label}.applicability", "must select exactly one typed applicability")
        applicability_kind = subject_kind
        applicability_id = _str(applicability[subject_kind], path, f"{label}.applicability.{subject_kind}")
        if applicability_id != subject_id:
            raise _fail(path, f"{label}.applicability", "must match subject")
        reachable = mapping.get("active_shelf_reachable", True)
        if not isinstance(reachable, bool):
            raise _fail(path, f"{label}.active_shelf_reachable", "must be boolean")
        return CandidateScope(subject_kind, subject_id, applicability_kind, applicability_id, reachable)
    expected = {"active_shelf_reachable", "product_ids", "composition_role_ids"}
    if set(applicability) != expected:
        raise _fail(path, f"{label}.applicability", "has invalid closed shape")
    reachable = applicability["active_shelf_reachable"]
    if not isinstance(reachable, bool):
        raise _fail(path, f"{label}.applicability.active_shelf_reachable", "must be boolean")
    product_ids = _string_list(applicability["product_ids"], path, f"{label}.applicability.product_ids")
    role_ids = _string_list(applicability["composition_role_ids"], path, f"{label}.applicability.composition_role_ids")
    if reachable and not product_ids and not role_ids:
        raise _fail(path, f"{label}.applicability", "reachable scope must name a product or composition role")
    if not reachable and (product_ids or role_ids):
        raise _fail(path, f"{label}.applicability", "unreachable scope cannot name active targets")
    if reachable and subject_kind == "product" and subject_id not in product_ids:
        raise _fail(path, f"{label}.applicability.product_ids", "must include the product subject")
    if reachable and subject_kind == "composition_role" and subject_id not in role_ids:
        raise _fail(path, f"{label}.applicability.composition_role_ids", "must include the composition-role subject")
    return CandidateScope(subject_kind, subject_id, None, None, reachable, product_ids, role_ids)


def _provenance(raw: object, path: Path, label: str) -> Mapping[str, object]:
    mapping = _map(raw, path, label)
    if set(mapping) == {"decision", "source"}:
        _str(mapping["decision"], path, f"{label}.decision")
        source = _map(mapping["source"], path, f"{label}.source")
        expected = {"receipt", "path", "field", "locator", "span_id", "span_sha256"}
        _map(source, path, f"{label}.source", expected)
        for key in ("receipt", "path", "field", "span_id"):
            _str(source[key], path, f"{label}.source.{key}")
        _sha(source["span_sha256"], path, f"{label}.source.span_sha256")
        locator = _map(source["locator"], path, f"{label}.source.locator")
        for key in ("line_start", "line_end", "byte_start", "byte_end"):
            value = locator.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise _fail(path, f"{label}.source.locator.{key}", "must be a non-negative integer")
        return mapping
    if set(mapping) == {"decision", "sources"}:
        _str(mapping["decision"], path, f"{label}.decision")
        for index, item in enumerate(_list(mapping["sources"], path, f"{label}.sources")):
            source = _map(item, path, f"{label}.sources[{index}]")
            if set(source) - {"path", "source", "locator"} or not ({"path", "source"} & set(source)):
                raise _fail(path, f"{label}.sources[{index}]", "must identify a path or source")
            for key in set(source) & {"path", "source", "locator"}:
                if key == "locator":
                    _str(source[key], path, f"{label}.sources[{index}].locator")
                else:
                    _str(source[key], path, f"{label}.sources[{index}].{key}")
        return mapping
    raise _fail(path, label, "must contain exactly decision and one closed source shape")


def _candidate(raw: object, path: Path, index: int, outside_model_reasons: frozenset[str]) -> Candidate:
    label = f"candidates[{index}]"
    mapping = _map(raw, path, label)
    required = {"id", "sequence", "candidate_type", "scope", "disposition", "provenance"}
    optional = {"pressure", "outside_model_reason"}
    if set(mapping) - required - optional or not required <= set(mapping):
        raise _fail(path, label, "has invalid closed shape")
    identifier = _str(mapping["id"], path, f"{label}.id")
    sequence = mapping["sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise _fail(path, f"{label}.sequence", "must be a positive integer")
    candidate_type = _str(mapping["candidate_type"], path, f"{label}.candidate_type")
    scope = _scope(mapping["scope"], path, f"{label}.scope")
    disposition = _str(mapping["disposition"], path, f"{label}.disposition")
    if disposition not in DISPOSITIONS:
        raise _fail(path, f"{label}.disposition", f"must be one of {sorted(DISPOSITIONS)!r}")
    provenance = _provenance(mapping["provenance"], path, f"{label}.provenance")
    pressure_value = mapping.get("pressure")
    pressure = None
    if disposition == "pressure":
        pressure_mapping = _map(
            pressure_value, path, f"{label}.pressure", {"fact_id", "law_id", "dimension", "value", "normalized_item"}
        )
        pressure = CandidatePressure(
            *(
                _str(pressure_mapping[key], path, f"{label}.pressure.{key}")
                for key in ("fact_id", "law_id", "dimension", "value", "normalized_item")
            )
        )
    elif pressure_value is not None:
        raise _fail(path, f"{label}.pressure", "is only valid for pressure dispositions")
    reason_value = mapping.get("outside_model_reason")
    reason = None
    if disposition == "outside_model":
        reason = _str(reason_value, path, f"{label}.outside_model_reason")
        if reason not in outside_model_reasons:
            raise _fail(path, f"{label}.outside_model_reason", "is not a closed outside-model reason")
    elif reason_value is not None:
        raise _fail(path, f"{label}.outside_model_reason", "is only valid for outside_model dispositions")
    return Candidate(identifier, sequence, candidate_type, scope, disposition, provenance, pressure, reason)


def _source_receipts(raw: object, path: Path) -> tuple[SourceReceipt, ...]:
    result: list[SourceReceipt] = []
    seen: set[str] = set()
    for index, item in enumerate(_list(raw, path, "source_receipts")):
        receipt = _source_receipt(item, path, index)
        if receipt.path in seen:
            raise _fail(path, "source_receipts", f"has duplicate path {receipt.path!r}")
        seen.add(receipt.path)
        result.append(receipt)
    return tuple(result)


def _source_receipt(item: object, path: Path, index: int) -> SourceReceipt:
    label = f"source_receipts[{index}]"
    mapping = _map(item, path, label, {"path", "sha256", "record_count"})
    receipt_path = _str(mapping["path"], path, f"{label}.path")
    relative_path = Path(receipt_path)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise _fail(path, f"{label}.path", "must be repository-relative")
    digest = _sha(mapping["sha256"], path, f"{label}.sha256")
    count = mapping["record_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise _fail(path, f"{label}.record_count", "must be a non-negative integer")
    try:
        content = (path.parent.parent / receipt_path).read_bytes()
    except OSError as error:
        raise _fail(path, label, f"cannot read {receipt_path!r}: {error}") from error
    if hashlib.sha256(content).hexdigest() != digest:
        raise _fail(path, label, f"stale hash for {receipt_path!r}")
    records = 0
    for line in content.splitlines():
        try:
            record = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise _fail(path, label, f"malformed JSONL {receipt_path!r}") from error
        if isinstance(record, Mapping) and record.get("record_type") != "summary":
            records += 1
    if records != count:
        raise _fail(path, f"{label}.record_count", f"expected {count}, found {records}")
    return SourceReceipt(receipt_path, digest, count)


def load_candidate_catalog(path: Path | None = None) -> CandidateCatalog:
    """Load and validate the complete candidate catalog and its source receipts."""
    catalog_path = path or Path(__file__).resolve().parents[2] / "data" / "scheduling-candidates.yaml"
    try:
        raw = load_yaml(catalog_path)
    except CardLoadError as error:
        raise _fail(catalog_path, "", f"cannot load: {error.message}") from error
    mapping = _map(raw, catalog_path, "root")
    expected = {
        "format",
        "authority",
        "source_receipts",
        "candidate_count",
        "disposition_counts",
        "outside_model_reasons",
        "candidate_fields",
        "coverage_references",
        "candidates",
    }
    if set(mapping) != expected:
        raise _fail(catalog_path, "root", "has invalid closed shape")
    if mapping["format"] != CATALOG_FORMAT:
        raise _fail(catalog_path, "format", f"must be {CATALOG_FORMAT!r}")
    _map(mapping["authority"], catalog_path, "authority")
    receipts = _source_receipts(mapping["source_receipts"], catalog_path)
    count = mapping["candidate_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise _fail(catalog_path, "candidate_count", "must be a positive integer")
    outside_model_reasons = frozenset(
        _string_list(mapping["outside_model_reasons"], catalog_path, "outside_model_reasons")
    )
    _map(mapping["candidate_fields"], catalog_path, "candidate_fields")
    _map(mapping["coverage_references"], catalog_path, "coverage_references")
    rows = tuple(
        _candidate(item, catalog_path, index, outside_model_reasons)
        for index, item in enumerate(_list(mapping["candidates"], catalog_path, "candidates"))
    )
    if len(rows) != count:
        raise _fail(catalog_path, "candidate_count", f"declares {count}, found {len(rows)}")
    if tuple(row.sequence for row in rows) != tuple(range(1, count + 1)):
        raise _fail(catalog_path, "candidates", "sequences must be contiguous and deterministically ordered")
    if len({row.id for row in rows}) != len(rows):
        raise _fail(catalog_path, "candidates", "must not contain duplicate IDs")
    declared_counts = _map(mapping["disposition_counts"], catalog_path, "disposition_counts")
    if set(declared_counts) != DISPOSITIONS or any(
        declared_counts[key] != sum(row.disposition == key for row in rows) for key in DISPOSITIONS
    ):
        raise _fail(catalog_path, "disposition_counts", "does not match candidate dispositions")
    digest = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    return CandidateCatalog(catalog_path, digest, rows, receipts)


__all__ = [
    "CATALOG_FORMAT",
    "DISPOSITIONS",
    "Candidate",
    "CandidateCatalog",
    "CandidatePressure",
    "CandidateScope",
    "SourceReceipt",
    "load_candidate_catalog",
]
