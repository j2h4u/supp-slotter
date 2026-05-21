"""JSON-schema loading and data-file validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

from planner.cards.traits import trait_source_files
from planner.contracts import CardLoadError
from planner.paths import SCHEMA_DIR, Paths, strip_root_prefix
from planner.yaml_io import load_yaml


def load_schema(name: str) -> dict[str, Any]:
    schema_path = SCHEMA_DIR / f"{name}.schema.json"
    try:
        text = schema_path.read_text(encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"could not read schema {schema_path}: {e}") from e
    try:
        return cast(dict[str, Any], json.loads(text))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"could not parse schema {schema_path}: {e}") from e


def schema_errors(data: object, schema_name: str, file_path: Path) -> list[str]:
    import jsonschema

    schema = load_schema(schema_name)
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )
    out: list[str] = []
    for err in validator.iter_errors(data):  # type: ignore[arg-type]
        out.append(_format_schema_error(data, schema_name, file_path, err))
    return out


def _format_schema_error(
    data: object,
    schema_name: str,
    file_path: Path,
    err: Any,
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
    err: Any,
) -> str | None:
    if err.validator != "oneOf":
        return None
    path_parts = list(err.absolute_path)
    if len(path_parts) != 2:
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
) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    data_dict = cast(dict[str, Any], data)
    relation_items_raw = data_dict.get(relation_type)
    if not isinstance(relation_items_raw, list):
        return None
    relation_items = cast(list[Any], relation_items_raw)
    if relation_index < 0 or relation_index >= len(relation_items):
        return None
    relation_raw = relation_items[relation_index]
    if not isinstance(relation_raw, dict):
        return None
    return cast(dict[str, Any], relation_raw)


def _present_fields(
    relation: dict[str, Any],
    field_names: tuple[str, ...],
) -> list[str]:
    return [field_name for field_name in field_names if field_name in relation]


def _schema_error_location(err: Any) -> str:
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
    errors: list[str] = []

    singular_files = [
        (paths.data / "pillboxes.yaml", "pillboxes"),
        (paths.relations_file, "relations"),
        (paths.stacks_file, "stacks"),
    ]
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

    try:
        trait_files = trait_source_files(paths.traits)
    except CardLoadError as e:
        errors.append(e.message)
    else:
        for path in trait_files:
            try:
                data = load_yaml(path)
            except CardLoadError as e:
                errors.append(e.message)
                continue
            errors.extend(schema_errors(data, "traits", path))

    collections = [
        (paths.substances, "substance"),
        (paths.products, "product"),
        (paths.dashboards, "dashboard"),
    ]
    for directory, schema_name in collections:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            try:
                data = load_yaml(path)
            except CardLoadError as e:
                errors.append(e.message)
                continue
            errors.extend(schema_errors(data, schema_name, path))

    if errors:
        for error in errors:
            print(f"ERROR: {strip_root_prefix(error)}", file=sys.stderr)
        print(f"\n{len(errors)} schema error(s) found", file=sys.stderr)
        return 1
    return 0
