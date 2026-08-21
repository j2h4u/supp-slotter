"""SHACL execution boundary for the generated canonical ontology shapes."""

from __future__ import annotations

import time
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml
from pyshacl import validate
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF
from rdflib.term import Node

from planner.ontology.errors import OntologyInfrastructureError
from planner.yaml_io import safe_load_yaml


@dataclass(frozen=True)
class ValidationRegistry:
    """Immutable generated ontology data needed by SHACL composition."""

    triples: tuple[tuple[Node, Node, Node], ...]
    ontology_term_class: URIRef
    relation_type_class: URIRef


@dataclass(frozen=True)
class _RegistrySelection:
    canonical: Graph
    terms: set[Node]
    categories: set[Node]
    profiles: set[Node]
    axes: set[Node]
    base: str


def _phase_start(phase_timings: MutableMapping[str, float] | None) -> float | None:
    return time.monotonic() if phase_timings is not None else None


def _record_phase(
    phase_timings: MutableMapping[str, float] | None,
    name: str,
    started: float | None,
) -> None:
    if phase_timings is not None and started is not None:
        phase_timings[name] = time.monotonic() - started


def build_validation_registry(ontology_root: Path) -> ValidationRegistry:
    """Load generated term/category/profile and placement metadata.

    The generated ontology also contains catalog and schema metadata.  Those
    records are not repository cards and must not become SHACL data targets.
    Keeping the registry slice explicit makes authored vocabulary, its
    OntoClean relationships, and runtime assignment metadata the only sources
    of placement during validation.
    """

    canonical = _load_canonical_ontology(ontology_root)
    base = _canonical_base(canonical)
    ontology_term = URIRef(f"{base}OntologyTerm")
    terms, category_nodes, profile_nodes, axis_nodes = _registry_nodes(canonical, base)
    metadata = category_nodes | profile_nodes | axis_nodes
    if not terms:
        raise OntologyInfrastructureError("Generated ontology has no canonical OntologyTerm registry")
    if not metadata:
        raise OntologyInfrastructureError("Generated ontology has no canonical placement metadata")

    registry = Graph()
    _copy_registry_nodes(
        registry, _RegistrySelection(canonical, terms, category_nodes, profile_nodes, axis_nodes, base)
    )

    # Entity selectors use the same authored substance identity registry as
    # the compiler/runtime.  Keep this registry in the composed SHACL graph so
    # an assertion cannot make an unknown ID/name valid merely by omitting its
    # corresponding Substance card from a focused fixture.
    _append_substance_registry(registry, ontology_root, base)

    # Relation assertions use literal relation_type values while directionality
    # and per-side selector forms are authored in the generated relation-type
    # catalog.  Project that catalog into the validation graph so SHACL never
    # needs a Python/domain list and a fixture cannot redefine relation policy.
    relation_type_class = URIRef(f"{base}OperationalRelationType")
    _append_relation_registry(registry, canonical, relation_type_class)
    triples = tuple(sorted(registry, key=lambda triple: tuple(str(value) for value in triple)))
    return ValidationRegistry(triples, ontology_term, relation_type_class)


def _load_canonical_ontology(ontology_root: Path) -> Graph:
    ontology_path = ontology_root / "generated" / "ontology.ttl"
    try:
        return Graph().parse(ontology_path, format="turtle")
    except Exception as error:  # RDF parsing is part of the validation boundary.
        raise OntologyInfrastructureError(f"Cannot load generated ontology registry: {error}") from error


def _canonical_base(canonical: Graph) -> str:
    base = next(
        (
            str(subject)
            for subject, ontology_class in canonical.subject_objects(RDF.type)
            if str(ontology_class).endswith("/Ontology")
        ),
        None,
    )
    if base is None:
        raise OntologyInfrastructureError("Generated ontology has no canonical ontology base")
    return base


def _registry_nodes(canonical: Graph, base: str) -> tuple[set[Node], set[Node], set[Node], set[Node]]:
    ontology_term = URIRef(f"{base}OntologyTerm")
    semantic_category = URIRef(f"{base}semantic_category")
    ontoclean_profile = URIRef(f"{base}ontoclean_profile")
    category_class = URIRef(f"{base}SemanticCategory")
    profile_class = URIRef(f"{base}OntoCleanProfile")
    assignment_source = URIRef(f"{base}assignment_source")
    axis_predicate = URIRef(f"{base}axis")
    terms = set(canonical.subjects(RDF.type, ontology_term))
    categories = set(canonical.subjects(RDF.type, category_class))
    categories.update(obj for term in terms for obj in canonical.objects(term, semantic_category))
    axes = {
        subject
        for subject in canonical.subjects(assignment_source, None)
        if (subject, axis_predicate, None) in canonical
    }
    profiles = set(canonical.subjects(RDF.type, profile_class))
    profiles.update(obj for category in categories for obj in canonical.objects(category, ontoclean_profile))
    return terms, categories, profiles, axes


def _copy_registry_nodes(registry: Graph, selection: _RegistrySelection) -> None:
    for node in selection.terms | selection.categories | selection.profiles:
        for triple in selection.canonical.triples((node, None, None)):
            registry.add(triple)
    axis_predicate = URIRef(f"{selection.base}axis")
    assignment_source = URIRef(f"{selection.base}assignment_source")
    assignment_field = URIRef(f"{selection.base}assignment_field")
    for axis in selection.axes:
        for predicate in (axis_predicate, assignment_source, assignment_field):
            for value in selection.canonical.objects(axis, predicate):
                registry.add((axis, predicate, value))


def _append_substance_registry(registry: Graph, ontology_root: Path, base: str) -> None:
    substances_dir = ontology_root.parent / "data" / "substances"
    if not substances_dir.is_dir():
        return
    records = _read_substance_records(substances_dir)
    substance_class = URIRef(f"{base}Substance")
    for substance_id, name in sorted(records):
        subject = URIRef(f"{base}substance/{substance_id}")
        registry.add((subject, RDF.type, substance_class))
        registry.add((subject, URIRef(f"{base}id"), Literal(substance_id)))
        registry.add((subject, URIRef(f"{base}label"), Literal(name)))


def _read_substance_records(substances_dir: Path) -> list[tuple[str, str]]:
    seen_ids: set[str] = set()
    records: list[tuple[str, str]] = []
    for path in sorted(substances_dir.glob("*.yaml")):
        try:
            raw = safe_load_yaml(path.read_text(encoding="utf-8"), path=path)
        except (OSError, UnicodeError, yaml.YAMLError) as error:
            raise OntologyInfrastructureError(f"Cannot load substance registry card {path}: {error}") from error
        if not isinstance(raw, Mapping):
            raise OntologyInfrastructureError(f"Substance registry card {path} must be a mapping")
        mapping = cast(Mapping[str, object], raw)
        substance_id, name = mapping.get("id"), mapping.get("name")
        if not isinstance(substance_id, str) or not substance_id.strip():
            raise OntologyInfrastructureError(f"Substance registry card {path} has no non-empty id")
        if not isinstance(name, str) or not name.strip():
            raise OntologyInfrastructureError(f"Substance registry card {path} has no non-empty name")
        if substance_id in seen_ids:
            raise OntologyInfrastructureError(f"Duplicate substance registry id {substance_id!r}")
        seen_ids.add(substance_id)
        records.append((substance_id, name))
    return records


def _append_relation_registry(registry: Graph, canonical: Graph, relation_type_class: URIRef) -> None:
    relation_nodes = set(canonical.subjects(RDF.type, relation_type_class))
    if not relation_nodes:
        raise OntologyInfrastructureError("Generated ontology has no canonical relation-type registry")
    for relation_node in relation_nodes:
        for triple in canonical.triples((relation_node, None, None)):
            registry.add(triple)


def _validation_shapes(shapes: Graph) -> Graph:
    """Exclude generated catalog class shapes from card validation.

    Registry nodes use IRI profile relationships while the source LinkML
    catalog classes remain string-shaped for authored YAML.  The generated
    registry shapes below are replaced by the explicit semantic registry
    shapes emitted by the compiler.
    """

    ontology_terms = {
        target
        for shape in shapes.subjects(RDF.type, URIRef("http://www.w3.org/ns/shacl#NodeShape"))
        for target in shapes.objects(shape, URIRef("http://www.w3.org/ns/shacl#targetClass"))
        if isinstance(target, URIRef) and str(target).endswith("/OntologyTerm")
    }
    if len(ontology_terms) != 1:
        raise OntologyInfrastructureError("Generated SHACL shapes have no unique OntologyTerm class")
    ontology_term = next(iter(ontology_terms))
    return _remove_catalog_shapes(shapes, ontology_term)


def _remove_catalog_shapes(shapes: Graph, ontology_term: URIRef) -> Graph:
    result = Graph()
    registry_classes = {
        ontology_term,
        URIRef(f"{ontology_term.rsplit('/', 1)[0]}/SemanticCategory"),
        URIRef(f"{ontology_term.rsplit('/', 1)[0]}/OntoCleanProfile"),
        URIRef(f"{ontology_term.rsplit('/', 1)[0]}/OperationalRelationType"),
    }
    generated_catalog_shapes = registry_classes | {URIRef(f"{value}Shape") for value in registry_classes}
    catalog_shapes = {
        shape
        for shape in shapes.subjects(RDF.type, URIRef("http://www.w3.org/ns/shacl#NodeShape"))
        if shape in generated_catalog_shapes
    }
    for triple in shapes:
        if triple[0] not in catalog_shapes:
            result.add(triple)
    return result


def compose_validation_graph(
    graph: Graph,
    ontology_root: Path,
    *,
    registry: ValidationRegistry | None = None,
    phase_timings: MutableMapping[str, float] | None = None,
) -> Graph:
    """Combine repository data with the generated semantic registry.

    Any repository-provided ``OntologyTerm`` subjects are deliberately
    excluded: an assertion or fixture cannot manufacture registry membership.
    RDF graphs de-duplicate triples naturally when a canonical term is already
    present, so authored terms are never duplicated in the validation input.
    """

    registry_started = _phase_start(phase_timings)
    if registry is None:
        registry = build_validation_registry(ontology_root)
    _record_phase(phase_timings, "identity_registry_seconds", registry_started)
    ontology_term = registry.ontology_term_class
    authored_terms = set(graph.subjects(RDF.type, ontology_term))
    authored_relation_types = set(graph.subjects(RDF.type, registry.relation_type_class))
    composed = Graph()
    for subject, predicate, obj in graph:
        if subject not in authored_terms and subject not in authored_relation_types:
            composed.add((subject, predicate, obj))
    for triple in registry.triples:
        composed.add(triple)
    return composed


def validate_graph(
    graph: Graph,
    ontology_root: Path,
    *,
    registry: ValidationRegistry | None = None,
    phase_timings: MutableMapping[str, float] | None = None,
) -> tuple[bool, Graph, str]:
    """Validate *graph* with generated shapes, never silently bypassing pySHACL."""
    shapes_path = ontology_root / "generated" / "shapes.ttl"
    shapes = Graph()
    shapes_started = _phase_start(phase_timings)
    try:
        shapes.parse(shapes_path, format="turtle")
        shapes = _validation_shapes(shapes)
        data_graph = compose_validation_graph(
            graph,
            ontology_root,
            registry=registry,
            phase_timings=phase_timings,
        )
        _record_phase(phase_timings, "shapes_parsing_composition_seconds", shapes_started)
        validation_started = _phase_start(phase_timings)
        conforms, report_graph, report_text = validate(
            data_graph,
            shacl_graph=shapes,
            inference="none",
            advanced=True,
            abort_on_first=False,
            meta_shacl=False,
        )
        _record_phase(phase_timings, "pyshacl_validation_seconds", validation_started)
    except Exception as error:  # pySHACL/RDF parsing is the authoritative operation.
        raise OntologyInfrastructureError(f"Cannot execute generated SHACL validation: {error}") from error
    if not isinstance(report_graph, Graph):
        raise OntologyInfrastructureError("pySHACL returned a non-graph validation report")
    return cast(bool, conforms), report_graph, cast(str, report_text)
