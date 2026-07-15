"""JSON-schema loading and data-file validation."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import cast

from jsonschema.exceptions import ValidationError
from jsonschema.protocols import Validator

from planner.contracts import CardLoadError
from planner.paths import ROOT, SCHEMA_DIR, Paths, strip_root_prefix
from planner.yaml_io import YamlValue, load_yaml

_GOVERNANCE_STATUSES = ["approved", "review_pending", "retired"]
_ENFORCEMENT_CAPS = ["block", "preference", "advisory", "none"]
_SCOPE_KEYS = ["planner", "food_model", "slot_model", "intended_use", "substrate", "product", "formulation"]
_CAP_RANK = {"none": 0, "advisory": 1, "preference": 2, "block": 3}


@dataclass(frozen=True, slots=True)
class _GovernanceValidationContext:
    file_path: Path
    policies: dict[str, dict[str, object]]
    evidence_keys: frozenset[str]
    card_kind: str
    card_id: YamlValue | None


def _governance_schema() -> dict[str, object]:
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
            "status": {"enum": _GOVERNANCE_STATUSES},
            "enforcement_cap": {"enum": _ENFORCEMENT_CAPS},
            "scope": {
                "type": "object",
                "minProperties": 1,
                "additionalProperties": False,
                "properties": {k: {"type": "string", "minLength": 1} for k in _SCOPE_KEYS},
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


def _governance_map_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "patternProperties": {"^(intake|timing|activity):[a-z][a-z0-9_]*$": _governance_schema()},
    }


RELATION_SCHEMA_ERROR_PATH_PARTS = 3


def load_schema(name: str) -> dict[str, object]:
    schema_path = (
        ROOT / "ontology" / "generated" / "card.schema.json"
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
            return _strict_canonical_substance_schema(schema)
        if name == "product":
            props = cast(dict[str, object], schema.setdefault("properties", {}))
            props["schedule"] = _schedule_contract_schema()
            props["schedule_governance"] = _governance_map_schema()
        return schema
    except json.JSONDecodeError as e:
        raise RuntimeError(f"could not parse schema {schema_path}: {e}") from e


def _strict_canonical_substance_schema(schema: dict[str, object]) -> dict[str, object]:
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
                "schedule_governance": _governance_map_schema(),
            },
        )
    )
    properties.setdefault("schedule", _schedule_contract_schema())
    properties.setdefault("schedule_governance", _governance_map_schema())
    schema["properties"] = properties
    schema["additionalProperties"] = False
    return schema


@lru_cache(maxsize=1)
def _governance_reference() -> tuple[dict[str, dict[str, object]], frozenset[str]]:
    runtime_path = ROOT / "ontology" / "generated" / "runtime-vocabulary.yaml"
    runtime = load_yaml(runtime_path)
    if not isinstance(runtime, dict):
        raise RuntimeError(f"runtime vocabulary must be a mapping: {runtime_path}")
    policies_raw = runtime.get("scheduling_policies")
    evidence_raw = runtime.get("slot_policy_evidence")
    if not isinstance(policies_raw, dict) or not isinstance(evidence_raw, dict):
        raise RuntimeError(f"runtime vocabulary is missing v2 governance: {runtime_path}")
    policies = {
        key: cast(dict[str, object], value)
        for key, value in policies_raw.items()
        if isinstance(key, str) and isinstance(value, dict)
    }
    return policies, frozenset(key for key in evidence_raw if isinstance(key, str))


def validate_schedule_contract(data: YamlValue, file_path: Path, *, card_kind: str) -> list[str]:
    """Validate assignment/governance parity and lifecycle constraints."""
    if not isinstance(data, dict):
        return []
    schedule = data.get("schedule")
    governance = data.get("schedule_governance")
    schedule = schedule if isinstance(schedule, dict) else {}
    governance = governance if isinstance(governance, dict) else {}
    assigned = {
        f"{axis}:{policy}"
        for axis in ("intake", "timing", "activity")
        for policy in (cast(list[YamlValue], schedule.get(axis)) if isinstance(schedule.get(axis), list) else [])
        if isinstance(policy, str)
    }
    errors: list[str] = []
    policies, evidence_keys = _governance_reference()
    context = _GovernanceValidationContext(file_path, policies, evidence_keys, card_kind, data.get("id"))
    errors.extend(
        f"{file_path}: schedule_governance key '{key}' has no schedule assignment"
        for key in sorted(set(governance) - assigned)
    )
    errors.extend(
        f"{file_path}: schedule assignment '{key}' is missing schedule_governance"
        for key in sorted(assigned - set(governance))
    )
    for key, record in governance.items():
        if not isinstance(record, dict):
            continue
        errors.extend(_governance_record_errors(context, str(key), record))
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
    if status == "approved" and not evidence:
        errors.append(f"{file_path}: {key}: approved assignment requires applicable evidence")
    if status == "review_pending" and not record.get("evidence_gap") and not evidence:
        errors.append(f"{file_path}: {key}: review_pending requires evidence or evidence_gap")
    if status == "retired":
        errors.append(f"{file_path}: retired governance '{key}' cannot remain beside an active assignment")
    if cap == "none":
        errors.append(f"{file_path}: {key}: enforcement_cap none is not legal beside an active assignment")
    policy_cap = policy.get("enforcement") if policy is not None else None
    if isinstance(cap, str) and isinstance(policy_cap, str) and _CAP_RANK.get(cap, -1) > _CAP_RANK.get(policy_cap, -1):
        errors.append(f"{file_path}: {key}: enforcement_cap '{cap}' exceeds policy enforcement '{policy_cap}'")
    errors.extend(_evidence_reference_errors(file_path, key, evidence, context.evidence_keys))
    errors.extend(_scope_errors(file_path, key, record.get("scope"), context.card_kind, context.card_id))
    scope = record.get("scope")
    if (
        isinstance(scope, dict)
        and any(k in scope for k in ("formulation", "intended_use", "substrate"))
        and cap == "block"
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


def schema_errors(data: YamlValue, schema_name: str, file_path: Path) -> list[str]:
    import jsonschema

    schema = load_schema(schema_name)
    validator: Validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    iter_errors = cast(Callable[[YamlValue], list[ValidationError]], validator.iter_errors)
    errors = list(iter_errors(data))
    formatted = [_format_schema_error(data, schema_name, file_path, err) for err in errors]
    if schema_name in {"substance", "product"}:
        formatted.extend(validate_schedule_contract(data, file_path, card_kind=schema_name))
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


def validate_schemas(paths: Paths) -> int:
    """Validate every YAML data file against its JSON Schema."""
    errors = [
        *_singular_schema_errors(paths),
        *_collection_schema_errors(paths),
    ]

    if errors:
        for error in errors:
            print(f"ERROR: {strip_root_prefix(error)}", file=sys.stderr)
        print(f"\n{len(errors)} schema error(s) found", file=sys.stderr)
        return 1
    return 0


def _singular_schema_errors(paths: Paths) -> list[str]:
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
        errors.extend(schema_errors(data, schema_name, path))
    return errors


def _collection_schema_errors(paths: Paths) -> list[str]:
    collections = [
        (paths.substances, "substance"),
        (paths.products, "product"),
        (paths.dashboards, "dashboard"),
    ]
    errors: list[str] = []
    for directory, schema_name in collections:
        if not directory.exists():
            continue
        errors.extend(_schema_errors_for_files(sorted(directory.glob("*.yaml")), schema_name))
    return errors


def _schema_errors_for_files(paths: list[Path], schema_name: str) -> list[str]:
    errors: list[str] = []
    for path in paths:
        try:
            data = load_yaml(path)
        except CardLoadError as e:
            errors.append(e.message)
            continue
        errors.extend(schema_errors(data, schema_name, path))
    return errors
