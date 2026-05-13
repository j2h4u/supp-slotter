# Phase 9: Planner / Reviewer Ontology Split — Research

**Researched:** 2026-05-13
**Domain:** Internal YAML data-model refactor + Python planner code restructuring
**Confidence:** HIGH — all findings from direct codebase inspection; no external libraries involved

---

## Summary

Phase 9 restructures the substance card schema from a flat 6-namespace layout
(`is`, `intake`, `effect`, `risk`, `activity`, `dashboard`) into two explicit
top-level sections: `schedule:` (Planner input) and `knowledge:` (Reviewer
input). The design is fully specified in `docs/ontology-v2.md`, which was
reviewed as a primary source.

The core migration challenge is that 198 substance cards must be rewritten
atomically, the Python contracts/loaders must support both old and new shapes
during transition, and the scheduler must continue to produce identical output
after the migration. The `effect:` namespace presents the most nuanced split:
three slugs (`energy_like`, `sleep_disruptive`, `sleep_support`) carry actual
slot-scoring rules and must move to `schedule.timing:`, while all other
`effect:` slugs are purely informational and move to `knowledge.effect:`.
Currently only those three slugs exist in `data/traits.yaml` under `effect:`,
so there is no ambiguity in the split.

Additionally, `separate_from:` on individual trait definitions must be retired
and replaced with class-level `competes` entries in `relations.yaml`, and a new
`planner review` command must be introduced to replace the advisory output of
`planner audit`.

**Primary recommendation:** Treat this as two atomic stages exactly as Phase 8
did. Stage 1 (single commit): schema + contract + loader + data migration.
Stage 2 (follow-on): `planner review` command, class-level competes, SKILL.md
and docs updates. The migration script can be a one-off Python script run
in-tree and then deleted.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Substance card YAML shape | Data layer (`data/substances/`) | Schema (`schema/substance.schema.json`) | Cards are the source of truth; schema enforces the shape |
| Dual-format loader (migration period) | `planner/cards/substance.py` | `planner/contracts.py` | Loader reads disk; contract defines the in-memory shape |
| Scheduling trait resolution | `planner/engine/_scheduling.py` | `planner/cards/traits.py` | `effective_stack_item_traits` aggregates per-product; `traits.py` defines which namespaces carry slot effects |
| Reviewer output | `planner/engine/review.py` (new `cmd_review`) | `planner/cards/substance.py` | New command reads `knowledge:` section |
| Class-level competes enforcement | `planner/engine/plan.py` (`_slot_is_blocked`) | `planner/cards/relations.py` | Planner resolves class membership from `knowledge.is:`, applies block |
| `planner audit` retirement | `planner/__main__.py` | `planner/engine/audit.py` | Routing change: advisory content migrates to `review`, cleanup stays in `audit` or retires |
| traits.yaml `timing:` namespace | `data/traits.yaml` | `planner/io.py` (REGISTERED_NAMESPACES) | New namespace must be registered to pass `check_traits` |
| Dashboard `from_traits` namespace update | `data/dashboards/*.yaml` | `planner/cards/dashboards.py` | One dashboard uses `from_traits: { is: [...] }` which maps to `knowledge.is:` in v2 |

---

## Standard Stack

No external packages. This is a pure internal refactor.

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.x (uv-managed) | Runtime |
| PyYAML | (already in uv.lock) | YAML read/write |
| jsonschema | (already in uv.lock) | Schema validation via `schema_errors()` |
| pytest | (already in uv.lock) | Test runner |
| ruff + pyright | (already in justfile) | Lint + type check |

**Installation:** No new packages needed.

---

## Package Legitimacy Audit

Not applicable — no new packages are installed in this phase.

---

## Architecture Patterns

### Recommended Project Structure (changes only)

```
schema/
├── substance.schema.json     # rewrite: schedule: + knowledge: nested structure
├── templates/
│   └── substance.yaml        # update to new shape
data/traits.yaml              # add timing: namespace, retire separate_from: fields
data/relations.yaml           # add class-level competes: entries
data/substances/*.yaml        # 198 cards rewritten
data/dashboards/*.yaml        # one card: antioxidant_protection.yaml (is: -> knowledge.is:)
planner/
├── contracts.py              # Substance dataclass: new nested fields
├── cards/
│   ├── substance.py          # load_substance: dual-format reader
│   └── traits.py             # NAMESPACE_ORDER update, timing: namespace
├── engine/
│   ├── _scheduling.py        # effective_stack_item_traits: read schedule.* fields
│   ├── plan.py               # _slot_is_blocked: class-level competes lookup
│   ├── review.py             # new cmd_review (currently review-substance only)
│   └── audit.py              # remove advisory output that moves to review
├── __main__.py               # add `review` subcommand, update/retire `audit`
tests/
├── test_schemas.py           # new: accepts schedule:/knowledge: shape; rejects old flat
├── test_scheduling_units.py  # update fixtures to new Substance shape
```

### Pattern 1: Dual-Format Loader (Migration Compatibility)

**What:** `load_substance()` detects card format by key presence and reads either path.
**When to use:** During Stage 1 only — after all 198 cards are migrated, the fallback is removed.

```python
# Source: docs/ontology-v2.md (Migration Strategy section) [CITED: docs/ontology-v2.md]
def load_substance(path: Path) -> Substance:
    data = load_card_mapping(path, "substance")
    errors = schema_errors(data, "substance", path)
    if errors:
        raise CardLoadError(path, errors[0])

    if "schedule" in data and any(k in data for k in ("intake", "effect", "risk", "activity")):
        # Ambiguous dual-format — reject immediately
        raise CardLoadError(path, f"{path}: card has both schedule: and flat fields — ambiguous")

    if "schedule" in data:
        # v2 nested format
        sched = data.get("schedule") or {}
        know = data.get("knowledge") or {}
        return Substance(
            id=data["id"],
            name=data["name"],
            intake=tuple(sched.get("intake") or [sched["intake"]] if sched.get("intake") else []),
            timing=tuple(sched.get("timing") or [sched["timing"]] if sched.get("timing") else []),
            activity=tuple(sched.get("activity") or [sched["activity"]] if sched.get("activity") else []),
            prefer_with=tuple(sched.get("prefer_with") or ()),
            is_=tuple(know.get("is") or ()),
            effect=tuple(know.get("effect") or ()),
            risk=tuple(know.get("risk") or ()),
            dashboard=tuple(know.get("dashboard") or ()),
            pathway=tuple(know.get("pathway") or ()),
            # ... common fields
        )
    else:
        # v1 flat format (backward compat during migration)
        return Substance(...)  # existing logic unchanged
```

**Key note on ontology-v2.md field cardinality:** `intake` is a single slug
(not a list) in v2 — `schedule.intake: food_preferred`. Likewise `activity`
and `timing`. The existing Substance dataclass uses tuples; the loader must
wrap single-slug values into a 1-tuple or empty tuple. The schema must enforce
this cardinality.

### Pattern 2: Class-Level Competes Resolution

**What:** Planner reads `knowledge.is:` on all active substances, then checks
class-level `competes` entries in `relations.yaml` against those classes.
**When to use:** Slot-blocking for class-vs-class incompatibilities (e.g. mineral vs fat_soluble).

```python
# Source: docs/ontology-v2.md (Class-level competes section) [CITED: docs/ontology-v2.md]
# In _slot_is_blocked(), after existing substance-level competes check:
def _class_level_competes_blocked(
    item_classes: set[str],       # knowledge.is: slugs for the item being placed
    existing_classes: set[str],   # knowledge.is: slugs for items already in slot
    class_relations: list[dict],  # class-level competes entries from relations.yaml
) -> bool:
    for rel in class_relations:
        src = rel.get("source_class")
        tgt = rel.get("target_class")
        if src and tgt:
            if (src in item_classes and tgt in existing_classes) or \
               (tgt in item_classes and src in existing_classes):
                return True
    return False
```

**Relations.yaml v2 structure (class-level entries alongside existing substance-level):**
```yaml
competes:
  # existing substance-level (unchanged)
  - source_name: Zinc
    target_name: Copper
    reason: "..."

  # new class-level (v2)
  - source_class: mineral
    target_class: fat_soluble
    reason: "..."
```

The `Relation` dataclass in `contracts.py` needs two new optional fields:
`source_class: str | None` and `target_class: str | None`.

### Pattern 3: `planner review` Command

**What:** New subcommand that outputs structured facts from `knowledge:` section
of all active substance cards — concerns, relations status, pathway memberships,
knowledge gaps — for a smart agent to interpret.
**When to use:** After stack changes, before committing or as a routine agent check.

The existing `cmd_review_substance` (single-card checklist) is distinct from the
new `cmd_review` (full-stack structured review). The new command is essentially
the advisory portion of `cmd_audit` refactored to read from `knowledge:` fields.

### Anti-Patterns to Avoid

- **Reading `knowledge:` fields in the Planner's scheduling path:** `effective_stack_item_traits` must only read `schedule.*` fields plus `knowledge.is:` (narrowly, for class-level competes). Do not let `knowledge.risk:` or `knowledge.effect:` influence slot scoring — this is the whole point of the split.
- **Migrating cards one by one without an atomic commit:** Partial migration leaves `planner check` broken for unmigrated cards if the schema is updated first. Migrate schema + all 198 cards + code in one commit (same pattern as Phase 8 Stage 1).
- **Adding `timing:` slugs to `knowledge:` section:** `timing:` is a Planner field. The three timing slugs (`energy_like`, `sleep_disruptive`, `sleep_support`) must live under `schedule.timing:`, not `knowledge.effect:`.
- **Forgetting the `antioxidant_protection` dashboard:** It uses `from_traits: { is: [antioxidant] }`. After migration, `is:` lives under `knowledge.is:`. The dashboard resolution code in `substance_carries()` must map the `is` namespace key to `substance.is_` (same as today, but confirm the dashboard YAML namespace key does not need to change to `knowledge.is` — the namespace key in `from_traits` is just a string label; the resolver maps it to the field by convention).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Card migration (198 files) | A complex multi-pass migration framework | A single Python script (`scripts/migrate_substance_cards.py`) that reads flat, writes nested | 198 files is large but all follow the same mechanical mapping; a one-off script is faster and verifiable |
| Dual-format detection | A heuristic that guesses format from field names | Explicit `"schedule" in data` key check | `docs/ontology-v2.md` specifies this exact sentinel |
| Class membership lookup | Re-parsing traits.yaml at block-check time | Read `substance.is_` from the already-loaded `Substance` dataclass | Classes are already loaded into the contract |

---

## Current State Inventory (What Phase 8 Delivered)

This is critical context for Phase 9 planning.

| Aspect | Current (post-Phase 8) | Required (post-Phase 9) |
|--------|----------------------|------------------------|
| Substance schema | Flat top-level: `is:`, `intake:`, `effect:`, `risk:`, `activity:`, `dashboard:` | Nested: `schedule: {intake, timing, activity, prefer_with}` + `knowledge: {is, effect, risk, dashboard, pathway}` |
| Substance cards | 198 cards in flat grouped shape | 198 cards in nested shape |
| `effect:` slugs in use | 3: `energy_like`, `sleep_disruptive`, `sleep_support` (all scheduling) | `timing:` in `schedule:` section |
| `risk:` namespace | Used in scheduling (warning emission via `trait_def.warning`) | Moves to `knowledge:`, Reviewer surfaces it |
| `is:` namespace | Review-classification + narrow competes use | `knowledge.is:` — same uses, new location |
| `separate_from:` | Exists on `TraitDef.separate_from`; used by `must_separate()` in `_scheduling.py` | Retired; class-level competes in `relations.yaml` replace it |
| `planner audit` | Mix of advisory (concerns, relations) and cleanup candidates | Advisory portions move to `planner review`; cleanup candidates stay or retire with `audit` |
| Commands | `check`, `audit [--full]`, `find`, `review-substance`, `show` (default) | Add `review`; retire or slim `audit` |
| `traits.yaml` namespaces | `intake`, `effect`, `is`, `risk`, `activity`, `dashboard` | Add `timing:` (scheduling-relevant effects only); `effect:` entries with `effects:` rules move to `timing:` |
| `REGISTERED_NAMESPACES` in `io.py` | `{intake, effect, is, risk, activity, dashboard}` | Add `timing`, remove `effect` if no `effect:` traits remain with `effects:` rules |
| `dashboard.from_traits` namespace keys | `is`, `dashboard` (currently used) | Unchanged — namespace key strings in `from_traits` are just labels for the resolver to map |
| Test fixtures | Use flat Substance dataclass shape | Must be updated to new nested or dual-format shape |

---

## Common Pitfalls

### Pitfall 1: `risk:` traits currently drive warning emission in the Planner path

**What goes wrong:** `effective_stack_item_traits` today includes `risk:*` in
`scheduling_traits`. In `_build_schedule_output`, the plan loop checks
`trait_def.warning` on every effective trait and emits a warning. After Phase 9,
`risk:` lives in `knowledge:` and the Planner must not read it. If this coupling
is not cleaned up, the Planner either silently drops safety warnings or crashes
on missing field.

**Why it happens:** Phase 8 explicitly noted that `risk:` slugs (e.g.
`manual_review`) were included in `scheduling_traits` inside
`effective_stack_item_traits`. See `_scheduling.py:53-58`:
```python
scheduling_traits = (
    {f"is:{s}" for s in substance.is_}
    | {f"intake:{s}" for s in substance.intake}
    | {f"effect:{s}" for s in substance.effect}
    | {f"risk:{s}" for s in substance.risk}      # <-- this line
    | {f"activity:{s}" for s in substance.activity}
)
```

**How to avoid:** After migration, `effective_stack_item_traits` must source from
`schedule.*` fields only, plus `knowledge.is:` (narrowly). Warning emission for
safety flags must move to `cmd_review` (Reviewer path).

**Warning signs:** Tests for `risk:manual_review` warning emission that pass
before the migration but not after — the warning mechanism must be wired into
`cmd_review`, not `cmd_plan`.

### Pitfall 2: `must_separate()` still reads `trait_def.separate_from` after retirement

**What goes wrong:** `separate_from:` is retired from trait definitions but
`must_separate()` in `_scheduling.py` still calls `trait.separate_from` on the
`TraitDef` dataclass. If the field is still present (even empty after migration),
code runs without errors but the old slot-blocking logic does nothing. Class-level
competes must be wired in separately or the block logic is silently lost.

**How to avoid:** Explicit removal of the `separate_from:` field handling from
`_scheduling.py` and `TraitDef`, combined with a test asserting class-level
competes blocks correctly.

### Pitfall 3: 198 substance cards — migration script correctness

**What goes wrong:** A mechanical mapping error in the migration script (e.g.,
misrouting `sleep_support` to `knowledge.effect:` instead of `schedule.timing:`)
propagates across all affected cards silently because `planner check` validates
schema shape but not semantic correctness of which slugs belong in which section.

**How to avoid:** The migration script must explicitly route the three timing
slugs. Write a test that loads a migrated card and asserts that `sleep_support`
appears in `schedule.timing`, not in `knowledge.effect`. Run `planner check` and
the full test suite after migration before committing.

**Current effect slugs by routing:**
- `sleep_support` → `schedule.timing:` (has slot effects in traits.yaml)
- `sleep_disruptive` → `schedule.timing:` (has slot effects in traits.yaml)
- `energy_like` → `schedule.timing:` (has slot effects in traits.yaml)
- _(no other effect slugs exist currently — confirmed by grep across all 198 cards)_

### Pitfall 4: `timing:` namespace must be registered before `planner check` runs

**What goes wrong:** `check_traits()` validates every trait against
`REGISTERED_NAMESPACES`. If `timing:` is not added to `REGISTERED_NAMESPACES`
in `io.py`, all three moved trait entries immediately fail `planner check`.

**How to avoid:** Update `REGISTERED_NAMESPACES` and `NAMESPACE_ORDER` in the
same commit as the `traits.yaml` change.

### Pitfall 5: Dashboard `from_traits` namespace key clash

**What goes wrong:** `antioxidant_protection.yaml` uses `from_traits: { is: [antioxidant] }`.
After migration, `is:` lives at `knowledge.is:` in substance cards. The resolver
in `dashboards.py` uses `substance_carries(substance, ns, slug)`:
```python
def substance_carries(substance: Substance, namespace: str, slug: str) -> bool:
    ...
```
If the namespace key in `from_traits` is still `"is"` but the resolver now maps
`"is"` to `substance.knowledge.is_`, the mapping must be updated. If it still
maps to `substance.is_` (now an empty field on a v2 Substance), the cluster
silently empties.

**How to avoid:** Verify `substance_carries()` maps `"is"` namespace key to the
correct Substance field after the dataclass change. Two options: keep the key as
`"is"` and update the resolver, or update the dashboard YAML to `"knowledge.is"`
— the design doc says "dashboard YAML files — `from_traits:` namespace references
update from `{ns: is}` to `{ns: knowledge.is}`" [CITED: docs/ontology-v2.md],
meaning the YAML key changes AND the resolver mapping changes.

### Pitfall 6: `planner review` vs `planner review-substance` naming collision

**What goes wrong:** The existing `review-substance` subcommand will be adjacent
to the new `review` subcommand. argparse subcommand matching could be ambiguous
if a user types `planner rev`.

**How to avoid:** This is low-risk (argparse handles abbreviated commands predictably)
but document both in the help text. The design doc explicitly names the new command
`planner review` [CITED: docs/ontology-v2.md].

---

## Code Examples

### Current `Substance` dataclass (contracts.py) — must change

```python
# Source: planner/contracts.py (current, post-Phase 8) [ASSUMED: internal codebase]
@dataclass(frozen=True, slots=True)
class Substance:
    id: str
    name: str
    is_: tuple[str, ...] = ()
    intake: tuple[str, ...] = ()
    effect: tuple[str, ...] = ()
    risk: tuple[str, ...] = ()
    activity: tuple[str, ...] = ()
    dashboard: tuple[str, ...] = ()
    form: str | None = None
    aliases: tuple[str, ...] = ()
    notes: str | None = None
    concerns: tuple[Concern, ...] = ()
    prefer_with: tuple[str, ...] = ()
```

### Target `Substance` dataclass (v2)

```python
# Source: docs/ontology-v2.md [CITED: docs/ontology-v2.md]
@dataclass(frozen=True, slots=True)
class Substance:
    id: str
    name: str
    # --- schedule: section (Planner reads these) ---
    intake: tuple[str, ...] = ()       # 0 or 1 slug (schedule.intake)
    timing: tuple[str, ...] = ()       # 0 or 1 slug (schedule.timing) — NEW
    activity: tuple[str, ...] = ()     # 0 or 1 slug (schedule.activity)
    prefer_with: tuple[str, ...] = ()  # sub_* IDs (schedule.prefer_with)
    # --- knowledge: section (Reviewer reads these) ---
    is_: tuple[str, ...] = ()          # structural classification
    effect: tuple[str, ...] = ()       # pharmacological effects (non-scheduling)
    risk: tuple[str, ...] = ()         # safety/interaction flags
    dashboard: tuple[str, ...] = ()    # editorial cluster membership
    pathway: tuple[str, ...] = ()      # metabolic pathway membership — NEW
    # --- common (neither actor) ---
    form: str | None = None
    aliases: tuple[str, ...] = ()
    notes: str | None = None
    concerns: tuple[Concern, ...] = ()
```

### `effective_stack_item_traits` — scheduling fields only (post-migration)

```python
# Source: planner/engine/_scheduling.py (current) [ASSUMED: internal codebase]
# After migration: remove risk: from scheduling_traits; add timing:
scheduling_traits = (
    {f"intake:{s}" for s in substance.intake}
    | {f"timing:{s}" for s in substance.timing}       # replaces effect: scheduling slugs
    | {f"activity:{s}" for s in substance.activity}
    # is: added ONLY when class-level competes are being checked, not here
)
```

### Migration script sketch (one-off)

```python
# Source: docs/ontology-v2.md (Migration Strategy) [CITED: docs/ontology-v2.md]
TIMING_SLUGS = {"energy_like", "sleep_disruptive", "sleep_support"}

def migrate_card(data: dict) -> dict:
    """Rewrite flat grouped card to schedule:/knowledge: nested shape."""
    if "schedule" in data:
        return data  # already migrated

    # Route effect: slugs
    effect_slugs = data.pop("effect", []) or []
    timing_slugs = [s for s in effect_slugs if s in TIMING_SLUGS]
    knowledge_effect_slugs = [s for s in effect_slugs if s not in TIMING_SLUGS]

    schedule: dict = {}
    intake = data.pop("intake", [])
    if intake:
        schedule["intake"] = intake[0] if isinstance(intake, list) else intake
    if timing_slugs:
        schedule["timing"] = timing_slugs[0]  # max 1 per design
    activity = data.pop("activity", [])
    if activity:
        schedule["activity"] = activity[0] if isinstance(activity, list) else activity
    prefer_with = data.pop("prefer_with", None)
    if prefer_with:
        schedule["prefer_with"] = prefer_with

    knowledge: dict = {}
    for ns in ("is", "effect", "risk", "dashboard"):
        key = ns
        if ns == "effect":
            val = knowledge_effect_slugs
        else:
            val = data.pop(ns, []) or []
        if val:
            knowledge[key] = val

    # Rebuild card
    result: dict = {}
    for k in ("id", "name", "form", "aliases", "notes", "concerns"):
        if k in data:
            result[k] = data[k]
    if schedule:
        result["schedule"] = schedule
    if knowledge:
        result["knowledge"] = knowledge
    return result
```

---

## State of the Art

| Old Approach | Current Approach (post-Phase 9) | Impact |
|--------------|--------------------------------|--------|
| Flat namespace (`risk:` in Planner path) | `risk:` in `knowledge:` — Reviewer only | Planner no longer emits safety warnings; `planner review` handles them |
| `separate_from:` on TraitDef | Class-level `competes` in `relations.yaml` | Separation rules are centralized, visible, and typed as relations |
| `planner audit` mixing scheduling hygiene and knowledge review | `planner review` for knowledge, `audit` slimmed or retired | Cleaner actor boundary |
| `effect:` for both timing and pharmacology | `schedule.timing:` for timing, `knowledge.effect:` for pharmacology | Explicit; no ambiguity about what drives slot assignment |

**Deprecated/outdated after Phase 9:**
- `separate_from:` field on `TraitDef` dataclass — retire
- `must_separate()` in `_scheduling.py` using `trait_def.separate_from` — remove or replace with class-level competes
- `planner audit` advisory output — migrate to `planner review`

---

## Open Questions (RESOLVED)

All four questions were resolved during plan authoring. The plans below
implement each recommendation as a concrete task. Markers added 2026-05-13.

1. **Does `planner audit` survive Phase 9?**
   - What we know: The design doc says "planner audit is retired. Its output splits: Scheduling cleanup → `planner schedule --cleanup` flag or separate subcommand; Concerns, relations, knowledge → `planner review`."
   - What's unclear: The `--cleanup` subcommand or flag is mentioned but not fully specified. `audit`'s cleanup-candidate section (unused substances, similar names, empty stacks) could stay in a slimmed `audit`, or move to a `check --full` flag, or a new `schedule --cleanup`.
   - Recommendation: In Phase 9, keep `audit` for cleanup candidates (non-advisory structural hygiene) and add `review` for knowledge/advisory output. Formally deprecating `audit` entirely can be a follow-on quick task.
   - **RESOLVED:** Keep `audit` for cleanup candidates only. Plan 02 Task 3a updates `_collect_cleanup_sections` in `planner/engine/audit.py` to iterate the v2 Substance field names so the cleanup pass continues to work. Advisory output (concerns, relations status, pathway memberships, knowledge gaps) migrates to a new `planner review` command in a follow-on plan within this phase. Formal deprecation of `audit` is deferred.

2. **`planner review` output format**
   - What we know: "structured facts about the active stack — concerns, relations status, pathway memberships, knowledge gaps" [CITED: docs/ontology-v2.md]. The design says it reports; a smart agent interprets.
   - What's unclear: Whether the output is structured YAML/JSON for agent consumption or human-readable prose like `audit`. For Phase 9, human-readable prose (matching `audit`'s style) is safest and avoids new output contract obligations.
   - Recommendation: Start with human-readable prose. Structured output format can be a separate phase.
   - **RESOLVED:** Human-readable prose, matching the current `audit` advisory section style. Structured (YAML/JSON) output is explicitly deferred to a later phase to avoid committing to an output-contract obligation now.

3. **`pathway:` namespace — needs entries in `traits.yaml`?**
   - What we know: `knowledge.pathway:` is introduced in v2 for metabolic pathway membership. Currently no substance cards use it and `traits.yaml` has no `pathway:` namespace.
   - What's unclear: Should Phase 9 bootstrap `pathway:` with empty entries, or leave `pathway:` as an unregistered namespace initially?
   - Recommendation: Add `pathway:` to `REGISTERED_NAMESPACES` and `traits.yaml` (even with zero entries) so `check_traits` does not reject future cards that use it. Do not require any card to use it in Phase 9.
   - **RESOLVED:** Bootstrap with a single seed entry. Plan 01 Task 1 adds a top-level `pathway:` block to `data/traits.yaml` containing one entry `methylation_cycle` (with `label`, `description`, `applies_when` — no `effects:`) to satisfy the schema's `minProperties: 1` constraint and give a concrete reference slug. Plan 01 Task 3 adds `pathway` to `REGISTERED_NAMESPACES` in `planner/io.py` and to `NAMESPACE_ORDER` in `planner/cards/traits.py`. No substance card is required to use `pathway:` in Phase 9.

4. **`intake`, `timing`, `activity` cardinality: single slug vs list in schema**
   - What we know: The design doc shows these as scalar fields (`intake: food_preferred`, not a list). The current schema enforces `maxItems: 1` on the array form.
   - What's unclear: Whether to model them as strings (scalar) or arrays (single-element, matching current convention).
   - Recommendation: Keep as arrays with `maxItems: 1` in the JSON schema (matches current convention, simpler loaders). Store as 0-or-1 element tuples in the Substance dataclass. The migration script normalizes list-form from current cards to the new nested array-form.
   - **RESOLVED:** Arrays with `maxItems: 1`. Plan 02 Task 1 defines `schedule.intake`, `schedule.timing`, `schedule.activity` as arrays of slug strings with `maxItems: 1` in `schema/substance.schema.json`. The `Substance` dataclass stores them as `tuple[str, ...]` (0-or-1 element). The migration script in plan 03 normalizes any list-form values to the same array shape.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (already installed) |
| Config file | `pyproject.toml` (or pytest default) |
| Quick run command | `uv run python -m planner check && uv run pytest tests/test_schemas.py` |
| Full suite command | `just check` (ruff + pyright + planner check + pytest) |

### Phase Requirements → Test Map

| Behavior | Test Type | Automated Command | File Exists? |
|----------|-----------|-------------------|-------------|
| New schema accepts `schedule:/knowledge:` nested shape | unit | `uv run pytest tests/test_schemas.py::test_substance_schema_accepts_nested_form` | ❌ Wave 0 |
| New schema rejects old flat top-level `intake:/effect:/risk:` | unit | `uv run pytest tests/test_schemas.py::test_substance_schema_rejects_flat_form` | ❌ Wave 0 |
| Dual-format: card with BOTH flat and schedule: is rejected by `planner check` | unit | `uv run pytest tests/test_schemas.py::test_check_rejects_ambiguous_dual_format` | ❌ Wave 0 |
| `effective_stack_item_traits` reads only `schedule.*` fields | unit | `uv run pytest tests/test_scheduling_units.py::test_scheduling_reads_schedule_section_only` | ❌ Wave 0 |
| Class-level competes blocks co-placement of mineral + fat_soluble | unit | `uv run pytest tests/test_scheduling_units.py::test_class_level_competes_blocks_slot` | ❌ Wave 0 |
| Migration: all 198 cards pass `planner check` after rewrite | integration | `uv run python -m planner check` | ✅ (planner check itself) |
| Schedule regression: `total_score` and slot assignment unchanged after migration | integration | `uv run pytest tests/test_phase_03.py::test_schedule_baseline_remains_stable` | ✅ (update fixture shape) |
| `planner review` command exits 0 and produces non-empty output | smoke | `uv run pytest tests/test_review_command.py` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run python -m planner check && uv run pytest tests/test_schemas.py tests/test_scheduling_units.py`
- **Per wave merge:** `just check`
- **Phase gate:** `just check` green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_schemas.py` — add nested-form acceptance tests (file exists, extend it)
- [ ] `tests/test_scheduling_units.py` — update Substance fixtures to new dataclass shape (file exists, update fixtures)
- [ ] `tests/test_review_command.py` — new file covering `cmd_review` smoke and output shape

---

## Security Domain

This phase has no authentication, network calls, cryptographic operations, or user input beyond YAML file reading. ASVS categories V2/V3/V4/V6 do not apply. V5 (input validation) is addressed by the existing JSON schema validation path (`schema_errors()`), which this phase extends but does not weaken.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (uv) | All planner commands | ✓ | system | — |
| pytest | Test suite | ✓ | in uv.lock | — |
| ruff | Lint | ✓ | justfile | — |
| pyright | Type check | ✓ | justfile | — |

No missing dependencies.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `effect:` namespace currently has exactly 3 slugs (`energy_like`, `sleep_disruptive`, `sleep_support`) — all scheduling-relevant — confirmed by Python grep across 198 cards. Zero non-scheduling effect slugs exist on substance cards today. | Common Pitfalls / Migration Script | Low — grep confirmed this directly from disk |
| A2 | `antioxidant_protection.yaml` is the only dashboard using a non-`dashboard:` namespace in `from_traits:` (uses `is:`). All others use `dashboard:`. | Pitfall 5 | Low — confirmed by iterating all 13 dashboards |
| A3 | No `separate_from:` fields exist in `data/traits.yaml` (grep returned no output). Thus retiring `must_separate()` has no data-side impact. | State of the Art | Low — confirmed by grep |
| A4 | `pathway:` namespace is new in v2 and no current substance cards use it. | Open Questions #3 | Low — grep confirmed; zero substance cards have `pathway:` |
| A5 | The design doc's command table (`planner schedule` replacing default plan command) may be aspirational — implementing a rename of the default command is not required for Phase 9 correctness. The existing default `show` + implicit plan behavior can remain. | Architecture Patterns | Medium — if the planner expects `schedule` as a subcommand name, `__main__.py` needs a new routing entry; if it's just a naming note in the doc, no change needed. Confirm with operator before renaming. |

---

## Sources

### Primary (HIGH confidence)

- `docs/ontology-v2.md` — authoritative design spec for Phase 9; read in full
- `planner/contracts.py` — current Substance dataclass and all contract types
- `planner/engine/_scheduling.py` — full scheduling logic including `effective_stack_item_traits` and `must_separate`
- `planner/cards/substance.py` — loader, checker, registry
- `planner/cards/traits.py` — NAMESPACE_ORDER, load_traits, check_traits
- `planner/engine/audit.py` — advisory and cleanup output that Phase 9 splits
- `data/traits.yaml` — current namespace + trait definitions (full file read)
- `data/relations.yaml` — current relation structure (full file read)
- `schema/substance.schema.json` — current schema (full file read)
- Python grep/count across all 198 substance cards in `data/substances/`
- All 13 dashboard `from_traits` configurations

### Secondary (MEDIUM confidence)

- `planner/engine/review.py` — existing `cmd_review_substance` implementation that informs the new `cmd_review` design
- `planner/engine/plan.py` (`_slot_is_blocked`) — how class-level competes must hook in
- `.planning/STATE.md` — Phase 8 decisions and accumulated context
- `SKILL.md` — agent entrypoint; must be updated in Stage 2

---

## Metadata

**Confidence breakdown:**

- Schema and data migration scope: HIGH — counted cards, read current schema, confirmed effect slug routing
- Code change scope: HIGH — traced the full call chain from loader through scheduler through warning emission
- `planner review` output format: MEDIUM — design doc describes purpose but not output format in detail; confirmed it replaces advisory audit output
- Class-level competes implementation: HIGH — design doc specifies exact YAML structure; implementation pattern is straightforward extension of existing `_slot_is_blocked`

**Research date:** 2026-05-13
**Valid until:** Indefinite — pure internal codebase; no external dependencies
