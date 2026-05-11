---
title: Grouped trait shape + dashboard membership via tags
date: 2026-05-11
context: Ontology refactor — substance cards move from flat `traits:` list with namespace-prefixed strings to top-level grouped keys per namespace; dashboards move from manual `taking[]` lists to computed membership via grouped `from_traits:`
---

# Grouped trait shape + dashboard membership via tags

## The tension

Two pains operating together:

1. **Dashboard membership is split source of truth.** Each `data/dashboards/*.yaml` currently carries an explicit `taking:` list of substance IDs. Adding a substance to a cluster means finding it across 100+ substance cards and editing the right dashboard file by hand. Substance cards know *what they are*, dashboards know *who's in them*, and the link is maintained manually.
2. **Substance cards are cognitively flat.** Every fact about a substance lives in one `traits:` list with namespace-prefixed strings: `intake:empty_preferred`, `is:adaptogen`, `effect:sleep_support`, `risk:manual_review`, `dashboard:cortisol_reduction`. Semantically heterogeneous predicates (intrinsic class vs scheduling rule vs operator curation vs warning marker) share one slot. The reader has to mentally parse prefixes to separate them.

## The decision

**Two structural changes, landing together:**

### 1. Substance cards use top-level grouped keys, not a flat list

Before:
```yaml
traits:
- intake:empty_preferred
- is:adaptogen
- effect:sleep_support
- dashboard:cortisol_reduction
- dashboard:sleep_recovery
- risk:manual_review
```

After:
```yaml
is:
- adaptogen
intake:
- empty_preferred
effect:
- sleep_support
risk:
- manual_review
dashboard:
- cortisol_reduction
- sleep_recovery
```

The namespace becomes a **YAML key**, the list contains **bare slugs** (no prefix). Schema-level constraints:

- `additionalProperties: false` on the substance object — namespace key set is **closed**. No agent-invented `note:`/`meta:`/etc. drift.
- `intake:` and `activity:` — `maxItems: 1` (mutually exclusive within namespace).
- `is:`, `effect:`, `risk:`, `dashboard:` — polyhierarchical (no max).

The old `class:*` namespace becomes the `is:` top-level key. No separate rename step — the rename is just choosing the right key while rewriting each card.

### 2. Dashboards use grouped `from_traits:`, not `taking[]`

Before:
```yaml
name: Connective Tissue Support
taking:
- substance: sub_49c7531eaf
- substance: sub_22bf1dfae0
# ... 8 entries
```

After:
```yaml
name: Connective Tissue Support
from_traits:
  dashboard:
  - connective_tissue_support
```

Pure-class clusters project directly from intrinsic categories:
```yaml
name: Antioxidant Protection
from_traits:
  is:
  - antioxidant
```

Mixed clusters union both:
```yaml
from_traits:
  is:
  - antioxidant
  dashboard:
  - antioxidant_protection_extras
```

`additionalProperties: false` on the `from_traits` object closes its namespace set. Resolution semantics: **union** over all listed slugs across all namespaces — every substance whose grouped trait keys contain any listed slug is in the cluster.

### Membership flow

When you ask "which substances are in cluster Foo?", the planner:
1. Reads cluster's `from_traits` object — collects (namespace, slug) pairs.
2. For each substance card, checks: does substance's `<namespace>:` list contain `<slug>` for any of the cluster's pairs?
3. Substances that match any pair → cluster member.

When you ask "which clusters is this substance in?", you read the substance card's `dashboard:` and `is:` lists, then look up which dashboards reference those slugs in `from_traits`. (`review-substance` will do this lookup for you.)

## Why this shape

### Why grouped over flat-with-prefix

**Cognitive load.** Reading a substance card: visual structure mirrors semantic structure. The reader instantly sees "1 intrinsic class, 1 scheduling rule, 1 timing effect, 1 risk flag, 2 dashboard memberships" without parsing prefixes. The grouped form is what `review-substance` already renders at output time — making the source representation match the rendered representation closes that gap.

**Schema enforceability.** Cardinality rules become **machine-checkable** per namespace: `intake:` `maxItems: 1` enforces "at most one food-state rule per substance"; previously this was an unenforceable convention. Closed key set via `additionalProperties: false` prevents agent-invented namespace drift in ceremonies.

**Semantic non-conflation.** Per the ontology panel: `is:antioxidant` is rdf:type-equivalent class membership (intrinsic, stable, polyhierarchical). `dashboard:foo` is skos:inCollection-equivalent curated membership (operator-defined, mutable, no inferential entailment). `intake:empty_preferred` is a functional behavioral assertion. These are three categorically different predicate types. Putting them in separate top-level keys makes them non-conflatable **at the schema level**, not just at parse time.

### Why drop `taking[]` and per-member rationale fields

Grep across all 14 dashboards: **106 substance entries, 0 use `reason`, 0 use `note`**. The schema allowed per-member rationale; we never used it. Keeping them as fallback would preserve a feature with zero adoption. KISS.

When the operator does want substance-level rationale for membership in a particular cluster, the natural home is a future `dashboard_roles: { foo: "primary cofactor" }` field on the substance card — but that's deferred until first real need (data says demand is zero today).

### Why `dashboard:*` as its own namespace (not just more `is:*`)

Keeping `is:*` strictly biochemical preserves a useful invariant: anyone reading a substance card knows that `is:*` is a claim about *what the substance is*, not about *operator review goals*. Allowing operator-curated tags into `is:*` would erode this — opening the door to `is:morning_energy`, `is:gut_motility`, kitchen-sink labels. `dashboard:*` honest-by-name: it announces "this is operator curation, not chemistry".

### Why `from_traits` accepts any namespace, not just `is:` + `dashboard:`

`from_traits: { is: [antioxidant] }` projects pure biochemistry. `from_traits: { dashboard: [foo] }` projects curated membership. But also: `from_traits: { intake: [fat_meal_required] }` could project an "audit fat-soluble timing" review cluster; `from_traits: { risk: [manual_review] }` a "what needs operator attention right now" audit. Restricting which namespaces are projectable adds complexity without semantic benefit.

### Why canonical serialization is "grouped at rest, grouped in queries"

Both substance card storage and dashboard `from_traits` queries use the grouped object form. Taxonomy specialist's concern: mixing grouped-at-rest with prefix-in-queries forces the reader to hold two mental models simultaneously, and agents periodically write the wrong form in the wrong place. Adopting grouped uniformly costs minor verbosity in `from_traits` (14 dashboards × 1-2 traits each) but eliminates the asymmetry entirely.

### Why defer `is_class:` vs `is_property:` split

Ontology specialist recommended splitting `is:` into `is_class:` (natural kinds: mineral, adaptogen, omega3) and `is_property:` (physicochemical attributes: fat_soluble) — because lumping them under one key implies they share identity criteria, which they don't. The argument is correct, but in the current registry only **1 of 8** `is:*` markers is a pure physicochemical property (`fat_soluble`). Splitting namespace for one entry is gold-plating. Mitigation: document the heterogeneity in `traits.yaml` description for `fat_soluble`. Revisit only if pure properties grow to 3+ entries.

## Watch-outs

### Slug-clash risk (mitigated, not eliminated)

Bare slugs lose their namespace anchor at the substance-card level. If two namespaces happen to coin the same slug, you can no longer grep for the prefixed form to find it. Mitigation:
- Schema enforces slug must be registered in the same-named namespace in `traits.yaml`.
- `planner check` (DT-08) catches missing registrations with file context.
- Slug renames should go through `planner` maintenance helpers, not raw grep-replace.

### Rename ghost (accept as known limitation)

If a substance is repurposed or substantially changed, its existing `dashboard:foo` tag remains structurally valid (matches a real registered slug) but may no longer reflect operator intent — silent membership ghost. No automatic detection is possible — no schema or check can distinguish "stale but valid tag" from "deliberate continued membership". This is recorded in `docs/ontology-facts.md` as "Decided: Not Solving — relies on operator hygiene + occasional review of `review-substance` output". Real-world frequency expected: very low (operator manages ~50 cards; renames are rare).

### `dashboard:*` namespace can grow without ceremony

Every operator-curated cluster needs a `dashboard:*` entry. With 10 operator-curated dashboards out of 13 (after killing `vasodilation_no_pathway`), the namespace will have ~10 entries on day one. Each `dashboard:*` entry has a 1:1 correspondence to a dashboard file by slug convention. The constraint is implicit but enforceable: `planner check` will catch slug↔file mismatches (DT-08).

### Intensional vs extensional in `from_traits`

`from_traits: { is: [antioxidant] }` is intensional — open-world: when a future substance acquires `is:antioxidant`, it silently joins the cluster. Desirable for pure-class projections. `from_traits: { dashboard: [foo] }` is extensional — closed curation: only substances explicitly tagged are members. Both forms are valid; the difference in **why** something is a member becomes the operator's design choice, made when authoring the dashboard yaml. Documented in `docs/ontology-facts.md`.

## Outcome for other documents

- **`docs/domain-model.md`**: Trait section, Trait Ontology section, Adding Data examples, and Ownership Rules all need rewriting under grouped model.
- **`docs/ontology-facts.md`**: "Decided: Not Encoding" entries that say "encode as dashboard cluster, not as a `supports` relation" remain correct *in conclusion* but the *mechanism* description ages out — re-word as "add `dashboard:<slug>` tag in members; cluster yaml is narrative wrapper". Add new "Decided: Not Solving — rename ghost" entry. Add explicit one-paragraph note about intensional vs extensional `from_traits` semantics.
- **`SKILL.md`** (agent entrypoint, ~23 KB): hardcoded class-marker enumeration at line 121 gets dropped entirely (point to `traits.yaml` + suggest `review-substance`); File Tree, Add Or Enrich A Substance, Add Or Update A Dashboard, Minimal YAML Shapes, Validation Contract all rewritten under grouped model; add 3-line "Which namespace?" decision block + textual (not ASCII) "Membership Flow" decision tree.
- **`.planning/PROJECT.md`** line 17 namespace list refresh.
- **`README.md`** if it references old shape.
- **Out of scope**: `docs/private/2026-05-11-expert-panel-round-*.md` are historical session snapshots, not ontology reference.

## Follow-up

Concrete refactor scoped as **Phase 8** in `.planning/ROADMAP.md`, split internally into Stage 1 (core atomic commit, DT-01 through DT-10 — schema + cards + planner + reference-integrity check land together so `planner check` is never broken between commits) and Stage 2 (additive separate commits, DT-11 through DT-14 — docs, review-substance audit, doctor lifecycle warnings).

DT-14 (doctor lifecycle warnings) is **required, not optional**: the primary consumer of `planner doctor` is the agent itself (per SKILL.md instruction to run doctor after substance/dashboard edits), and agents have no persistent memory across sessions. PM's "single-operator covers it mentally" argument doesn't apply — the operator never runs doctor manually; agents do, and they need actionable lifecycle hints to compensate for statelessness. DT-14 therefore ships with per-warning-class **actionable resolution text** (not just identification), and DT-12 ships a **"Doctor Warning Playbook"** in SKILL.md that tells agents when to run doctor + how to interpret each warning class with explicit resolution options.

Execution model: Sonnet, per memory `feedback_subagent_models.md`.
