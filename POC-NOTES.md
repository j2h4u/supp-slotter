# POC: SurrealDB-backed relations layer

**Branch**: `poc/surrealdb-relations`  
**Date**: 2026-05-15  
**Status**: Hypothesis confirmed — 10/10 equivalence tests pass on real `data/`.

## What was tested

Three representative functions from `planner/cards/relations.py`, each covering
a distinct query archetype:

| Archetype | Function | SurrealQL pattern |
|---|---|---|
| Both endpoints active | `collect_antagonizing_relations` | `src ANYINSIDE $active AND tgt ANYINSIDE $active` |
| One endpoint active, other absent | `collect_missing_balance_relations` | `src ANYINSIDE $active AND tgt NONEINSIDE $active` (×2 directions) |
| Graph pattern inside one entity | `collect_intra_product_relation_conflicts` | `src ANYINSIDE $components AND tgt ANYINSIDE $components` + pair-derivation in Python |

The SurrealDB versions live in `planner/cards/relations_surreal.py` alongside
the originals. Equivalence verified in `tests/test_poc_surrealdb.py` across
three active-set regimes (all, partial, empty) and four relation types for
intra-product. Output dicts are byte-identical after sort-normalisation.

## LOC accounting

Counted only the code that implements the three functions and their support
machinery (not the rest of `relations.py`):

| | Original Python | SurrealDB-backed |
|---|---|---|
| Endpoint-matching helpers (id-OR-name) | ~50 LOC | 0 LOC (resolved once in loader) |
| Warning-emit helper(s) | ~47 LOC (`_append_missing_relation_warning`) | ~17 LOC (`_warning_from_row`) |
| Pair/scan plumbing | ~95 LOC (`global_relation_matches`, `components_have_global_relation`, `collect_intra_product_…`) | ~50 LOC (one query + `_find_matching_row_for_pair`) |
| Two collect_* query functions | ~63 LOC | ~46 LOC (incl. forward+reverse balance + dedup) |
| Loader / model conversion | ~37 LOC (`load_global_relations`) | ~50 LOC (`build_surreal_db` — also handles substances + products) |
| Protocol/types | 0 | ~12 LOC |
| **Total (matching scope)** | **~292 LOC** | **~175 LOC** |

Net: about **40% reduction** in the matching/query-side surface, with the
matching-by-id-OR-name logic collapsing entirely into the loader.

## Where the win actually came from

The original code carries the **"match by id OR by name"** semantic through
every callsite — `substance_matches_relation_endpoint`,
`relation_endpoint_is_active`, `relation_endpoint_display`, and every caller
of these. In SurrealDB the loader pre-resolves each relation endpoint into a
list of substance IDs and stores it on the record. Queries then become
**array-set arithmetic** (`ANYINSIDE` / `NONEINSIDE`), which SurrealQL
expresses in one line per condition.

Side-by-side, the antagonising-pairs query:

**Python (≈42 LOC of body + helpers)**

```python
def collect_antagonizing_relations(substances, active, global_relations):
    warnings, seen = [], set()
    for relation in global_relations or []:
        if relation.type != "antagonizes":
            continue
        if not relation_endpoint_is_active(relation, "source", substances, active) \
        or not relation_endpoint_is_active(relation, "target", substances, active):
            continue
        source_key, source_name = relation_endpoint_display(relation, "source", substances)
        target_key, target_name = relation_endpoint_display(relation, "target", substances)
        warning_key = (source_key, "antagonizes", target_key)
        if warning_key in seen:
            continue
        seen.add(warning_key)
        # … build warning dict
```

…plus the bodies of `relation_endpoint_is_active`, `relation_endpoint_display`,
`substance_matches_relation_endpoint`, `_endpoint_fields` (~50 LOC of
supporting machinery).

**SurrealDB (1 query + 7 LOC of dedup)**

```sql
SELECT src_key, tgt_key, src_display, tgt_display, reason, action, severity
FROM relation
WHERE type = 'antagonizes'
  AND src_substances ANYINSIDE $active
  AND tgt_substances ANYINSIDE $active
```

```python
seen = set()
warnings = []
for row in rows:
    key = (row["src_key"], "antagonizes", row["tgt_key"])
    if key in seen:
        continue
    seen.add(key)
    warnings.append(_warning_from_row(row, "antagonizes_substance_present"))
```

The relation between concept and code is direct — no plumbing in between.

## Surprises

1. **SurrealQL has no top-level `UNION`.** `collect_missing_balance` needs the
   forward and reverse directions; in SQL this would be one UNION query. In
   SurrealQL it's two separate `.query()` calls plus a Python merge. Not
   painful, but worth noting.
2. **The Python SDK uses internal types** (`RecordIdType`, `Value`) that don't
   conform cleanly to a plain `Protocol`. Resolved by `cast()` at the single
   factory site (`build_surreal_db`) plus a positional-only Protocol for
   downstream functions — clean seam, no broad ignores.
3. **`Surreal` is a factory function, not a class.** Pyright correctly refuses
   it as a type annotation. Use `BlockingEmbeddedSurrealConnection` directly
   if you want the concrete type, or a Protocol like we did.
4. **Records auto-coerce `id` into `RecordID(table_name, record_id)`** on
   return. Querying back gives you the full `RecordID` object, not the bare
   string. Didn't matter for this POC because all dedup uses the separately
   stored `src_key`/`tgt_key` fields, not record IDs.
5. **Embedded mode (`mem://`) needs zero setup** — no daemon, no signin, no
   namespace beyond a one-liner `.use("ns", "db")`. Drop-in.

## Risks and gaps

- **SDK type hints are sparse.** Pyright strict needs a Protocol or local
  cast for any non-trivial usage. The Protocol approach scales — we'd write
  one per pattern of use, not per query.
- **Loader is the single point of failure for "match by id OR by name".** If
  resolution there is wrong, every downstream query is wrong silently. The
  equivalence tests against the canonical Python implementation guard against
  this for now; if Python relations.py is removed, we'd want unit tests on
  the resolution helpers directly.
- **`build_surreal_db` walks every substance and relation on construction.**
  ~250 substances + ~50 relations + ~50 products in current data = sub-second.
  Scales linearly; no concern for personal-use volume.
- **No FK constraints used.** We pre-resolve endpoints in Python, so we don't
  get the "integrity-constraints-as-documentation" win that would come from
  SurrealDB schema definitions. Worth a follow-up if we keep going — that
  would put `check_global_relations` under the schema rather than in code.

## Recommended next steps (if we keep going)

1. **Port the rest of `relations.py`** — `collect_missing_support_relations`,
   `check_global_relations`, `collect_substance_relation_matches`,
   `print_central_relation_matches`. Each follows the patterns proved here.
2. **Port `_collect_cleanup_sections` in `audit.py`** — this is the other
   high-density relational workload (`NOT EXISTS` / `EXCEPT` queries).
3. **Define schemas in SurrealDB** with `DEFINE TABLE … SCHEMAFULL` and field
   types. Lifts integrity checks out of `check_*` functions into the engine.
4. **Single shared `build_surreal_db`** call at command entry; pass the
   session into every consumer instead of rebuilding per-call.

## What I'd hold off on

- **No graph traversal (`->relation->substance` syntax) used here.** The data
  shape didn't need it for these three queries — array-set arithmetic was
  enough. If transitive queries appear later (e.g. "supports chain ≥2 hops"),
  that's when graph syntax pays off.
- **No vector / full-text / time-series features touched.** SurrealDB has
  them; we don't need them for this domain.

## Verification

```sh
git checkout poc/surrealdb-relations
just check  # 105 tests pass (initial POC: 115 incl. equivalence; post-migration: 105)
```

---

## Update 2026-05-15: full migration completed

The POC convinced; the rest of the work followed on the same branch.

**Commits (after the initial POC):**

1. `30237e7` — port `collect_missing_support_relations`
2. `d4d6624` — port `_collect_cleanup_sections` (with traits/stacks/pillboxes/dashboards
   loader extension)
3. `82e91df` — port remaining public API: `global_relation_refs`,
   `component_sets_have_relation`, `collect_substance_relation_matches`,
   `print_central_relation_matches`
4. `65cf1cf` — wire `cmd_audit` to use the SurrealDB-backed cleanup
5. `39a3ab3` — wire `cmd_review` (review-substance) to use SurrealDB-backed
   central-matches print
6. `e0b1c05` — wire `cmd_plan`: build `SurrealSession` once at command entry,
   thread it through `_build_active_index`, `_build_schedule_output`,
   `_run_plan_search`, `_slot_is_blocked`
7. `95160b4` — delete the now-orphan Python implementations from `relations.py`;
   delete `tests/test_poc_surrealdb.py` (equivalence tests obsolete);
   rewire two `test_scheduling_units.py` unit tests to the SurrealDB version
8. `6a0feac` — drop `_surreal` suffix from query function names (the suffix
   was POC-overlay noise; SurrealDB-backed versions are now canonical)

**Final architecture:**

- `planner/cards/relations.py` — dataclass-side helpers: `load_global_relations`,
  `check_global_relations` (raw-YAML validation pre-DB), `relation_endpoint_display`,
  `relation_endpoint_is_active`, `_endpoint_fields`.
- `planner/cards/relations_surreal.py` — SurrealDB-backed query layer:
  `SurrealSession` protocol, `build_surreal_db` loader, and the 8 query functions
  (now without `_surreal` suffix internally).
- `planner/engine/audit_surreal.py` — `collect_cleanup_sections` (mirrors the old
  Python helper one-for-one but builds its sets via SurrealQL against the session).
- `planner/cards/dashboards.py:collect_dashboard_substance_refs` — kept as Python
  (returns the empty set after a prior refactor; no SurrealDB equivalent needed).

**What stayed Python (and why):**

- `check_global_relations` — runs before SurrealDB construction; operates on raw
  YAML so schema breakage is reported pre-build.
- `relation_endpoint_display` / `relation_endpoint_is_active` — consumed by
  `review.py:_classify_relations` which iterates `Relation` dataclasses directly
  rather than going through the session. Different abstraction layer.
- `collect_similar_substances` — `SequenceMatcher` fuzzy match, no native
  SurrealQL equivalent.
- Plan scheduler optimization / branch-and-bound search — not a relational
  workload.

**Test suite impact:** runtime moved from ~41s to ~140s. The dominant cost is
`SurrealQL CONTAINS` lookups inside `_slot_is_blocked`, which fire for every
(item, slot, existing) triple during the slot-assignment search. Acceptable for
a personal-use tool; revisit if it becomes a feedback-loop friction point.
Possible optimizations later: pre-extract the candidate competes set once per
plan (it doesn't depend on slot state), or cache pair-existence lookups.

**Net code change across the migration** (relative to `main`): roughly +900,
−900 lines. The "old Python relation matching" surface is replaced by SurrealDB
loader + queries + a handful of Python helpers that stayed in `relations.py`.

POC hypothesis (relations.py becomes meaningfully cleaner under SurrealQL) —
confirmed and shipped.
