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
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{file_path}: {loc}: {err.message}")
    return out


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
