# Ontology v2 — Planner / Reviewer Split

Design document. Status: **draft, reviewed, pending phase planning**.

---

## Motivation

The current model conflates two actors in one flat namespace:

- **Planner** — a deterministic algorithm that assigns products to pillbox slots.
  Its only job is slot assignment based on timing and food constraints.
- **Reviewer** — a structured knowledge base. It surfaces facts about substances
  and stacks for consumption by a smart agent. The agent interprets; the Reviewer
  only reports.

Today `risk:` traits fire warnings inside planner output, `is:` drives both
scheduling rules and editorial grouping, and `planner audit` mixes scheduling
hygiene with knowledge review. The refactor enforces a hard boundary.

---

## Two Actors

### Planner

- **Input:** `schedule:` section of substance cards + `competes` relations
  (both substance-level and class-level — see below)
- **Output:** a deterministic slot assignment for every active product
- **Narrow exception:** reads `knowledge.is:` only to resolve class membership
  for class-level `competes` rules in `relations.yaml`. No other `knowledge:`
  field is read by the Planner.
- **Command:** `planner schedule`

### Reviewer

- **Input:** `knowledge:` section of substance cards + `balance`/`supports`/
  `antagonizes` relations
- **Output:** structured facts about the active stack — concerns, relations
  status, pathway memberships, knowledge gaps — for a smart agent to interpret
- **Constraint:** reads nothing that affects slot assignment; never drives placement
- **Command:** `planner review`

The Reviewer does not advise. It reports what the system knows. The smart agent
that consumes its output makes decisions.

---

## Substance Card Structure

```yaml
# ── Identity ─────────────────────────────────────────────────────────────────
id: sub_xxxxxxxxxx       # assigned by planner check
name: ""
form: ""                 # optional
aliases: []
notes: ""                # free-form; not parsed by either actor

# ── Planner section ───────────────────────────────────────────────────────────
schedule:
  intake: food_preferred   # one slug from intake: namespace in traits.yaml
  activity: ~              # one slug: pre_workout | post_workout | any_workout
  timing: ~                # one slug: energy_like | sleep_disruptive | sleep_support
                           # (scheduling-relevant effects only — see traits.yaml)
  prefer_with: []          # sub_* IDs — scheduling bonus for co-placement

# ── Reviewer section ─────────────────────────────────────────────────────────
knowledge:
  is: []          # structural classification: mineral, fat_soluble, botanical,
                  # enzyme, pharmaceutical, amino, vitamin, antioxidant, etc.
  effect: []      # pharmacological effects not relevant to timing:
                  # vasodilator, nootropic, ergogenic, adaptogen, etc.
  risk: []        # safety / interaction flags for the Reviewer to surface
  dashboard: []   # editorial cluster membership
  pathway: []     # metabolic pathway membership: tmao_precursor,
                  # methylation_cycle, etc.
  concerns:
  - kind: safety | data_quality | model_gap
    text: ""
```

### Key structural decisions

**`effect:` split into `schedule.timing:` and `knowledge.effect:`.** Some effect
slugs carry scheduling consequences — `energy_like` prefers wake slots and avoids
sleep slots; `sleep_disruptive` hard-blocks sleep slots; `sleep_support` prefers
sleep slots. These move to a new `schedule.timing:` field. All remaining effect
slugs (vasodilator, nootropic, ergogenic, adaptogen, etc.) are purely informational
and move to `knowledge.effect:`.

**`risk:` moves entirely to `knowledge:`.** The Planner never reads `risk:`.
Critical safety flags are surfaced by the Reviewer. The user contract is:
`planner schedule` produces slot assignments; `planner review` surfaces all
safety-relevant facts. A smart agent is expected to run both.

**`prefer_with:` stays in `schedule:`.** This is a scheduling optimisation bonus
(co-placement preference), not a pharmacological knowledge claim. The Planner
awards a score bonus for placing prefer_with pairs together; the mechanism is
scheduling-mechanical.

**`separate_from:` is not a per-card field.** Class-level separation rules live
in `relations.yaml` as class-level `competes` entries (see below). No per-card
`separate_from:` field exists in v2.

---

## Relations

| Type | Actor | Semantics |
|---|---|---|
| `competes` (substance-level) | **Planner** | Hard block: these two substances must not share a slot |
| `competes` (class-level) | **Planner** | Hard block: substances of class X must not share a slot with substances of class Y |
| `balance` | **Reviewer** | These substances should be reviewed together long-term |
| `supports` | **Reviewer** | Source is a cofactor for target; report when target active without source |
| `antagonizes` | **Reviewer** | Co-presence may be harmful; report when both active |

### Class-level `competes` — new in v2

`relations.yaml` gains class-level entries alongside existing substance-level
ones:

```yaml
competes:
  # substance-level (existing)
  - source_name: Zinc
    target_name: Copper
    reason: "..."

  # class-level (new)
  - source_class: mineral
    target_class: fat_soluble
    reason: "Minerals and fat-soluble vitamins have conflicting timing
             requirements; fat-solubles need a fat-containing meal while
             minerals benefit from general food presence but their absorption
             can be impaired by fats in some combinations."
```

The Planner resolves class-level entries by checking `knowledge.is:` on all
active substances to find class members. This is the **single documented
exception** to the rule that the Planner does not read `knowledge:`.

---

## traits.yaml Changes

In v2:
- `intake:` namespace — unchanged; Planner reads and executes `effects:` rules
- `activity:` namespace — unchanged
- `effect:` namespace — **split**: scheduling-relevant slugs (`energy_like`,
  `sleep_disruptive`, `sleep_support`) move to a new `timing:` namespace read
  by the Planner; all other `effect:` slugs remain in `effect:` as Reviewer-only
- `is:` namespace — Reviewer-only for classification; also used by Planner
  narrowly for class-level `competes` resolution
- `risk:`, `dashboard:`, `pathway:` namespaces — Reviewer-only; no `effects:`
  or `separate_from:` rules permitted in these namespaces
- `separate_from:` field on individual trait definitions — **retired**; class-level
  separation rules move to `relations.yaml`

---

## Commands

| Command | Actor | Output |
|---|---|---|
| `planner schedule` | Planner | Slot assignment |
| `planner review` | Reviewer | Structured facts: concerns, relations status, pathways |
| `planner check` | Both | Validates all data files; assigns missing IDs |
| `planner find` | — | Search cards |

`planner audit` is retired. Its output splits:
- Scheduling cleanup → `planner schedule --cleanup` flag or separate subcommand
- Concerns, relations, knowledge → `planner review`

---

## What This Does Not Change

- Product cards — no structural change
- Stacks and pillboxes — no change
- Dashboard YAML files — `from_traits:` namespace references update from `{ns: is}`
  to `{ns: knowledge.is}` and from `{ns: effect}` to `{ns: knowledge.effect}` as
  part of migration; mechanism otherwise unchanged
- `planner find` — unaffected
- ID assignment and filename convention — unaffected

---

## Migration Strategy

The migration is evolutionary. During transition, the Planner and Reviewer loaders
support both formats:

- If a substance card has a `schedule:` key → read from nested structure
- If no `schedule:` key → fall back to flat top-level fields

A card with BOTH `schedule:` and flat fields is **rejected by `planner check`** —
ambiguous state is not permitted.

Migration order:
1. Update `schema/templates/substance.yaml` to the new structure
2. Update `planner check` to reject dual-format cards
3. Migrate substance cards in batches (script)
4. Update `planner review-substance` to read `knowledge:` section
5. Update dashboard `from_traits:` namespace references
6. Add class-level `competes` entry for `mineral` ↔ `fat_soluble`
7. Retire `separate_from:` from trait definitions; retire `planner audit`

---

## Open Questions

1. **`notes:` placement** — stays top-level. Authoring ergonomics, not a
   principled architectural question.

---

## Deliberately Not Modelled

**Dietary fat sources (Krill Oil, Flaxseed Oil) satisfying `fat_meal_required`.**
Substances that are themselves fat sources provide the dietary fat needed for
co-administered fat-soluble vitamins. Modelling this would require a new
scheduling concept (e.g. `provides: [dietary_fat]`) and Planner logic to detect
when a fat source is present in a slot and relax `fat_meal_required` constraints
for co-scheduled substances. This affects at most 2-3 substances and the
scheduling impact is minor. Deferred as overengineering at current scale; the
edge case is captured in substance `notes:` where relevant.
