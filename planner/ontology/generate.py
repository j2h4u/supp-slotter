"""Deterministic build of the committed executable ontology artifacts.

This module is generation-only: it imports LinkML to prove and inspect the
authored schema, while normal planner runtime paths only read the resulting
runtime-vocabulary YAML and RDF/SHACL artifacts.
"""

# ruff: noqa: C901, PLR0912

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

import yaml
from linkml_runtime.utils.schemaview import SchemaView

from planner.ontology.errors import OntologyInfrastructureError

_BASE_IRI_KEY = "base_iri"
_MANIFEST_NAME = "manifest.yaml"
_GENERATED_DIR = "generated"
_RUNTIME_FORMAT = "supp-slotter.runtime-vocabulary/v2"
_ALLOWED_SCOPE_KEYS = {"planner", "food_model", "slot_model", "intended_use", "substrate", "product", "formulation"}
_POLICY_STATUSES = {"approved", "review_pending", "retired"}
_POLICY_ENFORCEMENTS = {"none", "preference", "advisory", "block"}
_POLICY_TERM_CATEGORIES = {"intake": "schedule_rule", "timing": "schedule_rule", "activity": "schedule_rule"}
_POLICY_SEMANTIC_CATEGORIES = {"schedule_rule", "risk"}
_ASSERTION_KINDS_BY_CATEGORY = {"context": {"clinical_exposure_context"}}
_ASSERTION_FAMILIES_BY_TYPE = {
    "balance": {"nutrient_balance_review_signal"},
    "supports": {
        "biochemical_mechanism_assertion",
        "absorption_interaction_claim",
        "nutritional_adequacy_advisory",
    },
    "review_with": {"clinical_review_signal"},
}
_ASSERTION_KIND_BY_TYPE = {
    "balance": "clinical_review_signal",
    "supports": "ontology_assertion",
    "review_with": "clinical_review_signal",
}


def generate_ontology(ontology_root: Path, *, check: bool = False) -> None:
    """Generate or freshness-check all artifacts declared by the manifest."""
    manifest = _load_manifest(ontology_root)
    _validate_linkml_root(ontology_root, manifest)
    artifact_bytes = _render_artifacts(ontology_root, manifest)
    generated_dir = ontology_root / _GENERATED_DIR
    if check:
        _check_fresh(generated_dir, artifact_bytes)
        return
    generated_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, content in artifact_bytes.items():
        target = generated_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def _load_manifest(ontology_root: Path) -> dict[str, object]:
    manifest_path = ontology_root / _MANIFEST_NAME
    if not manifest_path.is_file():
        raise OntologyInfrastructureError(f"Missing canonical ontology manifest: {manifest_path}")
    try:
        loaded = _safe_yaml_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise OntologyInfrastructureError(f"Invalid ontology manifest {manifest_path}: {error}") from error
    if not isinstance(loaded, dict):
        raise OntologyInfrastructureError(f"Ontology manifest must be a mapping: {manifest_path}")
    required = {
        "schema_version",
        _BASE_IRI_KEY,
        "linkml_root",
        "linkml_modules",
        "policy_sources",
        "constraint_sources",
        "assertion_sources",
        "custom_shapes",
    }
    missing = sorted(required - loaded.keys())
    if missing:
        raise OntologyInfrastructureError(f"Ontology manifest is missing required keys: {', '.join(missing)}")
    if loaded[_BASE_IRI_KEY] != "https://j2h4u.github.io/supp-slotter/ontology/v1/":
        raise OntologyInfrastructureError("Ontology manifest has a non-canonical ss base IRI")
    return cast(dict[str, object], loaded)


def _validate_linkml_root(ontology_root: Path, manifest: Mapping[str, object]) -> None:
    root = ontology_root / _required_string(manifest, "linkml_root")
    if not root.is_file():
        raise OntologyInfrastructureError(f"Missing LinkML root declared by manifest: {root}")
    try:
        schema_view = SchemaView(str(root))
        schema = schema_view.schema
    except Exception as error:  # LinkML owns parser/compiler failure details.
        raise OntologyInfrastructureError(f"LinkML cannot load canonical root {root}: {error}") from error
    base_iri = _required_string(manifest, _BASE_IRI_KEY)
    schema_id = schema.id if schema is not None else None
    if schema_id != base_iri:
        raise OntologyInfrastructureError(
            f"LinkML root id must equal canonical ss base IRI ({base_iri}), got {schema_id}"
        )


def _render_artifacts(ontology_root: Path, manifest: Mapping[str, object]) -> dict[Path, bytes]:
    source_hash = _source_hash(ontology_root, manifest)
    vocabulary = _load_yaml_mapping(ontology_root / "vocabulary.yaml")
    terms = _normalized_terms(vocabulary)
    categories = _required_mapping(vocabulary, "semantic_categories")
    scheduling_policies = _load_scheduling_policies(ontology_root, manifest, terms)
    audit_review_rules = _load_audit_review_rules(ontology_root, manifest)
    evidence_catalog = _load_evidence_catalog(ontology_root)
    audit_relation_exemptions = _load_audit_relation_exemptions(ontology_root, manifest)
    scheduling_constraints = _load_scheduling_constraints(ontology_root, manifest, terms)
    ontology_assertions = _load_ontology_assertions(ontology_root, manifest, terms)
    base_iri = _required_string(manifest, _BASE_IRI_KEY)
    header = _header(manifest, source_hash)
    runtime_vocabulary: object = {
        "format": _RUNTIME_FORMAT,
        "schema_version": str(manifest["schema_version"]),
        "base_iri": base_iri,
        "source_hash": source_hash,
        "categories": categories,
        "terms": terms,
        "slot_policy_evidence": evidence_catalog,
        "scheduling_policies": scheduling_policies,
        "audit_review_rules": audit_review_rules,
        "audit_relation_exemptions": audit_relation_exemptions,
        "scheduling_constraints": scheduling_constraints,
        "ontology_assertions": ontology_assertions,
    }
    semantic_shapes = _read_custom_shapes(ontology_root, manifest, base_iri)
    card_schema = cast(
        object,
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"{base_iri}generated/card.schema.json",
            "title": "Supp Slotter canonical card",
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "string", "pattern": "^(sub|prd)_[a-z0-9]+$"},
                "name": {"type": "string", "minLength": 1},
                "knowledge": {
                    "type": "object",
                    "properties": {
                        category: {"type": "array", "items": {"type": "string"}}
                        for category in sorted(categories)
                        if category != "schedule_rule"
                    },
                    "additionalProperties": False,
                },
                "schedule": {"type": "object"},
                "schedule_governance": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "required": ["status", "enforcement_cap", "scope", "evidence", "owner", "review_by"],
                        "properties": {
                            "status": {"enum": sorted(_POLICY_STATUSES)},
                            "enforcement_cap": {"enum": sorted(_POLICY_ENFORCEMENTS)},
                            "scope": {
                                "type": "object",
                                "minProperties": 1,
                                "additionalProperties": {"type": "string", "minLength": 1},
                            },
                            "evidence": {"type": "array"},
                            "owner": {"type": "string", "minLength": 1},
                            "review_by": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                            "evidence_gap": {"type": "string", "minLength": 1},
                            "retirement_reason": {"type": "string", "minLength": 1},
                        },
                        "additionalProperties": False,
                    },
                },
            },
        },
    )
    return {
        Path("card.schema.json"): _json_bytes(card_schema, header),
        Path("ontology.ttl"): _ttl_bytes(header, base_iri, categories, terms),
        Path("shapes.ttl"): _shapes_bytes(header, base_iri, semantic_shapes),
        Path("runtime-vocabulary.yaml"): _yaml_bytes(runtime_vocabulary),
    }


def _source_hash(ontology_root: Path, manifest: Mapping[str, object]) -> str:
    paths = [_MANIFEST_NAME]
    paths.extend(_required_string_list(manifest, "linkml_modules"))
    paths.extend(_required_string_list(manifest, "policy_sources"))
    paths.extend(_required_string_list(manifest, "constraint_sources"))
    paths.extend(_required_string_list(manifest, "assertion_sources"))
    paths.extend(_required_string_list(manifest, "custom_shapes"))
    digest = hashlib.sha256()
    for relative_path in paths:
        path = ontology_root / relative_path
        if not path.is_file():
            raise OntologyInfrastructureError(f"Manifest declares missing ontology source: {path}")
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _normalized_terms(vocabulary: Mapping[str, object]) -> list[dict[str, object]]:
    categories = _required_mapping(vocabulary, "semantic_categories")
    raw_terms = vocabulary.get("terms")
    if not isinstance(raw_terms, list):
        raise OntologyInfrastructureError("vocabulary.yaml terms must be a list")
    normalized: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for raw_term in raw_terms:
        if not isinstance(raw_term, dict):
            raise OntologyInfrastructureError("Each ontology term must be a mapping")
        term = cast(dict[str, object], raw_term)
        slug = _required_string(term, "slug")
        category = _required_string(term, "semantic_category")
        if category not in categories:
            raise OntologyInfrastructureError(f"Term {slug!r} has unknown semantic category {category!r}")
        key = (category, slug)
        if key in seen:
            raise OntologyInfrastructureError(f"Duplicate ontology term {category}:{slug}")
        seen.add(key)
        category_metadata = _required_mapping(cast(Mapping[str, object], categories), category)
        assertion_kind = term.get("assertion_kind")
        if assertion_kind is not None:
            allowed_assertion_kinds = _ASSERTION_KINDS_BY_CATEGORY.get(category, set())
            if not isinstance(assertion_kind, str) or assertion_kind not in allowed_assertion_kinds:
                raise OntologyInfrastructureError(
                    f"Term {category}:{slug} has assertion_kind incompatible with its semantic category"
                )
        normalized_term: dict[str, object] = {
            "slug": slug,
            "label": _required_string(term, "label"),
            "description": _required_string(term, "description"),
            "semantic_category": category,
            "allowed_predicates": _required_string_list(category_metadata, "allowed_predicates"),
            "ontoclean_profile": _required_string(category_metadata, "ontoclean_profile"),
        }
        if assertion_kind is not None:
            normalized_term["assertion_kind"] = assertion_kind
        normalized.append(normalized_term)
    return sorted(normalized, key=lambda item: (str(item["semantic_category"]), str(item["slug"])))


def _load_scheduling_policies(
    ontology_root: Path, manifest: Mapping[str, object], terms: Sequence[Mapping[str, object]]
) -> dict[str, dict[str, object]]:
    """Load the planner policy contract from manifest-owned canonical sources.

    The deliberately broad name includes risk warnings: they are planner policy
    facts, even though they do not affect slot scoring.  Runtime consumers get a
    stable flat ``category:term`` key and never need a separate card registry.
    """
    known_terms = {(str(term["semantic_category"]), str(term["slug"])): term for term in terms}
    policies: dict[str, dict[str, object]] = {}
    for relative_path in _required_string_list(manifest, "policy_sources"):
        source = _load_yaml_mapping(ontology_root / relative_path)
        raw_policies = _required_mapping(source, "scheduling_policies")
        governance = _policy_governance_defaults(source, relative_path)
        evidence_catalog = _required_mapping(source, "slot_policy_evidence")
        for key, raw_policy in raw_policies.items():
            if not isinstance(key, str) or key.count(":") != 1:
                raise OntologyInfrastructureError(f"Policy key must be category:term in {relative_path}: {key!r}")
            category, term = key.split(":", maxsplit=1)
            term_metadata = known_terms.get((_POLICY_TERM_CATEGORIES.get(category, category), term))
            if term_metadata is None:
                raise OntologyInfrastructureError(f"Policy {key!r} has no controlled vocabulary term")
            if str(term_metadata["semantic_category"]) not in _POLICY_SEMANTIC_CATEGORIES:
                raise OntologyInfrastructureError(
                    f"Policy {key!r} must target a schedule_rule or risk term, not a biological or context assertion"
                )
            if key in policies:
                raise OntologyInfrastructureError(f"Duplicate canonical scheduling policy {key!r}")
            if not isinstance(raw_policy, dict):
                raise OntologyInfrastructureError(f"Policy {key!r} must be a mapping")
            policies[key] = _normalize_scheduling_policy(
                key, cast(Mapping[str, object], raw_policy), term_metadata, governance, evidence_catalog
            )
    return dict(sorted(policies.items()))


def _load_audit_review_rules(ontology_root: Path, manifest: Mapping[str, object]) -> list[dict[str, object]]:
    rules: list[dict[str, object]] = []
    seen: set[str] = set()
    for relative_path in _required_string_list(manifest, "policy_sources"):
        source = _load_yaml_mapping(ontology_root / relative_path)
        raw_rules = _required_mapping(source, "audit_review_rules")
        evidence_catalog = _required_mapping(source, "slot_policy_evidence")
        for rule_id, raw in raw_rules.items():
            if not isinstance(rule_id, str) or not rule_id.startswith("audit_") or rule_id in seen:
                raise OntologyInfrastructureError(
                    f"Audit review rule id must be unique and start with audit_: {rule_id!r}"
                )
            if not isinstance(raw, dict):
                raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} must be a mapping")
            raw_mapping = cast(Mapping[str, object], raw)
            allowed = {
                "priority",
                "selector",
                "accepted_intake",
                "message",
                "action",
                "effects",
                "status",
                "enforcement",
                "scope",
                "evidence",
                "owner",
                "review_by",
                "evidence_gap",
                "retirement_reason",
            }
            extras = sorted(set(raw_mapping) - allowed)
            if extras:
                raise OntologyInfrastructureError(
                    f"Audit review rule {rule_id!r} has unsupported fields: {', '.join(extras)}"
                )
            selector = _normalize_audit_selector(rule_id, raw_mapping.get("selector"))
            priority = raw_mapping.get("priority")
            if not isinstance(priority, int) or isinstance(priority, bool) or priority < 0:
                raise OntologyInfrastructureError(
                    f"Audit review rule {rule_id!r} priority must be a non-negative integer"
                )
            accepted = raw_mapping.get("accepted_intake")
            if (
                not isinstance(accepted, list)
                or ((raw_mapping.get("status") != "retired") and not accepted)
                or any(not isinstance(v, str) or not v for v in accepted)
            ):
                raise OntologyInfrastructureError(
                    f"Audit review rule {rule_id!r} accepted_intake must be a non-empty list of strings"
                )
            accepted_values = sorted({v for v in accepted if isinstance(v, str)})
            normalized: dict[str, object] = {
                "id": rule_id,
                "priority": priority,
                "selector": selector,
                "accepted_intake": accepted_values,
                "message": _required_string(raw_mapping, "message"),
                "action": _required_string(raw_mapping, "action"),
                **_normalize_record_governance(
                    f"audit rule {rule_id}",
                    raw_mapping,
                    evidence_catalog,
                    effects=[],
                    warning=raw_mapping.get("enforcement") == "advisory",
                ),
            }
            rules.append(normalized)
            seen.add(rule_id)
    return sorted(rules, key=lambda item: str(item["id"]))


def _load_audit_relation_exemptions(ontology_root: Path, manifest: Mapping[str, object]) -> list[dict[str, object]]:
    exemptions: list[dict[str, object]] = []
    seen: set[str] = set()
    seen_selectors: set[tuple[str, str, str]] = set()
    for relative_path in _required_string_list(manifest, "policy_sources"):
        source = _load_yaml_mapping(ontology_root / relative_path)
        raw_exemptions = _required_mapping(source, "audit_relation_exemptions")
        governance = _policy_governance_defaults(source, relative_path)
        for exemption_id, raw in raw_exemptions.items():
            if (
                not isinstance(exemption_id, str)
                or not exemption_id.startswith("audit_relation_")
                or exemption_id in seen
            ):
                raise OntologyInfrastructureError(
                    f"Audit relation exemption id must be unique and start with audit_relation_: {exemption_id!r}"
                )
            if not isinstance(raw, dict):
                raise OntologyInfrastructureError(f"Audit relation exemption {exemption_id!r} must be a mapping")
            raw_mapping = cast(Mapping[str, object], raw)
            allowed = {"relation_type", "source_selector_key", "target_selector_key", "rationale", "action"}
            extras = sorted(set(raw_mapping) - allowed)
            if extras:
                raise OntologyInfrastructureError(
                    f"Audit relation exemption {exemption_id!r} has unsupported fields: {', '.join(extras)}"
                )
            relation_type = _required_string(raw_mapping, "relation_type")
            source_key = _required_string(raw_mapping, "source_selector_key")
            target_key = _required_string(raw_mapping, "target_selector_key")
            selector_key = (relation_type, source_key, target_key)
            if selector_key in seen_selectors:
                raise OntologyInfrastructureError(
                    f"Duplicate audit relation exemption selector: {relation_type} {source_key} -> {target_key}"
                )
            normalized: dict[str, object] = {
                "id": exemption_id,
                "relation_type": relation_type,
                "source_selector_key": source_key,
                "target_selector_key": target_key,
                "rationale": _required_string(raw_mapping, "rationale"),
                "action": _required_string(raw_mapping, "action"),
                **governance,
            }
            exemptions.append(normalized)
            seen.add(exemption_id)
            seen_selectors.add(selector_key)
    return sorted(exemptions, key=lambda item: str(item["id"]))


def _normalize_audit_selector(rule_id: str, raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} selector must be a mapping")
    raw_mapping = cast(Mapping[str, object], raw)
    allowed = {"field", "contains", "condition"}
    if (
        set(raw_mapping) - allowed
        or not isinstance(raw_mapping.get("field"), str)
        or raw_mapping.get("field") not in {"kind", "quality"}
    ):
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} selector has invalid fields")
    if not isinstance(raw_mapping.get("contains"), str) or not raw_mapping["contains"]:
        raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} selector contains must be non-empty")
    out: dict[str, object] = {"field": raw_mapping["field"], "contains": raw_mapping["contains"]}
    condition = raw_mapping.get("condition")
    if condition is not None:
        if not isinstance(condition, dict):
            raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} condition is invalid")
        condition_mapping = cast(Mapping[str, object], condition)
        if set(condition_mapping) - {"field", "contains", "not_contains"}:
            raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} condition is invalid")
        if condition_mapping.get("field") != "effect" or ("contains" not in condition_mapping) == (
            "not_contains" not in condition_mapping
        ):
            raise OntologyInfrastructureError(
                f"Audit review rule {rule_id!r} condition must target effect with one operator"
            )
        value = condition_mapping.get("contains", condition_mapping.get("not_contains"))
        if not isinstance(value, str) or not value:
            raise OntologyInfrastructureError(f"Audit review rule {rule_id!r} condition value must be non-empty")
        out["condition"] = dict(condition_mapping)
    return out


def _policy_governance_defaults(source: Mapping[str, object], relative_path: str) -> dict[str, object]:
    raw = source.get("governance_defaults")
    if isinstance(raw, dict):
        return cast(dict[str, object], raw)
    return {}


def _normalize_scheduling_policy(
    key: str,
    raw: Mapping[str, object],
    term_metadata: Mapping[str, object],
    governance: Mapping[str, object],
    evidence_catalog: Mapping[str, object],
) -> dict[str, object]:
    allowed = {
        "applies_when",
        "effects",
        "warning",
        "action",
        "status",
        "enforcement",
        "scope",
        "evidence",
        "owner",
        "review_by",
        "evidence_gap",
        "retirement_reason",
    }
    extras = sorted(set(raw) - allowed)
    if extras:
        raise OntologyInfrastructureError(f"Policy {key!r} has unsupported fields: {', '.join(extras)}")
    normalized: dict[str, object] = {
        "label": _required_string(term_metadata, "label"),
        "description": _required_string(term_metadata, "description"),
        "applies_when": _required_string(raw, "applies_when"),
    }
    effects_raw = raw.get("effects", [])
    if not isinstance(effects_raw, list):
        raise OntologyInfrastructureError(f"Policy {key!r} effects must be a list")
    normalized["effects"] = [_normalize_policy_effect(key, cast(object, item)) for item in effects_raw]
    warning = raw.get("warning", False)
    if not isinstance(warning, bool):
        raise OntologyInfrastructureError(f"Policy {key!r} warning must be boolean")
    normalized["warning"] = warning
    action = raw.get("action")
    if action is not None:
        if not isinstance(action, str) or not action:
            raise OntologyInfrastructureError(f"Policy {key!r} action must be a non-empty string")
        normalized["action"] = action
    normalized.update(
        _normalize_record_governance(
            f"policy {key}", raw, evidence_catalog, effects=cast(list[object], normalized["effects"]), warning=warning
        )
    )
    return normalized


def _load_evidence_catalog(ontology_root: Path) -> dict[str, dict[str, object]]:
    source = _load_yaml_mapping(ontology_root / "policies.yaml")
    raw = _required_mapping(source, "slot_policy_evidence")
    out: dict[str, dict[str, object]] = {}
    for key, item in raw.items():
        if not isinstance(key, str) or not isinstance(item, dict):
            raise OntologyInfrastructureError("Evidence catalog keys and records must be mappings")
        record = cast(Mapping[str, object], item)
        allowed = {"kind", "url", "ref", "title", "supports", "limitations"}
        if set(record) - allowed or ("url" in record) == ("ref" in record):
            raise OntologyInfrastructureError(f"Evidence {key!r} must contain exactly one of url/ref")
        kind = _required_string(record, "kind")
        if kind not in {
            "authoritative_instruction",
            "primary_human",
            "systematic_review",
            "regulatory_context",
            "operational_contract",
        }:
            raise OntologyInfrastructureError(f"Evidence {key!r} has invalid kind")
        if "url" in record:
            value = _required_string(record, "url")
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.netloc:
                raise OntologyInfrastructureError(f"Evidence {key!r} url must be HTTPS")
        else:
            value = _required_string(record, "ref")
            if value.startswith(("/", "http")):
                raise OntologyInfrastructureError(f"Evidence {key!r} ref must be repository-relative")
        for text_field in ("title", "supports", "limitations"):
            _required_string(record, text_field)
        out[key] = {
            k: record[k] for k in ("kind", "url" if "url" in record else "ref", "title", "supports", "limitations")
        }
    return dict(sorted(out.items()))


def _normalize_record_governance(
    context: str,
    raw: Mapping[str, object],
    catalog: Mapping[str, object],
    *,
    effects: list[object],
    warning: bool = False,
) -> dict[str, object]:
    status = _required_string(raw, "status")
    enforcement = _required_string(raw, "enforcement")
    if status not in _POLICY_STATUSES or enforcement not in _POLICY_ENFORCEMENTS:
        raise OntologyInfrastructureError(f"{context} has invalid status/enforcement")
    scope = cast(Mapping[str, object], _required_mapping(raw, "scope"))
    if not scope or set(scope) - _ALLOWED_SCOPE_KEYS or any(not isinstance(v, str) or not v for v in scope.values()):
        raise OntologyInfrastructureError(f"{context} has invalid scope")
    evidence = raw.get("evidence")
    if not isinstance(evidence, list):
        raise OntologyInfrastructureError(f"{context} evidence must be a list")
    for item_obj in cast(list[object], evidence):
        if not isinstance(item_obj, dict):
            raise OntologyInfrastructureError(
                f"{context} evidence entries must be source/supports/limitations mappings"
            )
        item = cast(Mapping[str, object], item_obj)
        if set(item) - {"source", "supports", "limitations"}:
            raise OntologyInfrastructureError(
                f"{context} evidence entries must be source/supports/limitations mappings"
            )
        source = item.get("source")
        if not isinstance(source, str) or source not in catalog:
            raise OntologyInfrastructureError(f"{context} references unknown evidence source {source!r}")
        if (
            not isinstance(item.get("supports"), str)
            or not item["supports"]
            or not isinstance(item.get("limitations"), str)
            or not item["limitations"]
        ):
            raise OntologyInfrastructureError(f"{context} evidence entries require supports and limitations")
    if status == "approved" and not evidence:
        raise OntologyInfrastructureError(f"{context} approved records require non-empty evidence")
    if status == "review_pending" and not evidence and not raw.get("evidence_gap"):
        raise OntologyInfrastructureError(f"{context} pending records require evidence or evidence_gap")
    if status == "retired" and (effects or warning or enforcement != "none"):
        raise OntologyInfrastructureError(
            f"{context} retired records must have empty effects, no warning, and enforcement none"
        )
    if status == "review_pending" and enforcement == "block":
        raise OntologyInfrastructureError(f"{context} review_pending records cannot block")
    if "review_by" not in raw or not isinstance(raw["review_by"], str) or len(raw["review_by"]) != 10:  # noqa: PLR2004
        raise OntologyInfrastructureError(f"{context} review_by must be YYYY-MM-DD")
    declared = (
        "block"
        if any(isinstance(e, dict) and cast(Mapping[str, object], e).get("block") is True for e in effects)
        else ("preference" if effects else ("advisory" if warning else "none"))
    )
    if declared != enforcement:
        raise OntologyInfrastructureError(f"{context} enforcement does not match effects")
    result = {
        "status": status,
        "enforcement": enforcement,
        "scope": dict(scope),
        "evidence": evidence,
        "owner": _required_string(raw, "owner"),
        "review_by": raw["review_by"],
    }
    for key in ("evidence_gap", "retirement_reason"):
        if key in raw:
            result[key] = raw[key]
    return result


def _load_scheduling_constraints(
    ontology_root: Path, manifest: Mapping[str, object], terms: Sequence[Mapping[str, object]]
) -> dict[str, dict[str, object]]:
    """Load first-class, governed planner constraints from manifest-owned sources.

    Constraints intentionally model operational scheduling decisions separately
    from ontology relations.  They preserve legacy behavior without asserting
    biochemical incompatibility or category disjointness.
    """
    known_terms = {(str(term["semantic_category"]), str(term["slug"])) for term in terms}
    constraints: dict[str, dict[str, object]] = {}
    legacy_ids: set[str] = set()
    for relative_path in _required_string_list(manifest, "constraint_sources"):
        source = _load_yaml_mapping(ontology_root / relative_path)
        raw_constraints = _required_mapping(source, "scheduling_constraints")
        for constraint_id, raw_constraint in raw_constraints.items():
            if not isinstance(constraint_id, str) or not constraint_id.startswith("sc_"):
                raise OntologyInfrastructureError(f"Scheduling constraint id must start with sc_: {constraint_id!r}")
            if constraint_id in constraints or not isinstance(raw_constraint, dict):
                raise OntologyInfrastructureError(f"Duplicate or malformed scheduling constraint {constraint_id!r}")
            normalized = _normalize_scheduling_constraint(
                constraint_id, cast(Mapping[str, object], raw_constraint), known_terms
            )
            legacy_id = str(normalized["legacy_relation_id"])
            if legacy_id in legacy_ids:
                raise OntologyInfrastructureError(
                    f"Duplicate legacy relation id in scheduling constraints: {legacy_id}"
                )
            legacy_ids.add(legacy_id)
            constraints[constraint_id] = normalized
    return dict(sorted(constraints.items()))


def _normalize_scheduling_constraint(
    constraint_id: str, raw: Mapping[str, object], known_terms: set[tuple[str, str]]
) -> dict[str, object]:
    allowed = {
        "legacy_relation_id",
        "assertion_type",
        "effect",
        "enforcement",
        "legacy_preserved",
        "status",
        "owner",
        "review_by",
        "evidence",
        "scope",
        "source_selector",
        "target_selector",
        "rationale",
        "semantic_note",
        "action",
    }
    extras = sorted(set(raw) - allowed)
    if extras:
        raise OntologyInfrastructureError(
            f"Scheduling constraint {constraint_id!r} has unsupported fields: {', '.join(extras)}"
        )
    if _required_string(raw, "assertion_type") != "clinical_scheduling_constraint":
        raise OntologyInfrastructureError(
            f"Scheduling constraint {constraint_id!r} must be a clinical_scheduling_constraint"
        )
    if _required_string(raw, "effect") != "separate_slots":
        raise OntologyInfrastructureError(f"Scheduling constraint {constraint_id!r} has unsupported effect")
    if _required_string(raw, "enforcement") not in {"block", "advisory", "review"}:
        raise OntologyInfrastructureError(f"Scheduling constraint {constraint_id!r} has invalid enforcement")
    normalized = {
        "legacy_relation_id": _required_string(raw, "legacy_relation_id"),
        "assertion_type": "clinical_scheduling_constraint",
        "effect": "separate_slots",
        "enforcement": _required_string(raw, "enforcement"),
        **_normalize_constraint_governance(f"Scheduling constraint {constraint_id!r}", raw),
        "source_selector": _normalize_constraint_selector(constraint_id, raw.get("source_selector"), known_terms),
        "target_selector": _normalize_constraint_selector(constraint_id, raw.get("target_selector"), known_terms),
        "rationale": _required_string(raw, "rationale"),
    }
    action = raw.get("action")
    semantic_note = raw.get("semantic_note")
    if semantic_note is not None:
        if not isinstance(semantic_note, str) or not semantic_note:
            raise OntologyInfrastructureError(
                f"Scheduling constraint {constraint_id!r} semantic_note must be non-empty"
            )
        normalized["semantic_note"] = semantic_note
    if action is not None:
        if not isinstance(action, str) or not action:
            raise OntologyInfrastructureError(f"Scheduling constraint {constraint_id!r} action must be non-empty")
        normalized["action"] = action
    return normalized


def _load_ontology_assertions(
    ontology_root: Path, manifest: Mapping[str, object], terms: Sequence[Mapping[str, object]]
) -> dict[str, dict[str, object]]:
    """Load non-blocking assertions separately from planner constraints.

    The source is intentionally the planner's current relations document: the
    generated projection adds formal semantics without introducing a duplicate
    source or changing today's planner consumer.
    """
    known_terms = {(str(term["semantic_category"]), str(term["slug"])) for term in terms}
    assertions: dict[str, dict[str, object]] = {}
    for relative_path in _required_string_list(manifest, "assertion_sources"):
        source = _load_yaml_mapping(ontology_root / relative_path)
        governance = _policy_governance_defaults(source, relative_path)
        raw_assertions = source.get("relations")
        if not isinstance(raw_assertions, list):
            raise OntologyInfrastructureError(f"Assertion source {relative_path} must contain a relations list")
        for raw_assertion in raw_assertions:
            if not isinstance(raw_assertion, dict):
                raise OntologyInfrastructureError(f"Assertion source {relative_path} contains a non-mapping record")
            normalized = _normalize_ontology_assertion(
                cast(Mapping[str, object], raw_assertion), known_terms, governance
            )
            assertion_id = str(normalized["id"])
            if assertion_id in assertions:
                raise OntologyInfrastructureError(f"Duplicate canonical ontology assertion id: {assertion_id}")
            assertions[assertion_id] = normalized
    return dict(sorted(assertions.items()))


def _normalize_ontology_assertion(
    raw: Mapping[str, object], known_terms: set[tuple[str, str]], governance: Mapping[str, object]
) -> dict[str, object]:
    allowed = {
        "id",
        "type",
        "reason",
        "action",
        "severity",
        "source_selector",
        "target_selector",
        "assertion_kind",
        "semantic_family",
    }
    extras = sorted(set(raw) - allowed)
    if extras:
        raise OntologyInfrastructureError(f"Ontology assertion has unsupported fields: {', '.join(extras)}")
    assertion_id = _required_string(raw, "id")
    relation_type = _required_string(raw, "type")
    allowed_families = _ASSERTION_FAMILIES_BY_TYPE.get(relation_type)
    if allowed_families is None:
        raise OntologyInfrastructureError(
            f"Ontology assertion {assertion_id} has unsupported relation type {relation_type!r}; "
            "hard scheduling behavior belongs only in scheduling_constraints"
        )
    assertion_kind = _required_string(raw, "assertion_kind")
    if assertion_kind != _ASSERTION_KIND_BY_TYPE[relation_type]:
        raise OntologyInfrastructureError(
            f"Ontology assertion {assertion_id} has assertion_kind incompatible with {relation_type}"
        )
    semantic_family = _required_string(raw, "semantic_family")
    if semantic_family not in allowed_families:
        raise OntologyInfrastructureError(
            f"Ontology assertion {assertion_id} has semantic_family incompatible with {relation_type}"
        )
    source_selector = _normalize_constraint_selector(assertion_id, raw.get("source_selector"), known_terms)
    target_selector = _normalize_constraint_selector(assertion_id, raw.get("target_selector"), known_terms)
    _validate_assertion_endpoints(assertion_id, semantic_family, source_selector, target_selector)
    normalized: dict[str, object] = {
        "id": assertion_id,
        "relation_type": relation_type,
        "assertion_kind": assertion_kind,
        "semantic_family": semantic_family,
        **governance,
        "source_selector": source_selector,
        "target_selector": target_selector,
        "reason": _required_string(raw, "reason"),
    }
    for key in ("action", "severity"):
        value = raw.get(key)
        if value is not None:
            if not isinstance(value, str) or not value:
                raise OntologyInfrastructureError(f"Ontology assertion {assertion_id} {key} must be a non-empty string")
            normalized[key] = value
    return normalized


def _validate_assertion_endpoints(
    assertion_id: str,
    semantic_family: str,
    source: Mapping[str, object],
    target: Mapping[str, object],
) -> None:
    """Keep semantic families from silently becoming generic planner rules."""
    source_is_entity = "entity" in source
    target_is_entity = "entity" in target
    if semantic_family in {"absorption_interaction_claim", "nutrient_balance_review_signal"} and (
        not source_is_entity or not target_is_entity
    ):
        raise OntologyInfrastructureError(
            f"Ontology assertion {assertion_id} {semantic_family} requires entity selectors on both endpoints"
        )
    if semantic_family == "nutritional_adequacy_advisory" and (
        not source_is_entity or target.get("category") != "context"
    ):
        raise OntologyInfrastructureError(
            f"Ontology assertion {assertion_id} nutritional_adequacy_advisory requires entity-to-context endpoints"
        )


def _normalize_governance(context: str, raw: Mapping[str, object]) -> dict[str, object]:
    if raw.get("legacy_preserved") is not True:
        raise OntologyInfrastructureError(f"{context} must declare legacy_preserved: true")
    if _required_string(raw, "status") != "review_pending":
        raise OntologyInfrastructureError(f"{context} must declare status: review_pending")
    evidence = raw.get("evidence")
    if not isinstance(evidence, list):
        raise OntologyInfrastructureError(f"{context} evidence must be a list")
    scope = _required_mapping(raw, "scope")
    planner_scope = _required_string(scope, "planner")
    return {
        "legacy_preserved": True,
        "status": "review_pending",
        "owner": _required_string(raw, "owner"),
        "review_by": _required_string(raw, "review_by"),
        "evidence": cast(list[object], evidence),
        "scope": {"planner": planner_scope},
    }


def _normalize_constraint_governance(context: str, raw: Mapping[str, object]) -> dict[str, object]:
    """Validate the explicit lifecycle/enforcement matrix for constraints."""
    status = _required_string(raw, "status")
    enforcement = _required_string(raw, "enforcement")
    valid = {
        ("proposed", "review"),
        ("review_pending", "review"),
        ("approved", "review"),
        ("approved", "advisory"),
        ("approved", "block"),
        ("retired", "review"),
    }
    if (status, enforcement) not in valid:
        raise OntologyInfrastructureError(
            f"{context} has invalid status/enforcement combination: {status}+{enforcement}"
        )
    if raw.get("legacy_preserved") is not True:
        raise OntologyInfrastructureError(f"{context} must declare legacy_preserved: true")
    evidence = raw.get("evidence")
    if not isinstance(evidence, list):
        raise OntologyInfrastructureError(f"{context} evidence must be a list")
    evidence_items = cast(list[object], evidence)
    for index, item in enumerate(evidence_items):
        if not isinstance(item, str):
            raise OntologyInfrastructureError(f"{context} evidence[{index}] must be a string HTTPS URL")
        parsed = urlparse(item)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username is not None or parsed.password is not None:
            raise OntologyInfrastructureError(f"{context} evidence[{index}] must be a string HTTPS URL")
    if status == "approved" and not evidence_items:
        raise OntologyInfrastructureError(f"{context} approved constraints require non-empty evidence")
    scope = _required_mapping(raw, "scope")
    return {
        "legacy_preserved": True,
        "status": status,
        "owner": _required_string(raw, "owner"),
        "review_by": _required_string(raw, "review_by"),
        "evidence": evidence_items,
        "scope": {"planner": _required_string(scope, "planner")},
    }


def _normalize_constraint_selector(
    constraint_id: str, raw: object, known_terms: set[tuple[str, str]]
) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise OntologyInfrastructureError(f"Scheduling constraint {constraint_id!r} selector must be a mapping")
    selector = cast(Mapping[str, object], raw)
    entity = selector.get("entity")
    if isinstance(entity, dict) and set(selector) == {"entity"}:
        entity_map = cast(Mapping[str, object], entity)
        keys = set(entity_map)
        if keys not in ({"id"}, {"name"}):
            raise OntologyInfrastructureError(
                f"Scheduling constraint {constraint_id!r} entity selector must use one id or name"
            )
        key = next(iter(keys))
        return {"entity": {key: _required_string(entity_map, key)}}
    if set(selector) == {"category", "term"}:
        category = _required_string(selector, "category")
        term = _required_string(selector, "term")
        if (category, term) not in known_terms:
            raise OntologyInfrastructureError(
                f"Scheduling constraint {constraint_id!r} has unknown selector {category}:{term}"
            )
        return {"category": category, "term": term}
    raise OntologyInfrastructureError(
        f"Scheduling constraint {constraint_id!r} selector must be entity or category/term"
    )


def _normalize_policy_effect(key: str, raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise OntologyInfrastructureError(f"Policy {key!r} effect must be a mapping")
    effect = cast(Mapping[str, object], raw)
    extras = sorted(set(effect) - {"match", "level", "block"})
    if extras:
        raise OntologyInfrastructureError(f"Policy {key!r} effect has unsupported fields: {', '.join(extras)}")
    normalized: dict[str, object] = {"match": _normalize_policy_match(key, effect.get("match"))}
    level = _normalize_policy_level(key, effect.get("level"))
    if level is not None:
        normalized["level"] = level
    block = _normalize_policy_block(key, effect.get("block"))
    if block is not None:
        normalized["block"] = block
    if len(normalized) == 1:
        raise OntologyInfrastructureError(f"Policy {key!r} effect must set level or block")
    return normalized


def _normalize_policy_match(key: str, raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise OntologyInfrastructureError(f"Policy {key!r} effect match must be a mapping")
    match_map = cast(Mapping[str, object], raw)
    match_extras = sorted(set(match_map) - {"near", "food"})
    if match_extras or not match_map:
        detail = ", ".join(match_extras) if match_extras else "empty match"
        raise OntologyInfrastructureError(f"Policy {key!r} effect has invalid match: {detail}")
    normalized_match: dict[str, object] = {}
    if "near" in match_map:
        near = match_map["near"]
        if near not in {"wake", "breakfast", "day_meal", "sleep", "workout_before", "workout_after"}:
            raise OntologyInfrastructureError(f"Policy {key!r} has invalid slot proximity {near!r}")
        normalized_match["near"] = near
    if "food" in match_map:
        food = match_map["food"]
        if not isinstance(food, bool):
            raise OntologyInfrastructureError(f"Policy {key!r} food match must be boolean")
        normalized_match["food"] = food
    return normalized_match


def _normalize_policy_level(key: str, level: object) -> str | None:
    if level is None:
        return None
    if level not in {"avoid_strong", "avoid", "prefer", "prefer_strong"}:
        raise OntologyInfrastructureError(f"Policy {key!r} has invalid score level {level!r}")
    return cast(str, level)


def _normalize_policy_block(key: str, block: object) -> bool | None:
    if block is None:
        return None
    if not isinstance(block, bool):
        raise OntologyInfrastructureError(f"Policy {key!r} block must be boolean")
    return block


def _read_custom_shapes(ontology_root: Path, manifest: Mapping[str, object], base_iri: str) -> str:
    files: list[str] = _required_string_list(manifest, "custom_shapes")
    contents: list[str] = []
    for relative_path in files:
        path = ontology_root / relative_path
        source = path.read_text(encoding="utf-8")
        if base_iri not in source:
            raise OntologyInfrastructureError(f"Custom SHACL source has no canonical ss base IRI: {path}")
        contents.append(source.rstrip())
    return "\n\n".join(contents) + "\n"


def _ttl_bytes(
    header: str, base_iri: str, categories: Mapping[str, object], terms: Sequence[Mapping[str, object]]
) -> bytes:
    lines = [
        header.rstrip(),
        f"@prefix ss: <{base_iri}> .",
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "",
    ]
    lines.extend([f"<{base_iri}> a ss:Ontology .", ""])
    lines.extend(f"ss:{category} a ss:SemanticCategory ." for category in sorted(categories))
    lines.append("")
    for term in terms:
        category = str(term["semantic_category"])
        slug = str(term["slug"])
        label = _ttl_literal(str(term["label"]))
        profile = str(term["ontoclean_profile"])
        lines.extend([
            f"<{base_iri}term/{category}/{slug}> a ss:OntologyTerm ;",
            f"  ss:semanticCategory ss:{category} ;",
            f"  ss:ontocleanProfile ss:{profile} ;",
            *([f"  ss:assertionKind ss:{term['assertion_kind']} ;"] if "assertion_kind" in term else []),
            f"  ss:label {label} .",
            "",
        ])
    return ("\n".join(lines).rstrip() + "\n").encode("utf-8")


def _shapes_bytes(header: str, base_iri: str, semantic_shapes: str) -> bytes:
    return (header + f"@prefix ss: <{base_iri}> .\n\n" + semantic_shapes).encode("utf-8")


def _header(manifest: Mapping[str, object], source_hash: str) -> str:
    return (
        f"# generated-by: scripts/generate_ontology.py\n"
        f"# schema-version: {manifest['schema_version']}\n"
        f"# source-hash: {source_hash}\n"
    )


def _json_bytes(value: object, header: str) -> bytes:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return (header + payload).encode("utf-8")


def _yaml_bytes(value: object) -> bytes:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=True).encode("utf-8")


def _check_fresh(generated_dir: Path, expected: Mapping[Path, bytes]) -> None:
    for relative_path, content in expected.items():
        current = generated_dir / relative_path
        if not current.is_file() or current.read_bytes() != content:
            raise OntologyInfrastructureError(f"Stale or missing generated ontology artifact: {current}")


def _load_yaml_mapping(path: Path) -> dict[str, object]:
    try:
        loaded = _safe_yaml_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise OntologyInfrastructureError(f"Cannot load ontology source {path}: {error}") from error
    if not isinstance(loaded, dict):
        raise OntologyInfrastructureError(f"Ontology source must be a mapping: {path}")
    return cast(dict[str, object], loaded)


def _required_string(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise OntologyInfrastructureError(f"Expected non-empty string {key!r} in ontology source")
    return value


def _required_string_list(mapping: Mapping[str, object], key: str) -> list[str]:
    value = mapping.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise OntologyInfrastructureError(f"Expected non-empty string list {key!r} in ontology source")
    return cast(list[str], value)


def _required_mapping(mapping: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise OntologyInfrastructureError(f"Expected mapping {key!r} in ontology source")
    return cast(Mapping[str, object], value)


def _ttl_literal(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _safe_yaml_load(text: str) -> object:
    return cast(object, yaml.safe_load(text))
