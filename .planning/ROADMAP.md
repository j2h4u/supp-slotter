# Roadmap: Supplement Slot Planner

**Core Value:** Personal supplement scheduling that respects food state, time of day, training routine, and health-goal clusters — without manual slot management.

## Milestones

- [x] **v1.1 Training Stacks + Goals Ontology** — Phase 1 (executed and verified)

<details>
<summary>Pre-GSD MVP (informational, not numbered)</summary>

The MVP system was built before GSD was introduced to this project: 23 substance cards, 4 physical slots, 16 traits in 5 namespaces, working `planner.py` with check/refresh/plan subcommands. `idea.md` is the authoritative SPEC.

</details>

### Phase 2: Substance/Product YAML model split

**Goal:** Split the YAML model into Substance, Product, and InventoryItem entities; migrate slots to declarative `near + food`; keep products physically inseparable during scheduling; and add only practical ontology improvements for scheduling, warnings, and explanations.
**Requirements**: TBD
**Depends on:** Phase 1
**Plans:** 5 plans

Plans:
- [x] 02-01-PLAN.md — Data/schema migration: Substance/Product/InventoryItem split, near+food slots, practical ontology
- [x] 02-02-PLAN.md — Planner validation: split-model loaders, schema checks, inventory/product refs, goal substance refs
- [x] 02-03-PLAN.md — Scheduler/explainability: schedule inventory products as inseparable units with component-aware reasons and warnings
- [x] 02-04-PLAN.md — Regression verification: Phase 2 tests, Phase 1 topology preservation, regenerated schedule smoke
- [x] 02-05-PLAN.md — Gap closure: target-mode prefer_with registry validation and malformed inventory schema errors

### Phase 3: Product Facts + Stack-Oriented Inventory

**Goal:** Correct data ownership after the product split: make inventory stack-oriented for readability, move product facts such as brand and label/component amounts into product cards, and split generic B6 into concrete label forms without adding unused taxonomy or a separate regimen model.
**Requirements**: TBD
**Depends on:** Phase 2
**Plans:** 4 plans

Plans:
- [x] 03-01-PLAN.md — Product fact preservation: copy known brand/label facts into product cards before stripping inventory
- [x] 03-02-PLAN.md — Stack-oriented inventory schema/data migration and planner loader/refresh normalization
- [x] 03-03-PLAN.md — Concrete B6 forms: P-5-P and pyridoxine HCl without unused taxonomy
- [x] 03-04-PLAN.md — Regression verification and regenerated schedule smoke

---

### Phase 1: Training Stacks + Goals Ontology
**Goal**: Add training-stack partition (2 virtual workout slots, `activity:` namespace, stack-aware planner) and goal-cards as first-class entities (vascular_health + mitochondrial_health seed cards, goal-master canonical with referential validator).

**Depends on**: none (extends pre-GSD MVP)

**Requirements**:
- TRAIN-01: Two virtual training slots (`pre_workout`, `post_workout`) usable by the planner
- TRAIN-02: Stack partition (`daily | training | inactive`) replacing `active: true|false` in inventory
- TRAIN-03: New `activity:` trait namespace with three peer traits (`pre_workout`, `post_workout`, `any_workout`) and asymmetric levels
- GOAL-01: Goal-card schema and `data/goals/*.yaml` directory
- GOAL-02: Two seed goal cards (vascular_health, mitochondrial_health) with members, candidates, declined
- GOAL-03: Referential integrity validator — `members[].substance` refs must point to existing substance cards

**Success Criteria** (what must be TRUE):
  1. `uv run planner.py check` passes with no errors after migration
  2. `uv run planner.py plan` produces a `schedule.yaml` where training-stack substances (citrulline, creatine, electrolyte_caps, l_carnitine_l_tartrate) land ONLY in `pre_workout` or `post_workout` slots
  3. Daily-stack substances land ONLY in the original 4 slots (morning_empty, morning_food, day_food, evening_empty); never in training slots
  4. Inactive-stack substances are skipped entirely from `schedule.yaml`
  5. `inventory.yaml` has no `active` field for any entry; every entry has a valid `stack` value
  6. `data/goals/vascular_health.yaml` exists with 4 members in `taking` status (citrulline, nattokinase, tadalafil, vitamin_b5)
  7. `data/goals/mitochondrial_health.yaml` exists with ALCAR (taking) + 2 candidates (CoQ10, ALA, name-only)
  8. Referential validator catches any goal-card `members[].substance` ref that doesn't have a matching substance card
  9. `schema/goal.schema.json` is registered and validates goal cards
  10. l_carnitine_l_tartrate is promoted from inactive to training stack with `activity:any_workout`

**Plans**: 4 plans
- [x] 01-01-PLAN.md — Data foundations: slots.yaml stack partition, traits.yaml activity namespace, inventory.yaml migration (active→stack)
- [x] 01-02-PLAN.md — Substance & goal cards: 4 product cards add activity:* traits; create data/goals/ + 2 seed cards (vascular_health, mitochondrial_health)
- [x] 01-03-PLAN.md — Planner code: register activity namespace, refresh writes stack:inactive, cmd_plan stack-partition filter, cmd_check goal-card referential validator
- [x] 01-04-PLAN.md — Smoke test: end-to-end check + plan + topology assertions; negative test for referential validator
