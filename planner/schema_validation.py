"""JSON-schema loading and data-file validation."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

from jsonschema.exceptions import ValidationError
from jsonschema.protocols import Validator

from planner.contracts import CardLoadError
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.runtime_program import RuntimeProgram
from planner.ontology.schema_enums import schema_enum_values
from planner.paths import SCHEMA_DIR, Paths, strip_root_prefix
from planner.yaml_io import YamlValue, load_yaml


def _assignment_fields(runtime: RuntimeProgram) -> tuple[str, ...]:
    return tuple(row.assignment_field for row in sorted(runtime.assignment_axes, key=lambda row: (row.order, row.id)))


def _schedule_contract_schema(runtime: RuntimeProgram, *, allow_prefer_with: bool = False) -> dict[str, object]:
    properties = {
        key: {
            "type": "array",
            "uniqueItems": True,
            "maxItems": 1,
            "items": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
        }
        for key in _assignment_fields(runtime)
    }
    if allow_prefer_with:
        properties["prefer_with"] = {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"type": "string", "pattern": "^sub_[a-z0-9]+$"},
        }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }


RELATION_SCHEMA_ERROR_PATH_PARTS = 3


def load_schema(name: str, bundle: OntologyBundle) -> dict[str, object]:
    runtime = bundle.runtime_program
    schema_path = (
        bundle.root / "generated" / "card.schema.json" if name == "substance" else SCHEMA_DIR / f"{name}.schema.json"
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
            return _strict_canonical_substance_schema(schema, runtime, bundle)
        if name == "product":
            props = cast(dict[str, object], schema.setdefault("properties", {}))
            _patch_concern_kind_schema(props, bundle)
            props["schedule"] = _schedule_contract_schema(runtime)
        if name == "relations":
            _patch_relation_schema(schema, bundle)
        return schema
    except json.JSONDecodeError as e:
        raise RuntimeError(f"could not parse schema {schema_path}: {e}") from e


def _concern_kind_schema(bundle: OntologyBundle) -> dict[str, object]:
    return {"type": "string", "enum": list(schema_enum_values(bundle, "ConcernKind"))}


def _patch_concern_kind_schema(properties: dict[str, object], bundle: OntologyBundle) -> None:
    concerns = properties.get("concerns")
    if not isinstance(concerns, dict):
        return
    concerns_mapping = cast(dict[str, object], concerns)
    concerns_items = concerns_mapping.get("items")
    if not isinstance(concerns_items, dict):
        return
    concerns_items_mapping = cast(dict[str, object], concerns_items)
    concerns_properties = concerns_items_mapping.get("properties")
    if isinstance(concerns_properties, dict):
        concerns_properties["kind"] = _concern_kind_schema(bundle)


def _patch_relation_schema(schema: dict[str, object], bundle: OntologyBundle) -> None:
    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        raise RuntimeError("relations schema is missing $defs")
    relation_list = cast(dict[str, object], defs).get("relationList")
    if not isinstance(relation_list, dict):
        raise RuntimeError("relations schema is missing $defs.relationList")
    relation_items = cast(dict[str, object], relation_list).get("items")
    if not isinstance(relation_items, dict):
        raise RuntimeError("relations schema is missing $defs.relationList.items")
    relation_properties = cast(dict[str, object], relation_items).get("properties")
    if not isinstance(relation_properties, dict):
        raise RuntimeError("relations schema is missing $defs.relationList.items.properties")
    relation_types = bundle.runtime_vocabulary.get("relation_types")
    if not isinstance(relation_types, dict) or not relation_types:
        raise RuntimeError("runtime vocabulary is missing relation_types")
    cast(dict[str, object], relation_properties)["type"] = {
        "type": "string",
        "enum": list(cast(dict[str, object], relation_types)),
    }
    cast(dict[str, object], relation_properties)["severity"] = {
        "type": "string",
        "enum": list(schema_enum_values(bundle, "Severity")),
    }


def _strict_canonical_substance_schema(
    schema: dict[str, object], runtime: RuntimeProgram, bundle: OntologyBundle
) -> dict[str, object]:
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
                            "kind": _concern_kind_schema(bundle),
                            "text": {"type": "string", "minLength": 1},
                        },
                    },
                },
                "schedule": _schedule_contract_schema(runtime, allow_prefer_with=True),
            },
        )
    )
    properties.setdefault("schedule", _schedule_contract_schema(runtime, allow_prefer_with=True))
    schema["properties"] = properties
    schema["additionalProperties"] = False
    return schema


def _schedule_assignment_errors(
    schedule: dict[str, YamlValue],
    file_path: Path,
    runtime: RuntimeProgram,
) -> list[str]:
    errors: list[str] = []
    valid_axes = frozenset(_assignment_fields(runtime)) | {"prefer_with"}
    for axis in schedule:
        if not isinstance(axis, str) or axis not in valid_axes:
            errors.append(f"{file_path}: schedule has unknown axis {axis!r}")
    for field in _assignment_fields(runtime):
        if field not in schedule:
            continue
        axis_raw = schedule[field]
        if not isinstance(axis_raw, list):
            errors.append(f"{file_path}: schedule.{field} must be an array")
            continue
        for index, policy in enumerate(axis_raw):
            if not isinstance(policy, str) or not policy:
                errors.append(f"{file_path}: schedule.{field}[{index}] must be a non-empty string")
                continue
    return errors


def validate_schedule_contract(
    data: YamlValue, file_path: Path, *, card_kind: str, bundle: OntologyBundle
) -> list[str]:
    """Validate that authored schedule assignments use declared ontology axes."""
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
    runtime = bundle.runtime_program
    errors.extend(_schedule_assignment_errors(schedule, file_path, runtime))
    return errors


def schema_errors(data: YamlValue, schema_name: str, file_path: Path, bundle: OntologyBundle) -> list[str]:
    import jsonschema

    schema = load_schema(schema_name, bundle)
    validator: Validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    iter_errors = cast(Callable[[YamlValue], list[ValidationError]], validator.iter_errors)
    validated_data = data
    if schema_name == "relations" and isinstance(data, dict):
        # The executable relation contract is the direct ``relations`` list.
        # Keep unrelated catalog metadata out of validation without mutating
        # the source document (the relation loader likewise reads only this list).
        validated_data = {"relations": data.get("relations")}
    errors = list(iter_errors(validated_data))
    formatted = [_format_schema_error(data, schema_name, file_path, err) for err in errors]
    if schema_name == "pillboxes":
        formatted.extend(_pillbox_slot_anchor_errors(data, file_path, bundle.runtime_program))
    if schema_name in {"substance", "product"}:
        formatted.extend(validate_schedule_contract(data, file_path, card_kind=schema_name, bundle=bundle))
    return formatted


def _pillbox_slot_anchor_errors(data: YamlValue, file_path: Path, runtime: RuntimeProgram) -> list[str]:
    if not isinstance(data, dict):
        return []
    valid_near = runtime.slot_near_values
    errors: list[str] = []
    for pillbox_id, pillbox in data.items():
        if not isinstance(pillbox_id, str) or not isinstance(pillbox, dict):
            continue
        slots = pillbox.get("slots")
        if not isinstance(slots, dict):
            continue
        for slot_id, slot in slots.items():
            if not isinstance(slot_id, str) or not isinstance(slot, dict):
                continue
            near = slot.get("near")
            if isinstance(near, str) and near not in valid_near:
                errors.append(
                    f"{file_path}: {pillbox_id}.slots.{slot_id}.near '{near}' is not in ontology slot anchors"
                )
    return errors


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
