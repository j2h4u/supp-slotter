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
- [docs/agent-stack-review.md](docs/agent-stack-review.md) is the stack review and optimization workflow.
- [docs/ontology-facts.md](docs/ontology-facts.md) keeps current unresolved ontology pressure points only.
- [README.md](README.md) is the human-facing project overview.
- [planner/](planner/) is the CLI/runtime entrypoint package; run `uv run python -m planner --help` to see available commands.
- [ontology/generated/](ontology/generated/) contains the machine-checked schemas; [schema/templates/](schema/templates/) contains copy-ready YAML templates.
- [tests/](tests/) contains regression coverage for data shape, validation, and scheduling.

Progressive disclosure: use [README.md](README.md) for project orientation, [docs/domain-model.md](docs/domain-model.md) for semantics and ownership rules, [schema/templates/](schema/templates/) for copy-ready YAML shapes, and this skill for operational workflow.

## Edit Targets

- Product cards: [data/products/](data/products/)
- Substance cards: [data/substances/](data/substances/)
- Substance relations: [data/relations.yaml](data/relations.yaml)
- Stack membership: [data/stacks.yaml](data/stacks.yaml)
- Dashboard clusters: [data/dashboards/](data/dashboards/)
- Ontology vocabulary and policies: [ontology/vocabulary.yaml](ontology/vocabulary.yaml), [ontology/policies.yaml](ontology/policies.yaml)
- Pillboxes and slots: [data/pillboxes.yaml](data/pillboxes.yaml)

## Mode Selector

- Read-only orientation: `uv run python -m planner --help`, `uv run python -m planner review`, `uv run python -m planner audit`, `uv run python -m planner find "<query>"`, and `uv run python -m planner review-substance --help`.
- Generated-output refresh: `uv run python -m planner` rewrites `schedule.yaml`; this is expected and does not change source data.
- Source validation and deterministic maintenance: `uv run python -m planner check` may fill missing stable IDs or normalize product/substance filenames.
- Source-data edits: changes under `data/`, `schema/`, `planner/`, `tests/`, or tracked docs require the validation path below.

## Working Rule

Before changing domain data, read [docs/domain-model.md](docs/domain-model.md) unless the edit is obviously mechanical. Treat it as authoritative for object ownership, IDs, filenames, trait ontology, and non-goals.

Keep the model small. Do not add regimen, journal, dose engine, evidence grading, or future-facing ontology unless the user explicitly asks and the checker/planner needs it now.

This is a self-owned product. Do not preserve old command aliases, schemas, docs, tests, or code paths solely because they existed before; keep old-version support only when the user explicitly asks for it or there is a current product reason.

## Product Operating Protocol

Full guided product workflow lives in [docs/agent-product-flow.md](docs/agent-product-flow.md). Keep this file as the quick operator surface.

Core loop:

```text
user concerns -> concern clusters -> axes to cover -> minimal stack proposal -> schedule/warnings -> next iteration
```

Rules that matter most:

- Start from goals, constraints, medications, labs, and safety context before touching cards.
- Save user-reported personal context only under gitignored [docs/private/](docs/private/).
- For recommendation/proposal work, pick reusable axes before products: `kind:`, `effect:`, `risk:`, `pathway:`, relations, or dashboard selectors.
- For product ingestion, start from the physical label first: product, components, labels/forms, then reusable substance facts.
- Enrich cards opportunistically when real product work reveals missing substances, forms, mechanisms, cofactors, risks, relations, URLs, or amounts that matter for the current task.
- Keep knowledge-only substance cards when they contain reusable knowledge.
- Propose small staged changes by default; do not edit stack data without explicit approval.

## Onboard A New Stack

Use [docs/agent-product-flow.md#onboard-a-new-stack](docs/agent-product-flow.md#onboard-a-new-stack). Short version for another user's own stack: treat existing substance cards as a reusable catalog; move current active product IDs from `daily` and `training` to `inactive` unless the user explicitly wants to extend the original stack; create one physical-product card per new product; search/reuse concrete substance cards before creating new ones; draft components with exact substance name/form, alias, filename stem, or `sub_*`; place only the new user's products into `daily`, `training`, or `inactive`; leave unknown planner facts empty instead of guessing; run `uv run python -m planner check` to normalize component refs to `sub_*`, then regenerate and review after at least one active product exists.

## Common Workflows

`find`, `review`, `review-substance`, and `audit` are read-only. The default command regenerates `schedule.yaml`; that is expected disposable output, not a source-data edit. `check` and the default command may also write deterministic source maintenance changes such as missing stable IDs or normalized filenames. Inspect `git status --short` and `git diff` when you need to distinguish generated output from source-data changes.

### Add Or Enrich A Product

1. Search existing products and substances first with `uv run python -m planner find "<name form brand>"`. It is read-only, accepts multiple words, does fuzzy partial matching, and searches card text, filenames, IDs, aliases, brands, forms, and URLs.
2. Create or update missing concrete substances before linking product components.
3. Product `components[].substance` is canonical as a `sub_*` ID. During drafting, it may use an exact substance name+form, alias, or filename stem; `uv run python -m planner check` rewrites unique matches to `sub_*` and fails on unknown or ambiguous names.
4. For a new product: copy [schema/templates/product.yaml](schema/templates/product.yaml) to `data/products/<slug>.yaml`. The template has all fields with inline comments explaining conventions. Fill all applicable fields. Do not add fields outside [ontology/generated/product.schema.json](ontology/generated/product.schema.json).
   Keep `Product.name` as a concise bottle-facing/commercial title. Do not append chemical form, dose/strength, package count, or ontology qualifiers merely for completeness; route form to `substance.form`/`component.label`, dose to `component.amount`, package count to product `notes`, and semantics to substance `knowledge`/notes. Preserve genuine commercial names that inherently contain a form term.
5. If the label gives a mineral salt/form, preserve the exact label form in component `label` or `notes`. Link a concrete form card only when that form affects review or scheduling; otherwise link the generic element card.
6. Leave excipients, flavor systems, proprietary blends, and non-specific label lines in product `notes` unless they need scheduler, dashboard, relation, or reusable review behavior.
7. Edit the product card and stacks as needed, following [docs/domain-model.md](docs/domain-model.md).
8. Run `uv run python -m planner`, then `uv run python -m planner review` (advisory). Run `uv run python -m planner audit --full` when the generic full-audit diagnostics are relevant to the current task.

### Add Or Enrich A Substance

1. **Always** search before creating: `uv run python -m planner find "<name form alias>"`. This read-only command does fuzzy matching across names, forms, aliases, IDs, and notes. Do NOT use grep, glob, or `ls` as the first check for whether a substance exists — these miss aliases and alternate spellings. If `find` returns no results, there is no indexed match; inspect likely cards when form, alias, or spelling ambiguity remains.
2. Before filling or changing traits on an existing substance, run `uv run python -m planner review-substance data/substances/<card>.yaml`. Read the grouped checklist from the canonical ontology vocabulary, not from memory. Use `--compact` only for a quick current-state scan; full output is the editing checklist. The vocabulary is grouped by namespace (`kind`, `role`, `quality`, `effect`, `risk`, `pathway`, and scheduling axes); `context` membership is resolved through dashboard `selectors:`. The planner's active-fact review projection currently includes only `context`, `effect`, `kind`, `role`, and `quality`; authored `risk` and `pathway` facts remain reviewer-only data. Substance cards store traits in nested `schedule:` / `knowledge:` sections. The command shows namespace headings once, short trait names under them, and the descriptions/application rules from ontology artifacts. Use it for traits and `concerns`; add substance-to-substance links separately in [data/relations.yaml](data/relations.yaml).
3. For a new substance: copy [schema/templates/substance.yaml](schema/templates/substance.yaml) to `data/substances/<slug>.yaml` — use only lowercase letters, digits, and underscores; no `sub_*` ID in the filename. Do NOT generate or invent an ID. The template has all fields with inline comments explaining conventions. At minimum fill `name`; fill all other applicable fields before saving. Run `uv run python -m planner check` — it assigns a stable ID and renames the file to `<slug>__sub_<id>.yaml` automatically. Use `git status --short` or `uv run python -m planner find "<name form>"` to get the renamed path, then run `uv run python -m planner review-substance data/substances/<new-card>.yaml` before adding traits.
4. Reuse existing concrete forms when they match; use aliases for spelling variants.
5. Prefer concrete `name + form` cards when the source gives the form. A no-`form` card is only a temporary unknown-form placeholder when the source does not disclose the form.
6. Do not create parent taxonomy cards such as generic `Magnesium` just because several forms exist. Use `planner audit` > Potential duplicate substance cards to review nearby forms before adding a new card.
7. Add traits only when they affect current slot timing or express a reusable reviewer fact: intrinsic class, pharmacological effect, authored risk/pathway fact, or dashboard projection. See [ontology/vocabulary.yaml](ontology/vocabulary.yaml) for the canonical namespace vocabulary. Run `uv run python -m planner review-substance data/substances/<card>.yaml` to inspect a card's current tags grouped by namespace before adding or changing tags.

   When the new substance is used by an active product, make a bounded,
   independent evidence-enrichment attempt after capturing the label facts and
   identity/form. Search the scheduling axes that apply (meal state, clock/day
   phase, and activity) plus important interaction/review context. Prefer
   authoritative, systematic, or human evidence; manufacturer directions are
   formulation evidence or leads, not sufficient general scheduling evidence.
   Admit a `schedule:` fact only after adjudication at the project's
   conservative threshold. If research finds no defensible rule, record the
   per-axis `scheduling_assessment` conclusion `insufficient` with sources and
   a concise summary; if evidence supports no rule, record
   `supports_no_rule`. If an axis was not researched, omit it as unassessed.
   Never describe an omitted or unsupported axis as an optimal slot: planner
   balance placement is technical only.
   Unavailable evidence does not block creating the card or product, but its
   `insufficient`/unassessed state must remain visible for grooming. This
   workflow does not add dose, owner/reviewer/lifecycle, automatic-task, or
   vendor-precedence machinery.

   Namespace rule of thumb: if a slug affects slot assignment, put it under `schedule:`; otherwise put it under `knowledge:`. Use `kind:` for intrinsic classification and `context:` only for curated dashboard membership. For exact namespace semantics and cardinality, use [docs/domain-model.md#trait-ontology](docs/domain-model.md#trait-ontology).
8. Avoid new `knowledge.effect` slugs ending in `_context` by default. Use `knowledge.context` for curated dashboard membership, `knowledge.risk` for safety or interaction flags, `knowledge.pathway` for biochemical routes, and precise effect names such as `*_support`, `*_inhibition`, `*_modulation`, or `*_cofactor` for reusable substance-level facts.
9. Treat broad effect axes as reviewer selectors only. Do not use broad axes such as `bone_mineral_metabolism_support` as relation endpoints without first narrowing the model. Do not create an effect merely to duplicate an existing dashboard/context projection.
10. Put all substance-to-substance relations in [data/relations.yaml](data/relations.yaml), never in substance cards. The file is grouped by ontology relation type: `balance`, `supports`, and `review_with`.
11. Choose one canonical selector shape for each relation endpoint:
   - `{entity: {entity_id: sub_XXXXXXXXXX}}` targets one concrete substance card.
   - `{entity: {name: Zinc}}` targets substances whose exact authored `name` is `Zinc`.
   - `{category: effect, term: pde5_inhibition}` targets every substance carrying that registered ontology term. Use category selectors only when future members should inherit the relation. `planner review` shows concrete active endpoint matches.
   Slot-blocking rules belong in ontology scheduling constraints, not `data/relations.yaml`.
   Do not add mirrors; relation directionality is declared in `ontology/relations.yaml` and consumed through generated ontology artifacts.
12. Add relation `action` only when the source gives a concrete review action; otherwise let the planner use the default wording.
    Add `severity` (`critical`, `high`, `medium`, `low`) only when the operator needs a review priority above baseline. Leave it unset for routine entries — the planner uses default warning wording when severity is absent.
13. Run `uv run python -m planner check`. Run `uv run python -m planner review` when concerns, relations, dashboards, or active stack membership changed. Run `uv run python -m planner audit` when structural diagnostics matter. Run `uv run python -m planner` when traits, relations, dashboard clusters, `prefer_with`, or active-product substances changed.

### Update Stacks

Edit only stack membership in [data/stacks.yaml](data/stacks.yaml). Allowed stacks are `daily`, `training`, and `inactive`.

Use `daily` for ordinary recurring products. Use `training` for workout-adjacent products. Products with `activity:*` substances usually belong in `training`, where those traits prefer the workout slots.

Run `uv run python -m planner`, then `uv run python -m planner review` and `uv run python -m planner audit`.

### Add Or Update A Dashboard

Dashboard clusters use typed `selectors:` membership rules. Prefer building dashboard membership from reusable semantic axes already present on substances, rather than adding a dashboard-specific tag to each substance.

Recommended sequence:
1. Decide which semantic fact defines membership: `kind:`, `effect:`, `risk:`, or `pathway:`.
2. If the fact is real and reusable, add or refine the trait/effect/risk/pathway on substance cards first.
3. Create `data/dashboards/<slug>.yaml` with `name`, `description`, `benefit`/`risk`, and `selectors:` entries such as `- {category: effect, term: <slug>}`.
4. Use `- {category: context, term: <slug>}` only when the membership is genuinely curated and cannot be expressed through a cleaner reusable axis.
5. Write the description to name the dashboard scope: candidate-comparison surface, cumulative load surface, or interaction-review surface.
6. Run `uv run python -m planner check` to validate reference integrity (hard FK errors).
7. Run `uv run python -m planner` to regenerate `schedule.yaml`.
8. Run `uv run python -m planner review` for concerns, typed relation outcomes, active fact memberships, and dashboard coverage (advisory, exit 0). Authored `risk` and `pathway` facts are not rendered as active planner-review sections. Run `uv run python -m planner audit` for diagnostics.
9. Run `just verify` (or the relevant bounded `just unit-target <path>` recipe) to confirm tests still pass.

Semantic projection rules live in [docs/domain-model.md#core-objects](docs/domain-model.md#core-objects). A single cluster may have both `benefit` and `risk` sections; do not split one member set into two files.

## YAML Shapes

Use [schema/templates/](schema/templates/) as the copy source for new cards and [ontology/generated/](ontology/generated/) as the machine-checked field contract. Do not duplicate YAML shape examples in this skill; if a template and generated schema disagree, fix the ontology source and regenerate artifacts, then update [docs/domain-model.md](docs/domain-model.md) only when the semantic model changed.

## Validation Contract

Use the validation path that matches the edit:

- Narrow data-only edits: run `uv run python -m planner check`, then inspect `git status --short` and `git diff`.
- Review-surface edits (concerns, relations, risks, pathways, dashboards, active stack membership): run `uv run python -m planner check`, `uv run python -m planner review`, and usually `uv run python -m planner`.
- Structural diagnostics: run `uv run python -m planner audit` when traits, dashboards, duplicate risk, empty stacks, or stack/pillbox alignment may be affected.
- Full-audit diagnostics: run `uv run python -m planner audit --full` when its generic diagnostics are relevant to the current task.
- Planner, ontology, or tests changed: `uv run python -m planner`, `uv run python -m planner review`, `uv run python -m planner audit --full`, `just check`, then `git status --short` and `git diff`.

Run `uv run python -m planner --help` to see the command list and workflow hints.

Reference-integrity errors (hard — from `planner check`, exit non-zero):
- Unknown trait `{slug}` under namespace `{namespace}:` in `substances/<file>.yaml` — the slug is not registered in the canonical ontology vocabulary under that namespace. Fix: add the term to [ontology/vocabulary.yaml](ontology/vocabulary.yaml), regenerate ontology artifacts, and then use it.
- Unknown review context `{slug}` in a substance card or dashboard `selectors` — the term is not registered in the canonical ontology vocabulary. Fix: add or correct the canonical `context` term; a dashboard declaration is optional presentation/grouping and is not required unless a specific check says otherwise.
- Unknown trait `{slug}` under a trait-backed namespace in `selectors` of `dashboards/<file>.yaml` — the slug is not registered in the canonical ontology vocabulary. Fix: register it in [ontology/vocabulary.yaml](ontology/vocabulary.yaml), regenerate ontology artifacts, or correct the slug.

Advisory output is split between two commands:
- `planner review` — starts with a short `Review brief`, then concerns grouped by annotation kind (safety / data_quality / model_gap); typed relation outcomes grouped by endpoint presence (`both_active`, `missing_source`, `missing_target`, and `neither_active`) with optional warning tags; active knowledge facts across `context`, `effect`, `kind`, `role`, and `quality`; and a dashboard summary.
- `planner audit` — diagnostics (valid knowledge-only substance cards, products outside stacks, unused traits, potential duplicate cards, empty clusters); `--full` adds generic diagnostics from the same read model.

Advisory cleanup warnings (soft — from `planner audit`, exit 0):
- `dashboard.empty_cluster` — dashboard `selectors` resolve to zero member substances.

Hard errors (`check`) block all downstream commands. Advisory output (`review` and `audit`) reports state for operator attention but does not block.

## Membership Flow

The full dashboard membership contract lives in [docs/domain-model.md#core-objects](docs/domain-model.md#core-objects) and [docs/domain-model.md#scheduling-semantics](docs/domain-model.md#scheduling-semantics). Operational shortcut:

- Use `uv run python -m planner review-substance data/substances/<card>.yaml` to inspect computed membership for one substance.
- Add the reusable fact a dashboard projects from (`kind:`, `effect:`, `risk:`, or `pathway:`); use `context:` only for explicit curated membership with no cleaner axis.
- Read `schedule.yaml` `benefits[].members` / `risks[].members` as neutral membership state, not as expert gap or adequacy judgment.

## Review Warning Playbook

WHEN to run `uv run python -m planner review`:
- After substance edits that change concerns, risks, pathways, dashboard membership, or relation context
- After stack changes (adding/removing/moving a product)
- Before commit when review-surface data changed

Concerns are rendered by annotation kind only (`safety`, `model_gap`, and `data_quality`); concern entries do not carry stack-state labels. Use the product/substance identity and the surrounding stack/dashboard state to decide whether a concern is relevant now. Do not delete knowledge-only cards or inactive product concerns merely because they are not active.

Note: `review` produces advisory output (soft — exit 0). It does NOT block commits.

## Audit Warning Playbook

WHEN to run `uv run python -m planner audit`:
- After substance edits that change traits, `context:` tags, or `kind:` tags
- After any dashboard yaml edit (`selectors` changes, new cluster created)
- After any ontology vocabulary change (trait-backed namespace entry, renamed slug)
- Once at end of session before commit when structural review surfaces changed

Use `uv run python -m planner audit --full` when the generic full-audit diagnostics are relevant to the task.

Note: `audit` produces diagnostic output (soft — exit 0). Concerns, relations, active fact memberships, and dashboards are in `planner review`; authored `risk` and `pathway` facts are not active planner-review output. For HARD reference-integrity errors that block commits, use `planner check`.

Per-warning-class resolution:

**`dashboard.empty_cluster`**
Message format: `Empty cluster: data/dashboards/{slug}.yaml selectors resolve to zero member substances (using union resolution: OR across all listed (category, term) pairs). Resolution: add the underlying authored fact, or remove the dashboard yaml if abandoned. (If this is an intentional placeholder, add a notes: field explaining the intent.)`
Causes: all matching facts were removed; or `selectors` terms do not match any substance's namespace fields under the canonical OR-across-namespaces resolution rule.
Resolution: first check whether the dashboard should project from a semantic axis (`kind:`, `effect:`, `risk:`, `pathway:`) and add/fix that underlying fact on substance cards. Use `context: <slug>` tagging only for explicit operator-curated clusters. Remove the dashboard yaml if the cluster is abandoned. If the cluster is an intentional placeholder for future use, add a `notes:` field explaining the intent.

## Command Behavior

- `check` validates the whole repository and may auto-fix deterministic maintenance, such as missing stable IDs or product/substance filenames.
- `find` is read-only lookup. If schema validation fails, fix with `check` or direct edits before searching again.
- Schemas are the source of truth for allowed fields. Do not infer support for old substance-card `relations` from stale examples or code comments; all current substance-to-substance links belong in [data/relations.yaml](data/relations.yaml).
- The default command runs the scheduler after validation, rewrites [schedule.yaml](schedule.yaml) as expected generated output, and prints a compact pillbox view.
- Do not edit [schedule.yaml](schedule.yaml) directly; regenerate it with `uv run python -m planner`. Its structure is documented in [docs/domain-model.md#scheduling-semantics](docs/domain-model.md#scheduling-semantics).
- `audit` reports diagnostics — valid knowledge-only substance cards, products outside stacks, unused traits, potential duplicate cards, empty stacks, stack/pillbox mismatches. It is a review surface, not a validator or automatic todo list.
- Read `substances.similar_names` as a potential-duplicate review surface, not a duplicate list. A cluster means "check whether this new/edited substance should reuse an existing form, add an alias, or remain a distinct concrete form."
- `check` and the default command may auto-fix deterministic source maintenance. After running them, inspect `git status --short` and `git diff` when source-data changes need review separately from generated `schedule.yaml`.

## Stack Grooming And Review

Full stack review and optimization workflows live in [docs/agent-stack-review.md](docs/agent-stack-review.md).

Start reviews from existing surfaces instead of building ad hoc aggregators:

```bash
uv run python -m planner review
uv run python -m planner
```

Use `planner review` first: its `Review brief` is the review intake surface. Use `schedule.yaml` for slot placement. Use `audit --full` only when the generic full-audit diagnostics matter for the review.

Default report is a **General Narrative Report**: short TL;DR first, then plain-language review-group interpretation. Expand non-obvious abbreviations on first mention. Produce a technical findings report only when the user asks for that format.

Review output is advisory and informational, not medical advice. Do not modify stack data without explicit user confirmation.

---

## When To Ask The User

Ask before inventing facts that are not on the label or already in the repo:

- uncertain ingredient form, for example B6 `pyridoxine HCl` vs `pyridoxal 5 phosphate`;
- unclear brand/vendor;
- uncertain component amount after checking existing URLs and doing a targeted source search, when that amount matters for the current task;
- missing product source/label for component facts or URLs after a targeted source search fails;
- whether a product is actually on the shelf or only a reference candidate;
- adding new trait axes or ontology categories.

Do not ask for deterministic maintenance such as stable ID generation or filename normalization. Run the checker, let it auto-fix when possible, then inspect `git status --short` and `git diff`.
