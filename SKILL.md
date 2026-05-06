---
name: supp-slotter
description: "Use when editing or reviewing this supplement stack planner repository: product cards, substance cards, inventory stacks, goals, traits, slots, schedule generation, and agent self-checks for the YAML-first supplement model."
metadata:
  short-description: "Edit and validate supplement stack data"
---

# Supp Slotter

Use this skill when the user asks to change supplement/product/substance data, review the stack, add goals, adjust planner behavior, or validate edits in this repository.

## Primary References

- [docs/domain-model.md](/home/j2h4u/repos/j2h4u/supp-slotter/docs/domain-model.md) is the current domain model and ontology reference.
- [planner.py](/home/j2h4u/repos/j2h4u/supp-slotter/planner.py) is the CLI/runtime entrypoint; run it without arguments to see agent workflows.
- [schema/](/home/j2h4u/repos/j2h4u/supp-slotter/schema) contains the machine-checked YAML schemas.
- [tests/](/home/j2h4u/repos/j2h4u/supp-slotter/tests) contains regression coverage for data shape, validation, and scheduling.

## File Tree

```text
supp-slotter/
├── SKILL.md                 # agent entrypoint
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
│   └── domain-model.md      # full ontology and ownership rules
├── schema/                  # JSON Schemas for YAML files
└── tests/                   # planner and data-contract regression tests
```

## Working Rule

Before changing domain data, read [docs/domain-model.md](/home/j2h4u/repos/j2h4u/supp-slotter/docs/domain-model.md) unless the edit is obviously mechanical. Treat it as authoritative for object ownership, IDs, filenames, trait ontology, and non-goals.

Keep the model small. Do not add regimen, journal, dose engine, evidence grading, or future-facing ontology unless the user explicitly asks and the checker/planner needs it now.

## Edit Targets

- Product cards: [data/products/](/home/j2h4u/repos/j2h4u/supp-slotter/data/products)
- Substance cards: [data/substances/](/home/j2h4u/repos/j2h4u/supp-slotter/data/substances)
- Inventory stacks: [data/inventory.yaml](/home/j2h4u/repos/j2h4u/supp-slotter/data/inventory.yaml)
- Goal clusters: [data/goals/](/home/j2h4u/repos/j2h4u/supp-slotter/data/goals)
- Trait rules: [data/traits.yaml](/home/j2h4u/repos/j2h4u/supp-slotter/data/traits.yaml)
- Slot definitions: [data/slots.yaml](/home/j2h4u/repos/j2h4u/supp-slotter/data/slots.yaml)

## Common Workflows

### Add Or Enrich A Product

1. Search existing products and substances first:
   - `rg -n "Minami|Nattokinase|Vitamin B6|pyridoxine" data/products data/substances`
2. Create or update missing concrete substances before linking product components.
3. Edit the product card and inventory as needed, following [docs/domain-model.md](/home/j2h4u/repos/j2h4u/supp-slotter/docs/domain-model.md).
4. Run `uv run planner.py plan`, then `uv run planner.py doctor`.

### Add Or Enrich A Substance

1. Search by `name`, `form`, and aliases before creating anything.
2. Reuse existing concrete forms when they match; use aliases for spelling variants.
3. Add only traits that affect current planning or warnings.
4. Run `uv run planner.py check`, then `uv run planner.py doctor`. Run `uv run planner.py plan` if active product scheduling may change.

### Update Inventory

Edit only stack membership in [data/inventory.yaml](/home/j2h4u/repos/j2h4u/supp-slotter/data/inventory.yaml).

Run `uv run planner.py plan`, then `uv run planner.py doctor`.

### Add A Goal

Create or update [data/goals/](/home/j2h4u/repos/j2h4u/supp-slotter/data/goals) files with substance IDs and short roles. Goals are descriptive clusters; do not add scheduling behavior there.

Run `uv run planner.py check`, then inspect `uv run planner.py doctor` output if the goal is intended to close orphan/coverage gaps.

## Validation Contract

Use the smallest check that matches the edit:

- Data-only YAML changes: `uv run planner.py check`, then `uv run planner.py doctor`.
- Schedule-affecting changes: `uv run planner.py plan`, then `uv run planner.py doctor`.
- Planner, schema, or tests changed: `uv run planner.py plan`, `uv run planner.py doctor`, then `uv run pytest`.

Run [planner.py](/home/j2h4u/repos/j2h4u/supp-slotter/planner.py) with no arguments to see the command list and scenario order.

`plan` writes [schedule.yaml](/home/j2h4u/repos/j2h4u/supp-slotter/schedule.yaml). `doctor` lists cleanup/refactor candidates.

## When To Ask The User

Ask before inventing facts that are not on the label or already in the repo:

- uncertain ingredient form, for example B6 `pyridoxine HCl` vs `pyridoxal 5 phosphate`;
- unclear brand/vendor;
- uncertain component amount;
- whether a product is actually on the shelf or only a reference candidate;
- adding new trait axes or ontology categories.

Do not ask for deterministic maintenance. Run the checker and let it auto-fix IDs/filenames where possible.
