# Project: Supplement Slot Planner (supp-slotter)

## Current product boundary

Supp Slotter is a local, deterministic planner for turning product and
substance cards into a reviewable pillbox schedule. YAML source data lives in
`data/`; `data/pillboxes.yaml` defines pillboxes and slots, while nested
`knowledge:` and `schedule:` card sections carry reviewer facts and scheduling
terms. Dashboard selectors project review clusters from authored card facts.

The canonical ontology is authored under `ontology/`, with
`ontology/manifest.yaml` as the compilation boundary and
`ontology/runtime-policy.yaml` governing executable scheduling behavior.
Generated ontology artifacts are checked-in build outputs. Python under
`planner/` is generic runtime glue and must not become a second ontology
registry.

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
