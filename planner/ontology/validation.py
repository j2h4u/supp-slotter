"""SHACL execution boundary for the generated canonical ontology shapes."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from pyshacl import validate
from rdflib import Graph

from planner.ontology.artifacts import load_runtime_vocabulary
from planner.ontology.errors import OntologyInfrastructureError


def validate_graph(graph: Graph, ontology_root: Path) -> tuple[bool, Graph, str]:
    """Validate *graph* with generated shapes, never silently bypassing pySHACL."""
    load_runtime_vocabulary(ontology_root)
    shapes_path = ontology_root / "generated" / "shapes.ttl"
    shapes = Graph()
    try:
        shapes.parse(shapes_path, format="turtle")
        conforms, report_graph, report_text = validate(
            graph,
            shacl_graph=shapes,
            inference="none",
            advanced=True,
            abort_on_first=False,
            meta_shacl=True,
        )
    except Exception as error:  # pySHACL/RDF parsing is the authoritative operation.
        raise OntologyInfrastructureError(f"Cannot execute generated SHACL validation: {error}") from error
    if not isinstance(report_graph, Graph):
        raise OntologyInfrastructureError("pySHACL returned a non-graph validation report")
    return cast(bool, conforms), report_graph, cast(str, report_text)
