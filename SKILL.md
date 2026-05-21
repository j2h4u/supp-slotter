---
name: supp-slotter
description: "Use when editing or reviewing this supplement stack planner repository's data model, YAML cards, stacks, pillboxes, dashboards, traits, slots, schedule generation, validation workflow, or guided supplement-stack intake/proposal flow. This is for repository data/model maintenance and structured product guidance, not medical advice."
metadata:
  short-description: "Guide, edit, and validate supplement stacks"
---

# Supp Slotter

Use this skill when the user asks to change supplement/product/substance data, guide supplement-stack intake, propose minimal stack improvements, review the stack, add dashboards, adjust planner behavior, or validate edits in this repository.

## Primary References

- [docs/domain-model.md](docs/domain-model.md) is the current domain model and ontology reference.
- [docs/effects-semantic-audit.md](docs/effects-semantic-audit.md) captures the current `effect:` boundary and cleanup status.
- [docs/ontology-facts.md](docs/ontology-facts.md) stress-tests how supplement facts fit the ontology.
- [README.md](README.md) is the human-facing project overview.
- [planner/](planner/) is the CLI/runtime entrypoint package; run `python -m planner --help` to see available commands.
- [schema/](schema/) contains the machine-checked YAML schemas.
- [tests/](tests/) contains regression coverage for data shape, validation, and scheduling.

## File Tree

```text
supp-slotter/
├── SKILL.md                 # agent entrypoint
├── README.md                # human-facing overview
├── planner/                 # default schedule, check, review, audit CLI package
│   └── query_model/          # in-memory SurrealDB read model; YAML remains source of truth
├── schedule.yaml            # generated schedule
├── data/
│   ├── stacks.yaml          # product stack membership only
│   ├── pillboxes.yaml       # pillboxes and their slots
│   ├── relations.yaml       # centralized substance-to-substance relations
│   ├── traits/              # split trait registry by namespace
│   ├── dashboards/          # benefit/risk review clusters — prefer semantic from_traits projections; context: tags are fallback-only.
│   ├── products/            # physical product cards
│   └── substances/          # substance/form cards
├── docs/
│   ├── domain-model.md      # full ontology and ownership rules
│   ├── effects-semantic-audit.md
│   ├── ontology-facts.md    # ontology stress-test facts
│   └── private/             # gitignored user-specific intake/proposal notes
├── schema/                  # JSON Schemas for YAML files
└── tests/                   # planner and data-contract regression tests
```

## Working Rule

Before changing domain data, read [docs/domain-model.md](docs/domain-model.md) unless the edit is obviously mechanical. Treat it as authoritative for object ownership, IDs, filenames, trait ontology, and non-goals.

Keep the model small. Do not add regimen, journal, dose engine, evidence grading, or future-facing ontology unless the user explicitly asks and the checker/planner needs it now.

This is a self-owned product. Do not preserve old command aliases, schemas, docs, tests, or code paths solely because they existed before; keep compatibility only when the user explicitly asks for it or there is a current product reason.

## Product Operating Protocol

Treat the product as a guided decision loop, not as a YAML editor. The useful flow is:

```text
user concerns -> concern clusters -> axes to cover -> minimal stack proposal -> schedule/warnings -> next iteration
```

Use this mode when the user asks how to improve their stack, what to add next, how to address health goals, or how another person should start using the system. Start with the person's goals and constraints before touching cards.

### Intake Before Data Edits

Ask one compact round of intake questions before proposing supplements:

- What are the top concerns or goals? Ask for plain-language symptoms/goals, not supplement names.
- What is already active? Include supplements, prescription medications, and relevant procedures.
- What constraints matter? Budget, pill burden, frequency, tolerated forms, risk tolerance, and "max new changes this round".
- What data exists? Labs, diagnoses, clinician guidance, wearable metrics, or "none yet".
- What must be avoided? Bleeding risk, blood pressure concerns, glucose meds, surgery, pregnancy, allergies, or other user-specific safety constraints.

If the user gives health history, frame it as context and hypotheses. Do not diagnose, treat, or imply causality. For prescription medication, dose changes, serious symptoms, or high-risk interactions, mark the item as "discuss with physician" rather than an action.

### Private User Context

Persist user-reported personal context only under [docs/private/](docs/private/). This directory is intentionally gitignored. Use it for intake notes, health history, symptoms, labs, medications, goals, constraints, expert-panel notes, candidate proposals, and decision rationale tied to a specific person.

Do not put user-specific health information into tracked docs, examples, data cards, dashboards, traits, or relations unless the user explicitly asks for that exact information to become tracked project data. Tracked YAML should contain reusable product/substance knowledge and approved stack membership, not private biography.

Recommended filenames:

- `docs/private/intake-YYYY-MM-DD.md` for the current user profile and goals;
- `docs/private/proposal-YYYY-MM-DD.md` for candidate stack proposals;
- `docs/private/expert-panel-YYYY-MM.md` for panel or optimization-session outputs.

Each private intake/proposal note should preserve:

- user-reported facts, clearly labeled as reported context;
- assumptions and uncertainties;
- concern clusters and axes considered;
- candidate changes separated from approved active stack changes;
- safety questions and labs/clinician follow-ups;
- next iteration agenda.

### Concern Clusters

Translate intake into 2-5 concern clusters. A concern cluster is a product-facing problem area, not a dashboard file by default.

Examples of concern clusters:

- vascular/endothelial support;
- fibrinolysis or clotting review;
- mitochondrial energy and lactate handling;
- lipid/cholesterol support;
- skin barrier/collagen/inflammation support;
- age-range prevention.

For each cluster, write:

- what the user said that makes it relevant;
- what would make it safer or more measurable, such as labs or clinician context;
- which claims are uncertain or should stay as hypotheses.

### Axes

For each concern cluster, pick axes before picking products. An axis is a reusable biological/review dimension that substances can cover.

Good axes are reusable and inspectable: `is:`, `effect:`, `risk:`, or `pathway:` traits, relation types in [data/relations.yaml](data/relations.yaml), or dashboard projections from those facts. Use `context:` only as a fallback when no cleaner reusable axis exists.

Do not create a new axis just because it sounds product-friendly. Add or refine an axis only when it will help multiple cards, improve review output, or make planner/audit behavior more accurate.

### Progressive Knowledge Growth

Expect guided product work to surface new substances, forms, mechanisms, cofactors, risks, relations, and candidate products. Treat this as a normal and valuable knowledge-base growth path, not as scope creep.

When a new fact or candidate appears:

1. Search first with `uv run python -m planner find "<name form alias>"`.
2. Prefer enriching an existing concrete card when it already represents the substance/form.
3. Create a new substance card when a real substance/form is missing, even if it is not active in the current stack.
4. Keep reference-only substance cards when they contain reusable knowledge; they do not need to be tied to an active product to be useful.
5. Add reusable facts to tracked cards only when they are about the substance/product itself, not about the user's private health context.
6. Put user-specific rationale, symptoms, hypotheses, and decision history in `docs/private/`.

Good enrichment targets:

- aliases and spelling variants;
- concrete forms and label-specific component notes;
- `knowledge.is:`, `effect:`, `risk:`, `pathway:` facts;
- scheduling facts under `schedule:` only when they affect slot assignment;
- substance-to-substance `balance`, `competes`, `supports`, or `antagonizes` relations;
- product URLs, label notes, and component amounts when available.

Do not attempt one-shot full enrichment of the whole ontology. Enrich opportunistically as product work reveals a concrete need, then run the relevant validation commands.

### Minimal Stack Proposal

Prefer a small first proposal over broad coverage. Default limit: 1-3 new active changes for a cautious round, 3-5 only if the user explicitly accepts a larger change set.

Rank candidate additions by:

1. safety and interaction risk;
2. relevance to the stated concern clusters;
3. evidence-to-impact ratio for this user profile;
4. coverage overlap across multiple axes;
5. cofactor/synergy support;
6. low antagonism, low redundancy, and low pill burden.

Use existing active products first. If a useful substance is not on the shelf, treat it as a candidate and possible knowledge-base enrichment, not an automatic stack edit. Put it in `inactive` only when the user wants to track it in the repo.

When explaining a proposal, use this structure:

```text
Concern -> Axis -> Current coverage -> Candidate change -> Why this is minimal -> Safety/review flags -> What to check next
```

### Guardrails

- Do not add 10-20 substances in one step.
- Do not optimize for maximum dashboard coverage at the expense of safety, simplicity, or interpretability.
- Do not treat reference-only substance cards as cleanup trash; they may be valid knowledge-base entries.
- Do not convert product-facing concern clusters into `data/dashboards/` files unless the user wants persistent tracking and the membership can be expressed cleanly.
- Do not edit stack data after a product intake/proposal unless the user explicitly approves the concrete changes.
- Always separate "candidate to discuss/research" from "active stack change".

### Testing The Guided Protocol

Test the product protocol at three levels:

1. **Private founder-user smoke**: use the real first user when product-discovering the flow. Save reported health context under `docs/private/intake-YYYY-MM-DD.md`, generate a proposal under `docs/private/proposal-YYYY-MM-DD.md`, and confirm `git status --short` does not show those files.
2. **Skill-behavior regression**: use synthetic personas only for shareable, non-private regression examples or future automated checks. Synthetic scenarios must not replace the founder-user smoke while the product protocol is still being shaped.
3. **Repo behavior test**: only after the user approves concrete stack/card edits, run the normal validation contract (`planner check`, `planner review`, `planner audit`, schedule generation, and tests as needed).

A passing guided-protocol test must show:

- user-reported facts are labeled as reported context and kept out of tracked files;
- concern clusters are separated from persistent dashboard files;
- axes are explicit and reusable where possible;
- candidate changes are limited and staged;
- safety questions and physician/lab follow-ups are visible;
- no active stack change is made without explicit user approval.

## Edit Targets

- Product cards: [data/products/](data/products/)
- Substance cards: [data/substances/](data/substances/)
- Substance relations: [data/relations.yaml](data/relations.yaml)
- Stacks: [data/stacks.yaml](data/stacks.yaml)
- Dashboard clusters: [data/dashboards/](data/dashboards/)
- Trait rules: [data/traits/](data/traits/)
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

- Keep [planner/](planner/), [schema/](schema/), [tests/](tests/), [docs/](docs/), [SKILL.md](SKILL.md), [README.md](README.md), [data/pillboxes.yaml](data/pillboxes.yaml), and [data/traits/](data/traits/).
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
- leave unknown planning facts as `schedule: {}` and `knowledge: {}` instead of guessing;
- run `uv run python -m planner check`.

Run `uv run python -m planner` after at least one non-inactive product exists. A blank stack can pass `check`, but it has nothing useful to schedule.

Enrich later with amounts, aliases, forms, more `urls`, label notes, traits, relations in [data/relations.yaml](data/relations.yaml), dashboards, and review warnings. Prefer a correct minimal first stack over a large guessed one.

## Common Workflows

`check` and the default command may write deterministic maintenance changes such as missing stable IDs or normalized filenames. Inspect `git status --short` and `git diff` after running them.

### Add Or Enrich A Product

1. Search existing products and substances first with `uv run python -m planner find "<name form brand>"`. It accepts multiple words, does fuzzy partial matching, and searches card text, filenames, IDs, aliases, brands, forms, and URLs.
2. Create or update missing concrete substances before linking product components.
3. Product `components[].substance` must reference a `sub_*` id, not a name.
4. For a new product: copy [schema/templates/product.yaml](schema/templates/product.yaml) to `data/products/<slug>.yaml`. The template has all fields with inline comments explaining conventions. Fill all applicable fields. Do not add fields outside [schema/product.schema.json](schema/product.schema.json).
5. If the label gives a mineral salt/form, link the concrete form card, for example `Magnesium (citrate)` or `Sodium (chloride)`, not a generic mineral placeholder.
6. Leave excipients or non-specific blends in product `notes` unless they need scheduler/review behavior.
7. Edit the product card and stacks as needed, following [docs/domain-model.md](docs/domain-model.md).
8. Run `uv run python -m planner`, then `uv run python -m planner review` (advisory) and `uv run python -m planner audit` (diagnostics).

### Add Or Enrich A Substance

1. **Always** search before creating: `uv run python -m planner find "<name form alias>"`. This command does fuzzy matching across names, forms, aliases, IDs, and notes. Do NOT use grep, glob, or `ls` to check whether a substance exists — these miss aliases and alternate spellings. If `find` returns no results, the substance does not exist.
2. Before filling or changing traits on an existing substance, run `uv run python -m planner review-substance data/substances/<card>.yaml`. Read the grouped checklist from the live [data/traits/](data/traits/) registry, not from memory. The registry is grouped by namespace (`is`, `effect`, `intake`, `timing`, `risk`, `activity`, `pathway`); `context` membership is resolved through [data/dashboards/](data/dashboards/). Substance cards store traits in the v2 nested `schedule:` / `knowledge:` sections. The command shows namespace headings once, short trait names under them, and the trait descriptions/application rules from the registry. Use it for traits and `concerns`; add substance-to-substance links separately in [data/relations.yaml](data/relations.yaml).
3. For a new substance: copy [schema/templates/substance.yaml](schema/templates/substance.yaml) to `data/substances/<slug>.yaml` — use only lowercase letters, digits, and underscores; no `sub_*` ID in the filename. Do NOT generate or invent an ID. The template has all fields with inline comments explaining conventions. At minimum fill `name`; fill all other applicable fields before saving. Run `uv run python -m planner check` — it assigns a stable ID and renames the file to `<slug>__sub_<id>.yaml` automatically. Then run `uv run python -m planner review-substance data/substances/<new-card>.yaml` before adding traits.
4. Reuse existing concrete forms when they match; use aliases for spelling variants.
5. Prefer concrete `name + form` cards when the source gives the form. A no-`form` card is only a temporary unknown-form fallback when the source does not disclose the form.
6. Do not create parent taxonomy cards such as generic `Magnesium` just because several forms exist. Use `planner audit` > Potential duplicate substance cards to review nearby forms before adding a new card.
7. Add traits only when they affect current slot timing or express a reusable reviewer fact: intrinsic class, pharmacological effect, risk flag, pathway, or dashboard projection. See [data/traits/](data/traits/) for the full namespace registry. Run `uv run python -m planner review-substance data/substances/<card>.yaml` to inspect a card's current tags grouped by namespace before adding or changing tags.

   **Which namespace? Which actor?**

   Rule of thumb: if a slug affects slot assignment → `schedule:`; otherwise → `knowledge:`.

   Scheduling namespaces (go under `schedule:` in the card):
   - Use `intake:` when the substance has a food-state preference (`food_required`, `empty_preferred`, etc.). Max 1 entry per substance.
   - Use `timing:` when the substance has a scheduling-relevant effect (`energy_like`, `sleep_disruptive`, `sleep_support`). Max 1 entry. Drives slot scoring.
   - Use `activity:` when the substance has a workout timing marker (`pre_workout`, `post_workout`, `any_workout`). Max 1 entry per substance.

   Reviewer namespaces (go under `knowledge:` in the card):
   - Use `is:` when the property is true regardless of stack goals (intrinsic class/category). It should be a nominal taxonomy: nouns or noun phrases that pass the "is a kind of X" test. Do not put action-shaped facts here.
   - Use `effect:` for registered pharmacological or functional facts not relevant to timing: vasodilator, cholinergic_support, pde5_inhibition, fibrinolytic, etc. Surfaced by `planner review`.
   - Use `risk:` when the substance carries a warning marker. Surfaced by `planner review` in the Risk flags section.
   - Use `context:` only as a fallback when no cleaner `is:`, `effect:`, `risk:`, or `pathway:` axis can express dashboard membership. Polyhierarchical; review-classification only — does not influence slot scoring.
   - Use `pathway:` when the substance participates in a named biochemical/metabolic pathway. Review/grouping only — does not influence slot scoring.
   - Leave unencoded if none apply.

   **What NOT to put in `context:`:**
   - Do NOT use `context:` for scheduling-affecting traits. Those go under `schedule:` (`intake:`, `timing:`, `activity:`).
   - Do NOT use `context:` as a synonym for `is:`. `is:` is for intrinsic biochemical category (open-world); `context:` is for operator-curated review-context membership (closed-world).
   - Do NOT default to `context:` for dashboard membership. Prefer projecting dashboards from existing semantic facts (`is:`, `effect:`, `risk:`, `pathway:`). Add or refine a trait axis when it is a real reusable review fact. Use `context:` only as the last resort for genuinely hand-curated clusters that cannot be modeled cleanly otherwise.
8. Put all substance-to-substance relations in [data/relations.yaml](data/relations.yaml), never in substance cards. The file is grouped by relation type: `balance`, `competes`, `supports`, and `antagonizes`.
9. Choose relation endpoint fields by how broad each side is:
   - `source_name` / `target_name`: every form whose exact `name` field matches, for example all `Zinc` forms balancing `Copper`.
   - `source_substance` / `target_substance`: one concrete `sub_*` card.
   - Mixed endpoints are valid when only one side is form-specific, for example `source_substance` for pyridoxine HCl and `target_name` for all `Levodopa` cards.
   Do not add mirrors; `balance` and `competes` are treated as symmetric by the planner, while `supports` and `antagonizes` are directional.
10. Add relation `action` only when the source gives a concrete review action; otherwise let the planner use the default wording.
    Add `severity` (`critical`, `high`, `medium`, `low`) only for clinically significant relations. Leave it unset for routine entries — the planner uses default warning wording when severity is absent.
11. Run `uv run python -m planner check`, then `uv run python -m planner review` (advisory: concerns, relations, risk flags, pathways) and `uv run python -m planner audit` (diagnostics). Run `uv run python -m planner` when traits, relations, dashboard clusters, `prefer_with`, or active-product substances changed.

### Update Stacks

Edit only stack membership in [data/stacks.yaml](data/stacks.yaml). Allowed stacks are `daily`, `training`, and `inactive`.

Use `daily` for ordinary recurring products. Use `training` for workout-adjacent products. Products with `activity:*` substances usually belong in `training`, where those traits prefer the workout slots.

Run `uv run python -m planner`, then `uv run python -m planner review` and `uv run python -m planner audit`.

### Add Or Update A Dashboard

Dashboard clusters use grouped `from_traits:` membership rules. Prefer building dashboard membership from reusable semantic axes already present on substances, rather than adding a dashboard-specific tag to each substance.

Recommended sequence:
1. Decide which semantic fact defines membership: `is:`, `effect:`, `risk:`, or `pathway:`.
2. If the fact is real and reusable, add or refine the trait/effect/risk/pathway on substance cards first.
3. Create `data/dashboards/<slug>.yaml` with `name`, `description`, `benefit`/`risk`, and a `from_traits:` projection over that semantic axis.
4. Use `from_traits: { context: [<slug>] }` only as a last resort when the membership is genuinely operator-curated and cannot be expressed through a cleaner reusable axis.
5. Run `uv run python -m planner check` to validate reference integrity (hard FK errors).
6. Run `uv run python -m planner` to regenerate `schedule.yaml`.
7. Run `uv run python -m planner review` for concerns, relations, risk flags, and pathways (advisory, exit 0). Run `uv run python -m planner audit` for diagnostics.
8. Run `uv run pytest` to confirm tests still pass.

When to use semantic projections vs `context:` tag:
- Use `from_traits: { is: [<class_slug>] }` when membership is defined by an intrinsic biochemical category (e.g. all antioxidants or electrolytes). The cluster grows automatically as new substances acquire that class — intensional / open-world.
- Use `from_traits: { risk: [<risk_slug>] }` for load/overload or medication-interaction review axes, such as bleeding, hypotensive, or serotonergic load.
- Use `from_traits: { effect: [<effect_slug>] }` for shared pharmacological/review effects that are not scheduling traits.
- Use `from_traits: { pathway: [<pathway_slug>] }` when the dashboard is exactly a biochemical/metabolic pathway view.
- Use `from_traits: { context: [<slug>] }` only when membership is curated by the operator and no cleaner semantic axis exists. This is extensional / closed-world and should be rare because it adds per-card membership bookkeeping without much model value.
- Mix namespaces in one `from_traits:` object when appropriate. Resolution is union (logical OR) across all listed (namespace, slug) pairs — there is NO AND across namespace groups.

A single cluster may have both `benefit` and `risk` sections. Do not split one member set into two files.

## Minimal YAML Shapes

```yaml
# substance card — v2 nested shape; schedule:/knowledge: blocks are optional; omit any that don't apply.
# id may be omitted for new cards; check/default command can generate it.
name: Example Substance
form: optional concrete form
aliases:
- EX
notes: Short universal substance note.
schedule:
  intake:
  - food_preferred
  timing: []
  activity: []
knowledge:
  is:
  - antioxidant
  effect: []           # registered pharmacological/review effects
  risk: []
  context: []
  pathway: []
```

```yaml
# product card
# id may be omitted for new cards; check/default command can generate it.
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
# dashboard — semantic projection over reusable traits
name: Example Risk Load
description: Why this review axis exists.
benefit:
  description: What useful coverage this cluster represents.
risk:
  description: What review load this cluster can create.
from_traits:
  risk:
  - example_risk_trait
```

```yaml
# dashboard — class projection over intrinsic categories
name: Antioxidant Protection
description: All antioxidant substances.
benefit:
  description: Antioxidant coverage.
from_traits:
  is:
  - antioxidant
```

## Validation Contract

Use the validation path that matches the edit:

- Data-only YAML changes: `uv run python -m planner check`, `uv run python -m planner review`, `uv run python -m planner audit`, then `git status --short` and `git diff`.
- Schedule-affecting changes: `uv run python -m planner`, `uv run python -m planner review`, `uv run python -m planner audit`, then `git status --short` and `git diff`.
- Planner, schema, or tests changed: `uv run python -m planner`, `uv run python -m planner review`, `uv run python -m planner audit --full`, `just check`, then `git status --short` and `git diff`.

Run `python -m planner --help` to see the command list and workflow hints.

Reference-integrity errors (hard — from `planner check`, exit non-zero):
- Unknown trait `{slug}` under namespace `{namespace}:` in `substances/<file>.yaml` — the slug is not registered in `data/traits/` under that namespace. Fix: add the trait definition under the correct namespace file before using it.
- Unknown review context `{slug}` in a substance card or dashboard `from_traits` — there is no matching `data/dashboards/{slug}.yaml`. Fix: create the dashboard yaml or correct the slug.
- Unknown trait `{slug}` under a trait-backed namespace in `from_traits` of `dashboards/<file>.yaml` — the slug is not registered in `data/traits/`. Fix: register it first, or correct the slug.

Advisory output is split between two commands:
- `planner review` — concerns (safety / data_quality / model_gap), each labeled `[active]`, `[inactive]`, `[reference-only]`, or `[unstacked]`; relations status (both_active / missing_source / missing_target / neither_active); risk flags (`knowledge.risk:` slugs on active substances); pathway memberships; dashboard summary.
- `planner audit` — diagnostics (valid reference-only KB cards, products outside stacks, unused traits, potential duplicate cards, empty clusters) and optional `--full` deep card quality checks.

Advisory cleanup warnings (soft — from `planner audit`, exit 0):
- `dashboard.empty_cluster` — dashboard `from_traits` resolves to zero member substances.

Hard errors (`check`) block all downstream commands. Advisory output (`review` and `audit`) reports state for operator attention but does not block.

## Membership Flow

Canonical `from_traits` resolution rule: a substance is a member of a dashboard if ANY (namespace, slug) pair in the dashboard's `from_traits` object also appears in the substance's corresponding per-namespace field. Resolution is union (logical OR) across the entire `from_traits` object — NO AND semantic across namespace groups.

To determine which substances are in a dashboard cluster:
1. Read the cluster's `from_traits` object to get all (namespace, slug) pairs.
2. For each substance card in `data/substances/`, check each namespace field against the cluster's pairs.
3. A substance is a cluster member if any of its namespace entries matches any (namespace, slug) pair from `from_traits`.
4. The full member set is the union of all matching substances.

To determine which clusters a substance belongs to:
1. Read the substance's semantic namespace lists (`is:`, `effect:`, `risk:`, `pathway:`) and match them against dashboard `from_traits:` rules.
2. Read the substance's `context:` list only for rare fallback clusters that use extensional projection.
3. Run `uv run python -m planner review-substance data/substances/<card>.yaml` to see the computed membership for a specific card.

To add a substance to a cluster:
1. Prefer adding the underlying reusable fact that the cluster projects from: `is:`, `effect:`, `risk:`, or `pathway:`.
2. Add the cluster slug to the substance card's `context:` list only for fallback operator-curated clusters with no cleaner semantic axis.

## Review Warning Playbook

WHEN to run `uv run python -m planner review`:
- After any substance card edit
- After any stack change (adding/removing/moving a product)
- Before commit

The Risk flags section is the canonical surface for `knowledge.risk:` tags on active substances — agents MUST scan it for every active substance carrying a `risk:` tag. If a substance has `knowledge.risk: [manual_review]`, its name will appear under the `manual_review` group in the Risk flags section of `planner review` output.

Concern headings include membership labels. Treat `[active]` concerns as current-stack work first; `[inactive]` concerns as shelf/backlog verification; `[reference-only]` as reusable KB notes; and `[unstacked]` product concerns as data that is not currently assigned to a stack. Do not delete reference-only cards or inactive product concerns merely because they are not active.

Note: `review` produces advisory output (soft — exit 0). It does NOT block commits.

## Audit Warning Playbook

WHEN to run `uv run python -m planner audit`:
- After any substance card edit (traits, `context:` tags, `is:` tags)
- After any dashboard yaml edit (`from_traits` changes, new cluster created)
- After any `data/traits/` change (trait-backed namespace entry, renamed slug)
- Once at end of session before commit

Note: `audit` produces diagnostic output (soft — exit 0). Concerns, relations, risk flags, and pathways are in `planner review`. For HARD reference-integrity errors that block commits, use `planner check`.

Per-warning-class resolution:

**`dashboard.empty_cluster`**
Message format: `Empty cluster: data/dashboards/{slug}.yaml from_traits resolves to zero member substances (using union resolution: OR across all listed (namespace, slug) pairs). Resolution: tag substances under context: {slug}, OR remove the dashboard yaml if abandoned. (If this is an intentional placeholder, add a notes: field explaining the intent.)`
Causes: all tagged substances were removed; or `from_traits` slugs do not match any substance's namespace fields under the canonical OR-across-namespaces resolution rule.
Resolution: first check whether the dashboard should project from a semantic axis (`is:`, `effect:`, `risk:`, `pathway:`) and add/fix that underlying fact on substance cards. Use `context: <slug>` tagging only for fallback operator-curated clusters. Remove the dashboard yaml if the cluster is abandoned. If the cluster is an intentional placeholder for future use, add a `notes:` field explaining the intent.

## Command Behavior

- `check` validates the whole repository and may auto-fix deterministic maintenance, such as missing stable IDs or product/substance filenames.
- Schemas are the source of truth for allowed fields. Do not infer support for old substance-card `relations` from stale examples or code comments; all current substance-to-substance links belong in [data/relations.yaml](data/relations.yaml).
- The default command runs the scheduler after validation, rewrites [schedule.yaml](schedule.yaml), and prints a compact pillbox view.
- SurrealDB is used only through [planner/query_model/](planner/query_model/) as a rebuilt in-memory read model for relation, dashboard, fact-index, and audit queries. Do not write source data through SurrealDB.
- Do not edit [schedule.yaml](schedule.yaml) directly; regenerate it with `uv run python -m planner`.
- `summary.take` is grouped by pillbox: read `daily` as the ordinary organizer and `training` as workout-only timing.
- `placement_notes` lists non-warning slot compromises, such as a food-preferred product placed in an empty-stomach slot.
- Active product/substance `concerns` of kind `safety` are emitted as review warnings in `schedule.yaml`. Use `uv run python -m planner review` to see all concerns grouped by kind (safety / data_quality / model_gap) with membership labels.
- Dashboard-cluster output is review-only: `benefits` shows `covered` and `inactive` substance lists; `risks` shows the same split under `active` and `inactive`. Reference-only substance cards are valid knowledge-base entries, not missing product coverage. Dashboard clusters must not drive slot assignment.
- `audit` reports diagnostics — valid reference-only KB cards, products outside stacks, unused traits, potential duplicate cards, empty stacks, stack/pillbox mismatches. It is a review surface, not a validator or automatic todo list.
- Read `substances.similar_names` as a potential-duplicate review surface, not a duplicate list. A cluster means "check whether this new/edited substance should reuse an existing form, add an alias, or remain a distinct concrete form."
- `check` and the default command may auto-fix deterministic maintenance. After running them, inspect `git status --short` and `git diff` so auto-maintenance does not hide file changes.

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

A focused variant of the expert panel — one session, narrow recommendations, no full-stack review. Use when the stack is already mature and the user wants incremental improvement rather than a comprehensive audit.

### When to use

- User asks "what's obviously missing", "what should I add next", "what's the weakest thing"
- After a full panel session, for follow-up grooming rounds
- When the stack has grown large and redundancy or noise has accumulated
- Periodically, as a lightweight check between full panel sessions

### Recommendation dimensions

1. **Add** — one substance with the highest evidence-to-impact ratio for this specific user profile, not ranked against a generic population
2. **Remove** — the weakest link: weakest evidence for this profile, most redundant, or risk/benefit unfavorable given what's already active
3. **Replace** — optional product-level recommendation: review active products one by one and identify products that should clearly be replaced by a better product or product class

The panel must reach consensus on add/remove. Replacement recommendations are stricter: include them only when the reason is obvious from the product, component, form, dose, tolerance, safety, or evidence context. Do not recommend a replacement just because an alternative exists.

Useful replacement signals:
- a desired role is valid, but the current product form is meaningfully worse for tolerance, safety, absorption, or evidence than a common alternative;
- the product carries the intended role weakly or incidentally while another product class would cover it directly;
- the product adds avoidable side-risk, redundancy, or label ambiguity while preserving the same intended benefit is easy.

Examples:
- unbuffered vitamin C / ascorbic acid may merit replacement with a buffered vitamin C form when stomach tolerance is a concrete concern;
- no replacement should be suggested when the current product is adequate and the improvement would be speculative or marginal.

If consensus is impossible, surface the conflict explicitly and ask the user to resolve it.

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
- Explicit instruction: recommend add/remove, and include product replacement only when clearly justified

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
- Product replacement recommendations only where the replacement is obvious and evidence-backed; otherwise state that no clear replacement is needed
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
