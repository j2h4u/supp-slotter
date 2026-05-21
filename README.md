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
- Validates schemas, references, stack alignment, and diagnostics through `python -m planner`.
- Flags potential duplicate substance cards in `audit` so agents can catch accidental duplicates before they become product components.
- Separates review concerns by kind and labels each entry as active, inactive, knowledge-only, or tracked-unassigned.
- Builds `schedule.yaml` as generated output with `summary.take`, `action_points`, `review_contexts`, `placement_notes`, `pillboxes`, `benefits`, `risks`, `warnings`, `kept_together`, and `explanations`.
- Uses lightweight traits for food timing, workout timing, conflicts, and single-substance warnings; broader benefit/risk groupings live in dashboard clusters.
- Keeps the model small: add structure only when it helps the planner or makes data maintenance less error-prone.

## Quick Start

```bash
uv run python -m planner
uv run python -m planner check
uv run python -m planner review
uv run python -m planner audit
```

`python -m planner` with no arguments regenerates the schedule and prints a compact pillbox view. Use `python -m planner --help` for the command list.

Read generated schedules from the top:

1. `summary.take.daily` gives the ordinary recurring organizer; `summary.take.training` is workout-only timing.
2. `action_points` lists the highest-signal review prompts.
3. `review_contexts` groups detailed warnings into practical review areas.
4. `pillboxes` expands products into their slots and substances.
5. `placement_notes`, `warnings`, `kept_together`, and `explanations` show why the planner made tradeoffs.

`schedule.yaml` is a review report, not medical advice. Edit source cards under `data/`, then regenerate it with `uv run python -m planner`.

## Agent Workflow

For data-only YAML edits:

```bash
uv run python -m planner check
uv run python -m planner review
uv run python -m planner audit
git status --short
```

For schedule-affecting edits:

```bash
uv run python -m planner
uv run python -m planner review
uv run python -m planner audit
git status --short
```

For planner, schema, or test changes:

```bash
uv run python -m planner
uv run python -m planner review
uv run python -m planner audit --full
just check
git status --short
```

`check` and the default command may perform deterministic maintenance such as filling missing stable IDs or normalizing filenames. Inspect `git status --short` and `git diff` after running them. `schedule.yaml` is generated output; do not edit it by hand.

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
│   ├── effects-semantic-audit.md
│   ├── ontology-facts.md    # ontology stress-test facts
│   └── private/             # gitignored user-specific intake/proposal notes
├── schema/                  # JSON Schemas for YAML files
└── tests/                   # regression tests
```

## Core Documents

- [SKILL.md](SKILL.md) is the agent operating guide.
- [docs/domain-model.md](docs/domain-model.md) is the current domain model and ontology reference.
- [docs/effects-semantic-audit.md](docs/effects-semantic-audit.md) captures the current `effect:` boundary and cleanup status.
- [docs/ontology-facts.md](docs/ontology-facts.md) stress-tests how supplement facts fit the ontology.
- [planner/](planner/) is the runtime entrypoint package.
- [schedule.yaml](schedule.yaml) is generated output for review: read `summary` first, then `action_points`, `review_contexts`, `pillboxes`, `benefits`, `risks`, `warnings`, `kept_together`, and `explanations`. Dashboard output under `benefits` and `risks` is a neutral membership map: each member separates relevance (`matched_traits`), product tracking (`tracked_product` or `no_tracked_product`), and usage (`current`, `on_shelf`, `unassigned`, or `not_current`).

To extend or improve the ontology, first add concrete supplement facts to
[docs/ontology-facts.md](docs/ontology-facts.md). The model should evolve from
real facts that are hard to express, not from abstract categories created ahead
of use.

## Requirements

- Python 3.14+
- `uv`

Dependencies are declared in `pyproject.toml`.

## Data Model Choice

YAML cards are the source of truth because they are readable, inspectable in git, and easy for an agent to edit safely. The runtime also builds an in-memory SurrealDB read model for graph-style questions: relation classification, stack usage, dashboard member projection, fact indexes, and audit cross-references.

SurrealDB is a query layer, not persistent storage. Each command loads YAML into typed domain objects, rebuilds the read model, runs queries, and writes only generated outputs such as `schedule.yaml`.

## Non-Goals

This is not a medical advice engine, dose optimizer, evidence grader, symptom journal, habit tracker, regimen tracker, or SaaS app. It does not decide whether a supplement is good for you. It organizes the current stack, highlights mechanical review points, and stays small unless a concrete planner behavior or data-maintenance problem requires more structure.
