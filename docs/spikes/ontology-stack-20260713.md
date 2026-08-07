# Ontology dependency spike — 2026-07-13

## Scope

This prerequisite proves the proposed Python 3.14 stack can resolve and run on
the current corpus before ontology sources or cards are migrated. It is not a
production generator and does not alter card data.

- Python: CPython 3.14.6, managed by uv 0.11.23
- Runtime dependencies: `rdflib==7.6.0`, `pyshacl==0.40.0`
- Development/CI generator dependency: `linkml==1.11.1`

This was a one-off pre-cutover spike. The spike runner was deleted after the
ontology compiler became the authoritative path. Re-run the current executable
ontology gates instead:

```bash
uv lock --check
uv sync --locked
just ontology-projection-check
just ontology-contract
```

The historical spike loaded every then-current substance and product YAML card
read-only, constructed a deterministic RDFLib graph for the corpus, and
validated it with pySHACL. It proved dependency viability only; it is not an
authoritative generator or validation entrypoint.

## Acceptance result

Run this after dependency changes and record the JSON result below. The plan's
budget is a clean process below 10 seconds and warm `planner check` below 5
seconds; this isolated prerequisite measures the ontology stack only, so it is
not a substitute for the post-cutover `planner check` performance gate.

```json
{
  "cold_clean_process_seconds": 2.992,
  "cold_result": {
    "conforms": true,
    "distinct_terms": 178,
    "linkml_generation_seconds": 0.561,
    "product_cards": 59,
    "rdf_projection_seconds": 0.058,
    "shacl_validation_seconds": 0.110,
    "substance_cards": 253,
    "total_seconds": 1.250,
    "triples": 2650
  },
  "warm_runs": [
    {"conforms": true, "total_seconds": 1.127},
    {"conforms": true, "total_seconds": 0.885},
    {"conforms": true, "total_seconds": 0.913}
  ]
}
```

Result: **pass**. Dependency resolution, LinkML JSON Schema/OWL/SHACL
generation, RDFLib projection, and pySHACL validation all executed in the
locked CPython 3.14.6 environment. The clean-process result is under the
10-second prerequisite budget. The full post-cutover gate must still measure
`planner check`, because this spike intentionally excludes the application's
card parsing, graph read model, and final constraint set.
