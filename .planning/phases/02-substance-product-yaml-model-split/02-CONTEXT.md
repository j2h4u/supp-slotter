# Phase 2: Substance/Product YAML model split - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 delivers a clean YAML data-model migration for the local planner. The goal is to make the YAML files a stable future wire format for a dumb deterministic MCP server, without building the MCP server yet.

The phase should include:

- split universal substance knowledge from real multi-component product formulas;
- make inventory reference real products/formulas rather than pretending every shelf item is a single substance;
- simplify slot declarations into intuitive physical-slot fields;
- improve the ontology enough that agents can author/edit cards consistently.

The phase should not preserve backwards compatibility with the current YAML layout. There is no external user base and no legacy contract.

</domain>

<decisions>
## Implementation Decisions

### Migration Philosophy

- **D-01:** No legacy compatibility is required. Do not add compatibility adapters, temporary dual-read paths, or long-lived `legacy` directories unless the planner needs a very short mechanical migration step inside the phase.
- **D-02:** Prefer a clean data shape over incremental coexistence. It is acceptable to rename/move `data/products/*.yaml` if those files are actually substance cards.
- **D-03:** YAML remains the primary model for this phase. MCP/server/database work is deferred.
- **D-04:** The future MCP server should be dumb and deterministic: CRUD, schema validation, planning, explanation, deterministic warnings. It should not perform web search, product-page parsing, approval workflows, drafts, or confidence-state management.
- **D-05:** Smart agents outside the server will handle iHerb/web research, product parsing, component normalization, and trait authoring. The YAML/schema should make that easy, but the repo should not implement import workflow state now.
- **D-06:** The current dataset is tiny; do the direct migration to the target YAML shape in one phase. Do not plan around staged rollout, compatibility shims, or partial coexistence just to reduce migration effort.

### Core Entity Split

- **D-07:** Introduce a real distinction between `Substance`, `Product`, and `InventoryItem`.
- **D-08:** `Substance` represents universal knowledge about a molecule/nutrient/active ingredient: traits, mechanisms, risks, general notes.
- **D-09:** `Product` represents a concrete formula/bottle and may contain multiple components, for example nattokinase + vitamin B6 + vitamin B12.
- **D-10:** `InventoryItem` represents the user's actual shelf/protocol: product reference, dose, brand/source details if needed, stack assignment, active/inactive state, and operator overrides.
- **D-11:** Components of a single product are physically inseparable. The planner must not "fix" a component-level conflict by assigning different components of the same capsule to different slots. Such conflicts should become product/inventory warnings.
- **D-12:** The planner should eventually schedule inventory items/products, but scoring should aggregate the traits of their component substances plus product/inventory overrides.

### Slot Model

- **D-13:** Slot names are labels, not semantics. Slot behavior should be expressed through declarative fields.
- **D-14:** Keep the base slot ontology small and intuitive: `near` plus `food` is enough for the current known physical slots.
- **D-15:** Candidate `near` values: `wake`, `breakfast`, `day_meal`, `sleep`, `workout_before`, `workout_after`.
- **D-16:** The first physical slot is immediately after waking and far from food: `near: wake`, `food: false`.
- **D-17:** The last daily physical slot is immediately before sleep and far from food: `near: sleep`, `food: false`.
- **D-18:** Two middle daily slots are food-associated: `near: breakfast`, `food: true`; `near: day_meal`, `food: true`.
- **D-19:** Training slots should use the same `near` field, likely `workout_before` and `workout_after`, with `food: false` for the current operator setup.
- **D-20:** Avoid ontological fields like `proximity`, `anchor`, `phase`, or `meal_anchor` unless a concrete trait cannot be expressed cleanly with `near + food`.

### Ontology Improvements

- **D-21:** Improve the ontology during this phase, but keep it practical and agent-authorable.
- **D-22:** Traits should explain why an item lands in a slot. Example: magnesium can prefer the last slot via `near: sleep`, while nattokinase can prefer the same slot via `food: false`.
- **D-23:** Add safety/mechanism traits only where they remove real ambiguity or generic warning noise.
- **D-24:** Good first ontology candidates from the review: `mechanism:vasodilator`, `mechanism:no_precursor`, `mechanism:fibrinolytic`, `risk:hypotension_stack`, `risk:fibrinolytic_bleeding`, `risk:antiplatelet_bleeding`, `risk:hyperkalemia_med_interaction`, `risk:dose_monitoring`, `risk:narrow_therapeutic_window`, `family:copper_like`, `intake:requires_fat_containing_meal`, `intake:with_water_or_food`, `intake:food_neutral`.
- **D-25:** Avoid a large medical ontology. The ontology should be just rich enough for scheduling, warnings, and explainability.

### Product Formula Example

- **D-26:** The current nattokinase shelf product is not pure nattokinase; it also includes vitamin B6 and B12. Phase 2 should model this as one product formula with multiple components.
- **D-27:** Nattokinase's empty-stomach requirement belongs to the `nattokinase` substance. B6/B12 belong to their own substance cards. The formula binds them into one physical product.
- **D-28:** If formula components have competing scheduling preferences, the product remains one schedulable unit and the conflict becomes an explanatory warning.

### the agent's Discretion

The implementation can choose exact directory names and schema filenames, but should keep the domain language explicit. Prefer names like `substances`, `products`, `inventory`, `slots`, `traits` over generic names.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project State

- `.planning/PROJECT.md` — project scope, current architecture, non-goals, and Phase 1 state.
- `.planning/ROADMAP.md` — Phase 2 roadmap entry and Phase 1 requirements.
- `.planning/STATE.md` — current GSD state and roadmap evolution.

### Prior Phase Artifacts

- `.planning/phases/01-training-stacks-goals-ontology/01-VERIFICATION.md` — verified Phase 1 behavior that must stay green after migration.
- `.planning/phases/01-training-stacks-goals-ontology/01-VALIDATION.md` — validation expectations from Phase 1.
- `.planning/phases/01-training-stacks-goals-ontology/01-SECURITY.md` — safety/security closure for existing planner surface.

### Domain Review

- `.planning/reviews/supplement-slot-data-review.md` — independent review of slot distribution and data-model gaps; source of ontology improvement candidates.

### Current Data and Code

- `data/products/*.yaml` — current substance-like cards, despite the directory name.
- `data/inventory.yaml` — current user shelf/protocol.
- `data/slots.yaml` — current slot declarations.
- `data/traits.yaml` — current trait ontology.
- `planner.py` — current planner, validation, refresh, and schedule generation logic.
- `tests/test_phase_01.py` — regression tests to preserve stack partition, goal references, and generated schedule topology.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- Existing YAML loader/writer paths in `planner.py` should be reused or cleanly renamed; avoid creating a second data-access style.
- Existing `cmd_check` referential validation is the natural place to add substance/product/inventory reference checks.
- Existing explanation output already traces product traits to slot matches; Phase 2 should preserve or improve this explainability after aggregation through products/components.

### Established Patterns

- Slot matching is generic: trait `effects[].match` is an AND match against slot fields. The new `near` field should fit this existing model.
- Stack partitioning is already established: `daily | training | inactive`. Product/inventory split should preserve that behavior.
- Goal cards are goal-master canonical and refer to substances. Planning must decide whether goal members continue to refer to substances or can refer to products/inventory items.

### Integration Points

- `planner.py refresh` currently creates/updates cards from inventory; this behavior needs rethinking once substances/products/inventory are separate.
- `planner.py check` must validate references: product components -> substances, inventory item -> product, goal member -> chosen canonical entity.
- `planner.py plan` must aggregate component substance traits to score a product/inventory item as one schedulable unit.
- `schedule.yaml` should remain a user-facing generated artifact, but may need to show inventory/product IDs instead of substance IDs.

</code_context>

<specifics>
## Specific Ideas

- Future MCP server use case: a user can install the server, add their own supplements/products, edit slots, and generate recommendations through agents.
- Future agents may research product pages externally, create missing substances, create product formulas, and call deterministic CRUD tools. The YAML model should support this without embedding import workflow state.
- The MCP server should eventually expose simple CRUD-style tools, but the current phase should prove the data model in YAML first.
- The ontology should be intuitive enough that agents do not confuse physical slots, universal substance facts, concrete product formulas, and user inventory overrides.

</specifics>

<deferred>
## Deferred Ideas

- MCP server implementation.
- Web/iHerb product import tooling.
- Draft/review/approval workflow for imported products.
- Database storage.
- Full evidence grading and medical interaction ontology.
- User-facing UI.

</deferred>

---

*Phase: 02-substance-product-yaml-model-split*
*Context gathered: 2026-05-05*
