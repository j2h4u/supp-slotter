"""SHACL execution boundary for the generated canonical ontology shapes."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml
from pyshacl import validate
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

from planner.ontology.errors import OntologyInfrastructureError
from planner.yaml_io import safe_load_yaml


def _canonical_term_registry(ontology_root: Path) -> Graph:  # noqa: C901, PLR0912, PLR0914, PLR0915
    """Load generated term/category/profile and placement metadata.

    The generated ontology also contains catalog and schema metadata.  Those
    records are not repository cards and must not become SHACL data targets.
    Keeping the registry slice explicit makes authored vocabulary, its
    OntoClean relationships, and runtime assignment metadata the only sources
    of placement during validation.
    """

    ontology_path = ontology_root / "generated" / "ontology.ttl"
    try:
        canonical = Graph().parse(ontology_path, format="turtle")
    except Exception as error:  # RDF parsing is part of the validation boundary.
        raise OntologyInfrastructureError(f"Cannot load generated ontology registry: {error}") from error

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
    ontology_term = URIRef(f"{base}OntologyTerm")
    semantic_category = URIRef(f"{base}semantic_category")
    ontoclean_profile = URIRef(f"{base}ontoclean_profile")
    semantic_category_class = URIRef(f"{base}SemanticCategory")
    ontoclean_profile_class = URIRef(f"{base}OntoCleanProfile")
    assignment_source = URIRef(f"{base}assignment_source")
    axis_predicate = URIRef(f"{base}axis")
    terms = set(canonical.subjects(RDF.type, ontology_term))
    category_nodes = set(canonical.subjects(RDF.type, semantic_category_class))
    category_nodes.update(obj for term in terms for obj in canonical.objects(term, semantic_category))
    axis_nodes = {
        subject
        for subject in canonical.subjects(assignment_source, None)
        if (subject, axis_predicate, None) in canonical
    }
    profile_nodes = set(canonical.subjects(RDF.type, ontoclean_profile_class))
    profile_nodes.update(obj for category in category_nodes for obj in canonical.objects(category, ontoclean_profile))
    metadata = category_nodes | profile_nodes | axis_nodes
    if not terms:
        raise OntologyInfrastructureError("Generated ontology has no canonical OntologyTerm registry")
    if not metadata:
        raise OntologyInfrastructureError("Generated ontology has no canonical placement metadata")

    registry = Graph()
    for term in terms:
        for triple in canonical.triples((term, None, None)):
            registry.add(triple)
    for category in category_nodes:
        for triple in canonical.triples((category, None, None)):
            registry.add(triple)
    for profile in profile_nodes:
        for triple in canonical.triples((profile, None, None)):
            registry.add(triple)
    for axis in axis_nodes:
        for predicate in (axis_predicate, assignment_source, URIRef(f"{base}assignment_field")):
            for value in canonical.objects(axis, predicate):
                registry.add((axis, predicate, value))

    # Entity selectors use the same authored substance identity registry as
    # the compiler/runtime.  Keep this registry in the composed SHACL graph so
    # an assertion cannot make an unknown ID/name valid merely by omitting its
    # corresponding Substance card from a focused fixture.
    substance_class = URIRef(f"{base}Substance")
    substance_id_predicate = URIRef(f"{base}id")
    label_predicate = URIRef(f"{base}label")
    substances_dir = ontology_root.parent / "data" / "substances"
    if substances_dir.is_dir():
        seen_ids: set[str] = set()
        substance_records: list[tuple[str, str]] = []
        for path in sorted(substances_dir.glob("*.yaml")):
            try:
                raw = safe_load_yaml(path.read_text(encoding="utf-8"), path=path)
            except (OSError, UnicodeError, yaml.YAMLError) as error:
                raise OntologyInfrastructureError(f"Cannot load substance registry card {path}: {error}") from error
            if not isinstance(raw, Mapping):
                raise OntologyInfrastructureError(f"Substance registry card {path} must be a mapping")
            raw = cast(Mapping[str, object], raw)
            substance_id = raw.get("id")
            name = raw.get("name")
            if not isinstance(substance_id, str) or not substance_id.strip():
                raise OntologyInfrastructureError(f"Substance registry card {path} has no non-empty id")
            if not isinstance(name, str) or not name.strip():
                raise OntologyInfrastructureError(f"Substance registry card {path} has no non-empty name")
            if substance_id in seen_ids:
                raise OntologyInfrastructureError(f"Duplicate substance registry id {substance_id!r}")
            seen_ids.add(substance_id)
            substance_records.append((substance_id, name))
        # GROUP_CONCAT in the relation identity SHACL rule consumes graph
        # order.  Insert canonical IDs lexically so the aggregate key is
        # deterministic and matches compiler/runtime sorted resolution.
        for substance_id, name in sorted(substance_records):
            subject = URIRef(f"{base}substance/{substance_id}")
            registry.add((subject, RDF.type, substance_class))
            registry.add((subject, substance_id_predicate, Literal(substance_id)))
            registry.add((subject, label_predicate, Literal(name)))

    # Relation assertions use literal relation_type values while directionality
    # and per-side selector forms are authored in the generated relation-type
    # catalog.  Project that catalog into the validation graph so SHACL never
    # needs a Python/domain list and a fixture cannot redefine relation policy.
    relation_type_class = URIRef(f"{base}OperationalRelationType")
    relation_nodes = set(canonical.subjects(RDF.type, relation_type_class))
    if not relation_nodes:
        raise OntologyInfrastructureError("Generated ontology has no canonical relation-type registry")
    for relation_node in relation_nodes:
        for triple in canonical.triples((relation_node, None, None)):
            registry.add(triple)
    return registry


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


def compose_validation_graph(graph: Graph, ontology_root: Path) -> Graph:
    """Combine repository data with the generated semantic registry.

    Any repository-provided ``OntologyTerm`` subjects are deliberately
    excluded: an assertion or fixture cannot manufacture registry membership.
    RDF graphs de-duplicate triples naturally when a canonical term is already
    present, so authored terms are never duplicated in the validation input.
    """

    registry = _canonical_term_registry(ontology_root)
    ontology_terms = {
        value
        for value in registry.objects(None, RDF.type)
        if isinstance(value, URIRef) and str(value).endswith("/OntologyTerm")
    }
    if len(ontology_terms) != 1:
        raise OntologyInfrastructureError("Generated ontology registry has an invalid OntologyTerm class")
    ontology_term = next(iter(ontology_terms))
    authored_terms = set(graph.subjects(RDF.type, ontology_term))
    relation_type_class = next(
        (
            target
            for target in registry.objects(None, RDF.type)
            if isinstance(target, URIRef) and str(target).endswith("/OperationalRelationType")
        ),
        None,
    )
    authored_relation_types = (
        set(graph.subjects(RDF.type, relation_type_class)) if relation_type_class is not None else set()
    )
    composed = Graph()
    for subject, predicate, obj in graph:
        if subject not in authored_terms and subject not in authored_relation_types:
            composed.add((subject, predicate, obj))
    for triple in registry:
        composed.add(triple)
    return composed


def validate_graph(graph: Graph, ontology_root: Path) -> tuple[bool, Graph, str]:
    """Validate *graph* with generated shapes, never silently bypassing pySHACL."""
    shapes_path = ontology_root / "generated" / "shapes.ttl"
    shapes = Graph()
    try:
        shapes.parse(shapes_path, format="turtle")
        shapes = _validation_shapes(shapes)
        data_graph = compose_validation_graph(graph, ontology_root)
        conforms, report_graph, report_text = validate(
            data_graph,
            shacl_graph=shapes,
            inference="none",
            advanced=True,
            abort_on_first=False,
            meta_shacl=False,
        )
    except Exception as error:  # pySHACL/RDF parsing is the authoritative operation.
        raise OntologyInfrastructureError(f"Cannot execute generated SHACL validation: {error}") from error
    if not isinstance(report_graph, Graph):
        raise OntologyInfrastructureError("pySHACL returned a non-graph validation report")
    return cast(bool, conforms), report_graph, cast(str, report_text)
