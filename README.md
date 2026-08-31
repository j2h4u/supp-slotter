# Supp Slotter

Supp Slotter is a local deterministic planner that turns a real supplement
shelf into a reviewable logical pillbox layout. It is not medical advice and
does not decide whether a supplement is appropriate.

Its published placement is derived through one closed path:

```text
world facts -> universal laws -> normalized pressures -> exact optimizer -> Optimal publisher
```

Products, substances, components, stack membership, and logical slots are
world facts. The planner derives pressures from the admitted canonical fact
catalog and universal laws, then proves the globally optimal assignment. It
publishes a layout only for `Optimal`; conflicting, interrupted, invalid, or
unproved work is layout-free `Indeterminate`.

## What belongs where

| Source | Owns |
|---|---|
| `data/products/` | Bottle identity, label components, and source URLs |
| `data/substances/` | Reusable substance/form identity and review facts |
| `data/stacks.yaml` | Product membership in logical planning domains |
| `data/pillboxes.yaml` | Unbounded logical slots and their anchors |
| `ontology/canonical-facts.yaml` | Admitted canonical evidence facts |
| `ontology/canonical-laws.yaml` | Universal mappings from facts to pressures |
| `ontology/runtime-policy.yaml` | The declared runtime protocol and exact objective |

Placement preferences, pairings, weights, and explanatory prose are stored
answers, not canonical instance facts. A slot is an unbounded logical intake
group: it does not express capsule count, mass, volume, or physical fit.

## Quick start

Requirements: Python 3.14+ and `uv`.

```bash
uv run python -m planner check
uv run python -m planner
uv run python -m planner review
```

`planner check` validates source cards against the compact verified runtime
contract. Online commands verify `runtime-lock.json` and exactly nine executable
outputs; they do not read authored ontology sources or the full formal artifact
set. `planner` derives pressures, proves the exact lexicographic optimum, and
writes `schedule.yaml` only when the result is `Optimal`. Generated output is a
report; edit source facts, not `schedule.yaml`. Each generated placement
explanation carries a derived `placement_basis`: `pressure_evidence` when at
least one normalized pressure match is satisfied, otherwise
`balance_and_tie_break_only`.
Neither value is an authored fact or scheduling input.

## Authoring a stack

1. Capture each physical product and its exact label components.
2. Reuse or add concrete substance/form identities.
3. Put active products in the intended logical stack and define its logical
   slots.
4. Admit only world facts with their applicable identity and provenance to the
   canonical catalog.
5. Add or change a universal law only when it holds for every fact in its
   declared family; it must not encode a product-specific desired placement.
6. Run `planner check`, then inspect the resulting `Optimal` publication or
   `Indeterminate` diagnostics.

Product cards may use `use_pattern: not_every_day` as a presentation marker. It
does not add recurrence, frequency, dose, or a second placement semantics.
Unresolved research belongs in offline evidence or gitignored `docs/private/`,
not in a generic card `notes` field.

## Runtime and formal validation

Normal commands load the hash-verified compact runtime program and generated
card schemas. The online boundary verifies only the runtime lock's nine declared
outputs. `just ontology-check` is the formal gate: it recompiles from authored
sources and verifies the complete generated artifact inventory, including
RDF/SHACL/context/projection outputs.

```bash
# Fast local runtime confidence
just smoke
just fast-unit
just canonical-runtime

# Explicit offline ontology generation and formal projection checks
just ontology-check
just ontology-contract
just corpus-projection

# Release candidate only
just release
```

The formal recipes install the separate `ontology` dependency group. RDFLib,
pySHACL, and LinkML are not ordinary planning dependencies.

## Documentation

- [Agent product flow](docs/agent-product-flow.md) — source capture and
  canonical authoring procedure.
- [Domain model](docs/domain-model.md) — authoritative field ownership and
  ontology boundary.
- [Ontology facts](docs/ontology-facts.md) — closed fact families and
  canonical authoring boundary.
- [Substance template](schema/templates/substance.yaml) — copy-ready card
  skeleton.

## Non-goals

Supp Slotter is not a dose optimizer, diagnosis engine, physical-container
model, recurrence tracker, or pair-preference scheduler.
