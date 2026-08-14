# Phase 1 Context: Training Stacks + Goals Ontology

## Goal

Extend the supplement scheduling system with two new ontological axes:

1. **Training-stack partition** — substances tied to aerobic training (separate from daily routine)
2. **Goal clusters** — purpose-driven groupings (vascular_health, mitochondrial_health) as first-class entities with `taking`/`candidate`/`declined` membership statuses

After this phase, operator can: model substances taken specifically around training; cluster substances by health goal; track which goal clusters are "closed" (complete) vs "open" (missing pieces); add wishlist members that don't yet have substance cards.

## Locked decisions

### Slots model

| Slot | Stack | Time | Food | Activity | Order |
|------|-------|------|------|----------|-------|
| morning_empty | daily | morning | false | — | 1 |
| morning_food | daily | morning | true | — | 2 |
| day_food | daily | day | true | — | 3 |
| evening_empty | daily | evening | false | — | 4 |
| pre_workout | training | (none — floats) | false | pre_workout | 5 |
| post_workout | training | (none — floats) | false | post_workout | 6 |

Training slots are virtual: time floats (training happens once per day, time varies). `food: false` is included so existing `intake:prefers_empty_stomach` substances score correctly.

### Stack partition

Substance belongs to exactly one stack: `daily | training | inactive`. Hard partition — no multi-stack assignment. This replaces `active: true|false` in inventory.yaml.

Default-deny mechanism for training slots is achieved via stack partition: training-stack substances cannot land in daily slots and vice versa. No separate `required_traits` gate.

### Activity namespace (new)

Three peer traits with asymmetric levels:

```yaml
"activity:pre_workout":
  effects:
    - match: {activity: pre_workout}
      level: prefer_strong   # +4

"activity:post_workout":
  effects:
    - match: {activity: post_workout}
      level: prefer_strong   # +4

"activity:any_workout":
  effects:
    - match: {activity: pre_workout}
      level: prefer           # +2
    - match: {activity: post_workout}
      level: prefer           # +2
```

Specific traits (pre/post) outscore the general `any_workout` (graceful degradation pattern — pragmatic subsumption without formal type hierarchy).

### Substance assignments

| Substance | Stack | Activity trait | Notes |
|-----------|-------|----------------|-------|
| l_citrulline_malate | training | activity:pre_workout | RCT-backed: 40-60 min before, NO/blood flow |
| creatine | training | activity:any_workout | Timing-agnostic per RCT evidence |
| electrolyte_caps | training | activity:any_workout | Operator's call: "around session" |
| l_carnitine_l_tartrate | training | activity:any_workout | Promoted from inactive — was actually training-only |
| acetyl_l_carnitine | daily | (none) | Used as nootropic, not training |
| All other active 11 substances | daily | (none) | vitamin_d3, vitamin_b5, coenzyme_b_complex, magnesium_glycinate, trace_minerals, potassium_citrate, lions_mane_b6_complex, astaxanthin, nattokinase, tadalafil |
| 8 currently-inactive (excluding l_carnitine_l_tartrate) | inactive | — | lions_mane (taxonomy ref), picamilon, se_methyl_l_selenocysteine, dihydroquercetin_complex, copper, n_acetyl_cysteine, krill_oil, glycine |

### Goal cards

**Goal-master canonical** — substance cards do NOT carry `goals:` field. Loader scans goal cards to derive substance→goals view at runtime. (Decision rationale: goal-driven authoring scenario dominates frequency; expert panel converged unanimously.)

Schema (new, `schema/goal.schema.json`):

```yaml
id: vascular_health
name: "Vascular Health"
description: "..."
status: active             # active | paused | retired
started: 2024-XX-XX        # optional

members:
  - substance: <ref>       # ref to existing substance card
    status: taking | candidate | declined
    role: "..."            # goal-specific role
    note: "..."            # optional
  - name: "Free-text"      # for candidates without substance card
    status: candidate
    role: "..."
```

Each member uses **either** `substance` (ref) **or** `name` (free-text) — `oneOf` constraint.

**Two seed goal cards (Phase 1):**

1. `vascular_health.yaml` — members: `l_citrulline_malate`, `nattokinase`, `tadalafil`, `vitamin_b5` (all status: taking)
2. `mitochondrial_health.yaml` — members: `acetyl_l_carnitine` (taking), `Coenzyme Q10` (candidate, name-only), `Alpha-Lipoic Acid` (candidate, name-only) — Bruce Ames triad pattern

### Referential integrity validator

In `planner.py:cmd_check`:
- Load and validate every `data/goals/*.yaml` against goal schema
- For each `members[i].substance` ref: verify the substance card exists at `data/products/{substance}.yaml`
- Error on missing substance refs

This is the "first-thing-built" gate flagged by data architect during expert panel.

### Naming convention

Activity traits use **workout** stem consistently: `pre_workout`, `post_workout`, `any_workout`. Avoids vocabulary clash (training_session vs workout) flagged by operator during taxonomy review.

## Already-done work (before GSD pivot)

These changes were made before pivoting to GSD. They remain — they correctly implement the locked decisions above:

- `schema/slots.schema.json` — added `stack` (required, enum daily|training), `activity` (optional enum), made `time` and `food` optional
- `schema/inventory.schema.json` — replaced `active` with `stack` (required, enum daily|training|inactive)
- `schema/goal.schema.json` — created from scratch

## Remaining work

1. `data/slots.yaml` — add `stack: daily` to existing 4 slots; add 2 new slots (pre_workout, post_workout)
2. `data/traits.yaml` — add `activity:` namespace section with 3 traits
3. `data/inventory.yaml` — migrate 23 entries from `active` to `stack`
4. `data/products/*.yaml` — add activity traits to 4 substance cards
5. `data/goals/` — create directory + 2 seed goal cards (vascular_health.yaml, mitochondrial_health.yaml)
6. `planner.py` — register `activity` namespace; `cmd_refresh` writes `stack: inactive` instead of `active: false`; `cmd_plan` filters by stack (substance.stack must match slot.stack); `cmd_check` validates goal cards + referential integrity
7. End-to-end smoke test: `uv run planner.py check && uv run planner.py plan` — verify training-stack substances land in training slots, daily-stack in daily slots
8. Update `idea.md` sections 8 (slots) and 15 (inventory) to document new model

## Out of scope (for this phase)

- Substance↔Product split (idea.md §24)
- Vector trait model (idea.md §25)
- Multi-substance-multi-goal authoring helpers
- CLI command to display goal cluster status (e.g., `planner.py goals`)
- Goal templates / inheritance
- Substance rename refactoring tool

## Constraints

- No git history to preserve in pre-Phase 1 — repo was non-git until this phase started
- Existing 23 substance cards must continue to validate (no schema-breaking changes to product card structure)
- Pre-existing planner score of 32 will change post-migration (substances repartition between daily/training); not a regression — different topology
- `tadalafil` stays in `daily` stack for now (operator hasn't classified it as training-tied; can be moved later if desired)
- electrolyte_caps has `intake:prefers_food` trait while now landing in food:false training slots — minor scoring mismatch accepted (universal trait of substance, training-context tolerance accepted by operator)
