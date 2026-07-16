"""Direct pySHACL coverage for the authored Wave B2A rule lane."""

from pathlib import Path

from pyshacl import validate
from rdflib import Graph
from rdflib.namespace import RDF, SH, Namespace

ROOT = Path(__file__).resolve().parents[1]
SHAPES_PATH = ROOT / "ontology/constraints/semantic.ttl"
FIXTURE_ROOT = ROOT / "tests/fixtures/ontology/shacl"
FULL_CATALOG_FIXTURE = FIXTURE_ROOT / "full_catalog_positive.ttl"
SS = Namespace("https://j2h4u.github.io/supp-slotter/ontology/v1/")


def _shapes() -> Graph:
    return Graph().parse(SHAPES_PATH, format="turtle")


def _rule_shapes(shapes: Graph) -> dict[str, object]:
    rules: dict[str, object] = {}
    for shape in shapes.subjects(RDF.type, SH.NodeShape):
        names = list(shapes.objects(shape, SH.name))
        assert len(names) == 1, f"shape {shape} must have one stable sh:name"
        rule_id = str(names[0])
        assert rule_id not in rules, f"duplicate stable rule ID {rule_id}"
        rules[rule_id] = shape
    return rules


def _validate_graph(graph: Graph, shapes: Graph) -> tuple[bool, Graph]:
    conforms, report, _ = validate(
        graph,
        shacl_graph=shapes,
        inference="none",
        advanced=True,
        abort_on_first=False,
    )
    return bool(conforms), report


def _validate(path: Path, shapes: Graph) -> tuple[bool, Graph]:
    return _validate_graph(Graph().parse(path, format="turtle"), shapes)


def test_every_authored_rule_has_exactly_one_positive_and_negative_fixture() -> None:
    shapes = _shapes()
    rules = _rule_shapes(shapes)
    fixture_rules = {path.name for path in FIXTURE_ROOT.iterdir() if path.is_dir()}
    assert fixture_rules == set(rules), (fixture_rules ^ set(rules))

    for rule_id in sorted(rules):
        directory = FIXTURE_ROOT / rule_id
        files = {path.name for path in directory.iterdir() if path.is_file()}
        assert files == {"positive.ttl", "negative.ttl"}, rule_id


def test_positive_fixtures_conform_and_negative_diagnostics_are_isolated() -> None:
    shapes = _shapes()
    rules = _rule_shapes(shapes)
    for rule_id in sorted(rules):
        positive, _ = _validate(FIXTURE_ROOT / rule_id / "positive.ttl", shapes)
        assert positive, f"positive fixture does not conform: {rule_id}"

        negative, report = _validate(FIXTURE_ROOT / rule_id / "negative.ttl", shapes)
        assert not negative, f"negative fixture unexpectedly conforms: {rule_id}"
        results = list(report.subjects(RDF.type, SH.ValidationResult))
        assert results, f"no SHACL result for negative fixture: {rule_id}"
        source_shapes = {report.value(result, SH.sourceShape) for result in results}
        assert source_shapes == {rules[rule_id]}, (rule_id, source_shapes)
        messages = {str(report.value(result, SH.resultMessage)) for result in results}
        assert messages == {
            next(str(message) for message in shapes.objects(rules[rule_id], SH.sparql)
                 for message in shapes.objects(message, SH.message))
        }


def test_selector_endpoint_cardinality_closes_all_four_prior_escapes() -> None:
    prefix = """@prefix ss: <https://j2h4u.github.io/supp-slotter/ontology/v1/> .\n"""
    cases = {
        "zero": "ss:s a ss:Selector .",
        "both_forms": """
            ss:s a ss:Selector ; ss:selectsTerm ss:t ; ss:selectsEntity ss:e .
            ss:t a ss:OntologyTerm ; ss:semanticCategory ss:kind ; ss:ontocleanProfile ss:rigid_identity .
            ss:e ss:entityId "sub_1" .
        """,
        "two_terms": """
            ss:s a ss:Selector ; ss:selectsTerm ss:t1, ss:t2 .
            ss:t1 a ss:OntologyTerm ; ss:semanticCategory ss:kind ; ss:ontocleanProfile ss:rigid_identity .
            ss:t2 a ss:OntologyTerm ; ss:semanticCategory ss:kind ; ss:ontocleanProfile ss:rigid_identity .
        """,
        "two_entities": """
            ss:s a ss:Selector ; ss:selectsEntity ss:e1, ss:e2 .
            ss:e1 ss:entityId "sub_1" .
            ss:e2 ss:entityId "sub_2" .
        """,
    }
    shapes = _shapes()
    expected_shape = _rule_shapes(shapes)["selector_exactly_one_endpoint"]
    for case, turtle in cases.items():
        conforms, report = _validate_graph(Graph().parse(data=prefix + turtle, format="turtle"), shapes)
        assert not conforms, case
        source_shapes = {
            report.value(result, SH.sourceShape)
            for result in report.subjects(RDF.type, SH.ValidationResult)
        }
        assert source_shapes == {expected_shape}, (case, source_shapes)


def test_relation_regression_fixtures_do_not_reuse_selector_resources() -> None:
    duplicate = Graph().parse(
        FIXTURE_ROOT / "symmetric_relation_duplicate/negative.ttl", format="turtle"
    )
    duplicate_pairs = {
        (duplicate.value(relation, SS.sourceSelector), duplicate.value(relation, SS.targetSelector))
        for relation in duplicate.subjects(RDF.type, SS.Relation)
    }
    assert len(duplicate_pairs) == 2

    reversed_graph = Graph().parse(
        FIXTURE_ROOT / "symmetric_relation_reversed_duplicate/negative.ttl", format="turtle"
    )
    reversed_pairs = {
        (reversed_graph.value(relation, SS.sourceSelector), reversed_graph.value(relation, SS.targetSelector))
        for relation in reversed_graph.subjects(RDF.type, SS.Relation)
    }
    assert len(reversed_pairs) == 2
    assert not any((target, source) in reversed_pairs for source, target in reversed_pairs)

    self_graph = Graph().parse(
        FIXTURE_ROOT / "symmetric_relation_self_prohibited/negative.ttl", format="turtle"
    )
    relation = next(self_graph.subjects(RDF.type, SS.Relation))
    assert self_graph.value(relation, SS.sourceSelector) != self_graph.value(
        relation, SS.targetSelector
    )


def test_full_catalog_sentinel_is_present_and_conforms() -> None:
    root_fixtures = {path.name for path in FIXTURE_ROOT.glob("*.ttl")}
    assert root_fixtures == {FULL_CATALOG_FIXTURE.name}
    conforms, report = _validate(FULL_CATALOG_FIXTURE, _shapes())
    assert conforms, report.serialize(format="turtle")
