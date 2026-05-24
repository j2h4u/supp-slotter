# Supp Slotter

**Local supplement stack planner for people who are tired of remembering the whole shelf in their head.**

Supp Slotter replaces the manual "what goes with what?" spreadsheet in your head. You list the products you take, describe the substances inside them, add small practical traits like `with food`, `away from food`, `pre-workout`, and keep substance-to-substance relations like `competes with another substance` or `supports another substance` in one central file.

Then the `planner` package reads those notes, validates the cards, automatically lays the stack out into intake slots, and reports conflicts, missing pairings, review warnings, dashboard memberships, and tradeoffs. The generated `schedule.yaml` is the readable answer: what to take when, what was kept together because it is one physical product, and what deserves another look.

The project is built for an agent-assisted workflow. A human can say what is on the shelf; an LLM can create and enrich the YAML cards; the script checks the structure and regenerates the schedule. It is not a medical advice engine. It is a small local system for keeping supplement facts explicit instead of recalculating them from memory.

## Why This Exists

A supplement stack starts simple, then quietly turns into a coordination problem:

- combination products hide five or ten substances behind one bottle name;
- the same "vitamin B6" or "magnesium" may mean different practical forms;
- some things want food, some want an empty stomach, and some are tied to training or sleep;
- minerals, stimulatory compounds, vasodilators, fibrinolytics, and electrolytes can create review points when stacked casually;
- product labels, active substances, dashboards, and timing rules are different kinds of facts;
- once the shelf changes, old mental schedules become stale fast.

I wanted something boring and inspectable: a local set of YAML files, a planner that catches obvious model mistakes, and a generated schedule that says what to take when, what was kept together because it is one physical product, and what should be checked before use. Not a SaaS dashboard, not a diagnosis engine, and not a giant medical ontology.

## What It Does

- Stores physical products, substances, stacks, pillboxes, dashboards, traits, and intake slots as YAML.
- Separates product labels from reusable substance/form behavior.
- Generates stable opaque IDs and readable filenames automatically when possible.
- Validates schemas, references, stack alignment, and diagnostics through `uv run python -m planner`.
- Flags potential duplicate substance cards in `audit` so agents can catch accidental duplicates before they become product components.
- Separates review concerns by kind and labels each entry as active, inactive, knowledge-only, or tracked-unassigned.
- Builds `schedule.yaml` as generated output with `summary.take`, `placement_notes`, `pillboxes`, `benefits`, `risks`, `warnings`, `kept_together`, `explanations`, and the active fact index.
- Uses lightweight traits for food timing, workout timing, conflicts, and single-substance warnings; broader benefit/risk groupings live in dashboard clusters.
- Keeps the model small: add structure only when it helps the planner or makes data maintenance less error-prone.

## Quick Start

First orient without changing source data:

```bash
uv run python -m planner --help
uv run python -m planner review
uv run python -m planner audit
```

`uv run python -m planner` with no arguments regenerates the schedule and prints a compact pillbox view. Use `uv run python -m planner --help` for the command list.

Read generated schedules from the top:

1. `summary.take.daily` gives the ordinary recurring organizer; `summary.take.training` is workout-only timing.
2. `pillboxes` expands products into their slots and substances.
3. `benefits`, `risks`, and `active_fact_index` show neutral review context.
4. `warnings`, `placement_notes`, `kept_together`, and `explanations` show review prompts and planner tradeoffs.

`schedule.yaml` is a review report, not medical advice. Edit source cards under `data/`, then regenerate it with `uv run python -m planner`.

For a new user with their own supplement stack, do not start by auditing the prefilled active stack. Use [docs/agent-product-flow.md#onboard-a-new-stack](docs/agent-product-flow.md#onboard-a-new-stack): keep the existing substance cards as a reusable catalog, move current active products from `daily` and `training` to `inactive`, add one product card per real product, draft components with exact substance names or IDs, then run `check` to normalize refs, regenerate the schedule, and review the new active stack.

## Agent Workflow

For the full agent validation contract, use [SKILL.md](SKILL.md#validation-contract). Short version:

```bash
uv run python -m planner check
uv run python -m planner
uv run python -m planner review
git status --short
```

The default command regenerates `schedule.yaml`; that is expected because the file is disposable generated output. Do not edit it by hand. `check` and the default command may also perform deterministic source maintenance such as filling missing stable IDs or normalizing filenames, so inspect `git status --short` and `git diff` when you need to distinguish generated output from source-data changes.

For stack review, start with `planner review`: its `Review brief` gives the compact intake surface, and the detailed sections below it carry concerns, relations, risk flags, pathways, and dashboard counts. Use `planner audit --full` only when product source URLs, notes, or component amounts matter for the current question.

## Project Structure

```text
supp-slotter/
├── SKILL.md                 # agent entrypoint
├── README.md                # human-facing project overview
├── planner/                 # default schedule, check, review, audit CLI package
├── schedule.yaml            # generated schedule
├── data/
│   ├── stacks.yaml          # product stack membership only
│   ├── pillboxes.yaml       # pillboxes and their slots
│   ├── relations.yaml       # substance-to-substance relations
│   ├── traits/              # split trait registry by namespace
│   ├── dashboards/          # benefit/risk review clusters
│   ├── products/            # physical product cards
│   └── substances/          # substance/form cards
├── docs/
│   ├── domain-model.md      # ontology and ownership rules
│   ├── agent-product-flow.md # guided intake and onboarding workflow
│   ├── agent-stack-review.md # stack review workflow
│   ├── ontology-facts.md    # unresolved ontology pressure points
│   └── private/             # gitignored user-specific intake/proposal notes
├── schema/                  # JSON Schemas for YAML files
└── tests/                   # regression tests
```

## Core Documents

- [SKILL.md](SKILL.md) is the agent operating guide.
- [docs/domain-model.md](docs/domain-model.md) is the current domain model and ontology reference.
- [docs/agent-product-flow.md](docs/agent-product-flow.md) is the guided intake, proposal, private-context, and onboarding workflow.
- [docs/agent-stack-review.md](docs/agent-stack-review.md) is the stack review workflow.
- [docs/ontology-facts.md](docs/ontology-facts.md) keeps unresolved ontology pressure points.
- [schema/templates/](schema/templates/) contains copy-ready YAML card skeletons.
- [planner/](planner/) is the runtime entrypoint package.
- [schedule.yaml](schedule.yaml) is generated output for review. Its dashboard member shape is documented in [docs/domain-model.md](docs/domain-model.md#scheduling-semantics).

To extend or improve the ontology, encode clear facts directly in cards, traits,
relations, or dashboards. Use [docs/ontology-facts.md](docs/ontology-facts.md)
only when a concrete fact has no clear current home.

## Requirements

- Python 3.14+
- `uv`

Dependencies are declared in `pyproject.toml`.

## Data Model Choice

YAML cards are the source of truth because they are readable, inspectable in git, and easy for an agent to edit safely. The runtime also builds an in-memory SurrealDB read model for graph-style questions: relation classification, stack usage, dashboard member projection, fact indexes, and audit cross-references.

SurrealDB is a query layer, not persistent storage. Each command loads YAML into typed domain objects, rebuilds the read model, runs queries, and writes only generated outputs such as `schedule.yaml`.

## Non-Goals

This is not a medical advice engine, dose optimizer, evidence grader, symptom journal, habit tracker, regimen tracker, or SaaS app. It does not decide whether a supplement is good for you. It organizes the current stack, highlights mechanical review points, and stays small unless a concrete planner behavior or data-maintenance problem requires more structure.
