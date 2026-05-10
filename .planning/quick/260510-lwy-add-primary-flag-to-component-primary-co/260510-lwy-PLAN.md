---
phase: 260510-lwy
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - planner/contracts.py
  - schema/product.schema.json
  - planner/io.py
  - planner/engine/_scheduling.py
  - planner/engine/plan.py
  - data/products/minami_healthy_foods__nattokinase_13000fu__prd_83dffd67bf.yaml
autonomous: true
requirements:
  - QUICK-260510-lwy
must_haves:
  truths:
    - "Component cards may declare `primary: false`; absent field defaults to primary=True (backwards compatible)"
    - "Product schema validates `primary: bool` on each component (optional)"
    - "Scheduler scores primary component traits at full weight, secondary-only traits at SECONDARY_TRAIT_WEIGHT (0.25) with no slot blocking"
    - "Intra-product trait conflicts and must_separate continue to use the FULL union (primary + secondary) — physical inseparability is unaffected"
    - "Nattokinase 13000FU lands in an empty-stomach slot (intake:empty_preferred drives placement; EPA's intake:fat_meal_required only nudges as secondary)"
    - "`pytest tests/ -x -q` passes; pyright reports 0 errors"
  artifacts:
    - path: planner/contracts.py
      provides: "Component dataclass with primary: bool = True field"
      contains: "primary: bool"
    - path: schema/product.schema.json
      provides: "Component schema accepts optional primary boolean"
      contains: "\"primary\""
    - path: planner/io.py
      provides: "SECONDARY_TRAIT_WEIGHT constant with derivation comment"
      contains: "SECONDARY_TRAIT_WEIGHT"
    - path: planner/engine/_scheduling.py
      provides: "effective_stack_item_traits returns (effective, primary_traits, secondary_only_traits, trait_sources, internal_conflicts) — primacy-aware split"
      contains: "secondary_only_traits"
    - path: planner/engine/plan.py
      provides: "ActiveIndex carries secondary_traits_by_item; scoring loop calls compute_slot_score twice and combines with SECONDARY_TRAIT_WEIGHT"
      contains: "secondary_traits_by_item"
    - path: data/products/minami_healthy_foods__nattokinase_13000fu__prd_83dffd67bf.yaml
      provides: "Nattokinase component marked primary: true; remaining components default to secondary via primary: false"
      contains: "primary: true"
  key_links:
    - from: "planner/engine/plan.py (slot scoring loop)"
      to: "planner/engine/_scheduling.py compute_slot_score"
      via: "two calls per (item, slot): one for primary_traits (full score + blocking), one for secondary_only_traits (scaled, ignored blocking)"
      pattern: "compute_slot_score\\("
    - from: "planner/io.py SECONDARY_TRAIT_WEIGHT"
      to: "planner/engine/plan.py scoring loop"
      via: "import + multiplication of secondary score, rounded to int"
      pattern: "SECONDARY_TRAIT_WEIGHT"
---

<objective>
Introduce a `primary: bool` flag on `ProductComponent` so the scheduler distinguishes the component a product is "really for" (primary) from physically-inseparable companions (secondary). Primary traits drive slot scoring at full weight and can block; secondary traits exclusive to non-primary components contribute at a derived `SECONDARY_TRAIT_WEIGHT = 0.25` and never block. This fixes Nattokinase 13000FU landing in a fat-meal slot because EPA's `intake:fat_meal_required` outranks nattokinase's `intake:empty_preferred`.

Purpose: a product like Minami Nattokinase 13000FU is bought *for* nattokinase; EPA / ginkgo / B-vitamins are physical companions, not co-equal scheduling drivers. The flat trait union loses that hierarchy.
Output: schema + dataclass + scheduler change + nattokinase product card update; nattokinase scheduled in an empty-stomach slot; tests + pyright clean.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@planner/contracts.py
@planner/engine/_scheduling.py
@planner/engine/plan.py
@planner/io.py
@schema/product.schema.json
@data/products/minami_healthy_foods__nattokinase_13000fu__prd_83dffd67bf.yaml

<interfaces>
<!-- Key contracts the executor will touch / extend. Extracted from current source. -->

From planner/contracts.py (current):
```python
@dataclass(frozen=True, slots=True)
class ProductComponent:
    substance: str
    label: str | None = None
    amount: str | None = None
    notes: str | None = None
```
Add: `primary: bool = True` — must be the LAST field (after every existing optional field) so positional construction in tests / loaders is unaffected. Field has a default → fully backwards-compatible for any code constructing ProductComponent without it.

From planner/io.py (current):
```python
LEVEL_SCORES = {
    "prefer_strong": 4,
    "prefer": 2,
    "avoid": -2,
    "avoid_strong": -4,
}
```
Add `SECONDARY_TRAIT_WEIGHT` immediately AFTER this dict. Derivation (must appear verbatim as a block comment above the constant):

```python
# SECONDARY_TRAIT_WEIGHT — slot-score multiplier for traits carried only by
# non-primary (companion) components in a multi-component product.
#
# Design constraint: a primary component's preference must always beat a
# secondary component's preference. Worst case to defeat: primary says
# `prefer` in slot A and `avoid` in slot B; a secondary says `prefer_strong`
# in slot B and `avoid_strong` in slot A. We need score(A) >= score(B):
#
#   prefer  - prefer_strong * w  >=  avoid + prefer_strong * w
#   (prefer - avoid) >= 2 * prefer_strong * w
#   w <= (prefer - avoid) / (2 * prefer_strong)         # upper bound
#
# Take half the upper bound for a comfortable margin:
#   w = (prefer - avoid) / (4 * prefer_strong)
#     = (2 - (-2)) / (4 * 4)
#     = 0.25
#
# Self-adjusts if LEVEL_SCORES is ever retuned.
SECONDARY_TRAIT_WEIGHT = (
    LEVEL_SCORES["prefer"] - LEVEL_SCORES["avoid"]
) / (4 * LEVEL_SCORES["prefer_strong"])
```

From planner/engine/_scheduling.py (current — the function whose contract changes):
```python
def effective_stack_item_traits(
    product: Product,
    substances: dict[str, Substance],
    trait_defs: dict[str, TraitDef],
) -> tuple[set[str], dict[str, list[str]], list[dict[str, Any]]]:
    # returns: (effective_traits, trait_sources, internal_conflicts)
```
NEW return shape — 5-tuple in this exact order:
```python
def effective_stack_item_traits(
    product: Product,
    substances: dict[str, Substance],
    trait_defs: dict[str, TraitDef],
) -> tuple[
    set[str],                    # effective_traits — full union (primary + secondary), unchanged semantics
    set[str],                    # primary_traits — union over components where primary is True
    set[str],                    # secondary_only_traits — traits in the full union that are NOT in primary_traits
    dict[str, list[str]],        # trait_sources — unchanged (full union -> component ids)
    list[dict[str, Any]],        # internal_conflicts — unchanged (computed over full union)
]:
```
Key invariants:
- `secondary_only_traits = effective_traits - primary_traits` (a trait shared by a primary and a secondary component is treated as primary).
- If a product has zero primary components (every component declares `primary: false`), `primary_traits` is empty and `secondary_only_traits == effective_traits`. Document this as the explicit fallback in a short comment.
- `internal_conflicts` is computed over the full effective set — physical inseparability means intra-product timing conflicts are real regardless of primacy.

From planner/engine/plan.py (current ActiveIndex):
```python
class ActiveIndex(NamedTuple):
    item_traits: dict[str, set[str]]
    item_products: dict[str, str]
    active_components: dict[str, list[str]]
    trait_sources_by_item: dict[str, dict[str, list[str]]]
    intra_product_conflicts_by_item: dict[str, list[dict[str, Any]]]
    intra_product_relation_conflicts_by_item: dict[str, list[dict[str, Any]]]
    item_stacks: dict[str, str]
```
NEW field — add `secondary_traits_by_item: dict[str, set[str]]` (place it adjacent to `item_traits` for readability). `item_traits` still stores the FULL union (it is consumed by `must_separate`, `_slot_is_blocked`, `explain_slot_choice`, warnings — none of those change behaviour).

From planner/engine/_scheduling.py compute_slot_score — DO NOT change its signature. The caller (plan.py) is the only thing that changes how it's invoked.

From planner/io.py — schema loader uses jsonschema; the only schema edit needed is adding the `primary` property entry under `components.items.properties`. Field is optional (not added to `required`). Default behaviour (loader-side default of True) is enforced in the dataclass, not the schema.

From data/products/minami_healthy_foods__nattokinase_13000fu__prd_83dffd67bf.yaml:
- `sub_877c24aad4` is nattokinase (primary intent of the product) — set `primary: true` (explicit, even though it would default to true; explicit makes intent visible).
- All other components (sub_66b783576c EPA, sub_45587454c0 ginkgo, sub_c36e075c09, sub_844a87d72b, sub_e9e80d003a niacin, sub_230c5c820e, sub_a873e428ee B6, sub_157418854b) get `primary: false`.
</interfaces>

<loader-contract>
The product loader (somewhere under `planner/cards/product.py` per the existing import in `_scheduling.py`) is the bridge between raw YAML and `ProductComponent`. The executor MUST locate it (grep `ProductComponent(` under `planner/cards/`) and confirm:
1. It currently constructs `ProductComponent` from the YAML mapping.
2. The change adds reading `primary` from the mapping with a default of `True` when absent.

If the loader uses `**raw` splat, no change is needed BUT the schema must still be extended (jsonschema validation runs first via `validate_schemas()`; an unknown key trips `additionalProperties: false`).
</loader-contract>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add primary flag — contracts, schema, loader, derived constant, nattokinase YAML</name>
  <files>
    planner/contracts.py,
    schema/product.schema.json,
    planner/io.py,
    planner/cards/product.py,
    data/products/minami_healthy_foods__nattokinase_13000fu__prd_83dffd67bf.yaml
  </files>
  <action>
1. **`planner/contracts.py`** — append `primary: bool = True` as the last field of `ProductComponent`. Keep frozen, slots, dataclass decorators intact.

2. **`schema/product.schema.json`** — under `properties.components.items.properties`, add:
   ```json
   "primary": { "type": "boolean" }
   ```
   Do NOT add it to `required`. `additionalProperties: false` already in place will reject typos.

3. **`planner/cards/product.py`** — locate the `ProductComponent(...)` construction site (grep first; do not invent a path). Read `primary` from the raw component mapping with `.get("primary", True)`. Pass it to the dataclass. If the loader currently splats `**raw`, instead build the kwargs explicitly so missing/extra YAML keys are handled deterministically (the existing schema validation guarantees only known keys reach the loader, but the explicit form makes the default visible).

4. **`planner/io.py`** — directly after the `LEVEL_SCORES` dict, add the `SECONDARY_TRAIT_WEIGHT` block comment + constant exactly as specified in `<interfaces>` above. Verify the computed value equals `0.25` (a one-line `assert SECONDARY_TRAIT_WEIGHT == 0.25` is acceptable but optional; tests will catch drift).

5. **`data/products/minami_healthy_foods__nattokinase_13000fu__prd_83dffd67bf.yaml`** — set `primary: true` on the `sub_877c24aad4` component, `primary: false` on every other component. Preserve all existing keys (`label`, `amount`, etc.). Sample shape:
   ```yaml
   - substance: sub_877c24aad4
     amount: 13000 FU
     primary: true
   - substance: sub_66b783576c
     label: EPA
     primary: false
   ```

DO NOT touch `_scheduling.py` or `plan.py` in this task — that's Task 2. Keeping the change isolated lets the executor verify schema + loader + dataclass independently of the scoring change.

Style: per project rules, no warning suppression; no broad type ignores. The `primary: bool = True` field with a default keeps every existing call site green without `# type: ignore`.
  </action>
  <verify>
    <automated>uv run python -m planner check && uv run pytest tests/ -x -q && uv run pyright</automated>
  </verify>
  <done>
- `Component` (ProductComponent) carries `primary: bool` with default `True`.
- `validate_schemas()` succeeds against the updated nattokinase YAML.
- Nattokinase YAML has `primary: true` on the nattokinase component and `primary: false` on every other component.
- `SECONDARY_TRAIT_WEIGHT` is exported from `planner.io` with the derivation block comment, evaluates to `0.25`.
- `python -m planner check` passes (no scoring change yet — schedule.yaml still produced as before since scheduler hasn't been wired to the new flag).
- pytest is green, pyright is 0 errors. (Test expectations for Task 2 do not yet exist; existing tests must not regress.)
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire primary/secondary into the scheduler — split scoring + ActiveIndex field</name>
  <files>
    planner/engine/_scheduling.py,
    planner/engine/plan.py,
    tests/(new test for nattokinase placement)
  </files>
  <action>
1. **`planner/engine/_scheduling.py` — extend `effective_stack_item_traits`:**
   - Iterate `product.components` directly (NOT just substance ids) so `component.primary` is in scope.
   - Maintain three sets while iterating:
     - `effective`: every trait_id of every component substance (existing behaviour, unchanged).
     - `primary_traits`: trait_ids of components where `component.primary is True`.
   - After the loop: `secondary_only_traits = effective - primary_traits` (note: a trait shared by a primary and a secondary component is therefore primary — encode that as a comment).
   - `trait_sources` and `internal_conflicts` keep their current full-union semantics — physical inseparability still means intra-product trait conflicts are real.
   - Update the docstring 3-tuple block to a 5-tuple, in the order: `(effective, primary_traits, secondary_only_traits, trait_sources, internal_conflicts)`.
   - Document the zero-primary edge case: "If every component declares `primary: false`, `primary_traits` is empty and the scheduler will score the product entirely under secondary weight — that is a lint smell, not an error; let `check` flag it elsewhere if desired."

2. **`planner/engine/plan.py` — extend `ActiveIndex`:**
   - Add field `secondary_traits_by_item: dict[str, set[str]]` adjacent to `item_traits`.
   - In `_build_active_index`, unpack the new 5-tuple from `effective_stack_item_traits` and populate the new dict.
   - Pass it through to `_run_plan_search` as a new keyword argument (mirrors the existing `item_traits` plumbing).

3. **`planner/engine/plan.py` — split scoring in two places:**
   - The feasibility loop that builds `feasible_slots_by_item` (currently calls `compute_slot_score(traits, slot, ...)`):
     - First call: `compute_slot_score(active.primary_traits_for(sid), slot, trait_defs, trait_sources)` — captures both score AND `blocked`. Use `active.item_traits[sid]` if there are no primary traits (fallback below).
     - Wait — re-read carefully: the design says **`primary_traits` drives blocking**. Decision: `compute_slot_score` is called with `primary_traits` for blocking + base score. If `secondary_only_traits` is non-empty, call `compute_slot_score` again with those traits, take its `score` (ignore `blocked`), multiply by `SECONDARY_TRAIT_WEIGHT`, round to nearest int (`round(...)` — Python's banker's rounding is fine), and add to the base score. Concatenate the reasons lists for logging.
     - Edge case: if a product has zero primary components, fall back to scoring with the full effective set as the "primary" pass (so behaviour is unchanged for that pathological product). Add a single-line comment marking it as a fallback.
   - The greedy seed inside `initialize_best_with_greedy` reads its score from `feasible_slots_by_item[item]`, so it inherits the new combined score automatically. Confirm by reading the loop — no separate change needed.
   - The branch-and-bound `search` reads scores from `feasible_slots_by_item` too (via the per-candidate score field) — same story.
   - `_slot_is_blocked` uses `item_traits` (full union) — DO NOT change. Symmetric `must_separate` over the full effective trait set is correct (physical inseparability).

4. **Test — add `tests/test_primary_component_scoring.py`** (new file) with at minimum:
   - A unit test on `effective_stack_item_traits` for a synthetic product with one primary + one secondary component, asserting the 5-tuple split is correct.
   - An integration-style test that builds a tiny stack with a mock pillbox containing both an `empty_preferred`-friendly slot and a `fat_meal_required`-friendly slot, places a product equivalent to nattokinase (one primary `intake:empty_preferred` substance + one secondary `intake:fat_meal_required` substance), and asserts the planner places it in the empty-preferred slot.
   - A regression test asserting that a product with all-secondary components (every `primary: false`) still gets scheduled (fallback path).
   - Match the existing `tests/` layout — grep an existing test file for fixture patterns; do not invent a new harness.

5. **Run `python -m planner` end-to-end** and confirm nattokinase 13000FU appears in an empty-stomach slot in the produced `schedule.yaml`. If the actual stack/pillbox layout doesn't contain an `empty_preferred`-compatible slot, document the observed slot in the SUMMARY and verify by inspecting the slot reasons that the primary trait (nattokinase) is the dominant driver and EPA's fat-meal preference is no longer pulling at full weight.

Style: existing rounding pattern in this codebase appears integer-only (LEVEL_SCORES are ints). Keep slot scores as `int`; `round()` returns int in Python 3 when given a float without a digit count. Use `int(round(secondary_raw * SECONDARY_TRAIT_WEIGHT))` to be explicit.

Do NOT use `# type: ignore` to silence pyright. If pyright complains about the 5-tuple unpacking, fix the type annotation on `effective_stack_item_traits` — that's the right surface to update.
  </action>
  <verify>
    <automated>uv run pytest tests/ -x -q && uv run pyright && uv run python -m planner plan && grep -A2 "Nattokinase 13000FU" schedule.yaml | head -20</automated>
  </verify>
  <done>
- `effective_stack_item_traits` returns a 5-tuple with `primary_traits` and `secondary_only_traits`.
- `ActiveIndex.secondary_traits_by_item` is populated and threaded into the search.
- Slot scoring splits into two `compute_slot_score` calls; secondary score is scaled by `SECONDARY_TRAIT_WEIGHT` and added.
- `compute_slot_score` signature is unchanged.
- `must_separate` and `_slot_is_blocked` continue to use the full effective union.
- New test file passes; existing tests still pass.
- pyright clean (0 errors).
- `python -m planner plan` places Nattokinase 13000FU in an empty-stomach (or `intake:empty_preferred`-matching) slot, OR the SUMMARY documents the observed placement and confirms (via slot reasons) that the primary trait is the dominant driver.
  </done>
</task>

</tasks>

<verification>
End-to-end checks (run after Task 2):
- `uv run python -m planner check` exits 0.
- `uv run python -m planner plan` writes a `schedule.yaml` containing Nattokinase 13000FU placed in a slot whose `near` is consistent with `intake:empty_preferred` (review_tags + why_here in `schedule.yaml.explanations` should reference nattokinase as the primary driver).
- `uv run pytest tests/ -x -q` exits 0.
- `uv run pyright` reports 0 errors and 0 warnings (project rule: don't suppress).
- Spot-grep: `grep -n "SECONDARY_TRAIT_WEIGHT" planner/io.py planner/engine/plan.py` shows definition + at least one use site.
- Spot-grep: `grep -n "primary" planner/contracts.py schema/product.schema.json` shows the new field + schema entry.
</verification>

<success_criteria>
1. `Component` (ProductComponent) has `primary: bool = True`.
2. Schema validates `primary: boolean` (optional) on each component.
3. `SECONDARY_TRAIT_WEIGHT = 0.25` derived from `LEVEL_SCORES`, with the full algebraic derivation in a block comment above it.
4. Scheduler scores primary traits at full weight (with blocking) and secondary-only traits at `SECONDARY_TRAIT_WEIGHT` (no blocking).
5. `must_separate` and intra-product trait conflicts continue to use the full union.
6. Nattokinase 13000FU is scheduled in an empty-stomach slot (or, if the active stack doesn't expose one, the explanations confirm the primary trait drives the choice).
7. `pytest tests/ -x -q` and `pyright` both clean.
</success_criteria>

<output>
After completion, create `.planning/quick/260510-lwy-add-primary-flag-to-component-primary-co/260510-lwy-SUMMARY.md` recording:
- Final placement slot for Nattokinase 13000FU + the `why_here` reason list.
- The derivation values (confirm `SECONDARY_TRAIT_WEIGHT == 0.25` post-import).
- Any other products whose placement shifted because of the primary-vs-secondary split (run a diff of the previous `schedule.yaml` if available).
- Any deferred follow-ups (e.g. a `check`-time lint for products with zero primary components).
</output>
