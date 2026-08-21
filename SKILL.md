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

- Read-only orientation: `uv run python -m planner find "<query>"`, `uv run python -m planner review`, and `uv run python -m planner groom`.
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

`find`, `review`, and `groom` are read-only. The bare planner command regenerates `schedule.yaml`; `check` performs deterministic normalization/maintenance and then validates the source data. Inspect `git status --short` and `git diff` after either command.

### Add, change, or groom cards

The normative lifecycle, event playbooks, fact routing, evidence boundary, and
acceptance checklist live in
[docs/agent-product-flow.md#authoritative-card-lifecycle](docs/agent-product-flow.md#authoritative-card-lifecycle).
Use that workflow for new Products, new Substances/forms, and existing-card
grooming; this skill is only the quick operator surface.

Quick rules:

- Grooming is card-level work. Run `uv run python -m planner groom`; it returns
  one deterministic active-reachable whole-card dossier. Luna collects all card
  evidence, Sol adjudicates, and Luna implements; run the targeted check or
  recomputation against actual output, then rerun `groom` for the next card.
  Cards remain atomic; relations have one deterministic owner.
  Assertion-level `research_state` and `sources` are internal provenance, not
  queue tasks or public filters. `searched_insufficient` is a valid completion.

- Search first with `uv run python -m planner find "<product substance form alias>"`;
  reuse matching Product/Substance/form identities and do not use grep/glob as
  the identity check.
- Draft from [schema/templates/](schema/templates/), keep
  `Product.name` concise and bottle-facing, preserve exact label forms and
  amounts in their component fields, and let `planner check` assign stable IDs
  and normalize `sub_*` references.
- Before changing Substance traits, use the generated vocabulary checklist and
  [docs/domain-model.md#trait-ontology](docs/domain-model.md#trait-ontology).
- Keep `schedule.*` for admitted executable meal/time/activity facts;
  `knowledge.*` for reusable reviewer knowledge; relations in
  [data/relations.yaml](data/relations.yaml); dashboards for review surfaces;
  and concerns for bounded prose with no better home.
- For a new active Substance, perform the bounded evidence attempt and the
  [mandatory completion handoff](docs/agent-product-flow.md#mandatory-completion-handoff);
  retain `unassessed`/`insufficient` states because unavailable evidence does
  not block card creation. Validate with `uv run python -m planner check`, then
  run only the relevant bounded planner/review commands for the changed
  surface.

### Update Stacks

Edit only stack membership in [data/stacks.yaml](data/stacks.yaml). Allowed stacks are `daily`, `training`, and `inactive`.

Use `daily` for ordinary recurring products. Use `training` for workout-adjacent products. Products with `activity:*` substances usually belong in `training`, where those traits prefer the workout slots.

Run `uv run python -m planner`, then `uv run python -m planner review`.

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
8. Run `uv run python -m planner review` for concise active-stack health,
   concerns, relations, active fact memberships, and dashboard coverage.
9. Run `just verify` (or the relevant bounded `just unit-target <path>` recipe) to confirm tests still pass.

Semantic projection rules live in [docs/domain-model.md#core-objects](docs/domain-model.md#core-objects). A single cluster may have both `benefit` and `risk` sections; do not split one member set into two files.

## YAML Shapes

Use [schema/templates/](schema/templates/) as the copy source for new cards and [ontology/generated/](ontology/generated/) as the machine-checked field contract. Do not duplicate YAML shape examples in this skill; if a template and generated schema disagree, fix the ontology source and regenerate artifacts, then update [docs/domain-model.md](docs/domain-model.md) only when the semantic model changed.

## Validation Contract

Use the validation path that matches the edit:

- Narrow data-only edits: run `uv run python -m planner check`, then inspect `git status --short` and `git diff`.
- Review-surface edits (concerns, relations, risks, pathways, dashboards, active stack membership): run `uv run python -m planner check`, `uv run python -m planner review`, and usually `uv run python -m planner`.
- Planner, ontology, or tests changed: run the bare planner command, `review`,
  `just check`, then inspect `git status --short` and `git diff`.

Run `uv run python -m planner --help` to see the command list and workflow hints.

Reference-integrity errors (hard — from `planner check`, exit non-zero):
- Unknown trait `{slug}` under namespace `{namespace}:` in `substances/<file>.yaml` — the slug is not registered in the canonical ontology vocabulary under that namespace. Fix: add the term to [ontology/vocabulary.yaml](ontology/vocabulary.yaml), regenerate ontology artifacts, and then use it.
- Unknown review context `{slug}` in a substance card or dashboard `selectors` — the term is not registered in the canonical ontology vocabulary. Fix: add or correct the canonical `context` term; a dashboard declaration is optional presentation/grouping and is not required unless a specific check says otherwise.
- Unknown trait `{slug}` under a trait-backed namespace in `selectors` of `dashboards/<file>.yaml` — the slug is not registered in the canonical ontology vocabulary. Fix: register it in [ontology/vocabulary.yaml](ontology/vocabulary.yaml), regenerate ontology artifacts, or correct the slug.

Advisory output is split between two commands:
- `planner review` — starts with a short `Review brief`, then concerns grouped by annotation kind (safety / data_quality / model_gap); typed relation outcomes grouped by endpoint presence (`both_active`, `missing_source`, `missing_target`, and `neither_active`) with optional warning tags; active knowledge facts across `context`, `effect`, `kind`, `role`, and `quality`; and a dashboard summary.
Hard errors (`check`) block downstream commands. `review` is advisory and
informational; it does not block commits.

## Membership Flow

The full dashboard membership contract lives in [docs/domain-model.md#core-objects](docs/domain-model.md#core-objects) and [docs/domain-model.md#scheduling-semantics](docs/domain-model.md#scheduling-semantics). Operational shortcut:

- Use `uv run python -m planner review` for active-stack membership and dashboard
  surfaces.
- Add the reusable fact a dashboard projects from (`kind:`, `effect:`, `risk:`, or `pathway:`); use `context:` only for explicit curated membership with no cleaner axis.
- Read `schedule.yaml` `benefits[].members` / `risks[].members` as neutral membership state, not as expert gap or adequacy judgment.

## Review Warning Playbook

WHEN to run `uv run python -m planner review`:
- After substance edits that change concerns, risks, pathways, dashboard membership, or relation context
- After stack changes (adding/removing/moving a product)
- Before commit when review-surface data changed

Concerns are rendered by annotation kind only (`safety`, `model_gap`, and `data_quality`); concern entries do not carry stack-state labels. Use the product/substance identity and the surrounding stack/dashboard state to decide whether a concern is relevant now. Do not delete knowledge-only cards or inactive product concerns merely because they are not active.

Note: `review` produces advisory output (soft — exit 0). It does NOT block commits.

## Command Behavior

- `check` validates the whole repository and may auto-fix deterministic maintenance, such as missing stable IDs or product/substance filenames.
- `find` is read-only lookup. If schema validation fails, fix with `check` or direct edits before searching again.
- Schemas are the source of truth for allowed fields. Do not infer support for old substance-card `relations` from stale examples or code comments; all current substance-to-substance links belong in [data/relations.yaml](data/relations.yaml).
- The bare planner command runs the scheduler after validation, rewrites [schedule.yaml](schedule.yaml), and prints a compact pillbox view.
- Do not edit [schedule.yaml](schedule.yaml) directly; regenerate it with `uv run python -m planner`. Its structure is documented in [docs/domain-model.md#scheduling-semantics](docs/domain-model.md#scheduling-semantics).
- Read `substances.similar_names` as a potential-duplicate review surface, not a duplicate list. A cluster means "check whether this new/edited substance should reuse an existing form, add an alias, or remain a distinct concrete form."
- `check` and the default command may auto-fix deterministic source maintenance. After running them, inspect `git status --short` and `git diff` when source-data changes need review separately from generated `schedule.yaml`.

## Stack Grooming And Review

Full stack review and optimization workflows live in [docs/agent-stack-review.md](docs/agent-stack-review.md).

Start reviews from existing surfaces instead of building ad hoc aggregators:

```bash
uv run python -m planner review
uv run python -m planner
```

Use `planner review` first: its concise active-stack health output is the review intake surface. Use `schedule.yaml` for slot placement.

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
