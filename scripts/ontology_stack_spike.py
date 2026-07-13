"""Exercise the proposed LinkML/RDFLib/pySHACL stack against the card corpus.

This is a prerequisite-only spike, not the production ontology generator. It
reads current cards without transforming them and creates LinkML inputs in a
temporary directory, so its result is reproducible before the cutover starts.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Never, cast

import yaml
from linkml.generators.jsonschemagen import JsonSchemaGenerator
from linkml.generators.owlgen import OwlSchemaGenerator
from linkml.generators.shaclgen import ShaclGenerator
from pyshacl import validate
from rdflib import RDF, Graph, Literal, Namespace, URIRef

BASE = Namespace("https://j2h4u.github.io/supp-slotter/ontology/v1/")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

LINKML_SCHEMA = """\
id: https://j2h4u.github.io/supp-slotter/ontology/v1/
name: supp_slotter_spike
imports:
  - linkml:types
prefixes:
  ss: https://j2h4u.github.io/supp-slotter/ontology/v1/
default_prefix: ss
default_range: string
classes:
  Substance:
    slots:
      - id
      - name
  Product:
    slots:
      - id
      - name
slots:
  id:
    identifier: true
    required: true
  name:
    required: true
"""

SHAPES = """\
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ss: <https://j2h4u.github.io/supp-slotter/ontology/v1/> .

ss:SubstanceShape a sh:NodeShape ;
  sh:targetClass ss:Substance ;
  sh:property [ sh:path ss:id ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path ss:name ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path ss:hasFact ; sh:class ss:Term ] .

ss:ProductShape a sh:NodeShape ;
  sh:targetClass ss:Product ;
  sh:property [ sh:path ss:id ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path ss:name ; sh:minCount 1 ; sh:maxCount 1 ] .
"""


@dataclass(frozen=True)
class SpikeResult:
    substance_cards: int
    product_cards: int
    distinct_terms: int
    triples: int
    linkml_generation_seconds: float
    rdf_projection_seconds: float
    shacl_validation_seconds: float
    total_seconds: float
    conforms: bool


@dataclass(frozen=True)
class Arguments:
    single_run: bool
    benchmark: bool


def _load_yaml_cards(directory: Path) -> list[dict[str, object]]:
    cards: list[dict[str, object]] = []
    for card_path in sorted(directory.glob("*.yaml")):
        raw = yaml.safe_load(card_path.read_text(encoding="utf-8"))  # pyright: ignore[reportAny]
        loaded = cast(object, raw)
        if not isinstance(loaded, Mapping):
            msg = f"{card_path}: expected a YAML mapping"
            raise ValueError(msg)
        loaded_mapping = cast(Mapping[object, object], loaded)
        card: dict[str, object] = {str(key): value for key, value in loaded_mapping.items()}
        card.setdefault("id", _id_from_filename(card_path))
        cards.append(card)
    return cards


def _id_from_filename(card_path: Path) -> str:
    if "__" not in card_path.stem:
        msg = f"{card_path}: no id and filename cannot supply one"
        raise ValueError(msg)
    return card_path.stem.rsplit("__", 1)[1]


def _string_values(value: object) -> Iterable[str]:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                yield item


def _term_uri(category: str, term: str) -> URIRef:
    return BASE[f"term/{category}/{term}"]


def _build_graph(substances: list[dict[str, object]], products: list[dict[str, object]]) -> tuple[Graph, int]:
    graph = Graph()
    graph.bind("ss", BASE)
    terms: set[tuple[str, str]] = set()
    for card in substances:
        substance = BASE[f"substance/{card['id']}"]
        graph.add((substance, RDF.type, BASE.Substance))
        graph.add((substance, BASE.id, Literal(str(card["id"]))))
        graph.add((substance, BASE.name, Literal(str(card.get("name", "")))))
        knowledge = card.get("knowledge", {})
        if not isinstance(knowledge, Mapping):
            msg = f"{card['id']}: knowledge must be a mapping"
            raise ValueError(msg)
        knowledge_mapping = cast(Mapping[str, object], knowledge)
        for category, value in knowledge_mapping.items():
            for term in _string_values(value):
                terms.add((str(category), term))
                graph.add((substance, BASE.hasFact, _term_uri(str(category), term)))
    for category, term in sorted(terms):
        term_uri = _term_uri(category, term)
        graph.add((term_uri, RDF.type, BASE.Term))
        graph.add((term_uri, BASE.category, Literal(category)))
        graph.add((term_uri, BASE.slug, Literal(term)))
    for card in products:
        product = BASE[f"product/{card['id']}"]
        graph.add((product, RDF.type, BASE.Product))
        graph.add((product, BASE.id, Literal(str(card["id"]))))
        graph.add((product, BASE.name, Literal(str(card.get("name", "")))))
    return graph, len(terms)


def _generate_linkml_artifacts(schema_path: Path) -> None:
    for artifact_path, generator in (
        (schema_path.with_suffix(".schema.json"), JsonSchemaGenerator(schema_path)),
        (
            schema_path.with_suffix(".owl.ttl"),
            OwlSchemaGenerator(
                schema_path,
                skip_vacuous_min_zero_cardinality_axioms=True,
                skip_vacuous_local_range_axioms=True,
                consolidate_cardinality_axioms=True,
            ),
        ),
        (schema_path.with_suffix(".shacl.ttl"), ShaclGenerator(schema_path)),
    ):
        artifact_path.write_text(generator.serialize(), encoding="utf-8")  # pyright: ignore[reportUnknownMemberType]
        if artifact_path.stat().st_size == 0:
            msg = f"LinkML produced an empty artifact: {artifact_path.name}"
            raise RuntimeError(msg)


def _validate_graph(graph: Graph) -> float:
    shapes = Graph().parse(data=SHAPES, format="turtle")
    validation_started = time.perf_counter()
    conforms, _, report_text = validate(
        graph,
        shacl_graph=shapes,
        advanced=True,
        allow_warnings=False,
        abort_on_first=False,
    )
    validation_seconds = time.perf_counter() - validation_started
    if not conforms:
        msg = f"Representative SHACL validation failed:\n{report_text}"
        raise RuntimeError(msg)
    return validation_seconds


def run_once() -> SpikeResult:
    started = time.perf_counter()
    substances = _load_yaml_cards(REPOSITORY_ROOT / "data/substances")
    products = _load_yaml_cards(REPOSITORY_ROOT / "data/products")
    with tempfile.TemporaryDirectory(prefix="supp-slotter-ontology-spike-") as temporary_directory:
        schema_path = Path(temporary_directory) / "spike.yaml"
        schema_path.write_text(LINKML_SCHEMA, encoding="utf-8")
        generation_started = time.perf_counter()
        _generate_linkml_artifacts(schema_path)
        generation_seconds = time.perf_counter() - generation_started
        projection_started = time.perf_counter()
        graph, distinct_terms = _build_graph(substances, products)
        projection_seconds = time.perf_counter() - projection_started
        validation_seconds = _validate_graph(graph)
    return SpikeResult(
        substance_cards=len(substances),
        product_cards=len(products),
        distinct_terms=distinct_terms,
        triples=len(graph),
        linkml_generation_seconds=generation_seconds,
        rdf_projection_seconds=projection_seconds,
        shacl_validation_seconds=validation_seconds,
        total_seconds=time.perf_counter() - started,
        conforms=True,
    )


def _parse_args() -> Arguments:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--single-run", action="store_true", help="run once and print JSON")
    parser.add_argument("--benchmark", action="store_true", help="run one clean process and three warm runs")
    parsed = parser.parse_args()
    return Arguments(
        single_run=cast(bool, parsed.single_run),
        benchmark=cast(bool, parsed.benchmark),
    )


def _benchmark() -> dict[str, object]:
    command = [sys.executable, str(Path(__file__).resolve()), "--single-run"]
    cold_started = time.perf_counter()
    cold = subprocess.run(command, capture_output=True, check=True, text=True)
    cold_seconds = time.perf_counter() - cold_started
    warm = [asdict(run_once()) for _ in range(3)]
    return {
        "cold_clean_process_seconds": cold_seconds,
        "cold_result": json.loads(cold.stdout),
        "warm_runs": warm,
    }


def main() -> Never:
    args = _parse_args()
    if args.single_run and args.benchmark:
        raise SystemExit("--single-run and --benchmark cannot be combined")
    payload: object = _benchmark() if args.benchmark else asdict(run_once())
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0)


if __name__ == "__main__":
    main()
