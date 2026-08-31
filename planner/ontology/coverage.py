"""Derived active-shelf coverage certificates.

Certificates are verification metadata.  They never enter canonical
inference or the optimizer and are recomputed from current inputs on every
planning attempt.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from planner.ontology.candidate_catalog import Candidate, CandidateCatalog
from planner.paths import ROOT
from planner.yaml_io import load_yaml

CLOSURE_FORMAT = "supp-slotter.coverage-closure/v1"
_SHA256_LENGTH = 64
_LEGACY_SPAN_COUNT = 354
_LEGACY_ATOM_COUNT = 1073


@dataclass(frozen=True, slots=True)
class CandidateDisposition:
    candidate_id: str
    disposition: str
    research_open: bool
    evidence_paths: tuple[str, ...] = ()

    @property
    def required_evidence_path(self) -> tuple[str, ...]:
        return self.evidence_paths


@dataclass(frozen=True, slots=True)
class CoverageCertificate:
    """One role-scoped proof that all discovered candidates were assessed."""

    composition_role_id: str
    applicable_dimensions: tuple[str, ...]
    evaluated_candidate_ids: tuple[str, ...]
    dispositions: tuple[CandidateDisposition, ...]
    input_hashes: Mapping[str, str]
    issues: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.issues

    @property
    def research_open_candidate_ids(self) -> tuple[str, ...]:
        return tuple(row.candidate_id for row in self.dispositions if row.research_open)

    @property
    def pressure_candidate_ids(self) -> tuple[str, ...]:
        return tuple(row.candidate_id for row in self.dispositions if row.disposition == "pressure")


@dataclass(frozen=True, slots=True)
class CoverageManifest:
    certificates: tuple[CoverageCertificate, ...]
    input_hashes: Mapping[str, str]
    sha256: str
    issues: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.issues and all(certificate.complete for certificate in self.certificates)

    @property
    def unassessed_candidate_ids(self) -> tuple[str, ...]:
        return tuple(
            issue.removeprefix("unassessed candidate ")
            for issue in self.issues
            if issue.startswith("unassessed candidate ")
        )


@dataclass(frozen=True, slots=True)
class CoverageClosure:
    """Opaque, hash-bound evidence that the global coverage boundary is closed."""

    path: Path
    source_classes: Mapping[str, Mapping[str, object]]
    role_universe_count: int
    role_universe_sha256: str


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != _SHA256_LENGTH or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _require_count(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def load_coverage_closure(path: Path | None = None) -> CoverageClosure:
    """Load the strict closure receipt; prose receipts are never interpreted."""
    closure_path = path or ROOT / "data" / "coverage-closure.yaml"
    raw = load_yaml(closure_path)
    if not isinstance(raw, Mapping):
        raise ValueError(f"{closure_path}: coverage closure must be a mapping")
    if set(raw) != {"format", "source_classes", "role_universe"}:
        raise ValueError(f"{closure_path}: unsupported coverage closure fields")
    if raw.get("format") != CLOSURE_FORMAT:
        raise ValueError(f"{closure_path}: unsupported coverage closure format")
    classes = raw.get("source_classes")
    if not isinstance(classes, Mapping) or set(classes) != {
        "legacy_notes", "active_structured_memberships", "current_relations"
    }:
        raise ValueError(f"{closure_path}: coverage closure requires exactly three source classes")
    validated: dict[str, Mapping[str, object]] = {}
    for name, value in classes.items():
        if not isinstance(name, str) or not isinstance(value, Mapping):
            raise ValueError(f"{closure_path}: malformed source class")
        validated[name] = dict(value)
    role = raw.get("role_universe")
    if not isinstance(role, Mapping) or set(role) != {"count", "sha256"}:
        raise ValueError(f"{closure_path}: malformed role universe closure")
    return CoverageClosure(
        closure_path,
        MappingProxyType(validated),
        _require_count(role.get("count"), "role_universe.count"),
        _require_sha(role.get("sha256"), "role_universe.sha256"),
    )


def role_universe_digest(active_roles: Iterable[object] | Mapping[str, object]) -> tuple[int, str]:
    roles = active_roles.values() if isinstance(active_roles, Mapping) else active_roles
    role_ids = sorted(_role_values(role)[0] for role in roles)
    if len(role_ids) != len(set(role_ids)):
        raise ValueError("active composition role universe contains duplicate IDs")
    return len(role_ids), _digest(role_ids)


def active_membership_digest(
    substances: Mapping[str, object], active_roles: Iterable[object] | Mapping[str, object]
) -> tuple[int, str]:
    """Hash active structured memberships without consulting review prose."""
    roles = active_roles.values() if isinstance(active_roles, Mapping) else active_roles
    memberships: set[tuple[object, ...]] = set()
    for role in roles:
        _role_id, _product_id, substance_id = _role_values(role)
        if substance_id is None:
            continue
        substance = substances.get(substance_id)
        if substance is None:
            raise ValueError(f"active role references missing substance {substance_id!r}")
        assertions = getattr(substance, "knowledge_assertions", None)
        if not isinstance(assertions, Sequence):
            raise ValueError(f"substance {substance_id!r} has no typed knowledge assertions")
        for assertion in assertions:
            category = getattr(assertion, "category", None)
            value = getattr(assertion, "value", None)
            state = getattr(assertion, "research_state", None)
            sources = getattr(assertion, "sources", ())
            if not isinstance(category, str) or not isinstance(value, str) or not isinstance(state, str):
                raise ValueError(f"substance {substance_id!r} has malformed knowledge assertion")
            if not isinstance(sources, Sequence) or isinstance(sources, (str, bytes)):
                raise ValueError(f"substance {substance_id!r} has malformed knowledge sources")
            memberships.add((substance_id, category, value, state, tuple(sources)))
    rows = [list(row) for row in sorted(memberships, key=repr)]
    return len(rows), _digest(rows)


def _selector_digest(selector: object) -> dict[str, object]:
    fields = ("entity_id", "entity_name", "category", "term", "scope")
    return {field: getattr(selector, field, None) for field in fields}


def relation_digest(relations: Iterable[object]) -> tuple[int, str]:
    rows = [
        {
            "id": getattr(relation, "id", None),
            "type": getattr(relation, "type", None),
            "reason": getattr(relation, "reason", None),
            "source_selector": _selector_digest(getattr(relation, "source_selector", None)),
            "target_selector": _selector_digest(getattr(relation, "target_selector", None)),
            "assertion_kind": getattr(relation, "assertion_kind", None),
            "semantic_family": getattr(relation, "semantic_family", None),
            "research_state": getattr(relation, "research_state", None),
            "sources": tuple(getattr(relation, "sources", ())),
        }
        for relation in relations
    ]
    rows.sort(key=lambda row: str(row["id"]))
    return len(rows), _digest(rows)


def _role_values(role: object) -> tuple[str, str | None, str | None]:
    if isinstance(role, str):
        return role, None, None
    if isinstance(role, Mapping):
        role_id = role.get("id") or role.get("composition_role_id")
        product = role.get("product") or role.get("product_id")
        substance = role.get("substance") or role.get("substance_id")
    else:
        role_id = getattr(role, "id", None) or getattr(role, "composition_role_id", None)
        product = getattr(role, "product", None) or getattr(role, "product_id", None)
        substance = getattr(role, "substance", None) or getattr(role, "substance_id", None)
    if not isinstance(role_id, str) or not role_id or role_id != role_id.strip():
        raise ValueError("active composition roles require non-blank IDs")
    return role_id, product if isinstance(product, str) else None, substance if isinstance(substance, str) else None


def _candidate_applies(candidate: Candidate, role_id: str, product_id: str | None, substance_id: str | None) -> bool:
    scope = candidate.scope
    if not scope.active_shelf_reachable:
        return False
    if scope.applicability_kind == "composition_role":
        return scope.applicability_id == role_id
    if scope.applicability_kind == "product":
        return scope.applicability_id == product_id
    if scope.applicability_kind == "substance":
        return scope.applicability_id == substance_id
    return product_id in scope.product_ids or role_id in scope.composition_role_ids


def _dimensions(value: object, candidates: Sequence[Candidate]) -> tuple[str, ...]:
    if value is None:
        return tuple(sorted({row.pressure.dimension for row in candidates if row.pressure is not None}))
    if isinstance(value, Mapping):
        values = tuple(value)
    else:
        dimensions = getattr(value, "dimensions", None)
        if dimensions is not None:
            values = tuple(row.id for row in dimensions)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            values = tuple(value)
        else:
            raise ValueError("coverage dimensions require a mapping or sequence")
    if any(not isinstance(item, str) or not item or item != item.strip() for item in values):
        raise ValueError("coverage dimensions require non-blank IDs")
    if len(set(values)) != len(values):
        raise ValueError("coverage dimensions must not contain duplicates")
    return tuple(sorted(values))


def _base_hashes(catalog: CandidateCatalog) -> dict[str, str]:
    return {
        "candidate_catalog": catalog.sha256,
        **{f"source_receipt:{row.path}": row.sha256 for row in catalog.source_receipts},
    }


def _evidence_paths(candidate: Candidate) -> tuple[str, ...]:
    """Project provenance references into certificate evidence metadata."""
    paths: list[str] = []
    provenance = candidate.provenance
    for key in ("decision", "source", "sources"):
        value = provenance.get(key)
        if isinstance(value, str):
            paths.append(value)
        elif isinstance(value, Mapping):
            paths.extend(_mapping_evidence_paths(value, ("receipt", "path", "span_id")))
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for row in value:
                if isinstance(row, Mapping):
                    paths.extend(_mapping_evidence_paths(row, ("path", "source", "locator")))
    return tuple(paths)


def _mapping_evidence_paths(mapping: Mapping[object, object], keys: Sequence[str]) -> list[str]:
    return [value for key in keys if isinstance(value := mapping.get(key), str)]


def _certificate(
    role_id: str,
    dimensions: tuple[str, ...],
    candidates: tuple[Candidate, ...],
    hashes: Mapping[str, str],
) -> CoverageCertificate:
    ordered = tuple(sorted(candidates, key=lambda row: row.sequence))
    dispositions = tuple(
        CandidateDisposition(
            row.id,
            row.disposition,
            row.disposition == "unresolved_without_direction",
            _evidence_paths(row),
        )
        for row in ordered
    )
    # An empty candidate tuple is a valid, audited result.  The global closure
    # receipt proves that the role universe and passive source classes were
    # inspected; inventing a per-role candidate would turn evidence into an
    # answer and would falsely create optimizer input.
    issues: list[str] = []
    return CoverageCertificate(
        role_id,
        dimensions,
        tuple(row.id for row in ordered),
        dispositions,
        MappingProxyType(dict(hashes)),
        tuple(issues),
    )


def _manifest_hash(certificates: tuple[CoverageCertificate, ...], hashes: Mapping[str, str]) -> str:
    payload = {
        "input_hashes": dict(sorted(hashes.items())),
        "certificates": [
            {
                "composition_role_id": certificate.composition_role_id,
                "applicable_dimensions": certificate.applicable_dimensions,
                "evaluated_candidate_ids": certificate.evaluated_candidate_ids,
                "dispositions": [
                    (row.candidate_id, row.disposition, row.research_open, row.evidence_paths)
                    for row in certificate.dispositions
                ],
                "input_hashes": dict(sorted(certificate.input_hashes.items())),
                "issues": certificate.issues,
            }
            for certificate in certificates
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def derive_coverage(
    catalog: CandidateCatalog,
    active_roles: Iterable[object] | Mapping[str, object],
    *,
    dimensions: object = None,
    input_hashes: Mapping[str, str] | None = None,
) -> CoverageManifest:
    """Derive deterministic certificates for every active composition role."""
    roles = active_roles.values() if isinstance(active_roles, Mapping) else active_roles
    normalized_roles = sorted((_role_values(role) for role in roles), key=lambda row: row[0])
    hashes = dict(_base_hashes(catalog))
    if input_hashes is not None:
        hashes.update(input_hashes)
    certificates: list[CoverageCertificate] = []
    issues: list[str] = []
    for role_id, product_id, substance_id in normalized_roles:
        matching = tuple(
            candidate
            for candidate in catalog.candidates
            if _candidate_applies(candidate, role_id, product_id, substance_id)
        )
        certificate = _certificate(role_id, _dimensions(dimensions, matching), matching, hashes)
        certificates.append(certificate)
    if len({certificate.composition_role_id for certificate in certificates}) != len(certificates):
        issues.append("duplicate active composition role")
    manifest_certificates = tuple(certificates)
    return CoverageManifest(
        manifest_certificates,
        MappingProxyType(dict(hashes)),
        _manifest_hash(manifest_certificates, hashes),
        tuple(issues),
    )


def validate_candidate_references(
    catalog: CandidateCatalog, active_roles: Iterable[object] | Mapping[str, object]
) -> tuple[str, ...]:
    """Reject active candidates that cannot reach any active composition role."""
    roles = active_roles.values() if isinstance(active_roles, Mapping) else active_roles
    normalized_roles = tuple(_role_values(role) for role in roles)
    errors = [
        f"orphan active candidate {candidate.id}"
        for candidate in catalog.candidates
        if candidate.scope.active_shelf_reachable
        and not any(
            _candidate_applies(candidate, role_id, product_id, substance_id)
            for role_id, product_id, substance_id in normalized_roles
        )
    ]
    return tuple(errors)


def validate_coverage_certificate(
    certificate: CoverageCertificate,
    catalog: CandidateCatalog,
    *,
    input_hashes: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Return deterministic validation errors for a certificate."""
    expected = dict(_base_hashes(catalog))
    if input_hashes is not None:
        expected.update(input_hashes)
    errors: list[str] = []
    if dict(certificate.input_hashes) != expected:
        errors.append("stale coverage certificate input hashes")
    known = catalog.by_id
    if len(set(certificate.evaluated_candidate_ids)) != len(certificate.evaluated_candidate_ids):
        errors.append("duplicate evaluated candidate IDs")
    if any(identifier not in known for identifier in certificate.evaluated_candidate_ids):
        errors.append("unknown evaluated candidate ID")
    disposition_ids = tuple(row.candidate_id for row in certificate.dispositions)
    if disposition_ids != certificate.evaluated_candidate_ids:
        errors.append("candidate dispositions do not exactly cover evaluated IDs")
    for row in certificate.dispositions:
        errors.extend(_validate_disposition(row, known.get(row.candidate_id)))
    return tuple(errors)


def _validate_disposition(row: CandidateDisposition, candidate: Candidate | None) -> list[str]:
    if candidate is None:
        return []
    errors: list[str] = []
    if row.disposition != candidate.disposition:
        errors.append(f"mutated disposition for candidate {row.candidate_id}")
    if row.research_open != (row.disposition == "unresolved_without_direction"):
        errors.append(f"invalid research state for candidate {row.candidate_id}")
    if row.evidence_paths != _evidence_paths(candidate):
        errors.append(f"mutated evidence path for candidate {row.candidate_id}")
    return errors


def validate_coverage_manifest(
    manifest: CoverageManifest,
    catalog: CandidateCatalog,
    *,
    input_hashes: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    errors: list[str] = []
    expected = dict(_base_hashes(catalog))
    try:
        expected["candidate_catalog"] = hashlib.sha256(catalog.path.read_bytes()).hexdigest()
        for receipt in catalog.source_receipts:
            receipt_path = catalog.path.parent.parent / receipt.path
            expected[f"source_receipt:{receipt.path}"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    except OSError as error:
        errors.append(f"coverage input unavailable: {error}")
    if input_hashes is not None:
        expected.update(input_hashes)
    if dict(manifest.input_hashes) != expected:
        errors.append("stale coverage manifest input hashes")
    for certificate in manifest.certificates:
        errors.extend(validate_coverage_certificate(certificate, catalog, input_hashes=input_hashes))
        errors.extend(certificate.issues)
    if manifest.sha256 != _manifest_hash(manifest.certificates, manifest.input_hashes):
        errors.append("coverage manifest hash mismatch")
    errors.extend(manifest.issues)
    return tuple(dict.fromkeys(errors))


def _closure_path(closure: CoverageClosure, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value or value.startswith("/") or ".." in Path(value).parts:
        raise ValueError(f"{label} must be a repository-relative path")
    return closure.path.parent.parent / value


def _closure_receipt_hash(closure: CoverageClosure, record: object, label: str) -> tuple[Path, str, int]:
    if not isinstance(record, Mapping) or not {"path", "sha256", "record_count"}.issubset(record):
        raise ValueError(f"{label} must contain path, sha256, and record_count")
    path = _closure_path(closure, record.get("path"), f"{label}.path")
    digest = _require_sha(record.get("sha256"), f"{label}.sha256")
    count = _require_count(record.get("record_count"), f"{label}.record_count")
    return path, digest, count


def _check_receipt(closure: CoverageClosure, record: object, label: str, errors: list[str]) -> int | None:
    try:
        path, expected, count = _closure_receipt_hash(closure, record, label)
    except ValueError as error:
        errors.append(str(error))
        return None
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        errors.append(f"coverage closure {label} unavailable: {error}")
        return None
    if actual != expected:
        errors.append(f"coverage closure stale source class: {label}")
    return count


def validate_coverage_closure(  # noqa: C901, PLR0912, PLR0915
    closure: CoverageClosure,
    catalog: CandidateCatalog,
    active_roles: Iterable[object] | Mapping[str, object],
    *,
    substances: Mapping[str, object] | None = None,
    relations: Iterable[object] | None = None,
) -> tuple[str, ...]:
    """Validate global closure receipts against freshly derived runtime inputs."""
    errors: list[str] = []
    classes = closure.source_classes
    legacy = classes.get("legacy_notes", {})
    memberships = classes.get("active_structured_memberships", {})
    current_relations = classes.get("current_relations", {})
    try:
        if set(legacy) != {
            "span_count", "atom_count", "aggregate_migration_sha256", "candidate_catalog_sha256", "migration_receipt"
        }:
            raise ValueError("coverage closure legacy_notes has unsupported or missing fields")
        if _require_count(legacy.get("span_count"), "legacy_notes.span_count") != _LEGACY_SPAN_COUNT:
            raise ValueError("coverage closure legacy_notes span count is not 354")
        if _require_count(legacy.get("atom_count"), "legacy_notes.atom_count") != _LEGACY_ATOM_COUNT:
            raise ValueError("coverage closure legacy_notes atom count is not 1073")
        _require_sha(legacy.get("aggregate_migration_sha256"), "legacy_notes.aggregate_migration_sha256")
        if legacy.get("candidate_catalog_sha256") != catalog.sha256:
            raise ValueError("coverage closure stale source class: legacy_notes candidate catalog")
        _check_receipt(closure, legacy.get("migration_receipt"), "legacy_notes.migration_receipt", errors)
    except ValueError as error:
        errors.append(str(error))
    try:
        if set(memberships) != {
            "membership_count", "current_derived_sha256", "adjudication_receipt"
        }:
            raise ValueError("coverage closure active_structured_memberships has unsupported or missing fields")
        count = _require_count(memberships.get("membership_count"), "active_structured_memberships.membership_count")
        if substances is None:
            raise ValueError("coverage closure active_structured_memberships requires substances")
        actual_count, actual_digest = active_membership_digest(substances, active_roles)
        if count != actual_count or memberships.get("current_derived_sha256") != actual_digest:
            raise ValueError("coverage closure stale source class: active_structured_memberships")
        receipt_count = _check_receipt(
            closure,
            memberships.get("adjudication_receipt"),
            "active_structured_memberships.adjudication_receipt",
            errors,
        )
        if receipt_count is not None and receipt_count != count:
            errors.append("coverage closure active_structured_memberships receipt count mismatch")
    except ValueError as error:
        errors.append(str(error))
    try:
        if set(current_relations) != {"relation_count", "current_derived_sha256", "pairwise_decision_receipt"}:
            raise ValueError("coverage closure current_relations has unsupported or missing fields")
        count = _require_count(current_relations.get("relation_count"), "current_relations.relation_count")
        if relations is None:
            raise ValueError("coverage closure current_relations requires relations")
        actual_count, actual_digest = relation_digest(relations)
        if count != actual_count or current_relations.get("current_derived_sha256") != actual_digest:
            raise ValueError("coverage closure stale source class: current_relations")
        pairwise = current_relations.get("pairwise_decision_receipt")
        receipt_count = _check_receipt(closure, pairwise, "current_relations.pairwise_decision_receipt", errors)
        admitted = pairwise.get("admitted_pairwise_count") if isinstance(pairwise, Mapping) else None
        if isinstance(admitted, bool) or not isinstance(admitted, int) or admitted != 0:
            errors.append("coverage closure current_relations admitted_pairwise_count must be zero")
        if receipt_count is not None and receipt_count != count:
            errors.append("coverage closure current_relations receipt count mismatch")
    except ValueError as error:
        errors.append(str(error))
    try:
        count, digest = role_universe_digest(active_roles)
        if count != closure.role_universe_count or digest != closure.role_universe_sha256:
            errors.append("coverage closure stale role universe")
    except ValueError as error:
        errors.append(str(error))
    return tuple(dict.fromkeys(errors))


# Descriptive aliases used by command/integration callers.
derive_coverage_manifest = derive_coverage
build_coverage_manifest = derive_coverage


__all__ = [
    "CandidateDisposition",
    "CoverageCertificate",
    "CoverageClosure",
    "CoverageManifest",
    "active_membership_digest",
    "build_coverage_manifest",
    "derive_coverage",
    "derive_coverage_manifest",
    "load_coverage_closure",
    "relation_digest",
    "role_universe_digest",
    "validate_candidate_references",
    "validate_coverage_certificate",
    "validate_coverage_closure",
    "validate_coverage_manifest",
]
