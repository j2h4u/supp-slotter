"""Generic, deterministic repository-to-RDF projection.

The projector is deliberately an interpreter for compiled projection
instructions.  It contains no card-field routing or scheduling semantics.
"""

# The compiled instruction payload is intentionally structural.  Detailed
# schema validation belongs to the ontology artifact loader.
# pyright: reportAny=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownLambdaType=false, reportArgumentType=false

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import quote

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import RDF

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
                    graph,
                    emitted,
                    repository_root,
                    document,
                    value,
                    str(key),
                    normalized_instructions,
                    base_iri,
                )
        else:
            _project_document(
                graph,
                emitted,
                repository_root,
                document,
                document.document,
                None,
                normalized_instructions,
                base_iri,
            )
    triples = tuple(sorted((_term_text(s), _term_text(p), _term_text(o)) for s, p, o in emitted))
    provenance = tuple(
        sorted(
            (emitted[key] for key in emitted),
            key=lambda item: (item.source_path, item.field_path, item.predicate, item.subject),
        )
    )
    return ProjectionResult(graph, triples, provenance)


def _project_document(  # noqa: C901, PLR0912, PLR0913, PLR0917
    graph: Graph,
    emitted: dict[tuple[object, object, object], ProvenanceRecord],
    repository_root: Path,
    document: RepositoryDocument,
    value: object,
    key: str | None,
    instructions: list[dict[str, object]],
    base_iri: str,
) -> None:
    identity = document.documents.get("identity")
    if identity is None and key is None:
        identity_value = document.source_id
    elif not isinstance(identity, Mapping):
        raise OntologyInfrastructureError(f"Source {document.source_id!r} has no identity instruction")
    else:
        identity_source = identity.get("source")
        if identity_source == "<key>":
            if key is None:
                raise OntologyInfrastructureError(f"Keyed source {document.source_id!r} has no key")
            identity_value = key
        else:
            identity_value = _lookup(value, str(identity_source))
    if identity_value is _MISSING or isinstance(identity_value, (Mapping, list)):
        raise OntologyInfrastructureError(f"Source {document.source_id!r} identity is missing or non-scalar")
    subject = URIRef(_entity_iri(base_iri, document.root_class, identity_value))
    _emit(
        graph, emitted, subject, RDF.type, URIRef(base_iri + document.root_class), document, "<root>", repository_root
    )
    for path, leaf, node_kind in _walk(value, (key,) if key is not None else ()):
        instruction = _exact_instruction(path, instructions)
        if instruction is None:
            continue
        if not _shape_compatible(instruction, node_kind):
            raise OntologyInfrastructureError(
                f"Instruction kind {instruction.get('kind')!r} is incompatible with {node_kind} at {path}"
            )
        kind = instruction["kind"]
        if kind not in {"slot", "alias", "sequence", "keyed-map", "opaque-value", "reference"}:
            raise OntologyInfrastructureError(f"Unsupported projection instruction kind: {kind!r}")
        predicate_value = instruction.get("predicate")
        if not isinstance(predicate_value, str) or not predicate_value:
            raise OntologyInfrastructureError(f"Instruction for {document.source_id!r} has no predicate")
        predicate = URIRef(predicate_value)
        if leaf is _CONTAINER:
            continue
        target = instruction.get("target")
        if target is not None:
            if not isinstance(target, str) or not target or isinstance(leaf, (Mapping, list)):
                raise OntologyInfrastructureError(f"Reference target has invalid value at {path}")
            obj = URIRef(_entity_iri(base_iri, target, leaf))
        elif kind == "reference":
            target = instruction.get("target")
            if not isinstance(target, str) or isinstance(leaf, (Mapping, list)):
                raise OntologyInfrastructureError(f"Reference instruction has invalid target/value at {path}")
            obj = URIRef(_entity_iri(base_iri, target, leaf))
        else:
            obj = _literal(leaf)
        _emit(graph, emitted, subject, predicate, obj, document, _display_path(path), repository_root)


def _validate_structure(  # noqa: C901, PLR0912
    document: RepositoryDocument, instructions: list[dict[str, object]]
) -> None:
    allowed = [str(item["source"]) for item in instructions]
    root = document.document
    if document.documents.get("document_shape") == "keyed-map":
        if not isinstance(root, Mapping):
            raise OntologyInfrastructureError(f"Source {document.source_id!r} must be a mapping")
        for key, value in root.items():
            for path, leaf, node_kind in _walk(value, (str(key),)):
                instruction = _exact_instruction(path, instructions)
                if leaf is _CONTAINER and instruction is None:
                    raise _unknown(document, path)
                if instruction is None and not _has_instruction_prefix(path, allowed, node_kind):
                    raise _unknown(document, path)
                if instruction is not None and not _shape_compatible(instruction, node_kind):
                    raise _unknown(document, path)
    else:
        for path, leaf, node_kind in _walk(root, ()):
            instruction = _exact_instruction(path, instructions)
            if leaf is _CONTAINER and instruction is None:
                raise _unknown(document, path)
            if instruction is None and not _has_instruction_prefix(path, allowed, node_kind):
                raise _unknown(document, path)
            if instruction is not None and not _shape_compatible(instruction, node_kind):
                raise _unknown(document, path)


def _walk(value: object, path: tuple[str, ...]) -> list[tuple[tuple[str, ...], object, str]]:
    if isinstance(value, Mapping):
        if not value:
            return [(path, _CONTAINER, "mapping")]
        result: list[tuple[tuple[str, ...], object, str]] = []
        for key in sorted(value, key=str):
            result.extend(_walk(value[key], (*path, str(key))))
        return result
    if isinstance(value, list):
        list_path = (*path[:-1], path[-1] + "[]") if path and not path[-1].endswith("[]") else path
        if not value:
            return [(list_path, _CONTAINER, "list")]
        result = []
        for item in value:
            result.extend(_walk(item, list_path))
        return result
    return [(path, value, "scalar")]


def _exact_instruction(path: tuple[str, ...], instructions: list[dict[str, object]]) -> dict[str, object] | None:
    matches: list[dict[str, object]] = []
    for item in instructions:
        source = item.get("source")
        if isinstance(source, str) and _pattern_matches(source, path):
            matches.append(item)
    if len(matches) > 1:
        raise OntologyInfrastructureError(
            f"Ambiguous projection instructions for {_display_path(path)}: "
            + ", ".join(str(item.get("source")) for item in matches)
        )
    return matches[0] if matches else None


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
    return all(_token_matches(expected, actual, prefix=True) for expected, actual in zip(pattern, path, strict=True))


def _token_matches(expected: str, actual: str, prefix: bool = False) -> bool:
    if expected == actual:
        return True
    if expected == "<key>":
        return not actual.endswith("[]")
    if expected == "<key>[]":
        return actual.endswith("[]")
    return prefix and expected.endswith("[]") and actual == expected[:-2]


def _shape_compatible(instruction: Mapping[str, object], node_kind: str) -> bool:
    kind = instruction.get("kind")
    if node_kind == "mapping":
        return kind == "keyed-map"
    if node_kind == "list":
        return kind in {"sequence", "keyed-map"}
    return kind in {"slot", "alias", "sequence", "keyed-map", "opaque-value", "reference"}


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


def _literal(value: object) -> Literal:
    if isinstance(value, (Mapping, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return Literal(value)


def _entity_iri(base_iri: str, root_class: str, value: object) -> str:
    segment = root_class[:1].lower() + root_class[1:]
    return base_iri + segment + "/" + quote(str(value), safe="-._~")


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
