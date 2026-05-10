---
phase: quick-260510-iwv
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - planner/engine/plan.py
  - planner/engine/_scheduling.py
  - planner/maintenance.py
  - planner/cards/_common.py
  - planner/cards/relations.py
  - planner/cards/warnings.py
  - planner/engine/check.py
  - tests/test_phase_02.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "Variable names in plan.py reflect what the values actually are (a prefix-sum upper bound, feasible-filtered slots, dict-insertion-order id sequence)"
    - "`generated_id` in maintenance.py is renamed to express intent (`needs_new_id`)"
    - "`connected_components` docstring leads with the non-obvious singleton-dropping behavior"
    - "`normalize_stack_items` test helper is renamed `group_items_by_stack` to reflect the pivot/reshape it actually performs"
    - "`cmd_check` no longer prints the misleading 'maintenance lock held' line on non-lock failures"
    - "Redundant docstrings/comments that merely restate function bodies, return types, or names are removed"
    - "The balance-display comment in relations.py is removed and the call site is self-documenting (or the comment accurately documents what the convention is)"
    - "`_derive_concern_text` docstring accurately describes the empty-string sentinel contract"
    - "Pyright is clean and `python -m pytest tests/ -x -q` passes after every task"
  artifacts:
    - path: planner/engine/plan.py
      provides: "BnB search with renamed locals (no `remaining_max_scores`, `scored_slots_by_item`, `item_ids_in_order`)"
    - path: planner/maintenance.py
      provides: "Auto-maintenance with `needs_new_id` rename"
    - path: planner/engine/check.py
      provides: "cmd_check with corrected failure message"
    - path: tests/test_phase_02.py
      provides: "Test module using `group_items_by_stack`"
  key_links:
    - from: planner/engine/plan.py
      to: "internal call sites in plan.py only (verified via grep — no external imports of these names)"
      via: "renamed parameters + locals threaded through `_run_branch_and_bound_search` / surrounding scope"
      pattern: "remaining_score_upper_bound|feasible_slots_by_item|item_id_sequence"
---

<objective>
Naming, docstring, and message-fidelity cleanup batch (Issues A from the recent code-quality review).

Purpose: Reduce reader confusion in the BnB scheduler, maintenance loop, graph helper, and test fixture by renaming a small set of misleading locals/parameters; remove docstrings and comments that pay no information rent; correct one user-facing message that lies about the failure mode.

Output: Eight files modified, all renames threaded across their (file-local) usages, redundant comments stripped, `cmd_check` failure message replaced. No behavior changes.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/quick/260510-iwv-issues-a-naming-renames-and-comment-nois/

# Source files to modify
@planner/engine/plan.py
@planner/engine/_scheduling.py
@planner/maintenance.py
@planner/cards/_common.py
@planner/cards/relations.py
@planner/cards/warnings.py
@planner/engine/check.py
@tests/test_phase_02.py

<verification-baseline>
All renames verified file-local via grep before planning:
- `remaining_max_scores`, `scored_slots_by_item`, `item_ids_in_order` → only `planner/engine/plan.py`
- `generated_id` → only `planner/maintenance.py` (4 occurrences in one function)
- `normalize_stack_items` → only `tests/test_phase_02.py` (definition + 1 call site)
- `connected_components` is imported by `planner/cards/substance.py` — DO NOT rename, only update its docstring
</verification-baseline>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Rename misleading locals in planner/engine/plan.py</name>
  <files>planner/engine/plan.py</files>
  <action>
Three file-local renames in `planner/engine/plan.py`. All occurrences live inside this file (verified by grep — `_run_branch_and_bound_search`, `cmd_plan`, and helpers in the same module).

1. `remaining_max_scores` → `remaining_score_upper_bound`
   - It is a prefix-sum array used as a branch-and-bound upper bound on remaining score (see usage at line ~566 inside `optimistic_total = slot_score_total + remaining_max_scores[index] + ...`).
   - Rename the parameter declaration (line ~477), the local construction (lines ~717-720), the call-site keyword arg (line ~732), and the indexing site (line ~566).

2. `scored_slots_by_item` → `feasible_slots_by_item`
   - It holds slots that have already been filtered for feasibility (the surrounding code constructs it via a feasibility filter, then iterates it as the candidate set during search).
   - Rename the parameter declaration (line ~475), local construction site (line ~683), assignment (line ~702), iteration sites (lines ~534, ~594, ~715, ~743), and the call-site keyword arg (line ~730).

3. `item_ids_in_order` → `item_id_sequence`
   - The "in_order" suffix implies sorted; it is just dict-insertion order used as a stable tiebreak.
   - Rename the two parameter declarations (lines ~264, ~472), the local construction (line ~704), the iteration/index uses (lines ~316, ~330, ~356, ~398, ~500, ~710), and the two call-site keyword args (lines ~727, ~764).

After renames, run pyright and the test suite. Do not change any logic or whitespace beyond the rename.

Commit message: `refactor(plan): rename BnB locals for accuracy (remaining_score_upper_bound, feasible_slots_by_item, item_id_sequence)`
  </action>
  <verify>
    <automated>pyright planner/engine/plan.py && python -m pytest tests/ -x -q</automated>
  </verify>
  <done>
- `grep -n "remaining_max_scores\|scored_slots_by_item\|item_ids_in_order" planner/engine/plan.py` returns no matches
- `grep -rn "remaining_max_scores\|scored_slots_by_item\|item_ids_in_order" --include="*.py"` returns no matches
- New names appear at all expected sites
- Pyright clean, pytest green
  </done>
</task>

<task type="auto">
  <name>Task 2: Rename `generated_id` → `needs_new_id` and rename `normalize_stack_items` → `group_items_by_stack`</name>
  <files>planner/maintenance.py, tests/test_phase_02.py</files>
  <action>
Two unrelated-but-tiny renames bundled (both fully file-local; both are 4-occurrence and 2-occurrence respectively). Two commits — one per rename — to keep history clean.

**A. `planner/maintenance.py` — rename `generated_id` → `needs_new_id`**
- At line ~80, `generated_id = not isinstance(old_id, str)` is a boolean meaning "we need to generate a new id." At that point on line 80 the id has not yet been generated, so the name is past-tense for a future event.
- Rename the assignment (line ~80) and the three later branches that read it (lines ~81, ~86, ~92).
- Verify no other file references this local: `grep -rn "generated_id" --include="*.py"` should return nothing after the change.

Commit: `refactor(maintenance): rename generated_id to needs_new_id (intent over past-tense outcome)`

**B. `tests/test_phase_02.py` — rename `normalize_stack_items` → `group_items_by_stack`**
- The function pivots an item_id→stack mapping into a stack→[item_ids] mapping. "normalize" implies same shape in / same shape out; this is a reshape.
- Rename the definition (line ~107) and the one call site (line ~220).
- Verify no other file imports it: `grep -rn "normalize_stack_items" --include="*.py"` should return nothing after the change.

Commit: `refactor(tests): rename normalize_stack_items to group_items_by_stack (it pivots, not normalizes)`

Run pyright + full test suite after each commit.
  </action>
  <verify>
    <automated>pyright planner/maintenance.py tests/test_phase_02.py && python -m pytest tests/ -x -q</automated>
  </verify>
  <done>
- `grep -rn "generated_id\|normalize_stack_items" --include="*.py"` returns no matches
- New names appear at expected sites in both files
- Two separate commits landed
- Pyright clean, pytest green
  </done>
</task>

<task type="auto">
  <name>Task 3: Fix cmd_check failure message + improve `connected_components` and `_derive_concern_text` docstrings</name>
  <files>planner/engine/check.py, planner/cards/_common.py, planner/cards/warnings.py</files>
  <action>
Three small accuracy fixes in three files. One commit covers all three (they are all "make the doc/message tell the truth" edits).

**A. `planner/engine/check.py` — fix misleading failure message (line ~34)**
- Current: on any non-zero return from `run_auto_maintenance`, prints `"check: skipped (maintenance lock held)"`. But `run_auto_maintenance` also returns non-zero on the card-load-error path (where `auto_maintenance_needed` returns `None`), and in that case the lock is not held — `run_auto_maintenance` has already printed the real error to stderr.
- Replace the print line with: `print("check: skipped (auto-maintenance failed; see errors above)", file=sys.stderr)`. Generic, accurate in both cases (lock-held and card-load-error), and points the reader at the real diagnostic.

**B. `planner/cards/_common.py` — lift singleton-drop behavior to docstring lead (line ~67)**
- Current docstring (lines 68-71) mentions singleton dropping in the second sentence. A caller using a standard graph library expects singletons back, so the surprising behavior should lead.
- Rewrite as:
  ```
  """Return non-trivial connected components of an undirected graph (singletons are dropped).

  The graph is given as an adjacency dict mapping node → set of neighbors. Each
  returned component is a sorted list of node names; only components with more
  than one node are returned.
  """
  ```
- Do NOT rename the function — `planner/cards/substance.py` imports it. Docstring-only change.

**C. `planner/cards/warnings.py` — clarify the sentinel contract on `_derive_concern_text` (lines ~184-201)**
- Current docstring narrates cross-function state coupling without naming it as a contract. Rewrite to make the empty-string sentinel explicit:
  ```
  """Return the human-readable concern label, or "" to defer to the caller.

  Sentinel contract: when warning_type == "risk_cluster_load", the `concern`
  field is already populated by `_format_warning_entities` (sourced from the
  `cluster` field). Returning "" here signals `humanize_warning` to keep that
  pre-populated value rather than overwriting it.
  """
  ```
- This documents the implicit coupling rather than refactoring it (refactor is out of scope for this batch).

Commit message: `docs: correct cmd_check failure message and clarify connected_components/_derive_concern_text contracts`
  </action>
  <verify>
    <automated>pyright planner/engine/check.py planner/cards/_common.py planner/cards/warnings.py && python -m pytest tests/ -x -q</automated>
  </verify>
  <done>
- `grep -n "maintenance lock held" planner/engine/check.py` returns no matches
- `connected_components` docstring's first line mentions "singletons are dropped"
- `_derive_concern_text` docstring uses the phrase "Sentinel contract" (or equivalent explicit wording) and names `_format_warning_entities` as the populating function
- Pyright clean, pytest green
  </done>
</task>

<task type="auto">
  <name>Task 4: Remove redundant docstrings and the balance-display comment</name>
  <files>planner/engine/_scheduling.py, planner/cards/relations.py, planner/cards/warnings.py</files>
  <action>
Strip docstrings/comments that pay no information rent. One commit.

**A. `planner/engine/_scheduling.py:67-73` — `slot_matches`**
- Remove the docstring `"""Slot satisfies match if all listed fields equal."""` — restates the 3-line body.
- Function body remains unchanged.

**B. `planner/engine/_scheduling.py:149-179` — `compute_slot_score`**
- Remove the docstring `"""Returns (score, blocked, reasons)."""` — restates the type annotation `tuple[int, bool, list[str]]`.

**C. `planner/cards/relations.py:316` — balance-display comment in `collect_missing_balance_relations`**
- The comment `# Balance display: active endpoint → source, missing endpoint → target` documents the default behavior of `_append_missing_relation_warning` — which is already the contract specified by the function's own docstring + parameter defaults (verified: `source_display_side` defaults to `active_side`, `target_display_side` defaults to `missing_side`).
- Action: Just delete the comment line. The default-arg path is the convention; the supports variant (lines ~337-343) already documents the override case explicitly via kwargs. No call-site change needed.

**D. `planner/cards/warnings.py:128-133` — `_format_warning_entities`**
- Replace the docstring `"""Resolve product/substance/source/target IDs to display names."""` with no docstring (the name + body already say this). Or, if a docstring is required by repo style, leave just the function unchanged with no doc — there is no project-wide rule mandating one for module-private helpers, and other private helpers in the same file have no docstring.
- Action: Delete the one-line docstring.

Commit message: `chore: remove redundant docstrings and comments that restate code`
  </action>
  <verify>
    <automated>pyright planner/engine/_scheduling.py planner/cards/relations.py planner/cards/warnings.py && python -m pytest tests/ -x -q</automated>
  </verify>
  <done>
- `slot_matches` and `compute_slot_score` in `_scheduling.py` have no docstrings
- The balance-display `# Balance display: ...` comment is gone from `relations.py`
- `_format_warning_entities` in `warnings.py` has no docstring
- No other unintended changes (whitespace-only edits except for the deletions)
- Pyright clean, pytest green
  </done>
</task>

</tasks>

<verification>
After all four tasks:

```bash
# No old names anywhere
grep -rn "remaining_max_scores\|scored_slots_by_item\|item_ids_in_order\|generated_id\|normalize_stack_items" --include="*.py"
# expect: no output

# cmd_check message changed
grep -n "maintenance lock held" planner/engine/check.py
# expect: no output

# Balance comment removed
grep -n "Balance display:" planner/cards/relations.py
# expect: no output

# Pyright + tests
pyright
python -m pytest tests/ -x -q
```
</verification>

<success_criteria>
- All four tasks committed (with the noted commit messages or close equivalents) — Task 2 produces two commits, the others one each, total ~5 commits
- Pyright reports zero errors after each task
- `python -m pytest tests/ -x -q` passes after each task
- No behavior changes — diff for each file is rename-only or doc/comment-only
- `connected_components` is NOT renamed (only its docstring changed)
</success_criteria>

<output>
After completion, create `.planning/quick/260510-iwv-issues-a-naming-renames-and-comment-nois/260510-iwv-01-SUMMARY.md` summarizing renames performed, comments/docstrings removed, and the cmd_check message change.
</output>
