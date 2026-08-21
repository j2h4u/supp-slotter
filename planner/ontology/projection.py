"""Generic, deterministic repository-to-RDF projection.

The projector is deliberately an interpreter for compiled projection
instructions.  It contains no card-field routing or scheduling semantics.
"""

# The compiled instruction payload is intentionally structural.  Detailed
# schema validation belongs to the ontology artifact loader.
# pyright: reportAny=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownLambdaType=false, reportArgumentType=false

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import quote

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from planner.ontology.artifacts import OntologyBundle, _is_verified_bundle
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.repository_sources import (
    RepositoryDocument,
    _discover_repository_sources,
)


@dataclass(frozen=True)
class ProvenanceRecord:
    source_id: str
    source_path: str
    field_path: str
    subject: str
    predicate: str


@dataclass(frozen=True)
class ProjectionResult:
    """RDF graph plus stable serializable and source-provenance views."""

    graph: Graph
    triples: tuple[tuple[str, str, str], ...]
    provenance: tuple[ProvenanceRecord, ...]

    @property
    def canonical_ntriples(self) -> bytes:
        return ("".join(f"{subject} {predicate} {obj} .\n" for subject, predicate, obj in self.triples)).encode("utf-8")

    @property
    def source_provenance(self) -> tuple[ProvenanceRecord, ...]:
        return self.provenance


@dataclass
class _ProjectionContext:
    graph: Graph
    emitted: dict[tuple[object, object, object], ProvenanceRecord]
    repository_root: Path
    document: RepositoryDocument
    value: object
    key: str | None
    instructions: list[dict[str, object]]
    base_iri: str
    subject: URIRef | None = None


@dataclass(frozen=True)
class _InlineNode:
    subject: URIRef
    predicate: URIRef
    path: tuple[str, ...]
    leaf: object
    instruction: Mapping[str, object]


def project_repository(repository_root: Path, ontology: OntologyBundle) -> ProjectionResult:
    """Project all declared repository sources using compiled instructions."""

    if not _is_verified_bundle(ontology):
        raise OntologyInfrastructureError("Repository projection requires a verified OntologyBundle")
    return _project_repository_with_projection(repository_root, ontology.projection_map)


def _project_repository_with_projection(
    repository_root: Path, projection_map: Mapping[str, object]
) -> ProjectionResult:
    """Private structural interpreter used only by focused fixture tests."""

    projection = _projection_mapping(projection_map)
    base_iri = _base_iri(projection)
    documents = _discover_repository_sources(repository_root, projection_map)
    graph = Graph()
    emitted: dict[tuple[object, object, object], ProvenanceRecord] = {}
    for document in documents:
        instructions = document.documents.get("instructions")
        if not isinstance(instructions, list):
            raise OntologyInfrastructureError(f"Source {document.source_id!r} has no instructions")
        normalized_instructions = [_instruction(item, document.source_id) for item in instructions]
        _validate_structure(document, normalized_instructions)
        if document.documents.get("document_shape") == "keyed-map":
            if not isinstance(document.document, Mapping):
                raise OntologyInfrastructureError(f"Keyed source {document.source_id!r} is not a mapping")
            for key in sorted(document.document, key=str):
                value = document.document[key]
                _project_document(
                    _ProjectionContext(
                        graph, emitted, repository_root, document, value, str(key), normalized_instructions, base_iri
                    )
                )
        else:
            _project_document(
                _ProjectionContext(
                    graph,
                    emitted,
                    repository_root,
                    document,
                    document.document,
                    None,
                    normalized_instructions,
                    base_iri,
                )
            )
    triples = tuple(sorted((_term_text(s), _term_text(p), _term_text(o)) for s, p, o in emitted))
    provenance = tuple(
        sorted(
            (emitted[key] for key in emitted),
            key=lambda item: (item.source_path, item.field_path, item.predicate, item.subject),
        )
    )
    return ProjectionResult(graph, triples, provenance)


def _project_document(context: _ProjectionContext) -> None:
    context.subject = _document_subject(context.base_iri, context.document, context.value, context.key)
    subject = context.subject
    _emit(
        context.graph,
        context.emitted,
        subject,
        RDF.type,
        URIRef(context.base_iri + context.document.root_class),
        context.document,
        "<root>",
        context.repository_root,
    )
    for path, leaf, node_kind in _walk(context.value, (context.key,) if context.key is not None else ()):
        compatible = _compatible_instructions(path, node_kind, context.instructions)
        for instruction in compatible:
            _project_instruction(context, path, leaf, instruction)


def _document_subject(base_iri: str, document: RepositoryDocument, value: object, key: str | None) -> URIRef:
    identity = document.documents.get("identity")
    if identity is None and key is None:
        identity_value: object = document.source_id
    elif not isinstance(identity, Mapping):
        raise OntologyInfrastructureError(f"Source {document.source_id!r} has no identity instruction")
    else:
        identity_source = identity.get("source")
        if identity_source == "<key>" and key is None:
            raise OntologyInfrastructureError(f"Keyed source {document.source_id!r} has no key")
        identity_value = key if identity_source == "<key>" else _lookup(value, str(identity_source))
    if identity_value is _MISSING or isinstance(identity_value, (Mapping, list)):
        raise OntologyInfrastructureError(f"Source {document.source_id!r} identity is missing or non-scalar")
    return URIRef(_entity_iri(base_iri, document.root_class, identity_value))


def _compatible_instructions(
    path: tuple[str, ...], node_kind: str, instructions: list[dict[str, object]]
) -> list[dict[str, object]]:
    matching = _matching_instructions(path, instructions)
    if not matching:
        return []
    compatible = [instruction for instruction in matching if _shape_compatible(instruction, node_kind)]
    if not compatible and node_kind not in {"list-item", "mapping-item"}:
        raise OntologyInfrastructureError(f"Projection instructions are incompatible with {node_kind} at {path}")
    return compatible


def _project_instruction(
    context: _ProjectionContext, path: tuple[str, ...], leaf: object, instruction: Mapping[str, object]
) -> None:
    document = context.document
    kind = instruction["kind"]
    if kind not in {
        "slot",
        "alias",
        "sequence",
        "keyed-map",
        "opaque-value",
        "reference",
        "inlined-node",
        "path-token",
    }:
        raise OntologyInfrastructureError(f"Unsupported projection instruction kind: {kind!r}")
    predicate_value = instruction.get("predicate")
    if not isinstance(predicate_value, str) or not predicate_value:
        raise OntologyInfrastructureError(f"Instruction for {document.source_id!r} has no predicate")
    if leaf is _CONTAINER:
        return
    predicate = URIRef(predicate_value)
    triple_subject = _instruction_subject(context, instruction, path)
    if kind == "inlined-node":
        _emit_inlined_node(context, _InlineNode(triple_subject, predicate, path, leaf, instruction))
        return
    obj = _instruction_object(instruction, kind, context.base_iri, path, leaf)
    _emit(
        context.graph,
        context.emitted,
        triple_subject,
        predicate,
        obj,
        document,
        _display_path(path),
        context.repository_root,
    )


def _instruction_subject(
    context: _ProjectionContext, instruction: Mapping[str, object], path: tuple[str, ...]
) -> URIRef:
    subject_ref = instruction.get("subject")
    if subject_ref is None:
        assert context.subject is not None
        return context.subject
    if not isinstance(subject_ref, str):
        raise OntologyInfrastructureError(f"Instruction subject is invalid at {path}")
    return _inlined_subject_iri(
        base_iri=context.base_iri,
        root_subject=context.subject,
        subject_pattern=subject_ref,
        actual_path=path,
        document_value=context.value,
        key=context.key,
        instructions=context.instructions,
    )


def _emit_inlined_node(context: _ProjectionContext, node: _InlineNode) -> None:
    triple_subject, predicate, path, leaf, instruction = (
        node.subject,
        node.predicate,
        node.path,
        node.leaf,
        node.instruction,
    )
    target_class = instruction.get("target")
    if not isinstance(target_class, str) or not target_class:
        raise OntologyInfrastructureError(f"Inlined-node instruction has invalid target at {path}")
    obj = URIRef(_child_entity_iri(context.base_iri, target_class, triple_subject, path, leaf))
    display_path = _display_path(path)
    _emit(
        context.graph,
        context.emitted,
        triple_subject,
        predicate,
        obj,
        context.document,
        display_path,
        context.repository_root,
    )
    _emit(
        context.graph,
        context.emitted,
        obj,
        RDF.type,
        URIRef(context.base_iri + target_class),
        context.document,
        display_path,
        context.repository_root,
    )


def _instruction_object(
    instruction: Mapping[str, object], kind: object, base_iri: str, path: tuple[str, ...], leaf: object
) -> URIRef | Literal:
    target = instruction.get("target")
    if target is not None:
        if not isinstance(target, str) or not target or isinstance(leaf, (Mapping, list)):
            raise OntologyInfrastructureError(f"Reference target has invalid value at {path}")
        return URIRef(_entity_iri(base_iri, target, leaf))
    if kind == "reference":
        if not isinstance(target, str) or isinstance(leaf, (Mapping, list)):
            raise OntologyInfrastructureError(f"Reference instruction has invalid target/value at {path}")
        return URIRef(_entity_iri(base_iri, target, leaf))
    if kind == "path-token":
        token = instruction.get("token")
        token_index = instruction.get("token_index", 0)
        source = instruction.get("source")
        if (
            not isinstance(token, str)
            or not isinstance(source, str)
            or isinstance(token_index, bool)
            or not isinstance(token_index, int)
        ):
            raise OntologyInfrastructureError(f"Path-token instruction is invalid at {path}")
        return _literal(_path_token_value(source, path, token, token_index))
    datatype = instruction.get("datatype")
    return _literal(leaf, datatype if isinstance(datatype, str) else None)


def _validate_structure(document: RepositoryDocument, instructions: list[dict[str, object]]) -> None:
    allowed = [str(item["source"]) for item in instructions]
    root = document.document
    if document.documents.get("document_shape") == "keyed-map":
        if not isinstance(root, Mapping):
            raise OntologyInfrastructureError(f"Source {document.source_id!r} must be a mapping")
        for key, value in root.items():
            _validate_paths(document, instructions, allowed, _walk(value, (str(key),)))
    else:
        _validate_paths(document, instructions, allowed, _walk(root, ()))


def _validate_paths(
    document: RepositoryDocument,
    instructions: list[dict[str, object]],
    allowed: list[str],
    walked: list[tuple[tuple[str, ...], object, str]],
) -> None:
    for path, leaf, node_kind in walked:
        matching = _matching_instructions(path, instructions)
        if leaf is _CONTAINER and not matching:
            raise _unknown(document, path)
        if not matching and not _has_instruction_prefix(path, allowed, node_kind):
            raise _unknown(document, path)
        if _has_incompatible_instruction(matching, node_kind):
            raise _unknown(document, path)


def _has_incompatible_instruction(matching: list[dict[str, object]], node_kind: str) -> bool:
    return bool(
        matching
        and not any(_shape_compatible(instruction, node_kind) for instruction in matching)
        and node_kind not in {"list-item", "mapping-item"}
    )


def _walk(value: object, path: tuple[str, ...]) -> list[tuple[tuple[str, ...], object, str]]:
    if isinstance(value, Mapping):
        if not value:
            return [(path, _CONTAINER, "mapping")]
        result: list[tuple[tuple[str, ...], object, str]] = []
        for key in sorted(value, key=str):
            child_path = (*path, str(key))
            if isinstance(value[key], Mapping):
                result.append((child_path, value[key], "mapping-item"))
            result.extend(_walk(value[key], child_path))
        return result
    if isinstance(value, list):
        list_path = (
            (*path[:-1], path[-1] + "[]")
            if path and not path[-1].endswith("[]") and not _is_indexed_list_token(path[-1])
            else path
        )
        if not value:
            return [(list_path, _CONTAINER, "list")]
        result = []
        for index, item in enumerate(value):
            item_path = (*path[:-1], f"{path[-1]}[{index}]") if path else (f"[{index}]",)
            if isinstance(item, (Mapping, str, int, float, bool)) or item is None:
                result.append((item_path, item, "list-item"))
            result.extend(_walk(item, item_path))
        return result
    return [(path, value, "scalar")]


def _matching_instructions(path: tuple[str, ...], instructions: list[dict[str, object]]) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for item in instructions:
        source = item.get("source")
        if isinstance(source, str) and _pattern_matches(source, path):
            matches.append(item)
    if len(matches) > 1 and not _compatible_same_path_instructions(matches):
        raise OntologyInfrastructureError(
            f"Ambiguous projection instructions for {_display_path(path)}: "
            + ", ".join(str(item.get("source")) for item in matches)
        )
    return matches


def _compatible_same_path_instructions(instructions: list[dict[str, object]]) -> bool:
    plain = [
        item
        for item in instructions
        if item.get("subject") is None and item.get("kind") not in {"inlined-node", "path-token"}
    ]
    nodes = [item for item in instructions if item.get("kind") == "inlined-node"]
    subject_fields = [item for item in instructions if item.get("subject") is not None]
    token_fields = [item for item in instructions if item.get("kind") == "path-token"]
    return (
        len(plain) <= 1
        and len(nodes) <= 1
        and all(isinstance(item.get("subject"), str) for item in subject_fields)
        and all(isinstance(item.get("token"), str) for item in token_fields)
    )


def _has_instruction_prefix(path: tuple[str, ...], sources: list[str], node_kind: str) -> bool:
    if node_kind == "scalar":
        return False
    return any(_prefix_shape_compatible(source, path, node_kind) for source in sources)


def _prefix_shape_compatible(source: str, path: tuple[str, ...], node_kind: str) -> bool:
    if not _pattern_prefix(source, path):
        return False
    if node_kind != "mapping":
        return True
    pattern = source.split(".")
    if len(path) >= len(pattern):
        return not (len(path) == len(pattern) and pattern[-1].endswith("[]") and not pattern[-1].startswith("<key>"))
    next_token = pattern[len(path)]
    # A literal ``field[]`` announces that the current field must be a list.
    # ``<key>[]`` instead traverses a mapping key whose value is a list, so the
    # current mapping container remains valid.
    return not next_token.endswith("[]") or next_token.startswith("<key>")


def _pattern_matches(source: str, path: tuple[str, ...]) -> bool:
    pattern = tuple(source.split("."))
    if len(pattern) != len(path):
        return False
    return all(_token_matches(expected, actual) for expected, actual in zip(pattern, path, strict=True))


def _pattern_prefix(source: str, path: tuple[str, ...]) -> bool:
    pattern = tuple(source.split("."))
    if len(path) > len(pattern):
        return False
    return all(_token_matches(expected, actual, prefix=True) for expected, actual in zip(pattern, path, strict=False))


def _token_matches(expected: str, actual: str, prefix: bool = False) -> bool:
    if expected == actual:
        return True
    if expected == "<key>":
        return not actual.endswith("[]") and not _is_indexed_list_token(actual)
    if expected == "<key>[]":
        return actual.endswith("[]") or _is_indexed_list_token(actual)
    if expected.endswith("[]"):
        base = expected[:-2]
        return (
            actual == base + "[]"
            or (actual.startswith(base + "[") and actual.endswith("]"))
            or (prefix and actual == base)
        )
    return prefix and expected.endswith("[]") and actual == expected[:-2]


def _shape_compatible(instruction: Mapping[str, object], node_kind: str) -> bool:
    kind = instruction.get("kind")
    if node_kind == "mapping":
        return kind == "keyed-map"
    if node_kind in {"list-item", "mapping-item"}:
        return kind in {"inlined-node", "path-token"}
    if node_kind == "list":
        return kind in {"sequence", "keyed-map", "inlined-node"}
    return kind in {"slot", "alias", "sequence", "keyed-map", "opaque-value", "reference", "path-token"}


def _instruction(item: object, source_id: str) -> dict[str, object]:
    if (
        not isinstance(item, Mapping)
        or not isinstance(item.get("kind"), str)
        or not isinstance(item.get("source"), str)
    ):
        raise OntologyInfrastructureError(f"Malformed projection instruction for source {source_id!r}")
    return cast(dict[str, object], dict(item))


def _lookup(value: object, source: str) -> object:
    current = value
    for token in source.split("."):
        if token.endswith("[]"):
            return _MISSING
        if not isinstance(current, Mapping) or token not in current:
            return _MISSING
        current = current[token]
    return current


def _lookup_actual_path(value: object, path: tuple[str, ...]) -> object:
    current = value
    for token in path:
        list_index = _list_index(token)
        if list_index is not None:
            field, index = list_index
            if field:
                if not isinstance(current, Mapping) or field not in current:
                    return _MISSING
                current = current[field]
            if not isinstance(current, list) or index >= len(current):
                return _MISSING
            current = current[index]
            continue
        if not isinstance(current, Mapping) or token not in current:
            return _MISSING
        current = current[token]
    return current


def _subject_path(subject_pattern: str, actual_path: tuple[str, ...]) -> tuple[str, ...]:
    parts = tuple(subject_pattern.split("."))
    if len(parts) > len(actual_path):
        raise OntologyInfrastructureError(f"Instruction subject {subject_pattern!r} is not an ancestor")
    subject_path = actual_path[: len(parts)]
    if not all(_token_matches(expected, actual) for expected, actual in zip(parts, subject_path, strict=True)):
        raise OntologyInfrastructureError(
            f"Instruction subject {subject_pattern!r} does not match {_display_path(actual_path)}"
        )
    return subject_path


def _relative_lookup_path(path: tuple[str, ...], key: str | None) -> tuple[str, ...]:
    if key is None or not path:
        return path
    first = path[0]
    indexed = _list_index(first)
    if first == key:
        return path[1:]
    if indexed is not None and indexed[0] == key:
        return (f"[{indexed[1]}]", *path[1:])
    return path


def _inlined_node_instruction(subject_pattern: str, instructions: list[dict[str, object]]) -> dict[str, object]:
    for instruction in instructions:
        if instruction.get("kind") == "inlined-node" and instruction.get("source") == subject_pattern:
            target = instruction.get("target")
            if isinstance(target, str) and target:
                return instruction
    raise OntologyInfrastructureError(f"Instruction subject {subject_pattern!r} has no matching inlined-node")


def _inlined_subject_iri(  # noqa: PLR0913
    *,
    base_iri: str,
    root_subject: URIRef,
    subject_pattern: str,
    actual_path: tuple[str, ...],
    document_value: object,
    key: str | None,
    instructions: list[dict[str, object]],
) -> URIRef:
    instruction = _inlined_node_instruction(subject_pattern, instructions)
    target_class = cast(str, instruction["target"])
    subject_path = _subject_path(subject_pattern, actual_path)
    child_value = _lookup_actual_path(document_value, _relative_lookup_path(subject_path, key))
    if child_value is _MISSING:
        raise OntologyInfrastructureError(f"Instruction subject {subject_pattern!r} is missing at {actual_path}")
    parent_pattern = instruction.get("subject")
    parent = root_subject
    if parent_pattern is not None:
        if not isinstance(parent_pattern, str):
            raise OntologyInfrastructureError(f"Instruction subject parent is invalid for {subject_pattern!r}")
        parent = _inlined_subject_iri(
            base_iri=base_iri,
            root_subject=root_subject,
            subject_pattern=parent_pattern,
            actual_path=subject_path,
            document_value=document_value,
            key=key,
            instructions=instructions,
        )
    return URIRef(_child_entity_iri(base_iri, target_class, parent, subject_path, child_value))


def _path_token_value(source: str, actual_path: tuple[str, ...], token: str, token_index: int) -> str:
    pattern = tuple(source.split("."))
    if len(pattern) != len(actual_path):
        raise OntologyInfrastructureError(f"Path-token source {source!r} does not match {_display_path(actual_path)}")
    seen = 0
    for expected, actual in zip(pattern, actual_path, strict=True):
        if expected == token:
            if seen != token_index:
                seen += 1
                continue
            indexed = _list_index(actual)
            return indexed[0] if indexed is not None else actual
    raise OntologyInfrastructureError(f"Path-token {token!r}[{token_index}] is not present in {source!r}")


def _emit(  # noqa: PLR0913, PLR0917
    graph: Graph,
    emitted: dict[tuple[object, object, object], ProvenanceRecord],
    subject: object,
    predicate: object,
    obj: object,
    document: RepositoryDocument,
    field_path: str,
    repository_root: Path,
) -> None:
    triple = (subject, predicate, obj)
    if triple in emitted:
        return
    graph.add(triple)
    source_path = document.path.relative_to(repository_root.absolute()).as_posix()
    emitted[triple] = ProvenanceRecord(
        document.source_id, source_path, field_path, _term_text(subject), _term_text(predicate)
    )


def _literal(value: object, datatype: str | None = None) -> Literal:
    if isinstance(value, (Mapping, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return Literal(value, datatype=XSD.date if datatype == str(XSD.date) else None)


def _entity_iri(base_iri: str, root_class: str, value: object) -> str:
    segment = root_class[:1].lower() + root_class[1:]
    return base_iri + segment + "/" + quote(str(value), safe="-._~")


def _child_entity_iri(base_iri: str, root_class: str, parent: object, path: tuple[str, ...], value: object) -> str:
    segment = root_class[:1].lower() + root_class[1:]
    payload = json.dumps(
        {"parent": _term_text(parent), "path": _display_path(path), "value": value},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return base_iri + segment + "/" + digest


def _is_indexed_list_token(value: str) -> bool:
    return _list_index(value) is not None


def _list_index(value: str) -> tuple[str, int] | None:
    if not value.endswith("]") or "[" not in value:
        return None
    field, raw_index = value.rsplit("[", 1)
    raw_index = raw_index[:-1]
    if not raw_index.isdigit():
        return None
    return field, int(raw_index)


def _base_iri(projection: Mapping[str, object]) -> str:
    value = projection.get("base_iri")
    if not isinstance(value, str) or not value.startswith(("http://", "https://")) or not value.endswith("/"):
        raise OntologyInfrastructureError("Compiled repository projection requires a valid base_iri")
    return value


def _projection_mapping(raw: Mapping[str, object]) -> dict[str, object]:
    if isinstance(raw.get("repository_projection"), Mapping):
        raw = cast(Mapping[str, object], raw["repository_projection"])
    if not isinstance(raw, Mapping) or not isinstance(raw.get("sources"), list):
        raise OntologyInfrastructureError("Compiled projection map has no repository_projection.sources")
    return cast(dict[str, object], raw)


def _unknown(document: RepositoryDocument, path: tuple[str, ...]) -> OntologyInfrastructureError:
    return OntologyInfrastructureError(f"Unknown uncovered structure in {document.source_path}: {_display_path(path)}")


def _display_path(path: tuple[str, ...]) -> str:
    return ".".join(path) or "<root>"


def _term_text(term: object) -> str:
    if isinstance(term, URIRef):
        return f"<{term}>"
    if isinstance(term, BNode):
        return f"_:{term}"
    if isinstance(term, Literal):
        return term.n3()
    return str(term)


_MISSING = object()
_CONTAINER = object()
