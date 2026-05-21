# Agent Product Flow

This document is the guided product workflow for agents using this repository with a real person. It is for structured supplement-stack thinking and data maintenance. It is not medical advice.

## Decision Loop

Treat the product as a guided decision loop, not as a YAML editor:

```text
user concerns -> concern clusters -> axes to cover -> minimal stack proposal -> schedule/warnings -> next iteration
```

Use this mode when the user asks how to improve a stack, what to add next, how to address health goals, or how another person should start using the system. Start with the person's goals and constraints before touching cards.

## Intake Before Data Edits

Ask one compact intake round before proposing supplements:

- top concerns or goals in plain language, not supplement names;
- already active supplements, prescription medications, and relevant procedures;
- constraints: budget, pill burden, frequency, tolerated forms, risk tolerance, and maximum new changes this round;
- available data: labs, diagnoses, clinician guidance, wearable metrics, or none yet;
- avoidances: bleeding risk, blood pressure concerns, glucose meds, surgery, pregnancy, allergies, or other safety constraints.

If the user gives health history, frame it as reported context and hypotheses. Do not diagnose, treat, or imply causality. For prescription medication, dose changes, serious symptoms, or high-risk interactions, mark the item as "discuss with physician" rather than an action.

## Private User Context

Persist user-reported personal context only under `docs/private/`. This directory is intentionally gitignored. Use it for intake notes, health history, symptoms, labs, medications, goals, constraints, expert-panel notes, candidate proposals, and decision rationale tied to a specific person.

Do not put user-specific health information into tracked docs, examples, data cards, dashboards, traits, or relations unless the user explicitly asks for that exact information to become tracked project data. Tracked YAML should contain reusable product/substance knowledge and approved stack membership, not private biography.

Recommended filenames:

- `docs/private/intake-YYYY-MM-DD.md` for the current user profile and goals;
- `docs/private/proposal-YYYY-MM-DD.md` for candidate stack proposals;
- `docs/private/expert-panel-YYYY-MM.md` for panel or optimization-session outputs.

Each private note should preserve reported facts, assumptions, uncertainties, concern clusters, axes considered, candidate changes, approved active changes, safety questions, lab/clinician follow-ups, and the next iteration agenda.

## Concern Clusters And Axes

Translate intake into 2-5 concern clusters. A concern cluster is a product-facing problem area, not a dashboard file by default.

Examples:

- vascular/endothelial support;
- fibrinolysis or clotting review;
- mitochondrial energy and lactate handling;
- lipid/cholesterol support;
- skin barrier/collagen/inflammation support;
- age-range prevention.

For each cluster, capture what the user said, what would make it safer or more measurable, and which claims should stay uncertain.

Pick axes before products. An axis is a reusable biological/review dimension that substances can cover: `is:`, `effect:`, `risk:`, `pathway:`, relation types in `data/relations.yaml`, or dashboard projections. Use `context:` only for explicit curated review membership when a cleaner reusable axis would over-include, under-include, or force an artificial trait.

Do not create a new axis just because it sounds product-friendly. Add or refine an axis only when it helps multiple cards, improves review output, or makes planner/audit behavior more accurate.

## Knowledge Growth

Guided product work should surface new substances, forms, mechanisms, cofactors, risks, relations, and candidate products. Treat this as normal knowledge-base growth, not scope creep.

When a new fact or candidate appears:

1. Search first with `uv run python -m planner find "<name form alias>"`.
2. Prefer enriching an existing concrete card when it already represents the substance/form.
3. Create a new substance card when a real substance/form is missing, even if it is not active.
4. Keep knowledge-only substance cards when they contain reusable knowledge.
5. Add reusable facts to tracked cards only when they are about the substance/product itself.
6. Put user-specific rationale, symptoms, hypotheses, and decision history in `docs/private/`.

Good enrichment targets: aliases, concrete forms, label-specific component notes, `knowledge.is:`, `effect:`, `risk:`, `pathway:`, scheduling facts that affect slot assignment, relations, product URLs, label notes, and component amounts.

Do not attempt one-shot full enrichment of the whole ontology. Enrich opportunistically as product work reveals a concrete need, then run validation.

## Minimal Stack Proposal

Prefer a small first proposal over broad coverage. Default limit: 1-3 new active changes for a cautious round, 3-5 only if the user explicitly accepts a larger change set.

Rank candidate additions by safety, relevance to concern clusters, evidence-to-impact ratio, overlap across multiple axes, cofactor/synergy support, low antagonism, low redundancy, and low pill burden.

Use existing active products first. If a useful substance is not on the shelf, treat it as a candidate and possible knowledge-base enrichment, not an automatic stack edit. Put it in `inactive` only when the user wants to track it in the repo.

Proposal structure:

```text
Concern -> Axis -> Current stack state -> Candidate change -> Why this is minimal -> Safety/review flags -> What to check next
```

Guardrails:

- Do not add 10-20 substances in one step.
- Do not optimize for maximum dashboard membership at the expense of safety, simplicity, or interpretability.
- Do not treat knowledge-only substance cards as cleanup trash.
- Do not convert product-facing concern clusters into dashboards unless the user wants persistent tracking and membership can be expressed cleanly.
- Do not edit stack data after a product intake/proposal unless the user explicitly approves the concrete changes.
- Always separate candidate to discuss/research from active stack change.

## Testing The Guided Protocol

Test the product protocol at three levels:

1. Private founder-user smoke: use the real first user while shaping the flow. Save reported health context under `docs/private/intake-YYYY-MM-DD.md`, generate a proposal under `docs/private/proposal-YYYY-MM-DD.md`, and confirm `git status --short` does not show those files.
2. Skill-behavior regression: use synthetic personas only for shareable, non-private regression examples or future automated checks.
3. Repo behavior test: after approved stack/card edits, run the normal validation contract.

A passing guided-protocol test keeps user-reported facts labeled and private, separates concern clusters from dashboards, makes axes explicit, limits candidate changes, shows safety/lab follow-ups, and makes no active stack change without explicit approval.

## Onboard A New Stack

Use this when a user cloned or forked the repository for their own supplements. Assume current files in `data/` may describe the original owner's real stack, not neutral sample data. Do not mix a new user's stack into existing data unless explicitly asked.

Start with one short onboarding pass:

- Ask whether the user wants to replace current data, extend it, or keep it only as reference.
- Ask for the product list: brand, product name, source URL, and label photo/text when available.
- Ask where each product belongs: `daily`, `training`, or `inactive`.
- Ask whether dashboards should be created now or skipped until the first schedule exists.
- Ask whether web research is allowed. Prefer official product pages, labels, or store pages, and save useful sources in product `urls`.
- Ask about user-specific constraints that should become review warnings. Do not make medical decisions.

For a clean start, keep project infrastructure and clear only user-specific stack data after explicit confirmation. Keep `planner/`, `schema/`, `tests/`, `docs/`, `SKILL.md`, `README.md`, `data/pillboxes.yaml`, and `data/traits/`. Treat `data/products/`, `data/substances/`, `data/dashboards/`, `data/stacks.yaml`, and `schedule.yaml` as user-specific.

For an empty stack:

```yaml
daily: []
training: []
inactive: []
```

First pass target: create one product card per physical product, create substance cards for known label components, link components to substance cards, place products into a stack, leave unknown planning facts empty instead of guessing, and run `uv run python -m planner check`.

Run `uv run python -m planner` after at least one non-inactive product exists. Enrich later with amounts, aliases, forms, URLs, label notes, traits, relations, dashboards, and review warnings.
