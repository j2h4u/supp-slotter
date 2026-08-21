# Ontology Cutover Decision And Completion Plan — 2026-08-21

## Decision Summary

**Decision: ADOPT FEATURE.** Supp Slotter will treat
`feature/executable-ontology-contract` as the sole long-term product line. The
branch is strategically preferred because it makes
supplement identities, relationships, scheduling policies, evidence, stacks,
pillboxes, and slots explicit and portable instead of leaving their meaning
distributed across Python behavior.

This is a product-line decision, not a decision to merge the feature branch
into `main`. The bounded cutover cluster is complete, and the project has made
the explicit choice:

- **ADOPT FEATURE** — the ontology branch becomes the only maintained product
  line.

Maintaining both branches is not an acceptable outcome.

### Final acceptance evidence

The final `just release` gate is green: smoke `3`, ontology A/B/C `23/19/61`,
runtime `50`, coverage `225`; `basedpyright` is clean and corpus conformance is
`true`. Fresh planner output contains daily base `10`, episodic `4`, and
training `4`, with every expected product appearing exactly once. Warm runtime
is `4.67s`. The grooming research filter reports `196` matching records and
shows `5`; the Kaizen audit is **ADOPTABLE**. Catalog/data preservation is
**PASS**, and no substantive product blocker remains.

The following items are consciously deferred: TypeDB deployment/importer work,
dose and recurrence modeling, broader medical evidence adjudication, and
optional future inference. They remain outside this cutover and do not weaken
the adoption decision.

The current Python-first planner was tactically successful and delivered value
quickly, but is strategically closed because its domain semantics remained
fragmented. It is preserved at remote branch
`archive/python-first-planner-20260821` for historical reference only, not as
maintained legacy or a compatibility target. This documentation commit does
not merge the feature branch into `main`.

## Product Context

Both branches already deliver the core product value: they assign the current
supplement shelf to practical pillbox slots. The decision is therefore not
whether the ontology branch can produce any schedule. It is which foundation
can continue accumulating useful knowledge without making every future change
an exercise in discovering semantics hidden in code.

`main` is smaller, slightly faster, and preserves more of the scheduling
behavior that was tuned before the ontology spike. Its domain model is split
across cards, trait registries, relation records, and Python behavior.

The feature branch adds an executable ontology contract, stable projections,
episodic-use presentation, grooming, and pairwise explanations. It also carries
a substantially larger maintenance surface and has changed or lost some
scheduling semantics. Formal structure alone does not prove that the resulting
model is medically correct or that the schedule is better.

## Expert Panel Record

### Product Manager: keep the feature branch

The Product Manager judged the feature branch to be the better long-term
product because it already adds user-facing value and gives future model changes
a coherent semantic home. The recommendation was conditional: reconcile the
lost interactions and conspicuous placement regressions before deleting the
other maintained branch.

### Ontology And TypeDB Architect: keep the feature branch

The ontology architect found that the feature branch is a strong executable
data contract and portable domain model, but not a complete declarative planner
or a rich reasoning ontology. Its stable identities, typed relationships,
policies, evidence records, manifests, and projections substantially reduce the
semantic archaeology required for a future TypeDB migration.

TypeDB would still require a deterministic importer and an application-level
optimizer. TypeQL queries alone would not reproduce candidate generation,
constraint execution, balancing, tie-breaking, warnings, or explanations.
Those mechanics may legitimately remain in Python when their semantics are
declared outside Python.

### Kaizen Master: keep `main`

The Kaizen Master rejected the feature branch on present-value grounds. The
feature roughly doubles important parts of the maintained implementation,
introduces a large compiler and artifact surface, runs more slowly, and still
depends on a Python optimizer. Its current scheduling regressions show that
formalization has not automatically improved the product.

The Kaizen recommendation was to retain `main`, port only stable identities,
episodic presentation, and grooming, and defer ontology infrastructure until a
real TypeDB requirement exists.

### Panel Synthesis

The disagreement is real and useful. The case for the feature branch is
strategic and cumulative; the case for `main` is operational and economic.
The project chooses to give the feature architecture one finite opportunity to
prove itself. Sunk cost is not evidence: the branch will be adopted only if it
passes the product and portability criteria below without another open-ended
ontology program.

## Verified Starting Gap

The comparison used `origin/main` at `4abac57` and
`origin/feature/executable-ontology-contract` at `70940b3`.

The feature branch does not merely rename the old model. It no longer carries
four prior same-slot exclusions:

- lysine and arginine;
- glycine and beta-alanine;
- glycine and taurine;
- minerals and fat-soluble substances.

Calcium and iron remain represented but were downgraded from a hard exclusion
to advisory behavior. Food, timing, and activity assertions also changed across
many shared substance cards. Some changes were deliberate evidence
recalibration, but not every behavior-affecting change has an explicit
adjudication record.

The feature branch can already export most domain facts without recovering them
from Python. It cannot reproduce the complete scheduler solely from its formal
artifacts: aggregation, constraint execution, search, objective calculation,
balancing, stable tie-breaking, and explanation mechanics still require an
execution engine.

## Bounded Cutover Cluster

The cluster is executed as one code-complete body of work. Targeted checks and
real shelf scenarios are used during development; heavyweight release gates run
only after the cluster is complete.

### 1. Reconcile Interaction Semantics

Create one inventory of all eight interaction rules previously expressed as
competition. For each rule, make and record exactly one evidence-aware decision:

- retain the relationship and retain a hard scheduling consequence;
- retain the relationship but make its scheduling consequence advisory;
- retain it as review knowledge with no scheduling consequence; or
- retire it because the assertion itself is not justified.

The biochemical or practical relationship and its operational effect on slot
assignment must be modeled separately. Removing a scheduling blocker must not
silently erase a still-useful domain assertion.

Completion evidence:

- all eight rules appear in one adjudication inventory;
- every retained fact has one canonical authored representation;
- every operational constraint points to an explicit policy decision;
- no supplement pair or class rule is encoded only in Python.

### 2. Reconcile Behavior-Affecting Scheduling Changes

Build a complete diff of intake, timing, and activity assertions between the two
branches, then prioritize facts reachable from the current active shelf. For
each changed assertion, classify it as:

- intentional evidence-backed correction;
- intentional weak heuristic;
- intentionally neutral or unknown after research; or
- accidental migration loss requiring repair.

Historical byte-for-byte parity is not a goal. Weak but useful heuristics are
allowed when their uncertainty and soft effect are explicit. The cluster must
not mechanically restore old rules merely because they existed in `main`.

Completion evidence:

- every active-reachable behavior change is adjudicated;
- no active placement depends on an unexplained missing assertion;
- high-salience changes such as B5, magnesium, trace minerals, and vitamin C
  have intelligible explanations;
- unresolved inactive-catalog changes are listed explicitly and do not block
  cutover unless they reveal a new class of migration loss.

### 3. Separate Catalog Changes From Ontology Migration

Reconcile products and substances that exist on only one side. Classify each as
a real shelf update, a canonical identity replacement, a deliberate catalog
addition/removal, or a migration artifact.

Completion evidence:

- all active and episodic products expected by the user are represented once;
- product-to-substance component links are preserved without data loss;
- stable identities are not replaced merely because labels, forms, or filenames
  changed;
- personal shelf changes are not presented as proof of ontology parity.

### 4. Declare The Execution-Engine Contract

Python may remain the solver and integration language. It must not remain a
second, implicit source of supplement knowledge. Externalize or formally
declare the semantics of:

- supported selectors and exact-form identity behavior;
- component aggregation and equal contribution of known scheduling votes;
- active, inactive, unassigned, and episodic stack interpretation;
- hard and advisory constraint operations;
- preference accumulation and conflict resolution;
- candidate feasibility, objective terms, balance penalty, and stable
  tie-breaking;
- warning/relation truth rules that affect product output.

Generic graph traversal, joins, search, pruning, serialization, and rendering
remain legitimate Python mechanics.

Completion evidence:

- changing a domain rule or tunable scheduling policy does not require editing
  a Python conditional or constant;
- unsupported authored operations fail closed with a useful diagnostic;
- an implementer could reproduce the solver contract from formal sources and
  documentation without reverse-engineering Python;
- Python contains no substance names, substance classes, pair assertions, or
  placement preferences as executable domain knowledge.

### 5. Validate Vertical Product Scenarios

After the preceding work is code-complete, validate a compact set of real
end-to-end scenarios:

- the current ordinary daily pillbox;
- the current episodic-use group;
- the training pillbox;
- a multi-component product whose component votes disagree;
- a hard separation, an advisory relationship, and a neutral pair;
- an unknown scheduling fact that contributes no vote;
- explanations showing why a placement or separation occurred.

The review asks whether the schedule is useful and explainable, not whether it
matches `main` byte for byte.

Completion evidence:

- every expected product appears exactly once in the proper physical pillbox;
- episodic use changes presentation but not hidden recurrence or dose logic;
- known hard constraints cannot be violated;
- weak preferences accumulate instead of collapsing to one arbitrary voice;
- neutral facts do not influence scoring;
- explanations identify the facts and policies responsible for meaningful
  decisions.

### 6. Run Final Gates And Repeat The Decision Review

Only after the full cluster is code-complete:

1. run the focused ontology, corpus-projection, and real-scenario gates;
2. run the release gate once;
3. measure a fresh and warm planner run;
4. repeat the branch review against the criteria below;
5. choose **ADOPT FEATURE** or **REJECT FEATURE**.

Do not insert full gates or general audits between individual card or policy
changes.

## Acceptance Scorecard

All mandatory criteria must pass. A partial result is not a reason to maintain
both branches.

| Area | Status | Mandatory acceptance criterion | Evidence |
| --- | --- | --- | --- |
| Product behavior | PASS | Daily, episodic, and training schedules are useful, complete, and explainable on the real shelf. | Smoke `3`; fresh planner daily base `10`, episodic `4`, training `4`, all exactly once. |
| Semantic preservation | PASS | Every old interaction and every active-reachable scheduling change has an explicit retain, weaken, neutralize, or retire decision. | Interaction and scheduling adjudication inventories; coverage `225`. |
| Data preservation | PASS | Expected products, substances, stable identities, forms, and component links survive without unintended duplication or loss. | Catalog closure and projection checks; catalog/data criterion PASS. |
| Single source of truth | PASS | Supplement facts, relations, policies, parameters, and supported operations are authored outside Python exactly once. | Boundary audit, formal engine contract, and Kaizen audit ADOPTABLE. |
| Solver contract | PASS | Aggregation, constraints, objective, balancing, and tie-breaking are declared well enough to reimplement without reading Python. | Engine protocol and conformance coverage `225`; runtime `50`. |
| Portability | PASS | A future TypeDB importer can be written from canonical sources and projection contracts without discovering domain semantics in Python. | Stable-ID catalog/projection inventory; TypeDB remains a future non-goal. |
| Formal consistency | PASS | Canonical sources generate fresh artifacts and reject malformed or unsupported semantics. | Final `just release` green; ontology A/B/C `23/19/61`; corpus conforms `true`. |
| Operability | PASS | Planner runtime is acceptable for the interactive CLI and has no unexplained cold-compilation path. | Runtime `50`; warm planner run `4.67s`. |
| Maintainability | PASS | The formal stack has one authoring path; generated artifacts and tests do not duplicate independent authorities. | `basedpyright` clean; grooming research filter `196` matching/showing `5`; Kaizen ADOPTABLE. |
| Scope control | PASS | No dose engine, recurrence scheduler, TypeDB deployment, or new medical expert system was added to complete the cutover. | Final diff and decision review; deferred items recorded above. |

## Final Decision Rules

### ADOPT FEATURE

Choose this only when every mandatory scorecard row passes and remaining
findings are limited to inactive-card grooming, documentation polish, malformed
input strictness, or optional future inference. Then:

- make the ontology architecture the only maintained product line;
- preserve the previous implementation through ordinary Git history rather
  than runtime legacy or a maintained compatibility branch;
- stop expanding the formal stack until a concrete product requirement needs
  it;
- treat TypeDB as a future storage/query migration, not as prerequisite work.

### REJECT FEATURE

Choose this when any of the following remains true after the bounded cluster:

- useful scheduling knowledge still has no canonical formal home;
- routine ontology changes still require coordinated Python knowledge edits;
- a future importer would still need semantic archaeology in planner code;
- schedule quality or explanations remain materially worse than the accepted
  product baseline;
- the maintenance surface cannot be reduced to one canonical authoring path;
- completing the gap requires another open-ended architecture program.

In that case, retain `main`, port only independently valuable product features,
and delete the maintained feature branch. Do not extend the cluster merely to
avoid admitting that the spike failed.

## Explicit Non-Goals

- Reproducing `main` byte for byte.
- Proving medical truth through schema validation.
- Modeling doses or intake recurrence.
- Deploying TypeDB during this cluster.
- Expressing the optimizer entirely in TypeQL.
- Building a general-purpose supplement expert system.
- Preserving legacy code or guard tests solely to prove that deleted legacy
  cannot return.

## Stop Condition

This cluster ends with a branch decision, not another review loop. One complete
implementation pass, one focused verification pass, one release gate, and one
final decision review are allowed. Newly discovered cosmetic or theoretical
improvements are recorded outside the cluster and do not delay the decision.
