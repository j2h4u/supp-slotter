---
phase: 260509-vcm
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - planner/maintenance.py
  - planner/cards/relations.py
  - planner/engine/plan.py
  - tests/test_scheduling_units.py
  - tests/test_phase_02.py
  - tests/test_phase_03.py
autonomous: true
requirements: [SI-01, SI-02, SI-03, SI-04, SI-05, SI-06, SI-07, SI-08, SI-09, SI-10, SI-11, SI-12]

must_haves:
  truths:
    - "acquire_maintenance_lock rolls back lock dir on pid-write OSError"
    - "rewrite_substance_refs skips and logs on per-file write OSError"
    - "normalize_substances reverts substance id and returns None on write OSError"
    - "compute_slot_score, must_separate, humanize_warning, review_context_key, collect_missing_support_relations have passing unit tests"
    - "_endpoint_fields extracted; 4 relation functions delegate to it"
    - "_append_missing_relation_warning extracted; both collect_missing_* functions call it"
    - "_slot_is_blocked at module level; seed_with_greedy_assignment and search call it"
    - "copy_planner_runtime_only in test_phase_02.py; copy_planner_with_data in test_phase_03.py; no stale references"
  artifacts:
    - path: "tests/test_scheduling_units.py"
      provides: "Unit tests for _scheduling and warnings helpers (SI-04–SI-08)"
    - path: "planner/maintenance.py"
      provides: "Write-failure hardened lock, rewrite, and normalize functions"
    - path: "planner/cards/relations.py"
      provides: "Deduplicated _endpoint_fields and shared _append_missing_relation_warning"
    - path: "planner/engine/plan.py"
      provides: "Extracted _slot_is_blocked helper replacing duplicated inline guards"
  key_links:
    - from: "planner/cards/relations.py::collect_missing_balance_relations"
      to: "_append_missing_relation_warning"
      via: "internal call"
      pattern: "_append_missing_relation_warning"
    - from: "planner/engine/plan.py::seed_with_greedy_assignment"
      to: "_slot_is_blocked"
      via: "direct call replacing inline any() guards"
      pattern: "_slot_is_blocked"
---

<objective>
Phase 6 KQ3 — Code Quality Structural Improvements (SI-01 through SI-12).

Purpose: Harden write-failure paths in maintenance.py, add focused unit tests for
scheduling/warning internals, and eliminate duplicated code in relations.py and plan.py.

Output: Patched maintenance.py, new tests/test_scheduling_units.py, refactored
relations.py and plan.py, renamed test helpers in test_phase_02.py and test_phase_03.py.

Scope constraint: Do NOT touch cmd_plan decomposition, _normalize_card_dir extraction,
or warning_action dict dispatch — those are Phase 7 (KQ4) scope.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/quick/260509-vcm-phase-6-kq3-code-quality-structural-impr/

Key signatures extracted from source (no re-reads needed):

```python
# planner/engine/_scheduling.py
def compute_slot_score(
    trait_ids: set[str],
    slot: Slot,
    trait_defs: dict[str, TraitDef],
    trait_sources: dict[str, list[str]] | None = None,
) -> tuple[int, bool, list[str]]:
    """Returns (score, blocked, reasons)."""

def must_separate(
    t1: set[str], t2: set[str], trait_defs: dict[str, TraitDef]
) -> bool:
    """Symmetric: t1 and t2 share a slot conflict if either declares separate_from
    referencing a trait in the other."""

# planner/cards/warnings.py — review_context_key keyword branches:
#   "bleeding"/"fibrinolytic"/"antiplatelet"  → "bleeding_context"
#   "cholinergic"                              → "cholinergic_load"
#   "blood-pressure"/"blood pressure"/"hypotension" → "blood_pressure"
#   "inside one product"/"intra-product"       → "intra_product_conflicts"
#   "missing balance"/"missing support"/"paired" → "missing_pairings"
#   "narrow therapeutic window"/"narrow-window" → "narrow_window_minerals"
#   "potassium"/"hyperkalemia"                 → "potassium_medication"
#   "timing conflict"                          → "timing_conflicts"
#   "unmatched"/"unresolved active concern"    → "unmatched_concerns"
#   else                                       → None

# planner/cards/relations.py — endpoint field pattern (used identically in 4 functions):
#   side=="source": (relation.source_substance, relation.source_name)
#   side=="target": (relation.target_substance, relation.target_name)

# tests/test_phase_02.py — function to rename:
#   def copy_planner_runtime(tmp_path) → copy_planner_runtime_only
#   copies planner/ and schema/ only (no data/)
#   call sites: write_split_model_fixture (line 176), test_cli_help_exposes_simple_agent_commands (line 345)

# tests/test_phase_03.py — function to rename:
#   def copy_planner_runtime(tmp_path) → copy_planner_with_data
#   copies data/, planner/, schema/; returns temp_data Path
#   call sites: every test accepting tmp_path that calls copy_planner_runtime(tmp_path)
```
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task A: Harden write-failure paths in maintenance.py (SI-01, SI-02, SI-03)</name>
  <files>planner/maintenance.py</files>
  <behavior>
    - SI-01: acquire_maintenance_lock — after mkdir() succeeds, pid write_text raises OSError → rmdir lock_dir, return False. No empty lock dir left behind.
    - SI-02: rewrite_substance_refs — each of the three path.write_text calls (products loop, dashboards loop, substances loop) raises OSError → print warning to stderr, continue. Function does not abort.
    - SI-03: normalize_substances — save old_id_value = substance.get("id") before generating new id; if write_text raises OSError → revert substance["id"] = old_id_value, print stderr warning, return None.
  </behavior>
  <action>
Edit planner/maintenance.py with three targeted changes only. Do not touch any other logic.

**SI-01 — acquire_maintenance_lock (line 103):**

Replace:
    (lock_dir / "pid").write_text(f"{os.getpid()}\n")
    return True

With:
    try:
        (lock_dir / "pid").write_text(f"{os.getpid()}\n")
    except OSError as e:
        print(f"warning: could not write maintenance lock pid: {e}", file=sys.stderr)
        try:
            lock_dir.rmdir()
        except OSError:
            pass
        return False
    return True

**SI-02 — rewrite_substance_refs:**

Three separate `if changed: path.write_text(...)` blocks exist (products loop ~line 148,
dashboards loop ~line 175, substances loop ~line 201). Wrap each one:

    if changed:
        try:
            path.write_text(yaml.safe_dump(...))
        except OSError as e:
            print(f"warning: could not write {path}: {e}", file=sys.stderr)
            continue

Do this independently for all three loops. The yaml.safe_dump(...) arguments remain
identical to what is currently there.

**SI-03 — normalize_substances (~line 225):**

Before the existing line:
    if generated_id:
        substance["id"] = generate_stable_id("sub")

Insert:
    old_id_value = substance.get("id")

Then locate the subsequent `if generated_id: path.write_text(...)` block (~line 238)
and wrap it:

    if generated_id:
        try:
            path.write_text(yaml.safe_dump(...))
        except OSError as e:
            substance["id"] = old_id_value
            print(
                f"warning: could not write substance id to {path}: {e}",
                file=sys.stderr,
            )
            return None

The yaml.safe_dump(...) arguments remain identical to the existing block.
  </action>
  <verify>
    <automated>cd /home/j2h4u/repos/j2h4u/supp-slotter && uv run pytest tests/ -x -q 2>&1 | tail -10</automated>
  </verify>
  <done>All existing tests pass. The three write paths in maintenance.py are wrapped in try/except OSError with the rollback/skip semantics described above.</done>
</task>

<task type="auto" tdd="true">
  <name>Task B: Unit tests for scheduling and warning internals (SI-04 through SI-08)</name>
  <files>tests/test_scheduling_units.py</files>
  <behavior>
    SI-04 — compute_slot_score:
    - prefer_strong match → score > 0, blocked=False
    - avoid match → score < 0, blocked=False
    - block=True effect matching slot → blocked=True
    - trait_ids empty or no matching effects → score=0, blocked=False

    SI-05 — must_separate:
    - t1 has trait_a, t1's TraitDef declares separate_from=[trait_b], t2 has trait_b → True
    - reverse (t2 declares against t1) → True (symmetry)
    - neither declares separate_from referencing the other → False

    SI-06 — humanize_warning:
    - type="missing_balance_substance" with source_substance/target_substance present in
      substances dict → category == WARNING_CATEGORY_LABELS["missing_balance_substance"],
      concern == "missing balance substance"
    - type="totally_unknown_xyz" → category == "Review"
    - message containing "operator attention" → "note" key absent from result

    SI-07 — review_context_key:
    - concern containing "bleeding" → "bleeding_context"
    - concern containing "potassium" → "potassium_medication"
    - concern containing "timing conflict" → "timing_conflicts"
    - concern with no matching keyword → None

    SI-08 — collect_missing_support_relations non-warning direction:
    - Construct a supports Relation with source_substance="sub_src", target_substance="sub_tgt"
    - substances = {"sub_src": <Substance>}, active_substances = {"sub_src"} (source active, target absent)
    - Result must be [] — only target-active / source-absent triggers the warning
  </behavior>
  <action>
Create tests/test_scheduling_units.py as a new file. Do not depend on the live data
directory; build all fixtures inline using dataclass constructors.

Import block:
```python
from __future__ import annotations
from planner.engine._scheduling import compute_slot_score, must_separate
from planner.cards.warnings import humanize_warning, review_context_key
from planner.cards.relations import collect_missing_support_relations
from planner.contracts import Slot, TraitDef, TraitEffect, TraitEffectMatch, Relation, Substance
from planner.io import WARNING_CATEGORY_LABELS, LEVEL_SCORES
```

Read planner/contracts.py briefly to confirm field names before constructing fixtures if
any field is uncertain. Known from reading _scheduling.py and warnings.py:
- Slot(pillbox, order, near, food, stack)
- TraitDef(label, description, applies_when, effects, separate_from, warning, action)
- TraitEffect(match, level, block)
- TraitEffectMatch(near, food)
- Relation(type, reason, source_substance, target_substance, source_name, target_name, action)
- Substance(id, name, traits, form, prefer_with, aliases, unmatched_concerns)

For SI-06: pass products={} and substances={"sub_src": Substance(...), "sub_tgt": Substance(...)}
to humanize_warning. The function formats substance names; the test only checks category and concern.

For SI-08: call collect_missing_support_relations(
    substances={"sub_src": Substance(id="sub_src", name="Src", traits=(), ...)},
    active_substances={"sub_src"},
    global_relations=[Relation(type="supports", source_substance="sub_src",
                               target_substance="sub_tgt", ...)],
) and assert the result == [].

Group tests by SI item using clear function names like test_compute_slot_score_prefer_strong,
test_must_separate_symmetric, etc.
  </action>
  <verify>
    <automated>cd /home/j2h4u/repos/j2h4u/supp-slotter && uv run pytest tests/test_scheduling_units.py -v 2>&1 | tail -20</automated>
  </verify>
  <done>All SI-04 through SI-08 test functions pass. File imports only from planner modules, not from live data files. No test touches DATA_DIR or reads YAML from disk.</done>
</task>

<task type="auto">
  <name>Task C: Deduplication + rename (SI-09 through SI-12)</name>
  <files>
    planner/cards/relations.py,
    planner/engine/plan.py,
    tests/test_phase_02.py,
    tests/test_phase_03.py
  </files>
  <action>
Apply four sub-changes in order. Run `uv run pytest tests/ -x -q` after each one to catch regressions early.

---

**SI-09 — _endpoint_fields in planner/cards/relations.py**

Insert before `relation_endpoint_value`:

```python
def _endpoint_fields(relation: Relation, side: str) -> tuple[str | None, str | None]:
    """Return (substance_field, name_field) for the given side of a relation."""
    if side == "source":
        return relation.source_substance, relation.source_name
    if side == "target":
        return relation.target_substance, relation.target_name
    return None, None
```

Then rewrite the four functions to call it (logic unchanged, just replace duplicated
if/elif blocks with _endpoint_fields):

`relation_endpoint_value`:
    exact_id, name = _endpoint_fields(relation, side)
    return exact_id or name

`substance_matches_relation_endpoint`:
    exact_id, expected_name = _endpoint_fields(relation, side)
    if exact_id is not None:
        return substance_id == exact_id
    return expected_name is not None and substance.name == expected_name

`relation_endpoint_display`:
    exact_id, name = _endpoint_fields(relation, side)
    if exact_id is not None:
        substance = substances.get(exact_id)
        if substance is not None:
            return exact_id, format_substance_name(substance)
        return exact_id, exact_id
    if name is not None:
        return name, name
    return "<unknown>", "<unknown>"

`relation_endpoint_match_label`:
    exact_id, expected_name = _endpoint_fields(relation, side)
    if exact_id is not None and substance_id == exact_id:
        return f"{side} exact id"
    if expected_name is not None and substance.name == expected_name:
        return f"{side} exact name"
    return None

---

**SI-10 — _append_missing_relation_warning in planner/cards/relations.py**

Add after _endpoint_fields:

```python
def _append_missing_relation_warning(
    relation: Relation,
    active_side: str,
    missing_side: str,
    warning_type: str,
    substances: dict[str, Substance],
    active_substances: set[str],
    seen: set[tuple[str, str, str]],
    warnings: list[dict[str, Any]],
) -> None:
    """Append one missing-relation warning if active_side is present and missing_side is not."""
    if not relation_endpoint_is_active(
        relation, active_side, substances, active_substances,
    ) or relation_endpoint_is_active(
        relation, missing_side, substances, active_substances,
    ):
        return
    source_key, source_name = relation_endpoint_display(relation, missing_side, substances)
    target_key, target_name = relation_endpoint_display(relation, active_side, substances)
    warning_key = (source_key, relation.type, target_key)
    if warning_key in seen:
        return
    seen.add(warning_key)
    warnings.append(
        {
            "type": warning_type,
            "source_substance": source_key,
            "source_name": source_name,
            "target_substance": target_key,
            "target_name": target_name,
            "reason": relation.reason,
            "action": relation.action or "",
        }
    )
```

Note on display semantics: the helper passes missing_side as first arg to
relation_endpoint_display (becomes source_key/source_name in the warning) and
active_side as second arg (becomes target_key/target_name). This preserves the
existing output shape of both callers:
- balance: active_side and missing_side swap per loop iteration — warning shows
  whichever is active as target and whichever is missing as source
- supports: active_side="target" (the supplement being supported is active),
  missing_side="source" (the supporter is missing) — warning shows supporter as
  source, supported substance as target

Rewrite collect_missing_balance_relations:
```python
def collect_missing_balance_relations(
    substances: dict[str, Substance],
    active_substances: set[str],
    global_relations: list[Relation] | None = None,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for relation in global_relations or []:
        if relation.type != "balance":
            continue
        for active_side, missing_side in (("source", "target"), ("target", "source")):
            _append_missing_relation_warning(
                relation, active_side, missing_side,
                "missing_balance_substance",
                substances, active_substances, seen, warnings,
            )
    return warnings
```

Rewrite collect_missing_support_relations:
```python
def collect_missing_support_relations(
    substances: dict[str, Substance],
    active_substances: set[str],
    global_relations: list[Relation] | None = None,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for relation in global_relations or []:
        if relation.type != "supports":
            continue
        _append_missing_relation_warning(
            relation, "target", "source",
            "missing_support_substance",
            substances, active_substances, seen, warnings,
        )
    return warnings
```

---

**SI-11 — _slot_is_blocked in planner/engine/plan.py**

Add before cmd_plan (at module level). Check current imports — Relation and TraitDef
are imported via `from planner.contracts import Slot` — verify what is already imported
and add only what is missing.

```python
def _slot_is_blocked(
    item: str,
    slot_name: str,
    item_traits: set[str],
    slot_traits: dict[str, list[set[str]]],
    slot_items: dict[str, list[str]],
    active_components: dict[str, list[str]],
    substances: dict[str, Substance],
    trait_defs: dict[str, TraitDef],
    global_relations: list[Relation],
) -> bool:
    """Return True if item cannot be placed in slot_name due to trait or competes conflict."""
    if any(
        must_separate(item_traits, existing_traits, trait_defs)
        for existing_traits in slot_traits[slot_name]
    ):
        return True
    if any(
        component_sets_have_relation(
            active_components[item],
            active_components[existing_item],
            substances,
            "competes",
            global_relations,
        )
        for existing_item in slot_items[slot_name]
    ):
        return True
    return False
```

In seed_with_greedy_assignment, replace the two `if any(...): continue` guards with:
    if _slot_is_blocked(
        item, slot_name, traits,
        greedy_slot_traits, greedy_slot_items,
        active_components, substances, trait_defs, global_relations,
    ):
        continue

In search (the `for slot_name, score, _reasons in ordered_candidates:` loop), replace
the two `if any(...): continue` guards with:
    if _slot_is_blocked(
        item, slot_name, traits,
        slot_traits, slot_items,
        active_components, substances, trait_defs, global_relations,
    ):
        continue

Both replacements are inside closures that already have access to active_components,
substances, trait_defs, global_relations via closure/nonlocal — pass them explicitly
to the module-level function so it remains testable without nested state.

---

**SI-12 — Rename test helpers**

In tests/test_phase_02.py:
- Rename `def copy_planner_runtime(tmp_path: Path) -> None:` → `def copy_planner_runtime_only(tmp_path: Path) -> None:`
- Update call in write_split_model_fixture: `copy_planner_runtime(tmp_path)` → `copy_planner_runtime_only(tmp_path)`
- Update call in test_cli_help_exposes_simple_agent_commands: `copy_planner_runtime(tmp_path)` → `copy_planner_runtime_only(tmp_path)`

In tests/test_phase_03.py:
- Rename `def copy_planner_runtime(tmp_path: Path) -> Path:` → `def copy_planner_with_data(tmp_path: Path) -> Path:`
- Update ALL call sites. Search the file for `copy_planner_runtime(tmp_path)` and replace
  each occurrence with `copy_planner_with_data(tmp_path)`. Affected tests include:
  test_check_auto_renames_files_when_names_change, test_check_warns_about_products_without_stack_entry,
  test_duplicate_stack_item_across_stacks_is_rejected, test_auto_maintenance_lock_only_blocks_mutations,
  test_workout_activity_product_is_not_scheduled_as_daily, test_duplicate_slot_ids_across_pillboxes_are_rejected,
  test_orphans_command_lists_cleanup_candidates, test_doctor_lists_similar_substance_cards,
  test_balance_relation_warns_when_related_substance_missing,
  test_relation_validation_rejects_unknown_substance_name,
  test_support_relation_warns_when_supporter_missing,
  test_support_relation_accepts_alternate_active_supporter_form.

After all SI-12 edits, confirm no occurrence of the old name remains:
    grep -n "copy_planner_runtime(" tests/test_phase_02.py tests/test_phase_03.py
  — must be empty.
  </action>
  <verify>
    <automated>cd /home/j2h4u/repos/j2h4u/supp-slotter && grep -c "copy_planner_runtime(" tests/test_phase_02.py tests/test_phase_03.py ; uv run pytest tests/ -x -q 2>&1 | tail -10</automated>
  </verify>
  <done>
  - _endpoint_fields present in relations.py; 4 endpoint functions use it; no duplicated if side == "source" / if side == "target" blocks remain in those functions.
  - _append_missing_relation_warning present; both collect_missing_* functions are ≤10 lines each.
  - _slot_is_blocked at module level in plan.py; seed_with_greedy_assignment and search each have a single _slot_is_blocked(...) call replacing the two inline any() guards.
  - grep -c "copy_planner_runtime(" returns 0:0 for both test files.
  - uv run pytest tests/ passes with 0 failures.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| filesystem → maintenance | YAML card paths are written; failures were previously unhandled |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-kq3-01 | Tampering | maintenance write paths | mitigate | SI-01/02/03: OSError wrapped; partial writes roll back or skip cleanly |
| T-kq3-02 | Denial of Service | stale empty lock dir on pid-write failure | mitigate | SI-01: rmdir() called on failure so no empty lock dir blocks future runs |
</threat_model>

<verification>
Run after Task C completes:

```bash
cd /home/j2h4u/repos/j2h4u/supp-slotter

# No stale old name in either test file
grep -n "copy_planner_runtime(" tests/test_phase_02.py tests/test_phase_03.py
# Expected: no output

# Confirm extracted helpers exist
grep -n "def _endpoint_fields" planner/cards/relations.py
grep -n "def _append_missing_relation_warning" planner/cards/relations.py
grep -n "def _slot_is_blocked" planner/engine/plan.py

# Full test gate
uv run pytest tests/ -q 2>&1 | tail -5
```
</verification>

<success_criteria>
- uv run pytest tests/ passes with 0 failures after each task
- maintenance.py: 3 write paths wrapped in OSError handlers with rollback/skip semantics
- tests/test_scheduling_units.py: SI-04 through SI-08 test groups, all green, no live-data access
- relations.py: _endpoint_fields and _append_missing_relation_warning present; 4 endpoint functions simplified; both collect_missing_* functions ≤10 lines
- plan.py: _slot_is_blocked at module level; seed_with_greedy_assignment and search simplified
- test_phase_02.py: copy_planner_runtime_only; test_phase_03.py: copy_planner_with_data; zero stale references to old name
</success_criteria>

<output>
After completion, create `.planning/quick/260509-vcm-phase-6-kq3-code-quality-structural-impr/260509-vcm-SUMMARY.md`
</output>
