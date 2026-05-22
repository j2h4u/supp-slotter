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
- [docs/agent-product-flow.md](docs/agent-product-flow.md) is the guided intake, proposal, private-context, and onboarding workflow.
- [docs/agent-stack-review.md](docs/agent-stack-review.md) is the expert-panel and stack-optimization workflow.
- [docs/effects-semantic-audit.md](docs/effects-semantic-audit.md) captures the current `effect:` boundary and cleanup status.
- [docs/ontology-facts.md](docs/ontology-facts.md) stress-tests how supplement facts fit the ontology.
- [README.md](README.md) is the human-facing project overview.
- [planner/](planner/) is the CLI/runtime entrypoint package; run `python -m planner --help` to see available commands.
- [schema/](schema/) contains the machine-checked YAML schemas.
- [tests/](tests/) contains regression coverage for data shape, validation, and scheduling.

Progressive disclosure: use [README.md](README.md) for project orientation, [docs/domain-model.md](docs/domain-model.md) for semantics and ownership rules, [schema/templates/](schema/templates/) for YAML shapes, and this skill for operational workflow.

## Edit Targets

- Product cards: [data/products/](data/products/)
- Substance cards: [data/substances/](data/substances/)
- Substance relations: [data/relations.yaml](data/relations.yaml)
- Stack membership: [data/stacks.yaml](data/stacks.yaml)
- Dashboard clusters: [data/dashboards/](data/dashboards/)
- Trait rules: [data/traits/](data/traits/)
- Pillboxes and slots: [data/pillboxes.yaml](data/pillboxes.yaml)

## Working Rule

Before changing domain data, read [docs/domain-model.md](docs/domain-model.md) unless the edit is obviously mechanical. Treat it as authoritative for object ownership, IDs, filenames, trait ontology, and non-goals.

Keep the model small. Do not add regimen, journal, dose engine, evidence grading, or future-facing ontology unless the user explicitly asks and the checker/planner needs it now.

This is a self-owned product. Do not preserve old command aliases, schemas, docs, tests, or code paths solely because they existed before; keep compatibility only when the user explicitly asks for it or there is a current product reason.

## Product Operating Protocol

Full guided product workflow lives in [docs/agent-product-flow.md](docs/agent-product-flow.md). Keep this file as the quick operator surface.

Core loop:

```text
user concerns -> concern clusters -> axes to cover -> minimal stack proposal -> schedule/warnings -> next iteration
```

Rules that matter most:

- Start from goals, constraints, medications, labs, and safety context before touching cards.
- Save user-reported personal context only under gitignored [docs/private/](docs/private/).
- Pick reusable axes before products: `is:`, `effect:`, `risk:`, `pathway:`, relations, or dashboard projections.
- Enrich cards opportunistically when real product work reveals missing substances, forms, mechanisms, cofactors, risks, relations, URLs, or amounts.
- Keep knowledge-only substance cards when they contain reusable knowledge.
- Propose small staged changes by default; do not edit stack data without explicit approval.

## Onboard A New Stack

Use [docs/agent-product-flow.md#onboard-a-new-stack](docs/agent-product-flow.md#onboard-a-new-stack). Short version: do not mix a new user's stack into existing data unless explicitly asked; create one physical-product card per product; link concrete substance cards; place products into `daily`, `training`, or `inactive`; leave unknown planner facts empty instead of guessing; run `uv run python -m planner check`.

## Common Workflows

`find`, `review`, `review-substance`, and `audit` are read-only. `check` and the default command may write deterministic maintenance changes such as missing stable IDs or normalized filenames. Inspect `git status --short` and `git diff` after running commands that may write.

### Add Or Enrich A Product

1. Search existing products and substances first with `uv run python -m planner find "<name form brand>"`. It is read-only, accepts multiple words, does fuzzy partial matching, and searches card text, filenames, IDs, aliases, brands, forms, and URLs.
2. Create or update missing concrete substances before linking product components.
3. Product `components[].substance` must reference a `sub_*` id, not a name.
4. For a new product: copy [schema/templates/product.yaml](schema/templates/product.yaml) to `data/products/<slug>.yaml`. The template has all fields with inline comments explaining conventions. Fill all applicable fields. Do not add fields outside [schema/product.schema.json](schema/product.schema.json).
5. If the label gives a mineral salt/form, link the concrete form card, for example `Magnesium (citrate)` or `Sodium (chloride)`, not a generic mineral placeholder.
6. Leave excipients or non-specific blends in product `notes` unless they need scheduler/review behavior.
7. Edit the product card and stacks as needed, following [docs/domain-model.md](docs/domain-model.md).
8. Run `uv run python -m planner`, then `uv run python -m planner review` (advisory) and `uv run python -m planner audit --full` (product/source diagnostics).

### Add Or Enrich A Substance

1. **Always** search before creating: `uv run python -m planner find "<name form alias>"`. This read-only command does fuzzy matching across names, forms, aliases, IDs, and notes. Do NOT use grep, glob, or `ls` to check whether a substance exists — these miss aliases and alternate spellings. If `find` returns no results, the substance does not exist.
2. Before filling or changing traits on an existing substance, run `uv run python -m planner review-substance data/substances/<card>.yaml`. Read the grouped checklist from the live [data/traits/](data/traits/) registry, not from memory. Use `--compact` only for a quick current-state scan; full output is the editing checklist. The registry is grouped by namespace (`is`, `effect`, `intake`, `timing`, `risk`, `activity`, `pathway`); `context` membership is resolved through [data/dashboards/](data/dashboards/). Substance cards store traits in the v2 nested `schedule:` / `knowledge:` sections. The command shows namespace headings once, short trait names under them, and the trait descriptions/application rules from the registry. Use it for traits and `concerns`; add substance-to-substance links separately in [data/relations.yaml](data/relations.yaml).
3. For a new substance: copy [schema/templates/substance.yaml](schema/templates/substance.yaml) to `data/substances/<slug>.yaml` — use only lowercase letters, digits, and underscores; no `sub_*` ID in the filename. Do NOT generate or invent an ID. The template has all fields with inline comments explaining conventions. At minimum fill `name`; fill all other applicable fields before saving. Run `uv run python -m planner check` — it assigns a stable ID and renames the file to `<slug>__sub_<id>.yaml` automatically. Then run `uv run python -m planner review-substance data/substances/<new-card>.yaml` before adding traits.
4. Reuse existing concrete forms when they match; use aliases for spelling variants.
5. Prefer concrete `name + form` cards when the source gives the form. A no-`form` card is only a temporary unknown-form placeholder when the source does not disclose the form.
6. Do not create parent taxonomy cards such as generic `Magnesium` just because several forms exist. Use `planner audit` > Potential duplicate substance cards to review nearby forms before adding a new card.
7. Add traits only when they affect current slot timing or express a reusable reviewer fact: intrinsic class, pharmacological effect, risk flag, pathway, or dashboard projection. See [data/traits/](data/traits/) for the full namespace registry. Run `uv run python -m planner review-substance data/substances/<card>.yaml` to inspect a card's current tags grouped by namespace before adding or changing tags.

   Namespace rule of thumb: if a slug affects slot assignment, put it under `schedule:`; otherwise put it under `knowledge:`. For exact namespace semantics, cardinality, and `context:` boundaries, use [docs/domain-model.md#trait-ontology](docs/domain-model.md#trait-ontology).
8. Avoid new `knowledge.effect` slugs ending in `_context` by default. Use `knowledge.context` for curated dashboard membership, `knowledge.risk` for safety or interaction flags, `knowledge.pathway` for biochemical routes, and precise effect names such as `*_support`, `*_inhibition`, `*_modulation`, or `*_cofactor` for reusable substance-level facts.
9. Treat broad effect axes as reviewer selectors only. Do not use broad axes such as `glucose_metabolism_context`, `energy_production_support`, `bone_mineral_metabolism_support`, or `nerve_muscle_function` as relation endpoints without first narrowing the model.
10. Put all substance-to-substance relations in [data/relations.yaml](data/relations.yaml), never in substance cards. The file is grouped by relation type: `balance`, `competes`, `supports`, and `review_with`.
11. Choose relation endpoint fields by how broad each side is:
   - `source_name` / `target_name`: every form whose exact `name` field matches, for example all `Zinc` forms balancing `Copper`.
   - `source_substance` / `target_substance`: one concrete `sub_*` card.
   - `source_trait` / `target_trait`: every substance carrying a registered `namespace:slug`, only when the relation is genuinely category-level and future members should inherit it.
   - `source_class` / `target_class`: every substance carrying an `is:<slug>` class, only for broad `competes` rules that should affect slot blocking.
   - Mixed endpoints are valid when only one side is form-specific, for example `source_substance` for pyridoxine HCl and `target_name` for all `Levodopa` cards.
   Do not add mirrors; `balance` and `competes` are treated as symmetric by the planner, while `supports` and `review_with` are directional.
12. Add relation `action` only when the source gives a concrete review action; otherwise let the planner use the default wording.
    Add `severity` (`critical`, `high`, `medium`, `low`) only for clinically significant relations. Leave it unset for routine entries — the planner uses default warning wording when severity is absent.
13. Run `uv run python -m planner check`, then `uv run python -m planner review` (advisory: concerns, relations, risk flags, pathways) and `uv run python -m planner audit` (diagnostics). Run `uv run python -m planner` when traits, relations, dashboard clusters, `prefer_with`, or active-product substances changed.

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
4. Use `from_traits: { context: [<slug>] }` only when the membership is genuinely operator-curated and cannot be expressed through a cleaner reusable axis.
5. Run `uv run python -m planner check` to validate reference integrity (hard FK errors).
6. Run `uv run python -m planner` to regenerate `schedule.yaml`.
7. Run `uv run python -m planner review` for concerns, relations, risk flags, and pathways (advisory, exit 0). Run `uv run python -m planner audit` for diagnostics.
8. Run `uv run pytest` to confirm tests still pass.

Semantic projection rules live in [docs/domain-model.md#core-objects](docs/domain-model.md#core-objects). A single cluster may have both `benefit` and `risk` sections; do not split one member set into two files.

## YAML Shapes

Use [schema/templates/](schema/templates/) as the copy source for new cards and [schema/](schema/) as the machine-checked field contract. Do not duplicate YAML shape examples in this skill; if a template and prose disagree, fix the template or schema first, then update [docs/domain-model.md](docs/domain-model.md) only when the semantic model changed.

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
- `planner review` — starts with a short `Review brief`, then active-first concerns (safety / data_quality / model_gap), each labeled `[active]`, `[inactive]`, `[knowledge-only]`, or `[tracked-unassigned]`; relation review grouped as `actionable_now`, `active_pair_present`, `latent_one_side_present`, and `inactive`; risk flags (`knowledge.risk:` slugs on active substances); pathway memberships; dashboard summary.
- `planner audit` — diagnostics (valid knowledge-only substance cards, products outside stacks, unused traits, relation name fan-out, potential duplicate cards, empty clusters) and optional `--full` deep card quality checks, including active product source/amount gaps.

Advisory cleanup warnings (soft — from `planner audit`, exit 0):
- `dashboard.empty_cluster` — dashboard `from_traits` resolves to zero member substances.
- `relations.name_fanout` — a `source_name` or `target_name` endpoint resolves to multiple substance cards; keep it only when the all-form match is intentional, otherwise switch to a concrete `source_substance` or `target_substance`.
- `full.active_product_source` — active product cards missing source URLs, product notes, brand, or component amounts. Fix the product card from label/manufacturer sources, or add a `data_quality` concern if the amount is genuinely undisclosed.

Hard errors (`check`) block all downstream commands. Advisory output (`review` and `audit`) reports state for operator attention but does not block.

## Membership Flow

The full dashboard membership contract lives in [docs/domain-model.md#core-objects](docs/domain-model.md#core-objects) and [docs/domain-model.md#scheduling-semantics](docs/domain-model.md#scheduling-semantics). Operational shortcut:

- Use `uv run python -m planner review-substance data/substances/<card>.yaml` to inspect computed membership for one substance.
- Add the reusable fact a dashboard projects from (`is:`, `effect:`, `risk:`, or `pathway:`); use `context:` only for explicit curated membership with no cleaner axis.
- Read `schedule.yaml` `benefits[].members` / `risks[].members` as neutral membership state, not as expert gap or adequacy judgment.

## Review Warning Playbook

WHEN to run `uv run python -m planner review`:
- After any substance card edit
- After any stack change (adding/removing/moving a product)
- Before commit

The Risk flags section is the canonical surface for `knowledge.risk:` tags on active substances — agents MUST scan it for every active substance carrying a `risk:` tag. If a substance has `knowledge.risk: [manual_review]`, its name will appear under the `manual_review` group in the Risk flags section of `planner review` output.

Concern headings include membership labels. Treat `[active]` concerns as current-stack work first; `[inactive]` concerns as shelf/backlog verification; `[knowledge-only]` as reusable KB notes; and `[tracked-unassigned]` product concerns as data that is not currently assigned to a stack. Do not delete knowledge-only cards or inactive product concerns merely because they are not active.

Note: `review` produces advisory output (soft — exit 0). It does NOT block commits.

## Audit Warning Playbook

WHEN to run `uv run python -m planner audit`:
- After any substance card edit (traits, `context:` tags, `is:` tags)
- After any dashboard yaml edit (`from_traits` changes, new cluster created)
- After any `data/traits/` change (trait-backed namespace entry, renamed slug)
- Once at end of session before commit

Use `uv run python -m planner audit --full` after product-card edits or source-completion work; its first full-audit section is active product source and amount gaps.

Note: `audit` produces diagnostic output (soft — exit 0). Concerns, relations, risk flags, and pathways are in `planner review`. For HARD reference-integrity errors that block commits, use `planner check`.

Per-warning-class resolution:

**`dashboard.empty_cluster`**
Message format: `Empty cluster: data/dashboards/{slug}.yaml from_traits resolves to zero member substances (using union resolution: OR across all listed (namespace, slug) pairs). Resolution: tag substances under context: {slug}, OR remove the dashboard yaml if abandoned. (If this is an intentional placeholder, add a notes: field explaining the intent.)`
Causes: all tagged substances were removed; or `from_traits` slugs do not match any substance's namespace fields under the canonical OR-across-namespaces resolution rule.
Resolution: first check whether the dashboard should project from a semantic axis (`is:`, `effect:`, `risk:`, `pathway:`) and add/fix that underlying fact on substance cards. Use `context: <slug>` tagging only for explicit operator-curated clusters. Remove the dashboard yaml if the cluster is abandoned. If the cluster is an intentional placeholder for future use, add a `notes:` field explaining the intent.

## Command Behavior

- `check` validates the whole repository and may auto-fix deterministic maintenance, such as missing stable IDs or product/substance filenames.
- `find` is read-only lookup. If schema validation fails, fix with `check` or direct edits before searching again.
- Schemas are the source of truth for allowed fields. Do not infer support for old substance-card `relations` from stale examples or code comments; all current substance-to-substance links belong in [data/relations.yaml](data/relations.yaml).
- The default command runs the scheduler after validation, rewrites [schedule.yaml](schedule.yaml), and prints a compact pillbox view.
- Do not edit [schedule.yaml](schedule.yaml) directly; regenerate it with `uv run python -m planner`. Its structure is documented in [docs/domain-model.md#scheduling-semantics](docs/domain-model.md#scheduling-semantics).
- `audit` reports diagnostics — valid knowledge-only substance cards, products outside stacks, unused traits, potential duplicate cards, empty stacks, stack/pillbox mismatches. It is a review surface, not a validator or automatic todo list.
- Read `substances.similar_names` as a potential-duplicate review surface, not a duplicate list. A cluster means "check whether this new/edited substance should reuse an existing form, add an alias, or remain a distinct concrete form."
- `check` and the default command may auto-fix deterministic maintenance. After running them, inspect `git status --short` and `git diff` so auto-maintenance does not hide file changes.

## Stack Grooming With Expert Panel

Full expert-panel and optimization workflows live in [docs/agent-stack-review.md](docs/agent-stack-review.md).

Start reviews from existing surfaces instead of building ad hoc aggregators:

```bash
uv run python -m planner review
uv run python -m planner audit --full
uv run python -m planner
```

Use `planner review` first: its `Review brief` is the panel intake surface. Use `audit --full` for product/source/amount drilldown and `schedule.yaml` for slot placement.

Default report is a **General Narrative Report**: short TL;DR first, then plain-language expert-group interpretation. Expand non-obvious abbreviations on first mention. Produce a technical findings report only when the user asks for that format.

Expert panel output is advisory and informational, not medical advice. Do not modify stack data without explicit user confirmation.

---

## When To Ask The User

Ask before inventing facts that are not on the label or already in the repo:

- uncertain ingredient form, for example B6 `pyridoxine HCl` vs `pyridoxal 5 phosphate`;
- unclear brand/vendor;
- uncertain component amount after checking existing URLs and doing a targeted source search;
- missing product source/label for component facts or URLs after a targeted source search fails;
- whether a product is actually on the shelf or only a reference candidate;
- adding new trait axes or ontology categories.

Do not ask for deterministic maintenance such as stable ID generation or filename normalization. Run the checker, let it auto-fix when possible, then inspect `git status --short` and `git diff`.
