"""Direct pySHACL coverage for the authored Wave B2A rule lane."""

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Protocol, TypeGuard, cast

from planner.ontology.artifacts import load_ontology
from planner.ontology.projection import project_repository
from planner.ontology.validation import compose_validation_graph
from pyshacl import validate
from pyshacl.errors import ValidationFailure
from rdflib import Graph
from rdflib.namespace import RDF, SH
from rdflib.term import Identifier, Node

ROOT = Path(__file__).resolve().parents[1]
SHAPES_PATH = ROOT / "ontology/constraints/semantic.ttl"
FIXTURE_ROOT = ROOT / "tests/fixtures/ontology/shacl"

type _ValidationReport = Graph | ValidationFailure | bytes
type _ValidationResult = tuple[bool, _ValidationReport, str]


class _PyShaclResultTuple(Protocol):
    """Structural view of pySHACL's unannotated three-item validation result."""

    def __iter__(self) -> Iterator[object]: ...

    def __len__(self) -> int: ...


def _is_pyshacl_result(value: object) -> TypeGuard[_PyShaclResultTuple]:
    if not isinstance(value, tuple):
        return False
    items = cast(tuple[object, ...], value)
    return len(items) == 3


def _validation_result(value: object) -> _ValidationResult:
    assert _is_pyshacl_result(value), "pySHACL returned an invalid result tuple"
    conforms, report, text = tuple(value)
    assert isinstance(conforms, bool), "pySHACL conformance result must be bool"
    assert isinstance(report, (Graph, ValidationFailure, bytes)), "pySHACL report has an unsupported type"
    assert isinstance(text, str), "pySHACL report text must be str"
    return conforms, report, text


def _identifier(value: Node | None) -> Identifier | None:
    assert value is None or isinstance(value, Identifier), "expected an RDF identifier"
    return value


@lru_cache(maxsize=1)
def _shapes() -> Graph:
    return Graph().parse(SHAPES_PATH, format="turtle")


@lru_cache(maxsize=1)
def _rules() -> dict[str, Identifier]:
    return _rule_shapes(_shapes())


@lru_cache(maxsize=None)
def _fixture_graph(path: Path) -> Graph:
    return Graph().parse(path, format="turtle")


def _rule_shapes(shapes: Graph) -> dict[str, Identifier]:
    rules: dict[str, Identifier] = {}
    for shape in shapes.subjects(RDF.type, SH.NodeShape):
        assert isinstance(shape, Identifier), f"shape {shape} must be an RDF identifier"
        names = list(shapes.objects(shape, SH.name))
        assert len(names) == 1, f"shape {shape} must have one stable sh:name"
        rule_id = str(names[0])
        assert rule_id not in rules, f"duplicate stable rule ID {rule_id}"
        rules[rule_id] = shape
    return rules


def _validate_graph(graph: Graph, shapes: Graph) -> tuple[bool, Graph]:
    result = _validation_result(
        cast(
            object,
            validate(
                graph,
                shacl_graph=shapes,
                inference="none",
                advanced=True,
                abort_on_first=False,
            ),
        )
    )
    conforms, report, _ = result
    assert isinstance(report, Graph), "expected a graph validation report"
    return conforms, report


def _validate(path: Path, shapes: Graph) -> tuple[bool, Graph]:
    return _validate_graph(compose_validation_graph(_fixture_graph(path), ROOT / "ontology"), shapes)


def test_custom_rules_have_focus_nodes_in_repository_projection() -> None:
    """Every live custom rule must target a node emitted by the real projector."""

    shapes = _shapes()
    rules = _rules()
    projection = project_repository(ROOT, load_ontology(ROOT / "ontology")).graph
    for rule_id, shape in rules.items():
        focus_nodes: set[Identifier] = set()
        for target_class in shapes.objects(shape, SH.targetClass):
            focus_nodes.update(
                node for node in projection.subjects(RDF.type, target_class) if isinstance(node, Identifier)
            )
        for target_predicate in shapes.objects(shape, SH.targetSubjectsOf):
            focus_nodes.update(
                node for node in projection.subjects(target_predicate, None) if isinstance(node, Identifier)
            )
        assert focus_nodes, f"custom rule has no repository-projection focus node: {rule_id}"


def test_positive_fixtures_conform_and_negative_diagnostics_are_isolated() -> None:
    shapes = _shapes()
    rules = _rules()
    for rule_id in sorted(rules):
        positive, _ = _validate(FIXTURE_ROOT / rule_id / "positive.ttl", shapes)
        assert positive, f"positive fixture does not conform: {rule_id}"

        negative, report = _validate(FIXTURE_ROOT / rule_id / "negative.ttl", shapes)
        assert not negative, f"negative fixture unexpectedly conforms: {rule_id}"
        results = list(report.subjects(RDF.type, SH.ValidationResult))
        assert results, f"no SHACL result for negative fixture: {rule_id}"
        source_shapes: set[Identifier | None] = {
            _identifier(report.value(result, SH.sourceShape)) for result in results
        }
        assert source_shapes == {rules[rule_id]}, (rule_id, source_shapes)
        messages = {str(report.value(result, SH.resultMessage)) for result in results}
        assert messages == {
            next(
                str(message)
                for message in shapes.objects(rules[rule_id], SH.sparql)
                for message in shapes.objects(message, SH.message)
            )
        }
