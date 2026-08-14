# Phase 8 Research: Grouped trait shape + dashboard membership via tags

**Date:** 2026-05-11
**Phase:** 08 — Grouped trait shape + dashboard membership via tags

---

## Current State Audit

### Schema: substance.schema.json

Current top-level fields: `id`, `name`, `traits`, `form`, `aliases`, `notes`, `concerns`, `prefer_with`.

`traits` is defined as `array of strings` with pattern `^[a-z]+:[a-z][a-z0-9_]*$` — a flat list of `namespace:slug` strings with no cardinality constraints per namespace. `additionalProperties: false` is already set at the object level, but it only applies to the top-level fields listed above — the namespace keys to be added (`is:`, `intake:`, `effect:`, `risk:`, `activity:`, `dashboard:`) are not present.

**Required change (DT-01):**
- Remove `traits` from `required` and from `properties`
- Add 6 new properties: `is`, `intake`, `effect`, `risk`, `activity`, `dashboard` — each an `array` of bare slug strings (pattern `^[a-z][a-z0-9_]*$`, no namespace prefix)
- `intake` and `activity`: add `maxItems: 1`
- All 6 groups: `uniqueItems: true`, all optional (not in `required`)
- `additionalProperties: false` remains — closes the key set

### Schema: dashboard.schema.json

Current `required`: `["name", "description", "taking"]`. `taking` is an array of member objects with `substance`, `name`, `note`, `reason` sub-fields. `anyOf` requires at least one of `benefit` or `risk`.

**Required change (DT-05):**
- Remove `taking` from `required` and from `properties`
- Add `from_traits` as an object with optional namespace keys (`is`, `intake`, `effect`, `risk`, `activity`, `dashboard`) each holding `array of strings` with bare slug pattern
- `additionalProperties: false` on the `from_traits` object
- `from_traits` added to `required`
- Keep `anyOf: [{required: [benefit]}, {required: [risk]}]` unchanged

### data/traits.yaml — namespace inventory

Current namespaces and entry counts:
- `intake`: 5 traits (`empty_preferred`, `fat_meal_required`, `food_neutral`, `food_preferred`, `food_required`)
- `effect`: 3 traits (`energy_like`, `sleep_disruptive`, `sleep_support`)
- `class`: 8 traits (`adaptogen`, `antioxidant`, `electrolyte`, `ergogenic`, `fat_soluble`, `mineral`, `nootropic`, `omega3`)
- `risk`: 3 traits (`hyperkalemia_med_interaction`, `manual_review`, `narrow_therapeutic_window`)
- `activity`: 3 traits (`any_workout`, `post_workout`, `pre_workout`)

Total: 22 trait definitions across 5 namespaces. No `dashboard:` namespace exists yet.

**Required change (DT-03):**
- Rename `class` namespace to `is` (all 8 entries move, slugs unchanged)
- Add new `dashboard` namespace with entries for each operator-curated cluster (see dashboard catalog below)
- `REGISTERED_NAMESPACES` in `planner/io.py` (line 29–36) currently lists: `{"intake", "effect", "class", "risk", "activity", "mechanism"}`. Must change `"class"` → `"is"`, add `"dashboard"`, remove dead `"mechanism"` entry.

### Dashboard catalog — DT-02 + DT-04 migration map

Classification legend:
- **pure-class** = membership fully determined by `is:` slug; no `dashboard:*` tags needed on substance cards
- **operator-curated** = hand-assembled cluster; substances get `dashboard:<slug>` tag

| Slug | Label | taking count | Classification | from_traits key |
|------|-------|-------------|----------------|-----------------|
| `antioxidant_protection` | Antioxidant Protection | 10 | mixed (≠ pure `is:antioxidant` — includes omega3, fat_soluble, mineral members) | `dashboard: [antioxidant_protection]` |
| `bleeding_load` | Bleeding Load | 16 | operator-curated | `dashboard: [bleeding_load]` |
| `cholinergic_load` | Cholinergic Load | 8 | operator-curated | `dashboard: [cholinergic_load]` |
| `connective_tissue_support` | Connective Tissue Support | 8 | operator-curated | `dashboard: [connective_tissue_support]` |
| `cortisol_reduction` | Cortisol Reduction | 4 | operator-curated | `dashboard: [cortisol_reduction]` |
| `electrolyte_hydration_support` | Electrolyte / Hydration Support | 7 | mixed (not all `is:electrolyte`) | `dashboard: [electrolyte_hydration_support]` |
| `mitochondrial_health` | Mitochondrial Health | 1 | operator-curated | `dashboard: [mitochondrial_health]` |
| `neurocognitive_support` | Neurocognitive Support | 13 | mixed (nootropic + ergogenic, not pure `is:nootropic`) | `dashboard: [neurocognitive_support]` |
| `serotonergic_load` | Serotonergic Load | 4 | operator-curated | `dashboard: [serotonergic_load]` |
| `skin_barrier_support` | Skin Barrier Support | 3 | operator-curated | `dashboard: [skin_barrier_support]` |
| `sleep_recovery` | Sleep Recovery | 11 | operator-curated | `dashboard: [sleep_recovery]` |
| `vascular_health` | Vascular Health | 7 | operator-curated | `dashboard: [vascular_health]` |
| `vasodilation_no_pathway` | Vasodilation / NO Pathway | 5 | **KILL** — strict subset of vascular_health | — |
| `workout_performance` | Workout Performance | 9 | mixed (ergogenic + electrolyte + mineral) | `dashboard: [workout_performance]` |

**Important finding:** The roadmap's four "pure-class candidates" (`antioxidant_protection`, `electrolyte_hydration_support`, `neurocognitive_support`, `workout_performance`) are **not** pure class projections — their `taking[]` members span multiple `class:*` namespaces. All 13 surviving dashboards should use `dashboard: [<slug>]` in `from_traits`, with substance cards tagged accordingly. This is simpler and avoids ambiguity about which class drives membership.

Exception: if the operator wants to use pure `is:` projection for any cluster, that's valid for a future cluster that genuinely maps 1:1 to a class. The 13 existing clusters are all operator-curated by composition evidence.

**vasodilation_no_pathway members (to confirm absorbed into vascular_health):**
- `sub_fmuptat7pw`, `sub_699a985e61`, `sub_3918fe347e`, `sub_396c221c31`, `sub_a3ec9f9c52`
- All 5 already appear in `vascular_health` (7 members) — confirmed strict subset. No data loss from deletion.

### Substance card sample (current flat form)

```yaml
# alpha_gpc__sub_tzg5glskrd.yaml
name: Alpha-GPC
traits:
- class:nootropic
- risk:manual_review
```

```yaml
# ashwagandha__sub_810b76cde1.yaml
name: Ashwagandha
traits:
- class:adaptogen
- intake:food_preferred
- risk:manual_review
```

**After migration (DT-02), same cards:**

```yaml
name: Alpha-GPC
is:
- nootropic
risk:
- manual_review
```

```yaml
name: Ashwagandha
is:
- adaptogen
intake:
- food_preferred
risk:
- manual_review
```

200 substance YAML files — all have `traits:` field currently. All must be migrated.

### Planner contracts (DT-07)

**`Substance` dataclass** (`planner/contracts.py`, line 37–47):
```python
@dataclass(frozen=True, slots=True)
class Substance:
    id: str
    name: str
    traits: tuple[str, ...]   # ← CHANGE to 6 per-namespace tuples
    form: str | None = None
    aliases: tuple[str, ...] = ()
    notes: str | None = None
    concerns: tuple[Concern, ...] = ()
    prefer_with: tuple[str, ...] = ()
```

New shape:
```python
    is_: tuple[str, ...] = ()       # note: is_ to avoid Python keyword
    intake: tuple[str, ...] = ()
    effect: tuple[str, ...] = ()
    risk: tuple[str, ...] = ()
    activity: tuple[str, ...] = ()
    dashboard: tuple[str, ...] = ()
```

`id` and `name` remain required (no default); all namespace fields default to `()`.

**`Dashboard` dataclass** (`planner/contracts.py`, line 89–96):
```python
@dataclass(frozen=True, slots=True)
class Dashboard:
    name: str
    description: str
    taking: tuple[DashboardMember, ...]   # ← REPLACE
    benefit: DashboardBenefit | None = None
    risk: DashboardRisk | None = None
    started: str | None = None
```

New shape: replace `taking` with `from_traits: dict[str, tuple[str, ...]]` (namespace → bare slugs). `DashboardMember` dataclass becomes dead code — remove.

**Substance loader** (`planner/cards/substance.py`, line 37–52): Currently reads `data.get("traits") or ()`. Change to read each namespace key: `data.get("is") or ()`, `data.get("intake") or ()`, etc. Note: YAML key `is` is not a Python keyword issue at the dict level — `data.get("is")` is fine.

**`check_substances()`** (`planner/cards/substance.py`, lines 177–247): Currently validates `substance.get("traits")` against `trait_ids` (line 235–239). Must change to iterate each namespace group: for each namespace key (`is`, `intake`, etc.), validate each bare slug against `trait_ids` for that namespace (i.e., check `f"{namespace}:{slug}"` is in `trait_ids`). Error message template per DT-08.

**Dashboard loader** (`planner/cards/dashboards.py`, lines 55–95): Currently reads `data.get("taking")` and builds `DashboardMember` tuples. Replace with reading `data.get("from_traits") or {}` into `dict[str, list[str]]`.

**`collect_dashboard_substance_refs()`** (`planner/cards/dashboards.py`, lines 98–109): Currently iterates `dashboard.taking` members and collects `member.substance` IDs. After refactor, this function's role inverts — substance refs come from substance cards (their `dashboard:` group) rather than from dashboard files. The function can be simplified or repurposed; `doctor.py` uses it at line 91 to contribute to `substance_refs` (which drives the `unused_substances` calculation). After refactor, dashboard files no longer reference substance IDs directly — substance cards reference dashboard slugs. `collect_dashboard_substance_refs()` should return an empty set or be removed; `doctor.py`'s `substance_refs` computation should instead check whether each substance is referenced by products, relations, or prefer_with (dashboards become pull-based, not push-based).

**`build_dashboard_review()`** (`planner/cards/dashboards.py`, lines 112–166): Currently iterates `dashboard.taking` to build covered/inactive/missing lists. Must change to: for each dashboard, resolve membership by scanning all substances and checking if any of the substance's per-namespace lists intersects with the dashboard's `from_traits` namespace entries. Pass the full substances dict (already available as parameter) and active/inactive sets.

**`check_dashboards()`** (`planner/cards/dashboards.py`, lines 169–208): Currently validates `taking[]` substance refs. Must change to validate `from_traits` slug refs against `trait_ids` per namespace.

**`effective_stack_item_traits()`** (`planner/engine/_scheduling.py`, lines 12–84): Iterates `substance.traits` at line 50. After refactor must iterate all namespace fields. The function is used for slot scoring — `dashboard:` slugs have no scheduling effects and should be excluded from the set fed to `compute_slot_score()`. Recommended: reconstruct a flat `set[str]` from `is_`, `intake`, `effect`, `risk`, `activity` (exclude `dashboard`) for scheduling purposes; keep `dashboard` accessible separately if needed for display (currently not used in scoring).

**`doctor.py`** (`planner/engine/doctor.py`): Line 55: `for trait_id in substance.traits` — must change to iterate all namespace fields. Line 91: `collect_dashboard_substance_refs(dashboard_files)` — see above; after refactor this returns empty set and the doctor's "unused substance" detection still works via products + relations + prefer_with.

### Check module — DT-08 hook points

**`cmd_check()`** (`planner/engine/check.py`): The check pipeline already calls:
1. `check_traits(trait_defs, traits_path)` — validates namespaces against `REGISTERED_NAMESPACES`
2. `check_substances(all_substance_files, trait_ids)` — validates trait refs; **hook here for substance-side ref-integrity**
3. `check_dashboards(dashboard_files, substance_ids, substances)` — validates dashboard refs; **hook here for dashboard-side ref-integrity**

No new error class needed — `CardLoadError` is already the established pattern. Use the same `f"{path}: ..."` format for consistency. The error messages must be prescriptive per DT-08: `"Unknown trait '{slug}' under namespace '{ns}:' in {path}:{line} — register it in data/traits.yaml under '{ns}:' first (with label and description)."` (line number may require tracking offset during YAML parse; simpler: omit line number and use file path only, matching existing error format).

**Existing trait ref check in `check_substances()`** (line 235–239):
```python
traits_raw = substance.get("traits") or []
for tid in traits_list:
    if tid not in trait_ids:
        errors.append(f"{sf}: trait '{tid}' not defined in traits.yaml")
```
Replace with: for each namespace key, for each bare slug, check `f"{namespace}:{slug}"` in `trait_ids`. Add to `errors` with the prescriptive message format.

**Existing `check_dashboards()`** (line 191–208): Currently checks `taking[]` substance refs. Replace taking-ref check with from_traits slug-ref check: for each namespace key in `from_traits`, for each bare slug, check `f"{namespace}:{slug}"` in `trait_ids`.

### schedule.yaml (DT-09)

Generated by `uv run python -m planner plan`. Top-level keys (from current file):
`summary`, `placement_notes`, `pillboxes`, `benefits`, `risks`, `warnings`, `kept_together`, `explanations` (plus comment blocks injected by `dump_schedule_yaml()`).

The `benefits` and `risks` sections are populated by `build_dashboard_review()` in `planner/cards/dashboards.py`. After refactor, the membership resolution logic in that function changes (from `taking[]` pull to `from_traits` push-from-substance), but the output shape of `benefits`/`risks` stays identical — `{name, covered, inactive, missing}` dicts.

**DT-09 requirement:** After migration, re-run `python -m planner plan` and verify that each surviving dashboard's covered/inactive/missing partitioning matches the pre-refactor baseline for all 13 retained clusters. `vasodilation_no_pathway` disappears from output; `vascular_health` should show its 7 members unchanged.

### Tests (DT-10)

**Tests requiring rewrite:**

1. `tests/test_phase_01.py:156–162` — `test_training_substances_have_expected_activity_traits()`:
   Currently checks `card["traits"]` for `activity:pre_workout` etc. After migration, substance YAML has `activity: [pre_workout]` not `traits: [activity:pre_workout]`. Rewrite to check `card.get("activity", [])` contains the bare slug.

2. `tests/test_phase_01.py:165–185` — `test_vascular_dashboard_taking_members_are_seven_known_substances()`:
   Checks `vascular["taking"]` length and substance IDs. After migration, `vascular_health.yaml` has no `taking` field. Rewrite to check `vascular["from_traits"]["dashboard"] == ["vascular_health"]` and that 7 substance cards carry `dashboard: [vascular_health]` (or derive membership via the loader and check resolved count = 7).

3. `tests/test_scheduling_units.py:65–66` — `make_substance()`:
   `Substance(id=sub_id, name=name, traits=())` — update to new field names.

4. `tests/test_schemas.py` — any fixture YAML inline in tests that uses `traits:` format needs updating.

**Fixtures to update:**
- Any YAML content in `tests/` that contains `traits:` field
- `tests/conftest.py` if it creates fixture substance cards

**New tests to add (DT-10):**
- Schema accepts grouped form: minimal substance with `is: [antioxidant]` passes `schema_errors()`
- Schema rejects old flat form: substance with `traits: [class:antioxidant]` fails validation
- Schema enforces `maxItems: 1` on `intake`: substance with `intake: [empty_preferred, food_required]` fails
- `from_traits` resolution: given substances with `dashboard: [connective_tissue_support]`, `build_dashboard_review()` puts them in covered/inactive
- Ref-integrity: substance with unknown slug `is: [unknown_slug]` fails `check_substances()`
- Ref-integrity: dashboard with `from_traits: {dashboard: [unknown_slug]}` fails `check_dashboards()`

### Docs scope (DT-11)

**`docs/domain-model.md`** — sections requiring change:
- "Trait" entry under Core Objects: rewrite to describe grouped namespace keys replacing flat list
- "Dashboard cluster" entry: rewrite to describe `from_traits` instead of `taking[]`
- "Trait Ontology" section: add/rewrite with each namespace, cardinality rules, intensional vs extensional semantics
- "Adding Data" YAML examples: all substance card examples show `traits: [...]` form — update to grouped form
- "Ownership Rules": bullet about "Put broad benefit/risk groupings in dashboard clusters" — update mechanism

**`docs/ontology-facts.md`** — sections requiring change:
- "Decided: Not Encoding" entries that say "encode as dashboard cluster": mechanism description ages out
- "Encoding Policy" final bullet: update
- Add intensional vs extensional paragraph for `from_traits`
- Add "Decided: Not Solving — rename ghost" entry

**`README.md`** — check for any `traits:` references in examples.

### SKILL.md scope (DT-12)

SKILL.md is 403 lines. Affected sections:

| Section | Lines | Change |
|---------|-------|--------|
| File Tree | ~21–43 | Refine `data/dashboards/` description: membership-via-tags + "grouped at rest, grouped in queries" |
| Add Or Enrich A Substance | 113–129 | Line 116: drop "The registry is grouped by namespace... substance cards still reference traits as `namespace:name`" — update to grouped shape. Line 117: update `traits: []` initial card. Line 121: drop hardcoded class-marker enumeration; replace with pointer to `data/traits.yaml` + `review-substance` suggestion. Add "Which namespace?" 3-line decision block. |
| Add Or Update A Dashboard | 139–143 | Full rewrite: replace `taking` workflow with `from_traits` workflow; explain pure-class vs operator-curated; bootstrap sequence (register in traits.yaml first, then tag substances); drop "sort taking alphabetically" |
| Minimal YAML Shapes | 145–198 | Update substance card example (remove `traits: []`, add grouped keys); update dashboard example (`from_traits:` instead of `taking:`) |
| Validation Contract | 200–207 | Add reference-integrity errors from DT-08; add doctor warning classes from DT-14 |
| Add new: Membership Flow | new | Textual decision tree (NOT ASCII visual) tracing substance tags → dashboard from_traits → resolved membership |
| Add new: Doctor Warning Playbook | new | WHEN to run doctor; per-warning-class decision trees for DT-14 (a)–(d) |

**`.planning/PROJECT.md` line 17** — namespace list refresh.

### readable_traits() and review-substance (DT-13)

**Current `readable_traits()`** (`planner/cards/traits.py`, lines 141–150):
```python
def readable_traits(trait_ids: set[str], trait_defs: dict[str, TraitDef]) -> list[str]:
    labels: list[str] = []
    for trait_id in sorted(trait_ids):
        if trait_id == "risk:manual_review":
            continue
        if trait_id.startswith("class:"):   # ← STALE after rename
            continue
        trait = trait_defs.get(trait_id)
        labels.append(trait.label if trait and trait.label else trait_id)
    return sorted(labels, key=str.casefold)
```

**Required change:** `startswith("class:")` → `startswith("is:")`. Also add exclusion for `startswith("dashboard:")` — dashboard membership tags are review-axes, not scheduling narrative. The input to this function will also change: callers pass a flat `set[str]` of prefixed trait IDs (`is:antioxidant`, `intake:food_preferred`, etc.); the function reconstructs this from the substance's per-namespace fields. Callers must flatten before calling, or the function signature changes to accept the namespace dict.

**`review-substance` output** (rendered by commands in `planner/engine/review.py`): After refactor, each namespace appears as a section heading with bare slugs underneath. The `print_trait_details()` function in `planner/cards/traits.py` (lines 128–138) renders `description`, `applies_when`, effects — unchanged, but it needs to be called with the reconstructed `TraitDef` for `dashboard:` namespace entries, which currently have no `effects` (informational only).

---

## Validation Architecture

### Unit tests required (DT-10)

- `test_substance_schema_accepts_grouped_form` — valid grouped substance YAML passes schema
- `test_substance_schema_rejects_flat_traits_form` — `traits: [class:antioxidant]` fails schema
- `test_substance_schema_enforces_intake_maxitems` — `intake: [empty_preferred, food_required]` fails schema
- `test_substance_schema_enforces_closed_keys` — `note: [foo]` as top-level field fails schema
- `test_from_traits_resolution_produces_correct_membership` — given substance with `dashboard: [connective_tissue_support]`, resolution returns it in covered set
- `test_ref_integrity_substance_unknown_slug` — `is: [unknown_slug]` triggers check error
- `test_ref_integrity_dashboard_unknown_slug` — `from_traits: {dashboard: [unknown_slug]}` triggers check error
- `test_ref_integrity_substance_cross_namespace` — slug in wrong namespace (e.g., `intake: [antioxidant]` where `antioxidant` is registered under `is:`) triggers error

### Integration checks

- `python -m planner check` exits 0 after full Stage 1 migration
- `python -m planner plan` regenerates schedule.yaml with identical covered/inactive/missing for 13 retained dashboards
- `uv run pytest` passes on migrated codebase
- `vasodilation_no_pathway` absent from `schedule.yaml` benefits/risks output

### Regression concerns

- `effective_stack_item_traits()` must NOT include `dashboard:` slugs in the set passed to `compute_slot_score()` — these have no `effects` in their `TraitDef` and would just be no-ops, but excluding them keeps the scoring surface clean and avoids future accidental effects if a `dashboard:` entry ever gets an `effects` block.
- `doctor.py` `substance_refs` currently includes refs from `collect_dashboard_substance_refs()`. After refactor, dashboards don't reference substances by ID. Removing this contribution must NOT cause previously referenced substances to appear as "unused" — verify that products + relations + prefer_with refs are sufficient to keep active substances out of the unused list.
- `check_traits()` validates namespaces against `REGISTERED_NAMESPACES`. After adding `dashboard` and removing `class` and `mechanism`, any `class:*` or `mechanism:*` trait in traits.yaml will fail. Confirm all `class:` entries are renamed to `is:` before running check.

---

## Implementation Order (Stage 1 — atomic commit)

The 10 DT tasks form a dependency chain. Within the single atomic commit, the logical order is:

1. **DT-01** — Update `schema/substance.schema.json` first. All subsequent substance YAML changes must validate against the new schema.
2. **DT-05** — Update `schema/dashboard.schema.json`. All subsequent dashboard YAML changes must validate against it.
3. **DT-03** — Add `dashboard:*` namespace to `data/traits.yaml`; rename `class` → `is`. Update `REGISTERED_NAMESPACES` in `planner/io.py` simultaneously (same commit — they must stay in sync or `check_traits()` fails).
4. **DT-07** — Update `planner/contracts.py` dataclasses and all loader/resolver code in `planner/cards/substance.py`, `planner/cards/dashboards.py`, `planner/engine/_scheduling.py`, `planner/engine/doctor.py`. Code must compile and import cleanly before data migration.
5. **DT-02** — Migrate all 200 substance YAML files from flat `traits:` to grouped keys. New schema validates them; new loader reads them.
6. **DT-04** — Tag substance cards with `dashboard:` entries from current `taking[]` migration map (13 clusters × their members).
7. **DT-06** — Rewrite all 13 `data/dashboards/*.yaml` to `from_traits:`. Delete `vasodilation_no_pathway.yaml`.
8. **DT-08** — Add reference-integrity checks to `check_substances()` and `check_dashboards()`.
9. **DT-10** — Update and add tests. All tests must pass before proceeding.
10. **DT-09** — Run `python -m planner plan`, verify schedule.yaml output matches baseline, commit regenerated file.

**Why DT-07 before DT-02/DT-04/DT-06:** The Python loader must understand the new YAML shape before the YAML files are migrated. Migrating data before updating the loader causes import errors on every test run.

**Why DT-03 before DT-07:** `REGISTERED_NAMESPACES` is referenced in `check_traits()` which is called during `cmd_check()`. If the namespace update is deferred, any intermediate `check` run fails.

---

## Known Risks and Gotchas

1. **`is` vs `is_` in Python dataclass:** YAML key `is` is a Python keyword. In the `Substance` dataclass, use `is_` as the field name. The loader uses `data.get("is")` (dict key, not keyword — safe). All call sites using `substance.traits` must change to use the new field names; `substance.is_` is the correct Python access pattern.

2. **`collect_dashboard_substance_refs()` inversion:** This function currently pulls substance IDs from dashboard files. After refactor, it should return an empty set (or be removed). Its only consumer is `doctor.py` line 91 where it contributes to `substance_refs` (which prevents substances from appearing unused). After removing this contribution, verify that every active substance is still reachable via product components — they all should be, since the unused detection is about "no product references this substance."

3. **200 substance files — migration scale:** DT-02 + DT-04 together touch every substance card. The planner must do this programmatically (a migration script or manual-with-script aid), not by hand. Risk: a substance with mixed-namespace traits (`class:antioxidant`, `intake:food_preferred`, `risk:manual_review`) must be correctly split into 3 separate top-level keys. The migration logic is a simple grouping operation but must be applied consistently.

4. **`effective_stack_item_traits()` trait set reconstruction:** Currently iterates `substance.traits` (line 50). After refactor, must reconstruct from 5 scheduling-relevant namespaces (`is_`, `intake`, `effect`, `risk`, `activity`) as prefixed IDs for lookup in `trait_defs`. The flat set used for scoring should be `{f"is:{s}" for s in substance.is_} | {f"intake:{s}" for s in substance.intake} | ...` (excluding `dashboard`). This is the critical correctness point — omitting any namespace from the reconstruction changes slot scoring.

5. **`check` sort order for dashboard members removed:** `check_dashboards()` currently validates that `taking` is sorted alphabetically. After migration, this check is gone (dashboards have no member list to sort). No replacement needed.

6. **`DashboardMember` removal:** `DashboardMember` dataclass in `contracts.py` becomes dead code. Remove it. Also remove `_build_dashboard_member()` helper in `dashboards.py`.

7. **Test `test_vascular_dashboard_taking_members_are_seven_known_substances`:** This test directly reads `vascular["taking"]`. After migration it will KeyError. Must be rewritten before running pytest.

8. **`mechanism` namespace dead entry in `REGISTERED_NAMESPACES`:** Currently `planner/io.py` lists `"mechanism"` in `REGISTERED_NAMESPACES` despite no `mechanism:*` traits in `traits.yaml`. This is already dead code. DT-03 should remove it as part of the namespace update.

9. **Doctor DT-14 warning logic (Stage 2):** The four DT-14 warning classes require iterating substance cards to check `dashboard:` group vs traits.yaml registry vs dashboard files. This is a new scan loop in `doctor.py` — `collect_orphans()` currently has no dashboard-trait lifecycle check. The new checks are additive (new keys in the returned dict).

## RESEARCH COMPLETE
