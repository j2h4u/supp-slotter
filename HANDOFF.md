# HANDOFF — Supplement Slot Planner

**Created:** 2026-05-05
**Status:** mid-conversation handoff. Next session resumes a discussion on slot model evolution. Operator does NOT want to start solutioning until next session — just capture context.

---

## 🎯 Where to resume

Operator wants to evolve the slot model. He raised two intertwined points:

### Point 1: Slots are routine-tied, not pure time-of-day

Current slots (`morning_empty`, `morning_food`, `day_food`, `evening_empty`) are framed as "time × food state". Operator's actual mental model is **daily routine markers**: утро, завтрак, обед, и т.д. — slots are anchored to recurring events in his day, not abstract time. Food state is one dimension of those events, not the primary axis.

> Quote: «слоты привязаны не столько к времени суток, сколько к распорядку внутри этого времени суток — утро, завтрак, обед и т.д. То есть это ещё и с едой связано».

### Point 2: Add a "training" slot (aerobic, specifically)

Each day there should be a dedicated slot called **«тренировка»** (training) — specifically aerobic per operator's emphasis. Substances optimal pre-workout or post-workout should gravitate toward this slot.

> Quote: «каждый день должен присутствовать слот, который называется «тренировка». Если есть субстанции, которые оптимальнее принимать перед тренировкой или после — то было бы здорово, если бы они притягивались именно к этому слоту, аэробная — это важно».

### What this likely needs

Operator hinted: **«возможно, придётся улучшить таксономию в карточках продуктов»**. Likely candidates (NOT yet decided — discuss in next session):
- New slot(s) for training (one or two? pre/post split?)
- New trait(s): possibly `effect:pre_workout`, `effect:post_workout`, or `effect:training_session`
- Possibly a new slot field (e.g., `activity:`) so traits can match against it

---

## 📂 Current project state (snapshot 2026-05-05)

### Files

| Path | What |
|---|---|
| `data/slots.yaml` | 4 slots: morning_empty, morning_food, day_food, evening_empty |
| `data/traits.yaml` | 16 traits in 5 namespaces: intake, effect, class, family, risk |
| `data/products/*.yaml` | 23 substance cards |
| `data/inventory.yaml` | 23 entries (14 active, 9 inactive) — operator's actual shelf |
| `schedule.yaml` | Last generated schedule, total_score 32 |
| `planner.py` | CLI: check + refresh + plan |
| `schema/*.schema.json` | 4 JSON schemas |
| `idea.md` | Full spec, 26 sections |
| `brief.md` | Authoring instructions for substance-card agents |
| `current-inventory.md` | Operator's informal source list (input artifact) |

### Active substances (14)

`vitamin_d3, vitamin_b5, coenzyme_b_complex, magnesium_glycinate, electrolyte_caps, trace_minerals, potassium_citrate, lions_mane_b6_complex, acetyl_l_carnitine, astaxanthin, nattokinase, l_citrulline_malate, tadalafil, creatine`

### Workout-relevant substances among active (operator-stated context)

- **creatine** — PCr resynthesis, performance. `prefer_with: [l_citrulline_malate]` already declared.
- **l_citrulline_malate** — NO production, vasodilation, pre-workout
- **acetyl_l_carnitine** — mitochondrial + nootropic + mild stim
- **electrolyte_caps** — hydration during exercise (operator implied use case)
- **tadalafil** — vascular tone (low-dose off-label, in vascular stack with citrulline + nattokinase)
- **nattokinase** — fibrinolytic, vascular stack member

### Planner architecture (relevant to upcoming discussion)

- **Slots are generic.** Each slot has properties; traits' `effects[].match` matches against any slot field (AND-only). Adding a new field like `activity: training` to slots is a clean extension — existing traits continue to work, new traits can target the new field.
- **Algorithm:** greedy initial assignment + first-improvement local search. Fast (300ms for 14 substances). Good enough for MVP.
- **Scoring:** `slot_scores + prefer_with_bonus − balance_penalty`. Levels map: prefer_strong=+4, prefer=+2, avoid=−2, avoid_strong=−4, block=−∞. PREFER_WITH_BONUS=3, BALANCE_WEIGHT=0.5.
- **prefer_with** — substance-level soft synergy. Symmetric. Just implemented. Could be ALTERNATIVE to a training slot (if all pre-workout substances declared prefer_with each other, they'd cluster anywhere planner placed one of them) — but doesn't pin them to a specific routine event.

---

## 🧭 Recent architecture decisions (relevant context)

| Decision | Status | Where |
|---|---|---|
| Substance↔Product split | Deferred — post-MVP | idea.md §24 |
| Vector trait model | Deferred until concrete use case | idea.md §25 item 14 |
| `prefer_with` synergy | **Implemented** (substance-level) | idea.md §17.1 |
| Personal trait overrides | Implemented (`traits_override` in inventory) | idea.md §15.1 |
| Folklore cleanup | Done (B-vitamins no longer carry energizing/evening-avoid) | traits.yaml |
| `product:multicomponent` trait | Removed (signalled by presence of `components:` block instead) | — |
| Reserved field names | `confidence:`, `dose:`, `brand:`, `min_distance:`, `started:`, `paused_until:`, `lot:` | idea.md §23 |

---

## 🧠 Behavioral feedback that applies (memory)

- **Don't propose solutions when user asks clarifying questions.** Operator flagged this explicitly. Wait for direction-mode signals before offering option menus. (memory: `feedback_clarifying_questions.md`)
- **Use Sonnet for subagent dispatch.** Haiku misapplied an explicit anti-example trait rule that Sonnet caught. (memory: `feedback_subagent_models.md`)
- **No allergen flagging.** Operator has no allergies. (memory: `user_health.md`)

Memory dir: `/home/j2h4u/.claude/projects/-home-j2h4u-repos-j2h4u-supp-slotter/memory/`

---

## ❓ Suggested first questions for next session

These are NOT solutions — just framing questions to align on direction before any code/data changes. The operator's exact framing should drive the design.

1. **Is the training time stable** (same wall-clock time daily) or **variable** (today morning, tomorrow evening)?
2. **One slot or two** — does the operator want a single `training` slot, or `pre_workout` and `post_workout` separately?
3. **Where on the time axis** does training sit relative to existing slots? Is it inside a current slot (e.g., between day_food and evening_empty) or replaces one?
4. **Aerobic specifically** — does this distinguish from strength/anaerobic? Different protocols, different substances. Operator emphasized "аэробная" — confirm whether the system models only aerobic or also other workout types.
5. **Routine reframe scope** — does the operator want slots fully renamed/restructured around routine markers (breakfast, lunch, dinner, training, bedtime), or is "training" a single addition while keeping current slot structure?
6. **Existing substances impact** — pre-workout candidates (creatine, citrulline, ALCAR, electrolytes) currently scattered. Does operator want them all to gravitate to training, or some pre / some post / some independent?

---

## 🚧 What NOT to do reflexively

- **Don't redesign the slot model unilaterally.** Operator wants to discuss before any changes.
- **Don't extend taxonomy proactively.** Wait for operator's direction on new traits.
- **Don't dispatch agents to refill cards.** No card changes needed until taxonomy is settled.
- **Don't trigger another expert panel without operator asking.** Recent panel was on trait taxonomy — too soon to convene another.

---

## ✅ What's safe to do at session start

1. Greet briefly, confirm pickup point.
2. Re-read this HANDOFF.
3. Skim `idea.md` §8 (slots) and §15 (inventory) for current model.
4. Look at last `schedule.yaml` to remind operator of current placement.
5. **Ask the first 1-2 questions above** — let operator lead the design discussion. Do not present pre-baked options.

---

## File pointer

This handoff file lives at: `/home/j2h4u/repos/j2h4u/supp-slotter/HANDOFF.md`
