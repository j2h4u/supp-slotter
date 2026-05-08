# Supp Slotter

**Local supplement stack planner for people who are tired of remembering the whole shelf in their head.**

Supp Slotter replaces the manual "what goes with what?" spreadsheet in your head. You list the products you take, describe the substances inside them, and add small practical notes to each substance: `with food`, `away from food`, `pre-workout`, `competes with another substance`, `supports another substance`, `needs review`, and so on.

Then `planner.py` reads those notes, validates the cards, automatically lays the stack out into intake slots, and reports conflicts, missing pairings, review warnings, goal coverage, and tradeoffs. The generated `schedule.yaml` is the readable answer: what to take when, what was kept together because it is one physical product, and what deserves another look.

The project is built for an agent-assisted workflow. A human can say what is on the shelf; an LLM can create and enrich the YAML cards; the script checks the structure and regenerates the schedule. It is not a medical advice engine. It is a small local system for keeping supplement facts explicit instead of recalculating them from memory.

## Why This Exists

A supplement stack starts simple, then quietly turns into a coordination problem:

- combination products hide five or ten substances behind one bottle name;
- the same "vitamin B6" or "magnesium" may mean different practical forms;
- some things want food, some want an empty stomach, and some are tied to training or sleep;
- minerals, stimulatory compounds, vasodilators, fibrinolytics, and electrolytes can create review points when stacked casually;
- product labels, active substances, goals, and timing rules are different kinds of facts;
- once the shelf changes, old mental schedules become stale fast.

I wanted something boring and inspectable: a local set of YAML files, a planner that catches obvious model mistakes, and a generated schedule that says what to take when, what was kept together because it is one physical product, and what should be checked before use. Not a SaaS dashboard, not a diagnosis engine, and not a giant medical ontology.

## What It Does

- Stores physical products, substances, inventory stacks, pillboxes, goals, traits, and intake slots as YAML.
- Separates product labels from reusable substance/form behavior.
- Generates stable opaque IDs and readable filenames automatically when possible.
- Validates schemas, references, inventory alignment, and cleanup candidates through `planner.py`.
- Flags clustered similar substance-card names in `doctor` so agents can catch accidental duplicates before they become product components.
- Builds `schedule.yaml` as generated output with `summary.take`, `action_points`, `pillboxes`, `goals`, `warnings`, `kept_together`, and `explanations`.
- Uses lightweight traits for food timing, workout timing, conflicts, warnings, and marker classes.
- Keeps the model small: add structure only when it helps the planner or makes data maintenance less error-prone.

## Quick Start

```bash
uv run planner.py
uv run planner.py check
uv run planner.py plan
uv run planner.py doctor
```

`planner.py` with no arguments prints the agent-friendly command guide and workflow hints.

Read generated schedules from the top:

1. `summary.take.daily_pillbox` gives the ordinary recurring organizer; `summary.take.training_pillbox` is workout-only timing.
2. `action_points` lists the highest-signal review prompts.
3. `pillboxes` expands products into their slots and substances.
4. `warnings`, `kept_together`, and `explanations` show why the planner made tradeoffs.

`schedule.yaml` is a review report, not medical advice. Edit source cards under `data/`, then regenerate it with `uv run planner.py plan`.

## Agent Workflow

For data-only YAML edits:

```bash
uv run planner.py check
uv run planner.py doctor
git status --short
```

For schedule-affecting edits:

```bash
uv run planner.py plan
uv run planner.py doctor
git status --short
```

For planner, schema, or test changes:

```bash
uv run planner.py plan
uv run planner.py doctor
uv run pytest
uv run planner.py plan
git status --short
```

`check`, `plan`, and `doctor` may perform deterministic maintenance such as filling missing stable IDs or normalizing filenames. Inspect `git status --short` and `git diff` after running them. `schedule.yaml` is generated output; do not edit it by hand.

## Project Structure

```text
supp-slotter/
├── SKILL.md                 # agent entrypoint
├── README.md                # human-facing project overview
├── planner.py               # check / plan / doctor CLI
├── schedule.yaml            # generated schedule
├── data/
│   ├── inventory.yaml       # product stack membership only
│   ├── pillboxes.yaml       # pillboxes and their slots
│   ├── traits.yaml          # planner-facing trait rules
│   ├── goals/               # descriptive substance clusters
│   ├── products/            # physical product cards
│   └── substances/          # substance/form cards
├── docs/
│   ├── domain-model.md      # ontology and ownership rules
│   └── ontology-facts.md    # ontology stress-test facts
├── schema/                  # JSON Schemas for YAML files
└── tests/                   # regression tests
```

## Core Documents

- [SKILL.md](SKILL.md) is the agent operating guide.
- [docs/domain-model.md](docs/domain-model.md) is the current domain model and ontology reference.
- [docs/ontology-facts.md](docs/ontology-facts.md) stress-tests how supplement facts fit the ontology.
- [planner.py](planner.py) is the runtime entrypoint.
- [schedule.yaml](schedule.yaml) is generated output for review: read `summary` first, then `action_points`, `pillboxes`, `goals`, `warnings`, `kept_together`, and `explanations`.

To extend or improve the ontology, first add concrete supplement facts to
[docs/ontology-facts.md](docs/ontology-facts.md). The model should evolve from
real facts that are hard to express, not from abstract categories created ahead
of use.

## Requirements

- Python 3.11+
- `uv`

Dependencies are declared inline in `planner.py` via PEP 723 metadata.

## Data Model Choice

Other data models were considered: graph databases, multidimensional vector-style representations, and a richer ontology in TypeDB. They all fit the domain in theory, because supplements have many relationships: products contain substances, substances have forms, substances can support or compete with each other, and goals cut across the stack.

For the current use case, those options are over-engineering. The useful workflow is still small: keep readable cards, let an agent edit them, validate references, then generate a schedule. YAML plus a simple planner keeps the data inspectable, easy to review in git, and easy to change without committing to a database model before the real needs are clear.

## Non-Goals

This is not a medical advice engine, dose optimizer, evidence grader, symptom journal, habit tracker, regimen tracker, or SaaS app. It does not decide whether a supplement is good for you. It organizes the current stack, highlights mechanical review points, and stays small unless a concrete planner behavior or data-maintenance problem requires more structure.
