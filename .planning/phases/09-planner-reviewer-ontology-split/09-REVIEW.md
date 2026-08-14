---
phase: 9
reviewed: 2026-05-13T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - planner/cards/substance.py
  - planner/cards/traits.py
  - planner/cards/relations.py
  - planner/cards/dashboards.py
  - planner/contracts.py
  - planner/engine/review.py
  - planner/engine/audit.py
  - planner/engine/plan.py
  - planner/engine/_scheduling.py
  - planner/__main__.py
  - planner/io.py
  - schema/substance.schema.json
  - schema/relations.schema.json
  - tests/test_review_command.py
  - tests/test_phase_02.py
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 9: Code Review Report

**Reviewed:** 2026-05-13
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Phase 9 is a Planner/Reviewer ontology split: concerns, relations, risk flags, pathways, and dashboard summary move from `cmd_audit` to a new `cmd_review`; `separate_from` is retired in favour of class-level competes via `source_class`/`target_class` in relations.yaml; the substance schema is v2-only (no oneOf transitional structure). The split is architecturally clean and the schema migration is complete. No BLOCKERs found.

Four warnings are worth fixing before relying on this in production: a dead variable left in `check_substances`, a dashboard merge that silently drops data when a dashboard name appears in both benefits and risks, a missing description for `both_active` in the relation status display, and a stale docstring that mis-lists namespace ordering. Three info items cover minor quality gaps.

---

## Warnings

### WR-01: Dead variable `know_raw` assigned but only conditionally used in `check_substances`

**File:** `planner/cards/substance.py:237`

**Issue:** `know_raw` is assigned unconditionally at line 237 inside the `for sf in substance_files:` loop, but the block that uses it (lines 265–284) only runs when `sid_raw` is a `str` — i.e. it is inside the `if isinstance(sid_raw, str):` branch. The assignment at line 237 occurs *outside* that branch (same indentation level as `sid_raw = substance.get("id")`), meaning it is always evaluated even when the `id` field is missing or non-string, which is harmless but misleading. More critically, if a substance card passes schema validation but has a non-string `id`, `know_raw` is computed and then the `is`/`dashboard` validation block below is silently skipped because the outer `if isinstance(sid_raw, str):` guard short-circuits. The result is that knowledge-namespace trait validation is not applied to cards with malformed ids.

**Fix:** Move the `know_raw` assignment inside the `if isinstance(sid_raw, str):` branch, or alternatively restructure to `continue` early on malformed id. Minimal fix:

```python
if isinstance(sid_raw, str):
    sid: str = sid_raw
    # ... existing name/form/filename checks ...
    sched_raw: dict[str, Any] = cast(dict[str, Any], substance.get("schedule") or {})
    know_raw: dict[str, Any] = cast(dict[str, Any], substance.get("knowledge") or {})
    # ... rest of validation ...
```

---

### WR-02: Dashboard merge in `_review_inner` silently drops data when a dashboard carries both `benefit` and `risk` blocks

**File:** `planner/engine/review.py:248-264`

**Issue:** `build_dashboard_review` returns separate `benefits` and `risks` lists. The merge at lines 249–250 uses `seen.setdefault(entry["name"], entry)`, which keeps the *first* entry seen for each name. Since `benefits` is iterated before `risks`, a dashboard that has both a `benefit:` and a `risk:` block will only have its benefit entry kept — the risk entry is silently discarded. The `covered`/`active` key difference between benefit entries (`"covered"`) and risk entries (`"active"`) then compounds this: even if a risk entry were merged, the display code at line 260 falls back through `entry.get("covered") or entry.get("active")`, which only works if both keys are tried. But the root problem is the dropped entry.

For a dashboard with `benefit:` and `risk:`, the printed summary shows the benefit-side `covered` count, but the `active` count from the risk side (which may differ) is never shown, and the risk description is absent.

**Fix:** Merge both entries into a single combined entry rather than keeping only the first:

```python
seen: dict[str, dict[str, Any]] = {}
for entry in review_data["benefits"] + review_data["risks"]:
    name = entry["name"]
    if name not in seen:
        seen[name] = dict(entry)
    else:
        # Merge: benefit uses "covered", risk uses "active" — union both keys.
        for key in ("covered", "active", "inactive", "missing"):
            if key in entry and key not in seen[name]:
                seen[name][key] = entry[key]
```

---

### WR-03: `_RELATION_STATUS_DESC` is missing the `both_active` key, producing silent empty suffix

**File:** `planner/engine/review.py:61-65`

**Issue:** The dict defines descriptions for `"missing_source"`, `"missing_target"`, and `"neither_active"`, but not for `"both_active"`. The display loop at line 186 uses `.get(status, "")`, so `both_active` relations print with no `[desc]` suffix. This is not a crash but it is inconsistent — every other status has a human-readable parenthetical and `both_active` is the most important status to describe clearly for a reviewer.

```python
_RELATION_STATUS_DESC: dict[str, str] = {
    "both_active":    "both present — active pairing",   # ADD
    "missing_source": "target present, source absent",
    "missing_target": "source present, target absent",
    "neither_active": "both absent",
}
```

---

### WR-04: `class_competes` filter re-evaluated on every `_slot_is_blocked` call during search

**File:** `planner/engine/plan.py:647-649`

**Issue:** `_slot_is_blocked` is called in the inner loop of both `initialize_best_with_greedy` and `search`. Each call reconstructs `class_competes` by filtering `global_relations` from scratch:

```python
class_competes = [
    r for r in global_relations
    if r.type == "competes" and r.source_class and r.target_class
]
```

`global_relations` is a list that does not change during the search. For a schedule with N items and S slots this list comprehension runs O(N × S × |relations|) times. With tens of relations this is negligible, but it is also trivially fixable by pre-computing once before the search loop. The current code is correct but the pattern is fragile — if `global_relations` ever grows, the performance cliff will be invisible. This is a quality/maintainability issue, not a performance-scope finding: the real concern is that the re-evaluation pattern makes it non-obvious that `class_competes` is stable.

**Fix:** Pass the pre-filtered list as a parameter, or compute it once in `_run_plan_search` and pass it down:

```python
# In _run_plan_search, before the nested functions:
class_competes = [
    r for r in global_relations
    if r.type == "competes" and r.source_class and r.target_class
]
# Then pass class_competes to _slot_is_blocked instead of global_relations.
```

---

## Info

### IN-01: `grouped_trait_defs` docstring mentions `effect` namespace in ordering but `NAMESPACE_ORDER` omits it

**File:** `planner/cards/traits.py:107-108`

**Issue:** The docstring at line 107 says `"Order is fixed: is, intake, effect, risk, activity, dashboard."` but `NAMESPACE_ORDER` at line 100 is `("is", "intake", "timing", "risk", "activity", "dashboard", "pathway")` — `effect` is absent and `timing` and `pathway` are present. The docstring was not updated when the tuple was extended.

**Fix:** Update the docstring to match:

```python
"""Order is fixed: is, intake, timing, risk, activity, dashboard, pathway."""
```

---

### IN-02: `check_global_relations` does not validate `source_class`/`target_class` values against the `is:` trait registry

**File:** `planner/cards/relations.py:207-258`

**Issue:** `check_global_relations` validates `source_name`, `target_name`, `source_substance`, and `target_substance` against the substance registry, but does not check that `source_class` and `target_class` slugs correspond to registered `is:` traits. A typo in a class slug (e.g. `minearl` instead of `mineral`) will silently produce a class-level competes rule that never fires in `_slot_is_blocked`, since `item_classes` is built from `substance.is_` which uses the trait-registered slugs. There is no error, no warning — the rule is just dead.

**Fix:** Add a validation pass in `check_global_relations` (or in `check.py` after trait_ids are available) that checks class slugs:

```python
# In check.py, after trait_ids is built:
for rel_type_name in ("competes",):
    for rel_raw in relations_dict.get(rel_type_name) or []:
        src_class = rel_raw.get("source_class")
        tgt_class = rel_raw.get("target_class")
        if isinstance(src_class, str) and f"is:{src_class}" not in trait_ids:
            errors.append(f"relations.yaml: source_class '{src_class}' not registered under is: in traits.yaml")
        if isinstance(tgt_class, str) and f"is:{tgt_class}" not in trait_ids:
            errors.append(f"relations.yaml: target_class '{tgt_class}' not registered under is: in traits.yaml")
```

---

### IN-03: `test_review_command.py` fixture uses `"schedule: {}"` which passes schema but is semantically unusual

**File:** `tests/test_review_command.py:31`

**Issue:** The minimal fixture substance writes `schedule: {}` explicitly. The schema allows an empty `schedule` object (no `required` inside it), so this is valid. However, the fixture also does not include a `schema/` directory in the temp root — `validate_schemas()` called inside `_review_substance_inner` would need the schema files to be present relative to the patched root. `cmd_review` (not `cmd_review_substance`) does not call `validate_schemas`, so the existing tests pass, but the fixture is misleading: it looks complete but would fail if `review-substance` were ever tested against the same fixture. Not a current test failure, but a latent fixture gap.

**Fix:** Either remove `"schedule: {}\n"` (the schema treats absent `schedule` and `{}` identically) or add a comment noting the fixture is only valid for `cmd_review`, not `cmd_review_substance`.

---

_Reviewed: 2026-05-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
