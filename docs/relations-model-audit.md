# Relations Model Audit

Date: 2026-05-21

## TL;DR

`source_trait` / `target_trait` endpoints are useful, but should stay narrow.
They should collapse repeated category-level interaction facts, not turn
`data/relations.yaml` into a general graph of everything related to everything.

Completed cleanup:

- Renamed `antagonizes` to `review_with`, matching the real behavior: show a
  review warning when both endpoints are active.
- Collapsed acid-suppressing drugs -> Vitamin B12 into one trait-endpoint
  relation.
- Collapsed Vitamin E -> EPA/DHA into one omega-3 pathway relation, intentionally
  including Krill Oil as omega-3 PUFA exposure.
- Relation review and warning output now renders trait/class endpoints with
  registry labels plus raw IDs, for example `Incretin Context
  (effect:incretin_context)`.

Remaining medium-confidence candidate:

- Generalize nitric-oxide donors -> PDE5 inhibitors after deciding that the
  broader warning should include beetroot, AAKG, and nitrate donors.

Most current relations should stay explicit. They are substance-specific,
severity-specific, scheduler-affecting, or too small to justify a new trait.

## Guardrails

Use a trait endpoint only when all of these are true:

- Every current member of the trait should participate in the same relation.
- Future members of the trait should probably inherit the relation automatically.
- The relation keeps the same severity and action text for all matched members.
- The trait is narrower than the dashboard or broad effect family.
- The resulting review output remains readable enough for an agent or human.

Do not use a trait endpoint when:

- The only benefit is shaving one or two YAML lines.
- Different substances need different severity.
- The relation affects scheduling through `competes` and broadening could move
  products into different slots.
- The fact is just shared dashboard membership, not a substance-to-substance
  interaction.
- A broad trait would over-match, for example `effect:glucose_metabolism_context`
  also catches magnesium and biotin, not just glucose-lowering interaction risks.

## Current Surface

`data/relations.yaml` currently has 36 relations:

| Type | Count | Notes |
| --- | ---: | --- |
| `balance` | 2 | Long-term paired review. |
| `competes` | 8 | Scheduling-sensitive; broadening is risky. |
| `supports` | 11 | Cofactor/supporter-to-target review. |
| `review_with` | 15 | Active-pair review when both endpoints are present. |

`review_with` is intentionally neutral. It covers true opposition, additive
vasodilation, medication-status effects, and GLP interaction review without
claiming they are all antagonism.

## Completed Changes

### 1. Acid Suppression -> B12

Previous explicit relations:

- `Omeprazole -> Vitamin B12`
- `Lansoprazole -> Vitamin B12`
- `Cimetidine -> Vitamin B12`
- `Ranitidine -> Vitamin B12`

Current model:

```yaml
review_with:
- source_trait: effect:gastric_acid_suppression_context
  target_name: Vitamin B12
  severity: medium
  reason: Gastric acid suppression can reduce absorption of food-bound vitamin B12; review B12 context when acid-suppressing medication is active.
```

Why this is safe:

- Same target.
- Same severity.
- Same practical action.
- Future cards such as pantoprazole or famotidine should inherit the same review.

### 2. Vitamin E -> Omega-3

Previous explicit relations:

- `Vitamin E -> Eicosapentaenoic acid`
- `Vitamin E -> Docosahexaenoic acid`

Current model:

```yaml
supports:
- source_name: Vitamin E
  target_trait: pathway:omega3_eicosanoid
  reason: Vitamin E helps protect long-chain omega-3 PUFA exposure from lipid peroxidation; review antioxidant context when omega-3 intake is active.
```

Current matched members of `pathway:omega3_eicosanoid`:

- EPA
- DHA
- Krill Oil

Decision: include Krill Oil intentionally, because it is an omega-3 source and
the antioxidant review applies to omega-3 PUFA exposure, not only split EPA/DHA
component cards.

### 3. GLP Trait Relations

The current GLP/incretin relations remain a good use of trait endpoints:

- `effect:incretin_context -> risk:glucose_med_interaction`
- `effect:incretin_context -> is:fiber`
- `effect:incretin_context -> Metformin`
- `Whey protein -> effect:incretin_context`
- `Creatine -> effect:incretin_context`

These are category-level review facts. Enumerating semaglutide, tirzepatide,
liraglutide, dulaglutide, exenatide, and retatrutide separately would create
noise without adding meaning.

Important boundary:

- Do not replace `risk:glucose_med_interaction` with
  `effect:glucose_metabolism_context`. The effect trait is too broad and includes
  foundational nutrients and context markers that are not drug-interaction risks.

### 4. Trait Endpoint Labels

Relation endpoints still keep raw identity keys such as
`effect:incretin_context` for deduplication and machine use, but review surfaces
now display the registered label next to the raw ID:

```text
Incretin Context (effect:incretin_context)
```

This keeps the output readable for humans and agents without hiding the exact
ontology key.

## Keep Explicit

### Folate-Drug Relations

Keep explicit:

- `Methotrexate -> Vitamin B9`, severity `high`
- `Sulfasalazine -> Vitamin B9`, no explicit severity

Reason:

- Severity differs.
- Mechanisms and clinical weight differ.
- A shared trait would either lose methotrexate severity or overstate
  sulfasalazine.

### Vitamin A/E -> Vitamin K

Keep explicit:

- `Vitamin E -> Vitamin K1`
- `Vitamin E -> Vitamin K2`
- `Vitamin A -> Vitamin K1`
- `Vitamin A -> Vitamin K2`

Reason:

- Only two target cards exist.
- Explicit names are clearer.
- Dose dependence already lives in `reason`.
- No current evidence that future K-family cards need broad automatic inheritance.

### Mineral And Amino Competition

Do not broaden:

- `Zinc <-> Copper`
- `Calcium <-> Iron`
- `Calcium <-> Zinc`
- `L-Lysine <-> L-Arginine`
- `Glycine <-> Beta-alanine`
- `Glycine <-> Taurine`
- `Vitamin E tocopherol <-> Vitamin E tocotrienols`

These are not generic category facts. Broad trait endpoints would either
over-match or change scheduler behavior.

The existing `is:mineral -> is:fat_soluble` class-level `competes` relation is
already the broad scheduling rule. Add more broad `competes` relations only with
great care.

### CYP Medication Pairs

Keep explicit:

- `Ginkgo biloba -> Efavirenz`
- `Ginkgo biloba -> Midazolam`

Reason:

- The target side is specific medication comparator cards.
- `risk:cyp450_med_interaction` on the source side is too broad for a relation
  because many botanicals can carry the same risk without the same target evidence.
- A future `cyp_sensitive_medication` trait might make sense, but only after more
  medication comparator cards exist.

## Remaining Candidate

### Nitric Oxide Donors -> PDE5 Inhibitors

Current relation:

- `L-Citrulline -> Tadalafil`

Possible future relation:

```yaml
review_with:
- source_trait: effect:nitric_oxide_support
  target_trait: effect:pde5_inhibition
```

Why not migrate immediately:

- It would broaden the warning to beetroot, AAKG, and nitrate donors. That may be
  correct, but it is behavior expansion, not only duplicate removal.
- The current explicit relation is only one line.

## Suggested Next Order

1. Revisit nitric-oxide donors -> PDE5 inhibitors as a model-policy decision.
2. Keep new trait-endpoint relations narrow and label-backed; do not use them
   only to reduce YAML line count.
