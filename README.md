# Supp Slotter

**Local-first supplement stack planner for an agent-maintained biohacking shelf.**

Supp Slotter exists because supplement stacks become hard to reason about once products contain multiple active substances, the same vitamin exists in different forms, and timing rules depend on food, workout context, absorption conflicts, and safety warnings.

The project keeps the data in transparent YAML files and uses a small planner CLI to validate the model, generate a schedule, and surface cleanup candidates. The intended workflow is agent-assisted: an LLM edits product/substance/inventory cards, then runs the checker instead of relying on manual file discipline.

## Why This Exists

A real supplement shelf is not a flat list of pills:

- one product can contain many substances;
- one substance can exist in several practical forms;
- product label facts differ from universal substance behavior;
- inventory is only "what is on the shelf";
- scheduling needs lightweight rules, not a medical ontology.

Supp Slotter separates those concerns so a stack can be reviewed and maintained without turning into a spreadsheet or a generic habit tracker.

## What It Does

- Stores physical products, substances, inventory, goals, traits, and slots as YAML.
- Keeps products and substances separate.
- Generates stable opaque IDs and readable filenames automatically when possible.
- Validates schemas, references, inventory alignment, and cleanup candidates.
- Builds `schedule.yaml` with both product-level and substance-level views per slot.
- Uses a small trait system for food timing, workout timing, conflicts, warnings, and marker classes.

## Quick Start

```bash
uv run planner.py
uv run planner.py check
uv run planner.py plan
uv run planner.py doctor
```

`planner.py` with no arguments prints the agent-friendly command guide and the recommended scenario order.

## Agent Workflow

For data-only YAML edits:

```bash
uv run planner.py check
uv run planner.py doctor
```

For schedule-affecting edits:

```bash
uv run planner.py plan
uv run planner.py doctor
```

For planner, schema, or test changes:

```bash
uv run planner.py plan
uv run planner.py doctor
uv run pytest
```

## Project Structure

```text
supp-slotter/
├── SKILL.md                 # agent entrypoint
├── README.md                # human-facing project overview
├── planner.py               # check / plan / doctor CLI
├── schedule.yaml            # generated schedule
├── data/
│   ├── inventory.yaml       # shelf stacks only
│   ├── slots.yaml           # slot definitions
│   ├── traits.yaml          # planner-facing trait rules
│   ├── goals/               # descriptive substance clusters
│   ├── products/            # physical product cards
│   └── substances/          # substance/form cards
├── docs/
│   ├── domain-model.md      # ontology and ownership rules
│   └── ontology-facts.md    # candidate facts before planner encoding
├── schema/                  # JSON Schemas for YAML files
└── tests/                   # regression tests
```

## Core Documents

- [SKILL.md](SKILL.md) is the agent operating guide.
- [docs/domain-model.md](docs/domain-model.md) is the current domain model and ontology reference.
- [docs/ontology-facts.md](docs/ontology-facts.md) captures candidate supplement facts before they become planner behavior.
- [planner.py](planner.py) is the runtime entrypoint.
- [schedule.yaml](schedule.yaml) is generated output.

## Requirements

- Python 3.11+
- `uv`

Dependencies are declared inline in `planner.py` via PEP 723 metadata.

## Non-Goals

This is not a medical advice engine, dose optimizer, evidence grader, symptom journal, regimen tracker, or SaaS app. The model stays small unless a concrete planner behavior or data-maintenance problem requires more structure.
