# Former `competes` rules: evidence and scheduling adjudication

Date: 2026-08-21
Scope: the eight interaction assertions that were represented as `competes` in
`main` at `4abac57`, compared with the executable-ontology branch at `HEAD`
(`feature/executable-ontology-contract`).  This is an evidence and policy
inventory only.  It does not change ontology data or Python code.

## How to read this inventory

The two judgments are deliberately separate:

1. **Relation** — whether a biochemical or practical relationship is justified,
   including its dose/form/context boundary.
2. **Scheduling policy** — whether that relationship should affect same-slot
   placement.  `hard-block` means a same-slot candidate is infeasible;
   `advisory` means it receives a soft penalty/preference only; `review-only`
   means it is knowledge shown for review with no placement effect; `retired`
   means neither the assertion nor a scheduling rule should be carried forward.

Confidence refers to the relation and its operational interpretation together,
not to the certainty that any individual person will experience an effect.
Transport, receptor, animal, and cell evidence is retained as mechanistic
context but is explicitly lower weight than human absorption/status evidence.

## Branch comparison

`main` authored all eight assertions under `competes` and described that type
as a hard same-slot exclusion.  The feature branch removed the old relation
records and currently has four executable constraints: zinc–copper,
calcium–iron (already advisory), calcium–zinc, and exact-form
tocopherol–tocotrienol.  It has no executable rule for either lysine/arginine
or either glycine pair, and no class-level mineral/fat-soluble rule.  The
inventory below is the adjudication, not a request to restore the old list.

## Adjudication inventory

### 1. Zinc–copper

- **Former assertion:** zinc and copper compete for absorption when
  co-administered.
- **Relation:** **Yes, bounded.** High zinc intake over weeks can inhibit
  copper absorption and lower copper status. NIH ODS reports this at roughly
  50 mg zinc or more for weeks and identifies high-dose zinc as a cause of
  copper deficiency; the adult zinc UL is 40 mg/day. This is primarily a
  chronic dose/status relationship, not proof that every ordinary same-slot
  pair materially fails absorption.
- **Evidence:** NIH ODS, *Zinc—Health Professional Fact Sheet*,
  https://ods.od.nih.gov/factsheets/zinc-healthprofessional/; NIH ODS,
  *Copper—Health Professional Fact Sheet*,
  https://ods.od.nih.gov/factsheets/Copper-HealthProfessional/.
- **Confidence:** **High** for the chronic high-zinc → copper-status relation;
  **medium** for a generic same-slot absorption rule because dose, duration,
  food, and form are not represented.
- **Scheduling decision:** **Retain as advisory; do not hard-block.** Keep a
  balance/review assertion and a separate soft same-slot preference when the
  endpoints are in separate products. Do not claim a universal separation
  interval.
- **Canonical representation consequence:** The balance fact belongs in the
  authored relation source; any soft placement policy belongs in the authored
  scheduling-constraint source. It must not be reconstructed from a Python
  name check. The policy should be symmetric and should not apply to a
  product's own inseparable components.
- **Product consequence:** A standalone zinc product and standalone copper
  product should preferably land in different slots when feasible. A combined
  zinc/copper product remains placeable and should produce a dose/status review,
  not an impossible hard-constraint diagnostic.
- **Unresolved questions:** elemental dose and duration are not modeled;
  whether chelated forms materially change this interaction is not established;
  the planner cannot infer copper status or treatment intent.

### 2. Calcium–iron

- **Former assertion:** calcium reduces iron absorption and should be separated
  by 2–4 hours.
- **Relation:** **Yes, bounded and context-dependent.** Human studies show
  acute inhibition of heme and non-heme iron uptake with added calcium, but the
  size depends on meal, iron form, calcium dose, and endpoint. A 61-person
  isotope study found no inhibition when 300 or 600 mg calcium carbonate was
  taken without food with ferrous sulfate; a human intestinal-lavage study
  found approximately 25% lower total iron absorbed with added calcium. A
  34-day randomized trial of 600 mg/day calcium found no change in iron
  bioavailability. NIH ODS therefore calls the effect possible/not definitive
  while suggesting different times for individual supplements.
- **Evidence:** NIH ODS, *Iron—Health Professional Fact Sheet*,
  https://ods.od.nih.gov/factsheets/Iron%20%20-HealthProfessional/; Cook et
  al., PMID **1984334**, https://pubmed.ncbi.nlm.nih.gov/1984334/; Hallberg et
  al., PMID **16155272**, https://pubmed.ncbi.nlm.nih.gov/16155272/; Ríos-Castillo
  et al., PMID **24290597**, https://pubmed.ncbi.nlm.nih.gov/24290597/.
- **Confidence:** **High** that a bounded acute absorption relation exists;
  **medium** for routine supplement scheduling.
- **Scheduling decision:** **Retain as advisory; do not hard-block.** The
  feature branch's advisory disposition is correct in kind: prefer different
  slots when feasible, with no computed 2–4 hour promise.
- **Canonical representation consequence:** Preserve a calcium–iron relation
  with dose/context caveats and a distinct advisory constraint. Do not encode a
  universal interval or treat all calcium/iron forms as equivalent evidence.
- **Product consequence:** Separate standalone calcium and iron when the
  schedule has room; co-location remains allowed. A multi-ingredient product
  containing both remains placeable, with no false hard-conflict failure.
- **Unresolved questions:** dose and iron form are absent from the solver's
  constraint inputs; food composition and iron deficiency status are absent;
  no validated threshold can currently be computed.

### 3. Calcium–zinc

- **Former assertion:** calcium competes with zinc for absorption.
- **Relation:** **Yes, bounded.** Controlled human studies found lower acute
  zinc exposure after co-ingestion of 600 mg elemental calcium with 4.5 mg
  zinc (both calcium carbonate and citrate), and a larger human study found
  reduced zinc absorption/balance with high-calcium supplementation. The
  studies do not justify a universal effect at low calcium doses, across all
  meals, or across all zinc forms.
- **Evidence:** Spencer et al., PMID **8194505**,
  https://pubmed.ncbi.nlm.nih.gov/8194505/; Wood et al., PMID **9174476**,
  https://pubmed.ncbi.nlm.nih.gov/9174476/; NIH ODS, *Calcium—Health
  Professional Fact Sheet*, https://ods.od.nih.gov/factsheets/calcium-HealthProfessional/.
- **Confidence:** **Medium** for high-dose acute absorption antagonism;
  **low-to-medium** for a general consumer same-slot rule.
- **Scheduling decision:** **Retain as advisory; do not hard-block.** Prefer
  different slots for separate products, without an interval claim and without
  treating co-formulated products as violations.
- **Canonical representation consequence:** Keep the relation and advisory
  policy separate. Narrowing to elemental-dose-aware selectors can be a future
  enhancement; until then the authored policy must state that it is a weak,
  dose-blind preference.
- **Product consequence:** Calcium and zinc in separate products are softly
  discouraged from the same slot when alternatives exist. Calcium-containing
  blends and low-dose products remain schedulable.
- **Unresolved questions:** elemental-dose threshold, meal/phytate effects,
  salt/form differences, and long-term clinical significance are not resolved;
  the 600 mg studies cannot be generalized to every product on the shelf.

### 4. L-Lysine–L-arginine

- **Former assertion:** lysine and arginine share cationic-amino-acid
  transport; high-dose lysine can reduce arginine uptake.
- **Relation:** **Yes, mechanistically and at high doses; practical routine
  interference is unproven.** Shared cationic transport is established, and a
  human proof-of-concept study (five healthy men, stable-isotope tracer) found
  arginine–lysine antagonism only with approximately 300–600 mg/kg/day
  arginine while lysine was restricted to the DRI. Human endothelial and liver
  studies also show lysine inhibition of arginine transport, but these are
  cellular/transport endpoints, not ordinary supplement co-dosing outcomes.
- **Evidence:** Schmidt et al., PMID **32187681**,
  https://pubmed.ncbi.nlm.nih.gov/32187681/; McAteer et al., PMID **14603368**,
  https://pubmed.ncbi.nlm.nih.gov/14603368/; Hrabák et al., PMID **7690540**,
  https://pubmed.ncbi.nlm.nih.gov/7690540/.
- **Confidence:** **Medium** for a high-dose transport relation; **low** for
  routine same-slot practical impact.
- **Scheduling decision:** **Retain as review-only.** Do not block or penalize
  same-slot placement without dose-aware evidence. A review note may be shown
  for unusually high-dose arginine/lysine use, but the current planner cannot
  identify that condition.
- **Canonical representation consequence:** If retained, author a bounded
  biochemical/clinical-review relation with high-dose wording; do not restore a
  generic `separate_products_same_slot` constraint. No Python pair special case.
- **Product consequence:** Ordinary lysine and arginine products can share a
  slot. A clinician/user reviewing very high-dose use should decide whether to
  stagger or adjust intake outside the automatic schedule.
- **Unresolved questions:** clinically meaningful dose thresholds for common
  formulations, effect of arginine salts/complexes, and whether timing rather
  than total daily dose changes outcomes remain unknown.

### 5. Glycine–beta-alanine

- **Former assertion:** beta-alanine competes with glycine at strychnine-
  sensitive glycine receptors and may attenuate glycine signaling.
- **Relation:** **Biochemical relation yes; practical supplement interaction
  not established.** Beta-alanine and glycine share transport systems in cell
  and vesicle preparations, and beta-alanine is a glycine-receptor agonist/
  partial agonist in neuronal preparations. The evidence is predominantly
  animal, ex vivo, or recombinant-receptor work; it does not demonstrate that
  ordinary oral beta-alanine changes human glycine sleep or neurotransmission
  outcomes when co-dosed.
- **Evidence:** Wapnir et al., PMID **7563025** (human Caco-2 transport model),
  https://pubmed.ncbi.nlm.nih.gov/7563025/; Christensen and Fonnum, PMID
  **1915594**, https://pubmed.ncbi.nlm.nih.gov/1915594/; Laube et al., PMID
  **7542038**, https://pubmed.ncbi.nlm.nih.gov/7542038/.
- **Confidence:** **Medium-low** for the mechanistic relation; **low** for
  practical same-slot consequences.
- **Scheduling decision:** **Retain as review-only.** No hard block and no
  soft slot penalty. Label the mechanism as weak/non-clinical if surfaced.
- **Canonical representation consequence:** Preserve only as a bounded,
  low-confidence review assertion if the product needs the knowledge. Do not
  create a scheduler constraint from receptor or transporter competition alone.
- **Product consequence:** Glycine sleep-support products and beta-alanine
  pre-workout products remain freely schedulable; their independent timing
  preferences continue to decide placement.
- **Unresolved questions:** human pharmacokinetic exposure at common doses,
  brain/spinal concentrations, receptor occupancy, and any measurable sleep or
  performance interaction are unknown.

### 6. Glycine–taurine

- **Former assertion:** taurine and glycine share transport and compete at
  glycine receptors; co-administration may reduce receptor occupancy.
- **Relation:** **Biochemical relation yes; practical supplement interaction
  not established.** Taurine and glycine can interact with glycine-receptor
  agonist sites in neuronal preparations, and taurine/glycine competition is
  observed in intestinal or epithelial transport models. Human intestinal
  studies establish taurine transporters but do not show that co-dosing common
  oral supplements changes clinical glycine or taurine effects.
- **Evidence:** Wapnir et al., PMID **7563025**,
  https://pubmed.ncbi.nlm.nih.gov/7563025/; Anderson et al., PMID **19074966**
  (human intestinal taurine transport model),
  https://pubmed.ncbi.nlm.nih.gov/19074966/; Mäkelä et al., PMID **2845721**
  (animal glycine-receptor preparation),
  https://pubmed.ncbi.nlm.nih.gov/2845721/; Laube et al., PMID **7542038**,
  https://pubmed.ncbi.nlm.nih.gov/7542038/.
- **Confidence:** **Medium-low** for shared transport/receptor mechanisms;
  **low** for practical same-slot consequences.
- **Scheduling decision:** **Retain as review-only.** No hard block and no
  soft placement penalty; mechanism and uncertainty must be explicit.
- **Canonical representation consequence:** If retained, author one low-
  confidence review relation, not an executable separation rule. Do not infer
  that `kind: amino` makes all such pairs schedulable constraints.
- **Product consequence:** Taurine and glycine remain co-placeable. Their
  authored sleep/workout timing preferences, not the former competition rule,
  control normal placement.
- **Unresolved questions:** human co-dose pharmacokinetics, receptor exposure,
  dose dependence, and clinical relevance to sleep, calm, or performance are
  unresolved.

### 7. Mineral–fat-soluble (class-level)

- **Former assertion:** minerals and fat-soluble substances have competing
  intake requirements (general food versus fat-containing meal), so the classes
  should not share a slot.
- **Relation:** **No generic biochemical or practical relation is justified.**
  "Mineral" and "fat-soluble" are heterogeneous classes, not competing
  transport pathways. Some fat-soluble nutrients absorb better with dietary fat
  (e.g., vitamin D and E), while mineral guidance is salt-, dose-, food-, and
  indication-specific. That does not establish a mineral↔fat-soluble
  incompatibility; several products intentionally combine both classes.
- **Evidence:** NIH ODS, *Vitamin D—Health Professional Fact Sheet*,
  https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/ (fat enhances
  but is not required for vitamin D absorption); NIH ODS, *Vitamin E—Health
  Professional Fact Sheet*,
  https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/ (vitamin E
  forms and handling); NIH ODS, *Calcium—Health Professional Fact Sheet*,
  https://ods.od.nih.gov/factsheets/calcium-HealthProfessional/ (calcium
  absorption is form/intake dependent).
- **Confidence:** **High** that the broad class assertion is overgeneralized;
  **high** that it should not be a generic scheduling constraint.
- **Scheduling decision:** **Retire.** Retire both the class relation and its
  hard-block consequence. Preserve substance-level food preferences (for
  example, a particular fat-soluble card's `food_preferred` vote) as separate
  scheduling knowledge.
- **Canonical representation consequence:** No mineral↔fat-soluble relation
  or class-level constraint should be authored. Specific, evidence-backed
  nutrient-pair interactions remain eligible for their own adjudication.
- **Product consequence:** A mineral and a fat-soluble substance may share a
  slot when their individual intake preferences permit it. The scheduler must
  not split a multivitamin merely because it contains both classes.
- **Unresolved questions:** individual nutrient/form/meal rules still need
  card-level review; this retirement does not adjudicate every specific mineral
  interaction.

### 8. Tocopherol–tocotrienol (exact forms)

- **Former assertion:** vitamin E tocopherols and tocotrienols compete for
  absorption and tissue uptake when co-administered.
- **Relation:** **Plausible biochemical relation; practical co-dose effect is
  not established.** Tocopherols and tocotrienols are vitamin E family forms
  with overlapping intestinal/lipoprotein handling but strongly different
  hepatic discrimination. In a human postprandial study, alpha-tocopherol was
  the dominant circulating form even after a tocotrienol-rich preparation and
  tocotrienol appearance was lower; however, that study compared separate
  administrations and did not demonstrate that co-administration harms either
  form. Rat/in-vitro work supports differing NPC1L1-mediated uptake, not a
  validated human timing rule.
- **Evidence:** NIH ODS, *Vitamin E—Health Professional Fact Sheet*,
  https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/; Fairus et
  al., PMID **22252050**, https://pubmed.ncbi.nlm.nih.gov/22252050/; Abuasal et
  al., PMID **22528033**, https://pubmed.ncbi.nlm.nih.gov/22528033/; Nguyen et
  al., PMID **27278668** (human tocotrienol pharmacokinetics),
  https://pubmed.ncbi.nlm.nih.gov/27278668/.
- **Confidence:** **Medium-low** for shared/differential handling;
  **low** for a clinically useful same-slot separation effect.
- **Scheduling decision:** **Retain as review-only; remove the hard block.**
  The feature branch's exact-form scope is a useful identity boundary, but the
  execution consequence should not be hard separation without direct human
  co-dose evidence. No advisory penalty is justified until dose and product
  formulation are represented.
- **Canonical representation consequence:** Keep an exact-form review relation
  between `sub_844a87d72b` (tocopherol) and `sub_5723eafac4` (tocotrienols), if
  the product needs this knowledge, but do not attach
  `separate_products_same_slot` to it. Do not broaden it to all Vitamin E
  forms.
- **Product consequence:** A mixed tocopherol/tocotrienol product remains
  placeable and cannot fail due to an unresolvable intra-product hard rule.
  Separate products may be co-placed; cumulative dose, anticoagulant/
  antiplatelet context, and formulation should be reviewed separately.
- **Unresolved questions:** direct human co-administration trials, dose and
  formulation effects, tissue-level competition, and any clinical outcome
  from staggering remain unknown.

## Resulting policy summary

| Former rule | Relation judgment | Scheduling disposition | Confidence |
| --- | --- | --- | --- |
| Zinc–copper | Retain, chronic high-dose/status bounded | Advisory | High relation; medium policy |
| Calcium–iron | Retain, acute absorption bounded | Advisory | High relation; medium policy |
| Calcium–zinc | Retain, high-dose absorption bounded | Advisory | Medium relation; low/medium policy |
| L-Lysine–L-arginine | Retain, high-dose transport bounded | Review-only | Medium relation; low policy |
| Glycine–beta-alanine | Retain, mechanistic only | Review-only | Medium-low relation; low policy |
| Glycine–taurine | Retain, mechanistic only | Review-only | Medium-low relation; low policy |
| Mineral–fat-soluble | Retire generic assertion | Retired | High |
| Tocopherol–tocotrienol | Retain, differential handling plausible | Review-only | Medium-low relation; low policy |

No rule in this inventory supports a universal same-slot hard block. The three
mineral-pair relations can remain useful as dose-blind advisory preferences
only because their human evidence supports a bounded absorption/status concern;
the remaining retained relations are review knowledge until dose, form, and
human co-administration evidence justify an operational policy.
