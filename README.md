# Supp Slotter

**Turn a messy supplement shelf into a clear, reviewable intake plan.**

Supp Slotter is a local, deterministic planner for complex supplement stacks. It keeps products, ingredients, timing rules, interaction notes, and goal-oriented review clusters in plain YAML, then generates a pillbox-style schedule that shows what to take when and what deserves a second look.

It is designed for an agent-assisted workflow: a human brings the real products and constraints, an AI agent can maintain the cards, and the planner validates the structure before anything becomes part of the schedule.

It is not a medical advice engine. It does not decide whether a supplement is right for you. It makes the stack visible, explicit, and easier to review.

## Why It Exists

Supplement stacks rarely fail because one bottle is hard to understand. They fail because the whole shelf becomes hard to reason about:

| Stack problem | What Supp Slotter gives you |
|---|---|
| Combination products hide many active ingredients | One product card expands into concrete substances |
| Timing rules conflict | The planner separates food, empty-stomach, sleep, and workout slots |
| Forms matter | Magnesium glycinate, citrate, oxide, and threonate can be separate facts |
| Interactions are easy to forget | Relations and risk flags stay in one review surface |
| AI chat loses context | Cards, schedules, and warnings are inspectable in git |
| A new shelf makes old plans stale | Regenerate `schedule.yaml` from source cards and ontology |

The goal is simple: make supplement planning boring enough to trust and structured enough for a careful agent to help.

## Example Output

Run the planner and get a compact pillbox view:

```bash
uv run python -m planner
```

Example schedule shape, using broadly available iHerb catalog examples rather than this repository's current stack:

```text
Daily

Morning / empty stomach
  • NOW Foods - NAC 600 mg
  • Jarrow Formulas - Acetyl L-Carnitine 500 mg

Morning / with breakfast
  • California Gold Nutrition - Vitamin D3 5,000 IU
  • Nordic Naturals - Ultimate Omega
  • Doctor's Best - High Absorption CoQ10 100 mg
  • NOW Foods - Astaxanthin 4 mg

Day / with meal
  • Jarrow Formulas - Methyl B-12 & Methyl Folate
  • Jarrow Formulas - B-Right
  • NOW Foods - Zinc Picolinate 50 mg
  • California Gold Nutrition - Buffered Gold C

Before sleep / empty stomach
  • NOW Foods - Magnesium Glycinate

Training

Pre-workout
  • NOW Foods Sports - Creatine Monohydrate
  • Doctor's Best - L-Citrulline Powder

Post-workout
  • Trace Minerals - PowerPak Electrolytes
```

The full generated `schedule.yaml` also includes placement notes, warnings, kept-together products, benefit/risk clusters, and an active fact index for review.

## Who It Helps

- People with more than a few bottles and no desire to keep the whole interaction graph in their head.
- Biohacker-style users who want their stack to be inspectable instead of trapped in chat history.
- AI agents helping maintain product cards, enrich substance facts, and prepare review reports.
- Anyone onboarding a new stack who wants a reusable supplement knowledge base without inheriting someone else's active products.

## What It Does

- Models real physical products, not just ingredient names.
- Separates product-label facts from reusable substance and form knowledge.
- Schedules products into daily and training pillboxes.
- Keeps multi-ingredient products together instead of pretending their components can be split.
- Surfaces review prompts for relations, risks, pathways, and dashboard coverage.
- Lets agents draft product components by exact substance names, then normalizes them to stable `sub_*` IDs through `planner check`.
- Keeps generated output disposable: edit source cards, regenerate the schedule.

## Quick Start

Requirements:

- Python 3.14+
- `uv`

Run the current stack:

```bash
uv run python -m planner --help
uv run python -m planner
uv run python -m planner review
```

Validate source data:

```bash
uv run python -m planner check
```

`uv run python -m planner` regenerates `schedule.yaml`. That is expected; `schedule.yaml` is the report, not the source of truth.

### Canonical ontology

The runtime ontology source of truth is `ontology/`. The manifest at
`ontology/manifest.yaml` owns the LinkML modules, scheduling policies,
constraints, assertion inputs, and custom shapes. The checked-in files under
`ontology/generated/` are deterministic build artifacts; regenerate them with
`uv run python scripts/generate_ontology.py` and do not edit them by hand.

Legacy references, formats, fixtures, or migration inputs may mention the old
`data/traits/` path; the directory itself is not a retained source and may be
absent. It is not loaded by the runtime planner and must not be used as the
source for new ontology terms. Product and substance cards remain under
`data/products/` and `data/substances/`; they reference the generated canonical
vocabulary when `planner check` validates them.

## Bring Your Own Stack

This repository currently contains a real prefilled stack. For another user, treat it as a working example with a reusable substance catalog; product cards and stack state remain user-specific unless explicitly retained.

Default onboarding path:

1. Keep existing substance cards as reusable catalog knowledge.
2. For a clean personal start, clear user-specific product/dashboard data, reset `data/stacks.yaml` to the empty stack shape, then regenerate `schedule.yaml` after cards exist. For reference-only starts, move current active IDs from `daily` and `training` to `inactive`.
3. Add one product card per real bottle or package under `data/products/`.
4. Place new cards into `daily`, `training`, `inactive`, or leave intentionally `tracked-unassigned` per your new stack decisions.
5. Link components to existing substances by `sub_*`, exact substance name/form, alias, or filename stem.
6. Run `uv run python -m planner check` to normalize refs and validate the data.
7. Run `uv run python -m planner`, then `uv run python -m planner review`.

Detailed onboarding rules live in [docs/agent-product-flow.md](docs/agent-product-flow.md#onboard-a-new-stack).

## Core Workflow

```text
products on shelf
  -> product cards
  -> substance/form cards
  -> stack membership
  -> planner check
  -> generated schedule
  -> review warnings and next edits
```

For stack-improvement conversations, the product flow is:

```text
user concerns -> concern clusters -> axes to cover -> minimal stack proposal -> schedule/warnings -> next iteration
```

That flow keeps the system from turning into a giant undifferentiated supplement wiki. New knowledge is added when real product work reveals a missing form, mechanism, relation, risk, or review axis.

## Command Map

| Command | Use it for |
|---|---|
| `uv run python -m planner` | Regenerate `schedule.yaml` and print the compact pillbox view |
| `uv run python -m planner check` | Validate cards, references, stacks, canonical ontology terms, and deterministic maintenance |
| `uv run python -m planner review` | Review active concerns, relations, risk flags, pathways, and dashboard coverage |
| `uv run python -m planner audit` | Inspect structural diagnostics such as duplicates, unused traits, and empty clusters |
| `uv run python -m planner audit --full` | Add source/amount drilldown when labels, URLs, or component amounts matter |
| `uv run python -m planner find "<words>"` | Search products and substances by name, alias, form, ID, URL, or card text |
| `uv run python -m planner review-substance <path>` | Show the trait checklist and relation context for one substance card |

## Data Model

YAML is the source of truth because it is readable, reviewable, and easy for an agent to edit safely.

| Object | Location | Owns |
|---|---|---|
| Products | `data/products/` | Brand, label components, URLs, notes, product-level concerns |
| Substances | `data/substances/` | Form, aliases, timing traits, knowledge traits, substance-level concerns |
| Stacks | `data/stacks.yaml` | Which products are active in `daily`, `training`, or `inactive` |
| Pillboxes | `data/pillboxes.yaml` | Slots such as breakfast, empty stomach, sleep, and workout timing |
| Relations | `data/relations.yaml` | Substance-to-substance review and scheduling relations |
| Dashboards | `data/dashboards/` | Goal/risk clusters for review surfaces |
| Ontology | `ontology/` | Canonical scheduling/review vocabulary, policies, constraints, relations, manifest, and generated runtime artifacts |

Default ownership baseline:

- `data/substances/` is reusable catalog knowledge and should generally stay across user onboarding unless a full catalog replacement is requested.
- `data/products/`, `data/stacks.yaml`, and `data/dashboards/` are personal stack state by default.
- `schedule.yaml` is a generated report and should be regenerated from source cards plus the canonical ontology.

The runtime also builds an in-memory SurrealDB read model for graph-style queries. SurrealDB is a query layer, not persistent storage.

## Documentation

Start with [docs/README.md](docs/README.md) for the documentation map.

Most useful entry points:

- [SKILL.md](SKILL.md) — operating guide for agents editing this repo.
- [docs/agent-product-flow.md](docs/agent-product-flow.md) — guided intake, onboarding, and stack proposal workflow.
- [docs/agent-stack-review.md](docs/agent-stack-review.md) — stack review and narrative report workflow.
- [docs/domain-model.md](docs/domain-model.md) — ontology and source-of-truth rules.
- [schema/templates/](schema/templates/) — copy-ready product and substance card skeletons.

## Development

Run the full local gate:

```bash
just check
```

That runs Ruff, Pyright, planner validation, and the test suite.

## Non-Goals

Supp Slotter is not a diagnosis engine, dose optimizer, evidence grader, habit tracker, symptom journal, or SaaS app. It organizes a supplement stack, highlights mechanical review points, and keeps the data small enough to maintain.
