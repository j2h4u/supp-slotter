---
name: supp-slotter
description: "Use when editing or reviewing this supplement stack planner repository's data model, YAML cards, stacks, pillboxes, dashboards, traits, slots, schedule generation, and validation workflow. This is for repository data/model maintenance, not medical advice."
metadata:
  short-description: "Edit and validate supplement stack data"
---

# Supp Slotter

Use this skill when the user asks to change supplement/product/substance data, review the stack, add dashboards, adjust planner behavior, or validate edits in this repository.

## Primary References

- [docs/domain-model.md](docs/domain-model.md) is the current domain model and ontology reference.
- [docs/ontology-facts.md](docs/ontology-facts.md) stress-tests how supplement facts fit the ontology.
- [README.md](README.md) is the human-facing project overview.
- [planner/](planner/) is the CLI/runtime entrypoint package; run `python -m planner` without arguments to see agent workflows.
- [schema/](schema/) contains the machine-checked YAML schemas.
- [tests/](tests/) contains regression coverage for data shape, validation, and scheduling.

## File Tree

```text
supp-slotter/
├── SKILL.md                 # agent entrypoint
├── README.md                # human-facing overview
├── planner/                 # check / plan / doctor CLI package
├── schedule.yaml            # generated schedule
├── data/
│   ├── stacks.yaml          # product stack membership only
│   ├── pillboxes.yaml       # pillboxes and their slots
│   ├── relations.yaml       # centralized substance-to-substance relations
│   ├── traits.yaml          # planner-facing trait rules
│   ├── dashboards/          # benefit/risk review clusters
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
- Stacks: [data/stacks.yaml](data/stacks.yaml)
- Dashboard clusters: [data/dashboards/](data/dashboards/)
- Trait rules: [data/traits.yaml](data/traits.yaml)
- Pillboxes and slots: [data/pillboxes.yaml](data/pillboxes.yaml)

## Onboard A New Stack

Use this when a user cloned or forked the repository for their own supplements. Assume the current files in [data/](data/) may describe the original owner's real stack, not neutral sample data. Do not mix a new user's stack into existing data unless the user explicitly asks for that.

Start with one short onboarding pass:

- Ask whether the user wants to replace current data, extend it, or keep it only as reference.
- Ask for the product list: brand, product name, source URL, and label photo/text when available.
- Ask where each product belongs: `daily`, `training`, or `inactive`.
- Ask whether dashboards should be created now or skipped until the first schedule exists.
- Ask whether web research is allowed. Prefer official product pages, labels, or store pages, and save useful sources in product `urls`.
- Ask about user-specific constraints that should become review warnings, such as medications, procedures, blood pressure, bleeding risk, or other known constraints. Do not make medical decisions.

For a clean start, keep project infrastructure and clear only user-specific stack data after explicit confirmation. Ask whether to keep [data/relations.yaml](data/relations.yaml) as a starter knowledge base or clear it with the user's stack data; relations can be generally useful, but they still reflect what this repository has modeled so far.

- Keep [planner/](planner/), [schema/](schema/), [tests/](tests/), [docs/](docs/), [SKILL.md](SKILL.md), [README.md](README.md), [data/pillboxes.yaml](data/pillboxes.yaml), and [data/traits.yaml](data/traits.yaml).
- Treat [data/products/](data/products/), [data/substances/](data/substances/), [data/dashboards/](data/dashboards/), [data/stacks.yaml](data/stacks.yaml), and [schedule.yaml](schedule.yaml) as user-specific.
- For an empty stack, set [data/stacks.yaml](data/stacks.yaml) to:

```yaml
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
- run `uv run python -m planner check`.

Run `uv run python -m planner plan` after at least one non-inactive product exists. A blank stack can pass `check`, but it has nothing useful to schedule.

Enrich later with amounts, aliases, forms, more `urls`, label notes, traits, relations in [data/relations.yaml](data/relations.yaml), dashboards, and review warnings. Prefer a correct minimal first stack over a large guessed one.

## Common Workflows

`check`, `plan`, and `doctor` may write deterministic maintenance changes such as missing stable IDs or normalized filenames. Inspect `git status --short` and `git diff` after running them.

### Add Or Enrich A Product

1. Search existing products and substances first with `uv run python -m planner find "<name form brand>"`. It accepts multiple words, does fuzzy partial matching, and searches card text, filenames, IDs, aliases, brands, forms, and URLs.
2. Create or update missing concrete substances before linking product components.
3. Product `components[].substance` must reference a `sub_*` id, not a name.
4. If a product source or label is available, fill the card as richly as the source supports: component labels/forms, amounts, `urls`, and other label facts in `notes` or component `notes`. Do not add fields outside [schema/product.schema.json](schema/product.schema.json).
5. If the label gives a mineral salt/form, link the concrete form card, for example `Magnesium (citrate)` or `Sodium (chloride)`, not a generic mineral placeholder.
6. Leave excipients or non-specific blends in product `notes` unless they need scheduler/review behavior.
7. Edit the product card and stacks as needed, following [docs/domain-model.md](docs/domain-model.md).
8. Run `uv run python -m planner plan`, then `uv run python -m planner doctor`.

### Add Or Enrich A Substance

1. Search by `name`, `form`, aliases, and likely spelling variants before creating anything: `uv run python -m planner find "<name form alias>"`.
2. Before filling or changing traits on an existing substance, run `uv run python -m planner review-substance data/substances/<card>.yaml`. Read the grouped checklist from the live [data/traits.yaml](data/traits.yaml) registry, not from memory. The registry is grouped by namespace (`intake`, `effect`, `class`, `risk`, `activity`); substance cards still reference traits as `namespace:name`. The command shows namespace headings once, short trait names under them, and the trait descriptions/application rules from the registry. Use it for traits and `concerns`; add substance-to-substance links separately in [data/relations.yaml](data/relations.yaml).
3. For a new substance, create the minimal card first (`name`, optional `form`, `aliases`, `traits: []`), run `uv run python -m planner check` so IDs/filenames are normalized, then run `uv run python -m planner review-substance data/substances/<new-card>.yaml` before adding traits.
4. Reuse existing concrete forms when they match; use aliases for spelling variants.
5. Prefer concrete `name + form` cards when the source gives the form. A no-`form` card is only a temporary unknown-form fallback when the source does not disclose the form.
6. Do not create parent taxonomy cards such as generic `Magnesium` just because several forms exist. Use `doctor` similar-name clusters to review nearby forms before adding a new card.
7. Add only traits that affect current slot timing or single-substance warnings, or `class:*` markers for intrinsic pharmacological category. Recognised class markers: `fat_soluble`, `mineral`, `electrolyte`, `adaptogen`, `antioxidant`, `ergogenic`, `nootropic`, `omega3`. Put broad benefit/risk groupings in [data/dashboards/](data/dashboards/) rather than inventing new marker traits.
8. Put all substance-to-substance relations in [data/relations.yaml](data/relations.yaml), never in substance cards. The file is grouped by relation type: `balance`, `competes`, `supports`, and `antagonizes`.
9. Choose relation endpoint fields by how broad each side is:
   - `source_name` / `target_name`: every form whose exact `name` field matches, for example all `Zinc` forms balancing `Copper`.
   - `source_substance` / `target_substance`: one concrete `sub_*` card.
   - Mixed endpoints are valid when only one side is form-specific, for example `source_substance` for pyridoxine HCl and `target_name` for all `Levodopa` cards.
   Do not add mirrors; `balance` and `competes` are treated as symmetric by the planner, while `supports` and `antagonizes` are directional.
10. Add relation `action` only when the source gives a concrete review action; otherwise let the planner use the default wording.
11. Run `uv run python -m planner check`, then `uv run python -m planner doctor`. Run `uv run python -m planner plan` when traits, relations, dashboard clusters, `prefer_with`, or active-product substances changed.

### Update Stacks

Edit only stack membership in [data/stacks.yaml](data/stacks.yaml). Allowed stacks are `daily`, `training`, and `inactive`.

Use `daily` for ordinary recurring products. Use `training` for workout-adjacent products. Products with `activity:*` substances usually belong in `training`, where those traits prefer the workout slots.

Run `uv run python -m planner plan`, then `uv run python -m planner doctor`.

### Add Or Update A Dashboard

Create or update [data/dashboards/](data/dashboards/) files with `name`, `description`, and `taking`. Add `benefit.description` when the cluster is useful coverage. Add `risk.description` when the same member set can become a review load. Every cluster must have `benefit`, `risk`, or both. Keep the `taking` list sorted alphabetically by human-readable substance name. A single cluster may have both `benefit` and `risk`; do not split one member set into two files just to separate positive and negative wording.

Run `uv run python -m planner plan`, then `uv run python -m planner doctor`. Dashboard clusters do not drive slot assignment, but they do change `benefits` and `risks` in generated [schedule.yaml](schedule.yaml). They are also a good source for future UI dashboards because they already group stack coverage and risk load into stable review buckets.

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
# data/stacks.yaml
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
# dashboard
name: Example Dashboard
description: Why this cluster exists.
benefit:
  description: What useful coverage this cluster represents.
risk:
  description: What review load this cluster can create.
taking:
- substance: <existing sub_* id>
```

## Validation Contract

Use the validation path that matches the edit:

- Data-only YAML changes: `uv run python -m planner check`, `uv run python -m planner doctor`, then `git status --short` and `git diff`.
- Schedule-affecting changes: `uv run python -m planner plan`, `uv run python -m planner doctor`, then `git status --short` and `git diff`.
- Planner, schema, or tests changed: `uv run python -m planner plan`, `uv run python -m planner doctor`, `uv run pytest`, then `uv run python -m planner plan` again before final `git status --short` and `git diff`.

Run `python -m planner` with no arguments to see the command list and workflow hints.

## Command Behavior

- `check` validates the whole repository and may auto-fix deterministic maintenance, such as missing stable IDs or product/substance filenames.
- Schemas are the source of truth for allowed fields. Do not infer support for old substance-card `relations` from stale examples or code comments; all current substance-to-substance links belong in [data/relations.yaml](data/relations.yaml).
- `plan` runs `check` first, then rewrites [schedule.yaml](schedule.yaml).
- Do not edit [schedule.yaml](schedule.yaml) directly; regenerate it with `uv run python -m planner plan`.
- `summary.take` is grouped by pillbox: read `daily` as the ordinary organizer and `training` as workout-only timing.
- `placement_notes` lists non-warning slot compromises, such as a food-preferred product placed in an empty-stomach slot.
- Active product/substance `concerns` of kind `safety` are emitted as review warnings in `schedule.yaml`. Use `uv run python -m planner audit` to see all concerns grouped by kind (safety / data_quality / model_gap).
- Dashboard-cluster output is review-only: `benefits` shows `covered`, `inactive`, and `missing` substance lists; `risks` shows the same split under `active`, `inactive`, `missing`. Dashboard clusters must not drive slot assignment.
- `doctor` reports cleanup/refactor candidates, such as unused products, unused substances, clustered similar substance names, empty stacks, and stack/pillbox mismatches. It is a refactor radar, not a validator, failure, or automatic todo list.
- Read `substances.similar_names` as a review surface, not a duplicate list. A cluster means "check whether this new/edited substance should reuse an existing form, add an alias, or remain a distinct concrete form."
- `check`, `plan`, and `doctor` may auto-fix deterministic maintenance. After running them, inspect `git status --short` and `git diff` so auto-maintenance does not hide file changes.

## Stack Grooming With Expert Panel

Use this workflow when the user wants a structured review of the active stack — not data validation, but qualitative evaluation from domain expertise.

### When to use

- User asks "evaluate my stack", "what do experts think", "is this protocol good"
- After significant stack changes (adding/removing products, new health context)
- When symptoms or health goals are stated and the user wants an informed opinion
- Periodically as a grooming pass on a mature stack

### Workflow

**Step 1 — Get full planner output**

```bash
uv run python -m planner          # schedule + slot assignment
python3 -c "
import yaml
s = yaml.safe_load(open('schedule.yaml'))
# extract warnings, benefits (covered/inactive), risks (active/inactive)
"
```

Collect: slot layout, all warnings with categories and messages, benefit cluster covered/inactive lists, active risk cluster members.

**Step 2 — Gather user context before convening**

Ask the user for any health background relevant to the stack's goals. Key dimensions:
- Health history that motivated the stack (e.g., post-smoking recovery, vascular rehab)
- Active symptoms (dyspnea, fatigue, cold extremities, etc.)
- Current medications (especially anything that interacts with supplements)
- Any prescription items in the stack (e.g., tadalafil) and their dose/intent
- Training type and frequency if ergogenic components are present
- Availability of lab markers (hsCRP, homocysteine, lipid panel, vitamin D level)

**Step 3 — Convene the panel**

Invoke `run_expert_panel` with a custom health domain panel. Standard composition for supplement stack review:

| Role | Focus |
|------|-------|
| Evidence-Based Medicine physician | Validates which components have strong vs weak evidence for the stated goal |
| Clinical Pharmacologist | Drug-supplement interactions, PK/PD of prescription items, safety flags |
| Cardiologist / Vascular Medicine | Relevant when vascular, cardiovascular, or BP goals are stated |
| Biochemist | Metabolic pathways, nutrient forms, synergies, antagonisms |
| Exercise Physiologist | Training-adjacent components, timing, ergogenic logic |
| Translational Medicine physician | Mechanistic plausibility, gap analysis between stated goal and actual coverage |

Add or replace roles based on the user's stated context (e.g., add Hepatologist if liver markers are involved, Endocrinologist if thyroid/hormonal context is present).

**Step 4 — Feed the panel**

Pass to the panel:
- Full slot layout (what, when, empty vs food)
- All active warnings with messages
- Benefit cluster coverage percentages and gaps (especially 0% clusters)
- Active risk cluster members
- User health context and symptoms
- Explicit disclaimer that this is not medical advice

**Step 5 — Handle panel questions**

If panel members formulate questions for the user (open questions), surface them clearly and wait for answers before delivering the final assessment. The answers often shift priority and risk framing significantly.

**Step 6 — Distill actionable output**

Summarise the panel consensus into:
1. What works in the current stack (validated by evidence)
2. Priority gaps to fill (highest evidence-to-impact ratio first)
3. Safety items requiring monitoring or physician discussion
4. Lab markers to establish as baseline

Do not encode panel recommendations directly into data files without the user's explicit instruction — the panel output is advisory, not automatic.

### Important boundaries

The expert panel produces informational analysis, not medical advice. Always include this framing in the output. Recommendations involving prescription medications (dose changes, additions) must be flagged as "discuss with physician" rather than presented as direct actions.

---

## Stack Optimization Ceremony

A focused variant of the expert panel — one session, two deliverables, no full-stack review. Use when the stack is already mature and the user wants incremental improvement rather than a comprehensive audit.

### When to use

- User asks "what's obviously missing", "what should I add next", "what's the weakest thing"
- After a full panel session, for follow-up grooming rounds
- When the stack has grown large and redundancy or noise has accumulated
- Periodically, as a lightweight check between full panel sessions

### Deliverables (always exactly two)

1. **Add** — one substance with the highest evidence-to-impact ratio for this specific user profile, not ranked against a generic population
2. **Remove** — the weakest link: weakest evidence for this profile, most redundant, or risk/benefit unfavorable given what's already active

The panel must reach consensus on both. If consensus is impossible, surface the conflict explicitly and ask the user to resolve it.

### Workflow

**Step 1 — Collect current state**

```bash
uv run python -m planner
python3 -c "
import yaml
s = yaml.safe_load(open('schedule.yaml'))
for b in s['benefits']: print(b['name'], 'covered:', b.get('covered', []))
for r in s['risks']: print(r['name'], 'active:', r.get('active', []))
"
```

Collect: slot layout, benefit cluster covered/inactive lists (flag fully empty covered), active risk cluster members, active warnings.

**Step 2 — Gather delta context**

Before convening, note what changed since the last panel:
- Products added or removed since last session
- Symptoms that changed
- Lab results that arrived
- Previous panel recommendations that were NOT yet acted on (carry-forward items)

Carry-forward items are high-signal: if a previous panel called something HIGH priority and it wasn't added, the optimization ceremony almost always confirms it.

**Step 3 — Convene with focused brief**

Invoke `run_expert_panel` with the same standard health domain panel composition (see above). Pass:
- Full slot layout and benefit/risk coverage map
- Delta context (what changed, what was deferred)
- Previous panel findings summary
- Explicit instruction: **two deliverables only — one to add, one to remove**

**Step 4 — Panel produces consensus**

Each expert gives an individual take on both questions. The panel then resolves any conflicts using this priority ladder for the supplement domain:

1. Safety (bleeding load, drug interactions, narrow therapeutic windows)
2. Evidence strength (RCT > mechanistic > observational)
3. Specificity to user profile (post-nicotine, vascular, active runner, etc.)
4. Cluster gap (0% coverage > partial coverage > already well-covered)
5. Redundancy signal (double-covering one mechanism while another is empty)

**Step 5 — Carry-forward to next session**

After each optimization ceremony, explicitly note items deferred to the next round. These become the Round N+1 agenda. Typical carry-forward candidates:
- The substance that ranked #2 for addition (but lost consensus to #1)
- Safety flags that need lab data before acting (e.g., TMAO from dual carnitine)
- Dose adequacy questions (e.g., EPA at subtherapeutic level)
- Redundancy patterns worth watching but not yet worth removing

### Session record

Save the optimization ceremony output to `docs/private/expert-panel-YYYY-MM.md`. Include:
- User health profile snapshot (delta from previous session)
- Stack at time of session (active products, slot layout)
- Panel composition
- Add/remove recommendations with full rationale
- Carry-forward agenda for next round

This creates a longitudinal record of how the stack evolved and why each decision was made.

### Important boundaries

Same as full panel: informational analysis, not medical advice. Prescription items require physician discussion. Panel recommendations are advisory — do not modify data files without explicit user confirmation.

---

## When To Ask The User

Ask before inventing facts that are not on the label or already in the repo:

- uncertain ingredient form, for example B6 `pyridoxine HCl` vs `pyridoxal 5 phosphate`;
- unclear brand/vendor;
- uncertain component amount;
- missing product source/label for component facts or URLs;
- whether a product is actually on the shelf or only a reference candidate;
- adding new trait axes or ontology categories.

Do not ask for deterministic maintenance such as stable ID generation or filename normalization. Run the checker, let it auto-fix when possible, then inspect `git status --short` and `git diff`.
