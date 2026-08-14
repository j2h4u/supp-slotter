"""Generic metadata-driven resolution of draft entity references."""

# Ontology artifacts are deliberately structural at this boundary; the
# verified compiler owns their detailed schema.
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import re
import sys
from collections.abc import Iterator, Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping, normalize_similarity_text
from planner.cards.search import search_score
from planner.contracts import CardLoadError
from planner.ontology.artifacts import OntologyBundle, _is_verified_bundle
from planner.ontology.errors import OntologyInfrastructureError
from planner.paths import strip_root_prefix


@dataclass(frozen=True, slots=True)
class ReferenceResolution:
    """The repository and schema metadata needed to resolve one reference kind."""

    source_path: str
    reference_path: str
    target_entity_class: str
    identity_field: str
    identity_pattern: re.Pattern[str]
    name_field: str
    aliases_field: str | None
    form_field: str | None
    entity_label: str
    document_path: str
    document_shape: str
    source_id: str
    target_source_id: str
    instruction_kind: str
    source_entity_class: str
    target_schema_artifact: str

    @property
    def reference_segments(self) -> tuple[str, ...]:
        return tuple(self.reference_path.split("."))


@dataclass(frozen=True, slots=True)
class EntityIdentity:
    identity: str
    label: str
    path: Path
    terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MaintenanceContract:
    """All repository locations and rewrite relations declared by ontology."""

    substance_path: str
    product_path: str
    stack_path: str
    product_substance: ReferenceResolution
    substance_preferences: tuple[ReferenceResolution, ...]
    stack_products: ReferenceResolution


def load_reference_resolutions(bundle: OntologyBundle) -> tuple[ReferenceResolution, ...]:  # noqa: C901, PLR0914
    """Derive every reference relation from a verified projection contract."""
    if not _is_verified_bundle(bundle):
        raise OntologyInfrastructureError("Maintenance requires a verified OntologyBundle")
    projection = _projection_mapping(bundle.projection_map)
    mappings = {
        str(mapping["source"]): cast(Mapping[str, object], mapping)
        for mapping in cast(list[object], projection["mappings"])
        if isinstance(mapping, Mapping) and isinstance(mapping.get("source"), str)
    }
    sources = {
        str(source["id"]): cast(Mapping[str, object], source)
        for source in cast(list[object], projection["sources"])
        if isinstance(source, Mapping) and isinstance(source.get("id"), str)
    }
    result: list[ReferenceResolution] = []
    for source_id, mapping in mappings.items():
        document_source = sources.get(source_id)
        if document_source is None:
            raise OntologyInfrastructureError(f"Repository projection has no source {source_id!r}")
        document_locator = _required_mapping(document_source, "locator")
        if document_locator.get("kind") == "catalog_ref":
            continue
        document_path = _locator_path(document_locator, source_id)
        document_shape = _required_text(mapping, "document_shape")
        for instruction in _instruction_list(mapping):
            if instruction.get("kind") not in {"reference", "sequence"}:
                continue
            target_class = instruction.get("target")
            if not isinstance(target_class, str) or not target_class:
                continue
            target_source_id, target_mapping = _find_target_mapping(mappings, target_class)
            target_source = sources.get(target_source_id)
            if target_source is None:
                raise OntologyInfrastructureError(f"No repository source declares target entity class {target_class!r}")
            target_locator = _required_mapping(target_source, "locator")
            source_path = _locator_path(target_locator, target_source_id)
            identity = _required_mapping(target_mapping, "identity")
            identity_field = _required_text(identity, "source")
            if identity_field == "<key>":
                continue
            target_instructions = _instruction_list(target_mapping)
            name_field = _instruction_field(target_instructions, "alias")
            aliases_field = _optional_sequence_field(target_instructions)
            target_maintenance = _maintenance_metadata(target_mapping, target_source_id)
            schema = _schema_for_artifact(bundle, target_maintenance["schema_artifact"], target_class)
            properties = schema.get("properties")
            if not isinstance(properties, Mapping):
                raise OntologyInfrastructureError(f"Generated schema for {target_class!r} has no properties")
            identity_schema = properties.get(identity_field)
            identity_pattern = _pattern(identity_schema, target_class, identity_field)
            form_field = _optional_declared_field(
                target_instructions, properties, identity_field, name_field, aliases_field
            )
            result.append(
                ReferenceResolution(
                    source_path=source_path,
                    reference_path=_required_text(instruction, "source"),
                    target_entity_class=target_class,
                    identity_field=identity_field,
                    identity_pattern=re.compile(identity_pattern),
                    name_field=name_field,
                    aliases_field=aliases_field,
                    form_field=form_field,
                    entity_label=target_maintenance["label"],
                    document_path=document_path,
                    document_shape=document_shape,
                    source_id=source_id,
                    target_source_id=target_source_id,
                    instruction_kind=str(instruction["kind"]),
                    source_entity_class=_required_text(mapping, "root_class"),
                    target_schema_artifact=target_maintenance["schema_artifact"],
                )
            )
    if not result:
        raise OntologyInfrastructureError("Repository projection declares no maintenance references")
    return tuple(result)


def load_reference_resolution(bundle: OntologyBundle) -> ReferenceResolution:
    """Return the first entity reference in the verified projection."""
    for item in load_reference_resolutions(bundle):
        if item.instruction_kind == "reference":
            return item
    return _missing_reference()


def load_maintenance_contract(bundle: OntologyBundle) -> MaintenanceContract:
    """Build the complete maintenance contract from formal projection metadata."""
    resolutions = load_reference_resolutions(bundle)
    projection = _projection_mapping(bundle.projection_map)
    sources = {
        str(source["id"]): cast(Mapping[str, object], source)
        for source in cast(list[object], projection["sources"])
        if isinstance(source, Mapping) and isinstance(source.get("id"), str)
    }
    mappings = {
        str(mapping["source"]): cast(Mapping[str, object], mapping)
        for mapping in cast(list[object], projection["mappings"])
        if isinstance(mapping, Mapping) and isinstance(mapping.get("source"), str)
    }
    substance_source = _source_for_role(mappings, "substance")
    product_source = _source_for_role(mappings, "product")
    stack_source = _source_for_role(mappings, "stack")
    source_paths = {
        key: _locator_path(_required_mapping(sources[key], "locator"), key)
        for key in (substance_source, product_source, stack_source)
    }
    product_substance = _unique_resolution(resolutions, source_id=product_source, target_source_id=substance_source)
    preferences = tuple(
        item for item in resolutions if item.source_id == substance_source and item.target_source_id == substance_source
    )
    stack_products = _unique_resolution(resolutions, source_id=stack_source, target_source_id=product_source)
    return MaintenanceContract(
        substance_path=source_paths[substance_source],
        product_path=source_paths[product_source],
        stack_path=source_paths[stack_source],
        product_substance=product_substance,
        substance_preferences=preferences,
        stack_products=stack_products,
    )


def has_draft_reference(document: Mapping[str, object], resolution: ReferenceResolution) -> bool:
    """Return whether a document has a non-schema-shaped reference value."""
    return any(
        isinstance(value, str) and resolution.identity_pattern.fullmatch(value) is None
        for _container, _key, value in iter_reference_values(document, resolution)
    )


def rewrite_references(
    document: dict[str, object], resolution: ReferenceResolution, renames: Mapping[str, str]
) -> bool:
    """Rewrite identity aliases in all locations declared by the reference path."""
    changed = False
    for container, key, value in iter_reference_values(document, resolution):
        if isinstance(value, str) and value in renames:
            _set_reference_value(container, key, renames[value])
            changed = True
    return changed


def resolve_references(  # noqa: PLR0913
    *,
    document_path: Path,
    document: dict[str, object],
    collection_dir: Path,
    resolution: ReferenceResolution,
    identity_renames: Mapping[str, str],
    errors: list[str],
) -> bool:
    """Resolve draft values against the metadata-declared target collection."""
    identities = _load_identities(collection_dir, resolution, identity_renames, errors)
    if not identities:
        return False
    index = _identity_index(identities)
    changed = False
    for index_number, (_container, _key, value) in enumerate(iter_reference_values(document, resolution)):
        if not isinstance(value, str) or resolution.identity_pattern.fullmatch(value) is not None:
            continue
        candidates = index.get(normalize_similarity_text(value), {})
        if len(candidates) == 1:
            container, key, _ = list(iter_reference_values(document, resolution))[index_number]
            _set_reference_value(container, key, next(iter(candidates)))
            changed = True
            continue
        if not candidates:
            _append_resolution_error(
                errors, _unknown_message(document_path, index_number, value, identities, resolution)
            )
            continue
        _append_resolution_error(errors, _ambiguous_message(document_path, index_number, value, candidates, resolution))
    return changed


def iter_reference_values(
    document: Mapping[str, object], resolution: ReferenceResolution
) -> Iterator[tuple[MutableMapping[str, object] | list[object], str | int, object]]:
    """Yield mutable parent mappings and values selected by a dotted path."""
    yield from _walk_reference(document, resolution.reference_segments)


def _walk_reference(
    value: object, segments: tuple[str, ...]
) -> Iterator[tuple[MutableMapping[str, object] | list[object], str | int, object]]:
    if not segments or not isinstance(value, Mapping):
        return
    segment = segments[0]
    if segment.endswith("[]"):
        yield from _walk_list_segment(value, segment[:-2], segments)
        return
    if segment not in value:
        return
    if len(segments) == 1:
        if isinstance(value, MutableMapping):
            yield value, segment, value[segment]
        return
    yield from _walk_reference(value[segment], segments[1:])


def _set_reference_value(container: MutableMapping[str, object] | list[object], key: str | int, value: str) -> None:
    if isinstance(container, list):
        if isinstance(key, int):
            container[key] = value
        return
    if isinstance(key, str):
        container[key] = value


def _walk_list_segment(
    value: Mapping[str, object], field: str, segments: tuple[str, ...]
) -> Iterator[tuple[MutableMapping[str, object] | list[object], str | int, object]]:
    if field == "<key>":
        yield from _walk_keyed_list(value, segments)
        return
    members = value.get(field)
    if not isinstance(members, list):
        return
    if len(segments) == 1:
        yield from ((members, index, item) for index, item in enumerate(members))
        return
    for member in members:
        yield from _walk_reference(member, segments[1:])


def _walk_keyed_list(
    value: Mapping[str, object], segments: tuple[str, ...]
) -> Iterator[tuple[MutableMapping[str, object] | list[object], str | int, object]]:
    for members in value.values():
        if not isinstance(members, list):
            continue
        if len(segments) == 1:
            yield from ((members, index, item) for index, item in enumerate(members))
            continue
        for member in members:
            yield from _walk_reference(member, segments[1:])


def _load_identities(
    collection_dir: Path,
    resolution: ReferenceResolution,
    identity_renames: Mapping[str, str],
    errors: list[str],
) -> list[EntityIdentity]:
    identities: list[EntityIdentity] = []
    for path in sorted(collection_dir.glob("*.yaml")):
        try:
            card = cast(dict[str, object], load_card_mapping(path, resolution.target_entity_class.casefold()))
        except CardLoadError as error:
            _append_resolution_error(errors, f"auto-maintenance: could not read {strip_root_prefix(error.message)}")
            continue
        raw_identity = card.get(resolution.identity_field)
        identity = raw_identity if isinstance(raw_identity, str) else identity_renames.get(path.stem)
        if identity is None:
            continue
        identities.append(_identity(path, card, identity, resolution))
    return identities


def _identity(path: Path, card: Mapping[str, object], identity: str, resolution: ReferenceResolution) -> EntityIdentity:
    name_raw = card.get(resolution.name_field)
    name = name_raw if isinstance(name_raw, str) else identity
    form = _field_string(card, resolution.form_field)
    label = f"{name} ({form})" if form else name
    terms = [identity, name, _stem_without_identity(path, resolution.identity_pattern)]
    if form:
        terms.extend((f"{name} {form}", f"{name} ({form})"))
    aliases = card.get(resolution.aliases_field) if resolution.aliases_field else None
    if isinstance(aliases, list):
        for alias in aliases:
            if isinstance(alias, str):
                terms.append(alias)
                if form:
                    terms.append(f"{alias} {form}")
    return EntityIdentity(identity, label, path, tuple(term for term in terms if term))


def _stem_without_identity(path: Path, identity_pattern: re.Pattern[str]) -> str:
    pattern = identity_pattern.pattern.removeprefix("^").removesuffix("$")
    try:
        return re.sub(pattern, "", path.stem)
    except re.error:
        return path.stem


def _identity_index(identities: list[EntityIdentity]) -> dict[str, dict[str, EntityIdentity]]:
    index: dict[str, dict[str, EntityIdentity]] = {}
    for identity in identities:
        for term in identity.terms:
            key = normalize_similarity_text(term)
            if key:
                index.setdefault(key, {})[identity.identity] = identity
    return index


def _unknown_message(
    path: Path,
    index_number: int,
    value: str,
    identities: list[EntityIdentity],
    resolution: ReferenceResolution,
) -> str:
    candidates = _candidate_labels(value, identities)
    suffix = f" Candidates: {', '.join(candidates)}." if candidates else ""
    return (
        f"{path}: {resolution.reference_path}[{index_number}] '{value}' could not be resolved "
        f"to a unique {resolution.entity_label}. Use an exact name+form, alias, filename stem, "
        f"or explicit identity.{suffix}"
    )


def _ambiguous_message(
    path: Path,
    index_number: int,
    value: str,
    candidates: Mapping[str, EntityIdentity],
    resolution: ReferenceResolution,
) -> str:
    labels = [
        f"{identity.identity} {identity.label}"
        for identity in sorted(candidates.values(), key=lambda item: item.label.casefold())
    ]
    return (
        f"{path}: {resolution.reference_path}[{index_number}] '{value}' is ambiguous: "
        f"{', '.join(labels)}. Use a more specific name+form or explicit identity."
    )


def _candidate_labels(value: str, identities: list[EntityIdentity]) -> list[str]:
    scored: list[tuple[float, str]] = []
    for identity in identities:
        score = search_score(value, list(identity.terms))
        if score > 0:
            scored.append((score, f"{identity.identity} {identity.label}"))
    return [label for _score, label in sorted(scored, key=lambda item: (-item[0], item[1].casefold()))[:5]]


def _append_resolution_error(errors: list[str], message: str) -> None:
    errors.append(message)
    print(f"ERROR: {strip_root_prefix(message)}", file=sys.stderr)


def _projection_mapping(projection: Mapping[str, object]) -> Mapping[str, object]:
    nested = projection.get("repository_projection")
    result = nested if isinstance(nested, Mapping) else projection
    sources = result.get("sources") if isinstance(result, Mapping) else None
    mappings = result.get("mappings") if isinstance(result, Mapping) else None
    if isinstance(sources, list) and mappings is None:
        rendered: list[dict[str, object]] = []
        for source in sources:
            if not isinstance(source, Mapping) or not isinstance(source.get("id"), str):
                continue
            documents = source.get("documents")
            if not isinstance(documents, Mapping):
                continue
            rendered.append({"source": source["id"], **dict(documents)})
        if rendered:
            return {"sources": sources, "mappings": rendered}
    if not isinstance(sources, list) or not isinstance(mappings, list):
        raise OntologyInfrastructureError("Compiled projection map has no repository projection metadata")
    return result


def _missing_reference() -> ReferenceResolution:
    raise OntologyInfrastructureError("Repository projection declares no entity reference for maintenance")


def _find_target_mapping(
    mappings: Mapping[str, Mapping[str, object]], target_class: str
) -> tuple[str, Mapping[str, object]]:
    matches = [
        (source_id, mapping) for source_id, mapping in mappings.items() if mapping.get("root_class") == target_class
    ]
    if len(matches) != 1:
        raise OntologyInfrastructureError(
            f"Repository projection must declare exactly one source for target class {target_class!r}"
        )
    return matches[0]


def _source_for_role(mappings: Mapping[str, Mapping[str, object]], role: str) -> str:
    matches = [
        source_id
        for source_id, mapping in mappings.items()
        if isinstance(mapping.get("maintenance"), Mapping) and _maintenance_metadata(mapping, source_id)["role"] == role
    ]
    if len(matches) != 1:
        raise OntologyInfrastructureError(
            f"Repository projection must declare exactly one maintenance source for role {role!r}"
        )
    return matches[0]


def _unique_resolution(
    resolutions: tuple[ReferenceResolution, ...], *, source_id: str, target_source_id: str
) -> ReferenceResolution:
    matches = [
        item for item in resolutions if item.source_id == source_id and item.target_source_id == target_source_id
    ]
    if len(matches) != 1:
        raise OntologyInfrastructureError(
            f"Repository projection must declare exactly one maintenance relation {source_id!r} -> {target_source_id!r}"
        )
    return matches[0]


def _instruction_list(mapping: Mapping[str, object]) -> list[Mapping[str, object]]:
    raw = mapping.get("instructions")
    return (
        [cast(Mapping[str, object], item) for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []
    )


def _instruction_field(instructions: list[Mapping[str, object]], kind: str) -> str:
    for instruction in instructions:
        source = instruction.get("source")
        if (
            instruction.get("kind") == kind
            and isinstance(source, str)
            and "." not in source
            and not source.endswith("[]")
        ):
            return source
    raise OntologyInfrastructureError(f"Repository projection has no {kind} field")


def _optional_sequence_field(instructions: list[Mapping[str, object]]) -> str | None:
    for instruction in instructions:
        source = instruction.get("source")
        if instruction.get("kind") == "sequence" and isinstance(source, str) and source.endswith("[]"):
            return source[:-2]
    return None


def _optional_declared_field(
    instructions: list[Mapping[str, object]],
    properties: Mapping[str, object],
    identity_field: str,
    name_field: str,
    aliases_field: str | None,
) -> str | None:
    for instruction in instructions:
        source = instruction.get("source")
        if instruction.get("kind") != "slot" or not isinstance(source, str) or "." in source or source.endswith("[]"):
            continue
        if source in {identity_field, name_field, aliases_field} or source not in properties:
            continue
        shape = properties[source]
        if isinstance(shape, Mapping) and _allows_string(shape):
            return source
    return None


def _schema_for_artifact(bundle: OntologyBundle, artifact_name: str, entity_class: str) -> Mapping[str, object]:
    decoded = bundle.decoded.get(artifact_name)
    if not isinstance(decoded, Mapping):
        raise OntologyInfrastructureError(
            f"Generated maintenance schema artifact {artifact_name!r} is missing or malformed for {entity_class!r}"
        )
    reference = decoded.get("$ref")
    if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
        raise OntologyInfrastructureError(
            f"Generated maintenance schema artifact {artifact_name!r} has no exact root definition"
        )
    definitions = decoded.get("$defs")
    if not isinstance(definitions, Mapping):
        raise OntologyInfrastructureError(f"Generated schema artifact {artifact_name!r} has no definitions")
    definition_name = reference.removeprefix("#/$defs/")
    value = definitions.get(definition_name)
    if not isinstance(value, Mapping):
        raise OntologyInfrastructureError(
            f"Generated schema artifact {artifact_name!r} has no definition {definition_name!r}"
        )
    return value


def _maintenance_metadata(mapping: Mapping[str, object], source_id: str) -> Mapping[str, str]:
    value = mapping.get("maintenance")
    if not isinstance(value, Mapping):
        raise OntologyInfrastructureError(f"Repository projection source {source_id!r} has no maintenance metadata")
    result = {key: value.get(key) for key in ("role", "label", "schema_artifact")}
    if not all(isinstance(item, str) and item for item in result.values()):
        raise OntologyInfrastructureError(
            f"Repository projection source {source_id!r} has invalid maintenance metadata"
        )
    return cast(Mapping[str, str], result)


def _pattern(value: object, entity_class: str, identity_field: str) -> str:
    if isinstance(value, Mapping) and isinstance(value.get("pattern"), str):
        return value["pattern"]
    raise OntologyInfrastructureError(
        f"Generated schema {entity_class!r}.{identity_field} has no identity pattern for maintenance"
    )


def _allows_string(value: Mapping[str, object]) -> bool:
    kind = value.get("type")
    if kind == "string":
        return True
    return isinstance(kind, list) and "string" in kind


def _required_mapping(value: Mapping[str, object], key: str) -> Mapping[str, object]:
    result = value.get(key)
    if not isinstance(result, Mapping):
        raise OntologyInfrastructureError(f"Ontology metadata field {key!r} must be a mapping")
    return result


def _required_text(value: Mapping[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise OntologyInfrastructureError(f"Ontology metadata field {key!r} must be non-empty text")
    return result


def _locator_path(value: Mapping[str, object], source_id: str) -> str:
    if "path" in value:
        return _required_text(value, "path")
    raise OntologyInfrastructureError(f"Maintenance source {source_id!r} must declare a filesystem path")


def _field_string(card: Mapping[str, object], field: str | None) -> str | None:
    value = card.get(field) if field else None
    return value if isinstance(value, str) else None
