"""JSON-schema loading and data-file validation."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from jsonschema.exceptions import ValidationError
from jsonschema.protocols import Validator

from planner.contracts import CardLoadError
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.runtime_program import RuntimeProgram
from planner.paths import SCHEMA_DIR, Paths, strip_root_prefix
from planner.yaml_io import YamlValue, load_yaml



@dataclass(frozen=True, slots=True)
class _GovernanceValidationContext:
    file_path: Path
    policies: dict[str, dict[str, object]]
    evidence_keys: frozenset[str]
    card_kind: str
    card_id: YamlValue | None
    runtime: RuntimeProgram


def _governance_schema(runtime: RuntimeProgram) -> dict[str, object]:
    evidence = {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["source", "supports", "limitations"],
            "properties": {k: {"type": "string", "minLength": 1} for k in ("source", "supports", "limitations")},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "enforcement_cap", "scope", "evidence", "owner", "review_by"],
        "properties": {
            "status": {"enum": list(runtime.lifecycle_by_state)},
            "enforcement_cap": {"enum": list(runtime.enforcement_by_mode)},
            "scope": {
                "type": "object",
                "minProperties": 1,
                "additionalProperties": False,
                "properties": {k: {"type": "string", "minLength": 1} for k in runtime.scope_by_key},
            },
            "evidence": evidence,
            "evidence_gap": {"type": "string", "minLength": 1},
            "owner": {"type": "string", "minLength": 1},
            "review_by": {"type": "string", "format": "date"},
            "retirement_reason": {"type": "string", "minLength": 1},
        },
    }


def _schedule_contract_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            key: {
                "type": "array",
                "uniqueItems": True,
                "maxItems": 1,
                "items": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            }
            for key in ("intake", "timing", "activity")
        },
    }


def _governance_map_schema(runtime: RuntimeProgram) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "patternProperties": {"^(intake|timing|activity):[a-z][a-z0-9_]*$": _governance_schema(runtime)},
    }


RELATION_SCHEMA_ERROR_PATH_PARTS = 3


def load_schema(name: str, bundle: OntologyBundle) -> dict[str, object]:
    runtime = bundle.runtime_program
    schema_path = (
        bundle.root / "generated" / "card.schema.json"
        if name == "substance"
        else SCHEMA_DIR / f"{name}.schema.json"
    )
    try:
        text = schema_path.read_text(encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"could not read schema {schema_path}: {e}") from e
    try:
        # Generated schema carries provenance comments; JSON Schema itself begins
        # at the first JSON token.
        json_text = text[text.find("{") :] if name == "substance" else text
        schema = cast(dict[str, object], json.loads(json_text))
        if name == "substance":
            return _strict_canonical_substance_schema(schema, runtime)
        if name == "product":
            props = cast(dict[str, object], schema.setdefault("properties", {}))
            props["schedule"] = _schedule_contract_schema()
            props["schedule_governance"] = _governance_map_schema(runtime)
        return schema
    except json.JSONDecodeError as e:
        raise RuntimeError(f"could not parse schema {schema_path}: {e}") from e


def _strict_canonical_substance_schema(schema: dict[str, object], runtime: RuntimeProgram) -> dict[str, object]:
    """Add card-shape constraints intentionally outside generated term vocabulary."""
    properties = cast(dict[str, object], schema.get("properties", {}))
    properties.update(
        cast(
            dict[str, object],
            {
                "form": {"type": "string", "minLength": 1},
                "aliases": {
                    "type": "array",
                    "minItems": 1,
                    "uniqueItems": True,
                    "items": {"type": "string", "minLength": 1},
                },
                "notes": {"type": "string", "minLength": 1},
                "concerns": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["kind", "text"],
                        "properties": {
                            "kind": {"enum": ["safety", "model_gap", "data_quality"]},
                            "text": {"type": "string", "minLength": 1},
                        },
                    },
                },
                "schedule": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        key: {
                            "type": "array",
                            "uniqueItems": True,
                            "maxItems": 1,
                            "items": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
                        }
                        for key in ("intake", "timing", "activity")
                    }
                    | {
                        "prefer_with": {
                            "type": "array",
                            "minItems": 1,
                            "uniqueItems": True,
                            "items": {"type": "string", "pattern": "^sub_[a-z0-9]+$"},
                        }
                    },
                },
                "schedule_governance": _governance_map_schema(runtime),
            },
        )
    )
    properties.setdefault("schedule", _schedule_contract_schema())
    properties.setdefault("schedule_governance", _governance_map_schema(runtime))
    schema["properties"] = properties
    schema["additionalProperties"] = False
    return schema


def _governance_reference(bundle: OntologyBundle) -> tuple[dict[str, dict[str, object]], frozenset[str], RuntimeProgram]:
    runtime_path = bundle.root
    vocabulary = bundle.runtime_vocabulary
    policies_raw = vocabulary.get("scheduling_policies")
    evidence_raw = vocabulary.get("slot_policy_evidence")
    if not isinstance(policies_raw, dict) or not isinstance(evidence_raw, dict):
        raise RuntimeError(f"runtime vocabulary is missing v2 governance: {runtime_path}")
    policies = {
        key: cast(dict[str, object], value)
        for key, value in policies_raw.items()
        if isinstance(key, str) and isinstance(value, dict)
    }
    return policies, frozenset(key for key in evidence_raw if isinstance(key, str)), bundle.runtime_program


def validate_schedule_contract(
    data: YamlValue, file_path: Path, *, card_kind: str, bundle: OntologyBundle
) -> list[str]:
    """Validate assignment/governance parity and lifecycle constraints."""
    if not isinstance(data, dict):
        return []
    errors: list[str] = []
    schedule_raw = data.get("schedule")
    if "schedule" not in data:
        schedule: dict[str, YamlValue] = {}
    elif isinstance(schedule_raw, dict):
        schedule = schedule_raw
    else:
        errors.append(f"{file_path}: schedule must be an object")
        schedule = {}
    governance_raw = data.get("schedule_governance")
    if "schedule_governance" not in data:
        governance: dict[str, YamlValue] = {}
    elif isinstance(governance_raw, dict):
        governance = governance_raw
    else:
        errors.append(f"{file_path}: schedule_governance must be an object")
        governance = {}
    assigned: set[str] = set()
    valid_axes = frozenset({"intake", "timing", "activity"})
    for axis in schedule:
        if not isinstance(axis, str) or axis not in valid_axes:
            errors.append(f"{file_path}: schedule has unknown axis {axis!r}")
    for axis in ("intake", "timing", "activity"):
        if axis not in schedule:
            continue
        axis_raw = schedule[axis]
        if not isinstance(axis_raw, list):
            errors.append(f"{file_path}: schedule.{axis} must be an array")
            continue
        for index, policy in enumerate(axis_raw):
            if not isinstance(policy, str) or not policy:
                errors.append(f"{file_path}: schedule.{axis}[{index}] must be a non-empty string")
                continue
            assigned.add(f"{axis}:{policy}")
    policies, evidence_keys, runtime = _governance_reference(bundle)
    context = _GovernanceValidationContext(file_path, policies, evidence_keys, card_kind, data.get("id"), runtime)
    errors.extend(
        f"{file_path}: schedule_governance key '{key}' has no schedule assignment"
        for key in sorted(set(governance) - assigned)
    )
    errors.extend(
        f"{file_path}: schedule assignment '{key}' is missing schedule_governance"
        for key in sorted(assigned - set(governance))
    )
    for key, record in governance.items():
        if not isinstance(key, str):
            errors.append(f"{file_path}: schedule_governance keys must be strings")
            continue
        if not isinstance(record, dict):
            errors.append(f"{file_path}: schedule_governance key '{key}' must be an object")
            continue
        errors.extend(_governance_record_errors(context, key, record))
    return errors


def _governance_record_errors(
    context: _GovernanceValidationContext,
    key: str,
    record: dict[str, YamlValue],
) -> list[str]:
    errors: list[str] = []
    file_path = context.file_path
    policy = context.policies.get(key)
    if policy is None:
        errors.append(f"{file_path}: schedule_governance key '{key}' references unknown scheduling policy")
    status = record.get("status")
    cap = record.get("enforcement_cap")
    evidence = record.get("evidence")
    lifecycle = context.runtime.lifecycle_decision(status) if isinstance(status, str) else None
    gate = context.runtime.execution_gate_for(status) if isinstance(status, str) else None
    if lifecycle is None:
        errors.append(f"{file_path}: {key}: unknown lifecycle state")
    elif not lifecycle.executable:
        errors.append(f"{file_path}: {key}: lifecycle state '{lifecycle.state}' is not executable")
    if gate is None:
        errors.append(f"{file_path}: {key}: lifecycle state has no runtime execution gate")
    elif gate.evidence_requirement == "required" and not evidence:
        errors.append(f"{file_path}: {key}: runtime gate requires applicable evidence")
    elif gate.evidence_requirement == "evidence_or_gap" and not evidence and not record.get("evidence_gap"):
        errors.append(f"{file_path}: {key}: runtime gate requires evidence or evidence_gap")
    elif gate.evidence_requirement == "prohibited" and evidence:
        errors.append(f"{file_path}: {key}: runtime gate prohibits evidence")
    cap_decision = context.runtime.enforcement_decision(cap) if isinstance(cap, str) else None
    if cap_decision is None:
        errors.append(f"{file_path}: {key}: unknown enforcement_cap")
    elif lifecycle is not None and lifecycle.executable and not cap_decision.executable:
        errors.append(f"{file_path}: {key}: enforcement_cap '{cap_decision.mode}' is not executable")
    policy_cap = policy.get("enforcement") if policy is not None else None
    policy_decision = context.runtime.enforcement_decision(policy_cap) if isinstance(policy_cap, str) else None
    if policy is not None and policy_decision is None:
        errors.append(f"{file_path}: {key}: referenced policy has unknown enforcement")
    if cap_decision is not None and policy_decision is not None and cap_decision.rank > policy_decision.rank:
        errors.append(f"{file_path}: {key}: enforcement_cap '{cap}' exceeds policy enforcement '{policy_cap}'")
    errors.extend(_evidence_reference_errors(file_path, key, evidence, context.evidence_keys))
    errors.extend(_scope_errors(file_path, key, record.get("scope"), context.card_kind, context.card_id))
    scope = record.get("scope")
    if (
        isinstance(scope, dict)
        and any(k in scope for k in ("formulation", "intended_use", "substrate"))
        and cap_decision is not None
        and cap_decision.effect_role == "blocking"
    ):
        errors.append(f"{file_path}: {key}: unobservable scope cannot declare enforcement_cap block")
    return errors


def _evidence_reference_errors(
    file_path: Path, key: str, evidence: YamlValue | None, evidence_keys: frozenset[str]
) -> list[str]:
    if not isinstance(evidence, list):
        return []
    errors: list[str] = []
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        if isinstance(source, str) and source not in evidence_keys:
            errors.append(f"{file_path}: {key}: evidence[{index}].source '{source}' is not in slot_policy_evidence")
    return errors


def _scope_errors(
    file_path: Path, key: str, scope: YamlValue | None, card_kind: str, card_id: YamlValue | None
) -> list[str]:
    if not isinstance(scope, dict):
        return []
    product_scope = scope.get("product")
    if card_kind == "substance" and product_scope is not None:
        return [f"{file_path}: {key}: scope.product is valid only on a product card"]
    if card_kind != "product":
        return []
    if product_scope is None:
        return [f"{file_path}: {key}: direct product assignment requires scope.product"]
    if product_scope != card_id:
        return [f"{file_path}: {key}: scope.product must equal product id '{card_id}'"]
    return []


def schema_errors(data: YamlValue, schema_name: str, file_path: Path, bundle: OntologyBundle) -> list[str]:
    import jsonschema

    schema = load_schema(schema_name, bundle)
    validator: Validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    iter_errors = cast(Callable[[YamlValue], list[ValidationError]], validator.iter_errors)
    errors = list(iter_errors(data))
    formatted = [_format_schema_error(data, schema_name, file_path, err) for err in errors]
    if schema_name in {"substance", "product"}:
        formatted.extend(validate_schedule_contract(data, file_path, card_kind=schema_name, bundle=bundle))
    return formatted


def _format_schema_error(
    data: YamlValue,
    schema_name: str,
    file_path: Path,
    err: ValidationError,
) -> str:
    if schema_name == "relations":
        relation_error = _format_relation_endpoint_error(data, file_path, err)
        if relation_error is not None:
            return relation_error
    loc = _schema_error_location(err)
    return f"{file_path}: {loc}: {err.message}"


def _format_relation_endpoint_error(
    data: object,
    file_path: Path,
    err: ValidationError,
) -> str | None:
    if err.validator != "oneOf":
        return None
    path_parts = list(err.absolute_path)
    if len(path_parts) != RELATION_SCHEMA_ERROR_PATH_PARTS:
        return None
    relation_type, relation_index, _selector_name = path_parts
    if not isinstance(relation_type, str) or not isinstance(relation_index, int):
        return None
    relation = _relation_at(data, relation_type, relation_index)
    if relation is None:
        return None

    loc = _schema_error_location(err)
    source_desc = _selector_fields(relation.get("source_selector"))
    target_desc = _selector_fields(relation.get("target_selector"))
    return (
        f"{file_path}: {loc}: relation endpoints must choose exactly one source "
        f"endpoint and exactly one target endpoint; found source endpoints: "
        f"{source_desc}; target endpoints: {target_desc}. Use the canonical "
        f"selector shape {{entity: {{id|name}}}} or "
        f"{{category, term}} on each side."
    )


def _relation_at(
    data: object,
    relation_type: str,
    relation_index: int,
) -> dict[str, object] | None:
    if not isinstance(data, dict):
        return None
    data_dict = cast(dict[str, object], data)
    relation_items_raw = data_dict.get(relation_type)
    if not isinstance(relation_items_raw, list):
        return None
    relation_items = cast(list[object], relation_items_raw)
    if relation_index < 0 or relation_index >= len(relation_items):
        return None
    relation_raw = relation_items[relation_index]
    if not isinstance(relation_raw, dict):
        return None
    return cast(dict[str, object], relation_raw)


def _selector_fields(selector: object) -> str:
    if not isinstance(selector, dict):
        return "none"
    fields = set(cast(dict[str, object], selector))
    canonical = fields & {"entity", "category", "term"}
    return ", ".join(sorted(canonical)) if canonical else "invalid shape"


def _schema_error_location(err: ValidationError) -> str:
    return "/".join(str(p) for p in err.absolute_path) or "<root>"


def validate_schemas(paths: Paths, bundle: OntologyBundle) -> int:
    """Validate every YAML data file against its JSON Schema."""
    errors = [
        *_singular_schema_errors(paths, bundle),
        *_collection_schema_errors(paths, bundle),
    ]

    if errors:
        for error in errors:
            print(f"ERROR: {strip_root_prefix(error)}", file=sys.stderr)
        print(f"\n{len(errors)} schema error(s) found", file=sys.stderr)
        return 1
    return 0


def _singular_schema_errors(paths: Paths, bundle: OntologyBundle) -> list[str]:
    singular_files = [
        (paths.data / "pillboxes.yaml", "pillboxes"),
        (paths.relations_file, "relations"),
        (paths.stacks_file, "stacks"),
    ]
    errors: list[str] = []
    for path, schema_name in singular_files:
        if not path.exists():
            errors.append(f"missing: {path}")
            continue
        try:
            data = load_yaml(path)
        except CardLoadError as e:
            errors.append(e.message)
            continue
        errors.extend(schema_errors(data, schema_name, path, bundle))
    return errors


def _collection_schema_errors(paths: Paths, bundle: OntologyBundle) -> list[str]:
    collections = [
        (paths.substances, "substance"),
        (paths.products, "product"),
        (paths.dashboards, "dashboard"),
    ]
    errors: list[str] = []
    for directory, schema_name in collections:
        if not directory.exists():
            continue
        errors.extend(_schema_errors_for_files(sorted(directory.glob("*.yaml")), schema_name, bundle))
    return errors


def _schema_errors_for_files(paths: list[Path], schema_name: str, bundle: OntologyBundle) -> list[str]:
    errors: list[str] = []
    for path in paths:
        try:
            data = load_yaml(path)
        except CardLoadError as e:
            errors.append(e.message)
            continue
        errors.extend(schema_errors(data, schema_name, path, bundle))
    return errors
