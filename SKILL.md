---
name: supp-slotter
description: "Use when editing or reviewing this supplement stack planner repository's data model, YAML cards, inventory stacks, pillboxes, goals, traits, slots, schedule generation, and validation workflow. This is for repository data/model maintenance, not medical advice."
metadata:
  short-description: "Edit and validate supplement stack data"
---

# Supp Slotter

Use this skill when the user asks to change supplement/product/substance data, review the stack, add goals, adjust planner behavior, or validate edits in this repository.

## Primary References

- [docs/domain-model.md](docs/domain-model.md) is the current domain model and ontology reference.
- [docs/ontology-facts.md](docs/ontology-facts.md) stress-tests how supplement facts fit the ontology.
- [README.md](README.md) is the human-facing project overview.
- [planner.py](planner.py) is the CLI/runtime entrypoint; run it without arguments to see agent workflows.
- [schema/](schema/) contains the machine-checked YAML schemas.
- [tests/](tests/) contains regression coverage for data shape, validation, and scheduling.

## File Tree

```text
supp-slotter/
├── SKILL.md                 # agent entrypoint
├── README.md                # human-facing overview
├── planner.py               # check / plan / doctor CLI
├── schedule.yaml            # generated schedule
├── data/
│   ├── inventory.yaml       # product stack membership only
│   ├── pillboxes.yaml       # pillboxes and their slots
│   ├── relations.yaml       # centralized substance-to-substance relations
│   ├── traits.yaml          # planner-facing trait rules
│   ├── goals/               # benefit/risk review clusters
│   ├── products/            # physical product cards
│   └── substances/          # substance/form cards
├── docs/
│   ├── domain-model.md      # full ontology and ownership rules
│   └── ontology-facts.md    # ontology stress-test facts
├── schema/                  # JSON Schemas for YAML files
└── tests/                   # planner and data-contract regression tests
```

## Working Rule

Before changing domain data, read [docs/domain-model.md](docs/domain-model.md) unless the edit is obviously mechanical. Treat it as authoritative for object ownership, IDs, filenames, trait ontology, and non-goals.

Keep the model small. Do not add regimen, journal, dose engine, evidence grading, or future-facing ontology unless the user explicitly asks and the checker/planner needs it now.

## Edit Targets

- Product cards: [data/products/](data/products/)
- Substance cards: [data/substances/](data/substances/)
- Substance relations: [data/relations.yaml](data/relations.yaml)
- Inventory stacks: [data/inventory.yaml](data/inventory.yaml)
- Goal clusters: [data/goals/](data/goals/)
- Trait rules: [data/traits.yaml](data/traits.yaml)
- Pillboxes and slots: [data/pillboxes.yaml](data/pillboxes.yaml)

## Onboard A New Stack

Use this when a user cloned or forked the repository for their own supplements. Assume the current files in [data/](data/) may describe the original owner's real stack, not neutral sample data. Do not mix a new user's stack into existing data unless the user explicitly asks for that.

Start with one short onboarding pass:

- Ask whether the user wants to replace current data, extend it, or keep it only as reference.
- Ask for the product list: brand, product name, source URL, and label photo/text when available.
- Ask where each product belongs: `daily`, `training`, or `inactive`.
- Ask whether goals should be created now or skipped until the first schedule exists.
- Ask whether web research is allowed. Prefer official product pages, labels, or store pages, and save useful sources in product `urls`.
- Ask about user-specific constraints that should become review warnings, such as medications, procedures, blood pressure, bleeding risk, or other known constraints. Do not make medical decisions.

For a clean start, keep project infrastructure and clear only user-specific stack data after explicit confirmation. Ask whether to keep [data/relations.yaml](data/relations.yaml) as a starter knowledge base or clear it with the user's stack data; relations can be generally useful, but they still reflect what this repository has modeled so far.

- Keep [planner.py](planner.py), [schema/](schema/), [tests/](tests/), [docs/](docs/), [SKILL.md](SKILL.md), [README.md](README.md), [data/pillboxes.yaml](data/pillboxes.yaml), and [data/traits.yaml](data/traits.yaml).
- Treat [data/products/](data/products/), [data/substances/](data/substances/), [data/goals/](data/goals/), [data/inventory.yaml](data/inventory.yaml), and [schedule.yaml](schedule.yaml) as user-specific.
- For an empty stack, set [data/inventory.yaml](data/inventory.yaml) to:

```yaml
stacks:
  daily: []
  training: []
  inactive: []
```

First pass target:

- create one product card per physical product;
- create substance cards for known label components;
- link product components to existing or newly created substance cards;
- place products into `daily`, `training`, or `inactive`;
- leave unknown planning facts as `traits: []` instead of guessing;
- run `uv run planner.py check`.

Run `uv run planner.py plan` after at least one non-inactive product exists. A blank stack can pass `check`, but it has nothing useful to schedule.

Enrich later with amounts, aliases, forms, more `urls`, label notes, traits, relations in [data/relations.yaml](data/relations.yaml), goals, and review warnings. Prefer a correct minimal first stack over a large guessed one.

## Common Workflows

`check`, `plan`, and `doctor` may write deterministic maintenance changes such as missing stable IDs or normalized filenames. Inspect `git status --short` and `git diff` after running them.

### Add Or Enrich A Product

1. Search existing products and substances first with `uv run planner.py find "<name form brand>"`. It accepts multiple words, does fuzzy partial matching, and searches card text, filenames, IDs, aliases, brands, forms, and URLs.
2. Create or update missing concrete substances before linking product components.
3. Product `components[].substance` must reference a `sub_*` id, not a name.
4. If a product source or label is available, fill the card as richly as the source supports: component labels/forms, amounts, `urls`, and other label facts in `notes` or component `notes`. Do not add fields outside [schema/product.schema.json](schema/product.schema.json).
5. If the label gives a mineral salt/form, link the concrete form card, for example `Magnesium (citrate)` or `Sodium (chloride)`, not a generic mineral placeholder.
6. Leave excipients or non-specific blends in product `notes` unless they need scheduler/review behavior.
7. Edit the product card and inventory as needed, following [docs/domain-model.md](docs/domain-model.md).
8. Run `uv run planner.py plan`, then `uv run planner.py doctor`.

### Add Or Enrich A Substance

1. Search by `name`, `form`, aliases, and likely spelling variants before creating anything: `uv run planner.py find "<name form alias>"`.
2. Before filling or changing traits on an existing substance, run `uv run planner.py review-substance data/substances/<card>.yaml`. Read the grouped checklist from the live [data/traits.yaml](data/traits.yaml) registry, not from memory. The command shows namespace headings once, short trait names under them, and the trait descriptions/application rules from the registry. Use it for traits and `unmatched_concerns`; add substance-to-substance links separately in [data/relations.yaml](data/relations.yaml).
3. For a new substance, create the minimal card first (`name`, optional `form`, `aliases`, `traits: []`), run `uv run planner.py check` so IDs/filenames are normalized, then run `uv run planner.py review-substance data/substances/<new-card>.yaml` before adding traits.
4. Reuse existing concrete forms when they match; use aliases for spelling variants.
5. Prefer concrete `name + form` cards when the source gives the form. A no-`form` card is only a temporary unknown-form fallback when the source does not disclose the form.
6. Do not create parent taxonomy cards such as generic `Magnesium` just because several forms exist. Use `doctor` similar-name clusters to review nearby forms before adding a new card.
7. Add only traits that affect current slot timing or single-substance warnings. Put broad benefit/risk groupings such as nootropic support, calming support, blood-pressure load, bleeding load, or cholinergic load in [data/goals/](data/goals/) instead of inventing marker traits.
8. Put all substance-to-substance relations in [data/relations.yaml](data/relations.yaml), never in substance cards. The file is grouped by relation type: `balance`, `competes`, `supports`, and `antagonizes`.
9. Choose relation endpoint fields by how broad each side is:
   - `source_name` / `target_name`: every form whose exact `name` field matches, for example all `Zinc` forms balancing `Copper`.
   - `source_substance` / `target_substance`: one concrete `sub_*` card.
   - Mixed endpoints are valid when only one side is form-specific, for example `source_substance` for pyridoxine HCl and `target_name` for all `Levodopa` cards.
   Do not add mirrors; `balance` and `competes` are treated as symmetric by the planner, while `supports` and `antagonizes` are directional.
10. Add relation `action` only when the source gives a concrete review action; otherwise let the planner use the default wording.
11. Run `uv run planner.py check`, then `uv run planner.py doctor`. Run `uv run planner.py plan` when traits, relations, goal clusters, `prefer_with`, or active-product substances changed.

### Update Inventory

Edit only stack membership in [data/inventory.yaml](data/inventory.yaml). Allowed stacks are `daily`, `training`, and `inactive`.

Use `daily` for ordinary recurring products; it maps to `daily_pillbox`. Use `training` for workout-adjacent products; it maps to `training_pillbox`. Products with `activity:*` substances usually belong in `training`, where those traits prefer the workout slots.

Run `uv run planner.py plan`, then `uv run planner.py doctor`.

### Add Or Update A Goal Cluster

Create or update [data/goals/](data/goals/) files with `name`, `description`, `status`, and `members`. Add `benefit` when the cluster is useful coverage. Add `risk`, `warning_threshold`, and optional `action` when the same member set can become a review load. A single cluster may have both `benefit` and `risk`; do not split one member set into two files just to separate positive and negative wording.

Run `uv run planner.py plan`, then `uv run planner.py doctor`. Goal clusters do not drive slot assignment, but they do change `benefits` and `risks` in generated [schedule.yaml](schedule.yaml).

## Minimal YAML Shapes

```yaml
# substance card
# id may be omitted for new cards; check/plan/doctor can generate it.
name: Example Substance
form: optional concrete form
aliases:
- EX
traits: []
notes: Short universal substance note.
```

```yaml
# product card
# id may be omitted for new cards; check/plan/doctor can generate it.
brand: Example Brand
name: Example Product
urls:
- https://example.com/product
components:
- substance: <existing sub_* id>
  label: Label ingredient name
  amount: 100 mg
notes: Product label context or non-active facts.
```

```yaml
# inventory
stacks:
  daily:
  - <existing prd_* id>
  training: []
  inactive: []
```

```yaml
# relation in data/relations.yaml
antagonizes:
- source_substance: sub_a873e428ee
  target_name: Levodopa
  reason: Concrete form-specific reason.
```

```yaml
# goal
name: Example Goal
description: Why this cluster exists.
status: active
members:
- substance: <existing sub_* id>
  status: taking
  role: Why it belongs to the goal.
```

## Validation Contract

Use the validation path that matches the edit:

- Data-only YAML changes: `uv run planner.py check`, `uv run planner.py doctor`, then `git status --short` and `git diff`.
- Schedule-affecting changes: `uv run planner.py plan`, `uv run planner.py doctor`, then `git status --short` and `git diff`.
- Planner, schema, or tests changed: `uv run planner.py plan`, `uv run planner.py doctor`, `uv run pytest`, then `uv run planner.py plan` again before final `git status --short` and `git diff`.

Run [planner.py](planner.py) with no arguments to see the command list and workflow hints.

## Command Behavior

- `check` validates the whole repository and may auto-fix deterministic maintenance, such as missing stable IDs or product/substance filenames.
- Schemas are the source of truth for allowed fields. Do not infer support for old substance-card `relations` from stale examples or code comments; all current substance-to-substance links belong in [data/relations.yaml](data/relations.yaml).
- `plan` runs `check` first, then rewrites [schedule.yaml](schedule.yaml).
- Do not edit [schedule.yaml](schedule.yaml) directly; regenerate it with `uv run planner.py plan`.
- `summary.take` is grouped by pillbox: read `daily_pillbox` as the ordinary organizer and `training_pillbox` as workout-only timing.
- `review_contexts` groups warnings into practical review areas; read it before the detailed `warnings` list.
- `placement_notes` lists non-warning slot compromises, such as a food-preferred product placed in an empty-stomach slot.
- Active product/substance `unmatched_concerns` are emitted as review warnings. Do not hide uncertainty in notes when it should affect review.
- Goal-cluster output is review-only: `benefits` can show `coverage_percent`, `covered`, `inactive`, and `missing`; `risks` can show active risk load and emit warnings at `warning_threshold`. Goal clusters must not drive slot assignment.
- `doctor` reports cleanup/refactor candidates, such as unused products, unused substances, clustered similar substance names, empty stacks, and stack/pillbox mismatches. It is a refactor radar, not a validator, failure, or automatic todo list.
- Read `substances.similar_names` as a review surface, not a duplicate list. A cluster means "check whether this new/edited substance should reuse an existing form, add an alias, or remain a distinct concrete form."
- In `check` output, `INFO unmatched_concern` lines are review hints, not failures. Treat `check` as passing when it ends with `All checks passed.`
- `check`, `plan`, and `doctor` may auto-fix deterministic maintenance. After running them, inspect `git status --short` and `git diff` so auto-maintenance does not hide file changes.

## When To Ask The User

Ask before inventing facts that are not on the label or already in the repo:

- uncertain ingredient form, for example B6 `pyridoxine HCl` vs `pyridoxal 5 phosphate`;
- unclear brand/vendor;
- uncertain component amount;
- missing product source/label for component facts or URLs;
- whether a product is actually on the shelf or only a reference candidate;
- adding new trait axes or ontology categories.

Do not ask for deterministic maintenance such as stable ID generation or filename normalization. Run the checker, let it auto-fix when possible, then inspect `git status --short` and `git diff`.
