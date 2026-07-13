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
from planner.paths import ROOT, SCHEMA_DIR, Paths, strip_root_prefix
from planner.yaml_io import YamlValue, load_yaml

RELATION_SCHEMA_ERROR_PATH_PARTS = 2


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
        return _strict_canonical_substance_schema(schema) if name == "substance" else schema
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
            },
        )
    )
    schema["properties"] = properties
    schema["additionalProperties"] = False
    return schema


def schema_errors(data: YamlValue, schema_name: str, file_path: Path) -> list[str]:
    import jsonschema

    schema = load_schema(schema_name)
    validator: Validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    iter_errors = cast(Callable[[YamlValue], list[ValidationError]], validator.iter_errors)
    errors = list(iter_errors(data))
    return [_format_schema_error(data, schema_name, file_path, err) for err in errors]


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
    relation_type, relation_index = path_parts
    if not isinstance(relation_type, str) or not isinstance(relation_index, int):
        return None
    relation = _relation_at(data, relation_type, relation_index)
    if relation is None:
        return None

    loc = _schema_error_location(err)
    source_fields = _present_fields(relation, _SOURCE_ENDPOINT_FIELDS)
    target_fields = _present_fields(relation, _TARGET_ENDPOINT_FIELDS)
    source_desc = ", ".join(source_fields) if source_fields else "none"
    target_desc = ", ".join(target_fields) if target_fields else "none"
    return (
        f"{file_path}: {loc}: relation endpoints must choose exactly one source "
        f"endpoint and exactly one target endpoint; found source endpoints: "
        f"{source_desc}; target endpoints: {target_desc}. Use *_name, "
        f"*_substance, or *_trait on each side, or source_class + target_class "
        f"for class-level competes only."
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


def _present_fields(
    relation: dict[str, object],
    field_names: tuple[str, ...],
) -> list[str]:
    return [field_name for field_name in field_names if field_name in relation]


def _schema_error_location(err: ValidationError) -> str:
    return "/".join(str(p) for p in err.absolute_path) or "<root>"


_SOURCE_ENDPOINT_FIELDS = (
    "source_name",
    "source_substance",
    "source_trait",
    "source_class",
)

_TARGET_ENDPOINT_FIELDS = (
    "target_name",
    "target_substance",
    "target_trait",
    "target_class",
)


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
