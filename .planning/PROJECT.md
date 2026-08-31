# Project: Supplement Slot Planner (supp-slotter)

## Current product boundary

Supp Slotter is a local deterministic planner that turns world facts into a
reviewable logical pillbox layout. The active runtime path is canonical facts
-> universal laws -> normalized pressures -> exact optimizer -> `Optimal`
publisher. Conflicts and unproved work remain layout-free `Indeterminate`.

YAML source data lives in `data/`: product/substance identity and composition,
stack membership, logical slots, and review facts. Canonical evidence facts
live in `ontology/canonical-facts.yaml`; universal pressure laws live in
`ontology/canonical-laws.yaml`. Cards do not store desired placements, pair
preferences, weights, policies, constraints, or inferred answers.

The canonical ontology is authored under `ontology/`, with
`ontology/manifest.yaml` as the compilation boundary. Generated ontology
artifacts are checked-in build outputs. Python under `planner/` is generic
runtime glue and must not become a second ontology registry. Ordinary commands
load the compact typed runtime program and schemas; RDF/SHACL projection is an
explicit offline ontology/release gate.

## Authoritative references

- `README.md` — product overview, workflow, and source ownership.
- `docs/domain-model.md` — current domain model and ontology boundaries.
- `SKILL.md` — agent workflow and authoring guidance.
- `ontology/manifest.yaml` — ontology source manifest and compilation boundary.
- `data/pillboxes.yaml` — pillbox and slot source data.

## Planning status

The prior GSD milestone is complete. New planning must reconcile proposed
changes with the authoritative references above and the executable ontology
contract.
