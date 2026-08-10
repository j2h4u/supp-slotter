"""JSON-schema loading and data-file validation."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import cast

from jsonschema.exceptions import ValidationError
from jsonschema.protocols import Validator

from planner.contracts import CardLoadError
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.glue_capabilities import IMPLEMENTED_EFFECT_MATCH_VALUE_HANDLERS
from planner.ontology.runtime_program import RuntimeProgram
from planner.paths import SCHEMA_DIR, Paths, strip_root_prefix
from planner.yaml_io import YamlValue, load_yaml


def load_schema(name: str, bundle: OntologyBundle) -> dict[str, object]:
    if name == "pillboxes":
        generated = bundle.decoded.get("pillboxes.schema.json")
        if not isinstance(generated, dict):
            raise RuntimeError("verified ontology bundle is missing generated pillboxes.schema.json")
        return cast(dict[str, object], generated)
    generated_names = {
        "dashboard": "dashboard.schema.json",
        "substance": "card.schema.json",
        "product": "product.schema.json",
        "relations": "relations.schema.json",
        "stacks": "stacks.schema.json",
    }
    generated_name = generated_names.get(name)
    if generated_name is not None:
        generated = bundle.decoded.get(generated_name)
        if not isinstance(generated, dict):
            raise RuntimeError(f"verified ontology bundle is missing generated {generated_name}")
        return cast(dict[str, object], generated)
    schema_path = SCHEMA_DIR / f"{name}.schema.json"
    try:
        text = schema_path.read_text(encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"could not read schema {schema_path}: {e}") from e
    try:
        return cast(dict[str, object], json.loads(text))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"could not parse schema {schema_path}: {e}") from e


def schema_errors(
    data: YamlValue,
    schema_name: str,
    file_path: Path,
    bundle: OntologyBundle,
    *,
    reference_values: Mapping[str, set[str]] | None = None,
) -> list[str]:
    import jsonschema

    schema = load_schema(schema_name, bundle)
    validator: Validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    iter_errors = cast(Callable[[YamlValue], list[ValidationError]], validator.iter_errors)
    # Validate the document itself.  In particular, the relation catalog root
    # is closed: dropping sibling fields here would turn an authored typo into
    # silently ignored data.
    errors = list(iter_errors(data))
    formatted = [
        _format_schema_error(data, schema_name, file_path, detail)
        for err in errors
        for detail in (_nested_unique_item_errors(err) or [err])
    ]
    if schema_name == "pillboxes":
        formatted.extend(_pillbox_slot_anchor_errors(data, file_path, bundle.runtime_program))
    formatted.extend(_generated_contract_errors(data, file_path, schema, reference_values))
    return formatted


def _generated_contract_errors(
    data: YamlValue,
    file_path: Path,
    schema: Mapping[str, object],
    reference_values: Mapping[str, set[str]] | None,
) -> list[str]:
    """Execute generated cross-record rules without duplicating their semantics."""
    raw_contract = schema.get("x-supp-slotter-validation")
    if not isinstance(raw_contract, Mapping) or not isinstance(data, dict):
        return []
    errors: list[str] = []
    for rule_name, raw_rule in raw_contract.items():
        if not isinstance(rule_name, str) or not isinstance(raw_rule, Mapping):
            errors.append(f"{file_path}: generated validation rule is malformed")
            continue
        source = raw_rule.get("source")
        if not isinstance(source, str) or not source:
            # A rule without a source cannot be evaluated safely.  Keep the
            # contract fail-closed while allowing purely structural JSON
            # Schema rules to remain independent of this extension.
            errors.append(f"{file_path}: generated validation rule {rule_name!r} has no source")
            continue
        matches = list(_source_matches(data, source))
        if not matches:
            # A repeated-record rule is vacuously satisfied when its source
            # collection is empty.  Structural JSON Schema validation still
            # rejects a missing or malformed required collection, while this
            # generic extension must not turn unrelated/empty fixture data
            # into a false validation failure.
            continue
        errors.extend(_validate_generated_rule(file_path, rule_name, raw_rule, matches, reference_values))
    return errors


type _SourceMatch = tuple[tuple[str, ...], Mapping[str, object], dict[str, str]]


def _source_matches(data: Mapping[object, object], source: str) -> Iterator[_SourceMatch]:
    tokens = tuple(source.split("."))
    if not tokens or any(not token for token in tokens):
        return

    def walk(  # noqa: PLR0911
        value: object, index: int, path: tuple[str, ...], bindings: dict[str, str]
    ) -> Iterator[_SourceMatch]:
        if index == len(tokens):
            if isinstance(value, Mapping):
                yield path, cast(Mapping[str, object], value), bindings
            return
        if not isinstance(value, Mapping):
            return
        token = tokens[index]
        if token.endswith("[]"):
            field = token[:-2]
            if not field or field not in value:
                return
            children = value[field]
            if not isinstance(children, list):
                return
            for child_index, child in enumerate(children):
                yield from walk(
                    child,
                    index + 1,
                    (*path, field, str(child_index)),
                    bindings,
                )
            return
        if token.startswith("<") and token.endswith(">"):
            binding = token[1:-1]
            if not binding:
                return
            for key, child in value.items():
                if isinstance(key, str):
                    yield from walk(child, index + 1, (*path, key), {**bindings, binding: key})
            return
        if token in value:
            yield from walk(value[token], index + 1, (*path, token), bindings)

    yield from walk(data, 0, (), {})


def _validate_generated_rule(  # noqa: PLR0914
    file_path: Path,
    rule_name: str,
    rule: Mapping[str, object],
    matches: list[_SourceMatch],
    reference_values: Mapping[str, set[str]] | None,
) -> list[str]:
    errors: list[str] = []
    uniqueness = rule.get("uniqueness")
    scope = rule.get("scope")
    target_class = rule.get("target_class")
    source_field = rule.get("source_field")
    semantics = rule.get("semantics")
    if uniqueness is not None and uniqueness != "required":
        errors.append(f"{file_path}: generated validation rule {rule_name!r} has unsupported uniqueness")
    if scope is not None and not isinstance(scope, str):
        errors.append(f"{file_path}: generated validation rule {rule_name!r} has invalid scope")
    if (
        any(value is not None for value in (target_class, source_field, semantics))
        and semantics != "required_reference"
    ):
        errors.append(f"{file_path}: generated validation rule {rule_name!r} has unsupported reference semantics")
    if all(value is None for value in (rule.get("minimum"), uniqueness, target_class, source_field, semantics)):
        errors.append(f"{file_path}: generated validation rule {rule_name!r} has no executable operation")
    field = rule.get("field")
    if field is not None and not isinstance(field, str):
        errors.append(f"{file_path}: generated validation rule {rule_name!r} has invalid field")
    values: list[tuple[tuple[str, ...], object, dict[str, str]]] = []
    for path, record, bindings in matches:
        value = record.get(field) if isinstance(field, str) else bindings.get(_last_placeholder(rule["source"]))
        value_path = (*path, field) if isinstance(field, str) else path
        values.append((value_path, value, bindings))

    minimum = rule.get("minimum")
    if minimum is not None:
        if isinstance(minimum, bool) or not isinstance(minimum, int):
            errors.append(f"{file_path}: generated validation rule {rule_name!r} has invalid minimum")
        else:
            for path, value, _bindings in values:
                if isinstance(value, int) and not isinstance(value, bool) and value < minimum:
                    errors.append(
                        f"{file_path}: generated validation rule {rule_name!r} rejected {'.'.join(path)}="
                        f"{value!r}; minimum={minimum!r}"
                    )
    if uniqueness == "required":
        seen: dict[tuple[object, tuple[tuple[str, str], ...]], tuple[str, ...]] = {}
        for path, value, bindings in values:
            if value is None:
                continue
            scope_key = () if scope == "global" else _parent_scope_bindings(rule.get("source"), bindings)
            key = (value, scope_key)
            previous = seen.get(key)
            if previous is not None:
                errors.append(
                    f"{file_path}: generated validation rule {rule_name!r} rejected duplicate value {value!r} "
                    f"at {'.'.join(path)} (previously at {'.'.join(previous)}); scope={scope!r}"
                )
            else:
                seen[key] = path

    if (
        isinstance(target_class, str)
        and isinstance(source_field, str)
        and semantics == "required_reference"
        and reference_values is not None
    ):
        allowed = reference_values.get(target_class)
        if allowed is None:
            errors.append(f"{file_path}: generated validation rule {rule_name!r} has no {target_class!r} references")
        else:
            for path, record, _bindings in matches:
                value = record.get(source_field)
                if isinstance(value, str) and value not in allowed:
                    errors.append(
                        f"{file_path}: generated validation rule {rule_name!r} rejected unknown reference "
                        f"{value!r} at {'.'.join((*path, source_field))}"
                    )
    return errors


def _last_placeholder(source: object) -> str:
    if not isinstance(source, str):
        return ""
    return next(
        (token[1:-1] for token in reversed(source.split(".")) if token.startswith("<") and token.endswith(">")), ""
    )


def _parent_scope_bindings(source: object, bindings: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    """Group a sourced record by its parent placeholders for non-global rules."""
    leaf = _last_placeholder(source)
    return tuple(sorted((key, value) for key, value in bindings.items() if key != leaf))


def _pillbox_slot_anchor_errors(data: YamlValue, file_path: Path, runtime: RuntimeProgram) -> list[str]:
    if not isinstance(data, dict):
        return []
    errors: list[str] = []
    dimensions = runtime.effect_match_dimensions
    for pillbox_id, pillbox in data.items():
        if not isinstance(pillbox_id, str) or not isinstance(pillbox, dict):
            continue
        slots = pillbox.get("slots")
        if not isinstance(slots, dict):
            continue
        for slot_id, slot in slots.items():
            if not isinstance(slot_id, str) or not isinstance(slot, dict):
                continue
            for dimension in dimensions:
                handler = IMPLEMENTED_EFFECT_MATCH_VALUE_HANDLERS.get(dimension.value_type)
                value = slot.get(dimension.slot_field)
                if handler == "capability_values" and isinstance(value, str) and value not in runtime.slot_near_values:
                    errors.append(
                        f"{file_path}: {pillbox_id}.slots.{slot_id}.{dimension.slot_field} "
                        f"'{value}' is not in ontology slot anchors"
                    )
    return errors


def _format_schema_error(
    data: YamlValue,
    schema_name: str,
    file_path: Path,
    err: ValidationError,
) -> str:
    loc = _schema_error_location(err)
    if schema_name == "relations" and isinstance(err.instance, dict):
        path = tuple(str(part) for part in err.absolute_path)
        if path and path[-1] in {"source_selector", "target_selector"}:
            side = path[-1].removesuffix("_selector")
            instance = cast(dict[object, object], err.instance)
            found = ", ".join(sorted(str(key) for key in instance)) or "none"
            return (
                f"{file_path}: {loc}: relation endpoints must choose exactly one source endpoint and exactly one "
                f"target endpoint; found {side} endpoints: {found}. Use the canonical selector shape "
                "{entity: {entity_id|name}} or {category, term} on each side."
            )
    del data
    return f"{file_path}: {loc}: {err.message}"


def _nested_unique_item_errors(error: ValidationError) -> list[ValidationError]:
    """Expose actionable uniqueItems failures hidden under nullable anyOf branches."""
    if error.validator == "uniqueItems":
        return [error]
    return [detail for context in error.context for detail in _nested_unique_item_errors(context)]


def _schema_error_location(err: ValidationError) -> str:
    return "/".join(str(p) for p in err.absolute_path) or "<root>"


def validate_schemas(paths: Paths, bundle: OntologyBundle) -> int:
    """Validate every YAML data file against its JSON Schema."""
    references = _reference_values(paths)
    errors = [
        *_singular_schema_errors(paths, bundle, references),
        *_collection_schema_errors(paths, bundle),
    ]

    if errors:
        for error in errors:
            print(f"ERROR: {strip_root_prefix(error)}", file=sys.stderr)
        print(f"\n{len(errors)} schema error(s) found", file=sys.stderr)
        return 1
    return 0


def _singular_schema_errors(
    paths: Paths,
    bundle: OntologyBundle,
    references: Mapping[str, set[str]],
) -> list[str]:
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
        errors.extend(schema_errors(data, schema_name, path, bundle, reference_values=references))
    return errors


def _reference_values(paths: Paths) -> dict[str, set[str]]:
    """Expose authored record identities to generated reference rules."""
    try:
        stacks = load_yaml(paths.stacks_file)
    except CardLoadError:
        return {}
    if not isinstance(stacks, Mapping):
        return {}
    return {"Stack": {key for key in stacks if isinstance(key, str)}}


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
