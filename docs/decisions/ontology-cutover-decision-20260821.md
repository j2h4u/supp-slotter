# Ontology-first versus Python-first spike closure — 2026-08-22

## Verdict

**STOP THE SPIKE.** Confidence: **high**.

The ontology-first direction is the accepted product boundary. The project has
enough evidence to stop comparing foundations and continue with the current
small product contract. Python-first remains historical context, not a second
maintained product line.

## Source-of-truth boundary

Formal sources own the supplement domain:

- supplement entities and identities;
- relations and interaction meaning;
- scheduling facts and policies;
- numeric policy values;
- warnings; and
- stack and grooming semantics.

Python legitimately remains the generic interpreter, optimizer, and integration
glue. It may resolve selectors, group and round values, execute constraints,
search and tie-break candidates, and render schedules, explanations, and
reports. It must not become the authority for supplement semantics.

This boundary is portable: a future TypeDB move needs an importer for the
formal sources and a generic optimizer/execution layer. It does not need to
recover supplement meaning from Python planner code.

## Product evidence

The current real scenarios work as a coherent product contract:

- daily and training pillboxes are produced;
- `not_every_day` is a presentation grouping, not hidden dose or recurrence;
- `prefer_together` and separation behavior are represented and explained;
- advisory relationships remain distinguishable from hard constraints;
- warnings are emitted from the authored relation/policy model; and
- grooming is deterministic and bounded.

The final release gate passed, including the formal projection conformance
check. The CRAP Core gate also passed: **780 production functions, zero with
CRAP score >= 30**. These are closure evidence for the current release, not a
claim that the product is a medical recommendation system.

## Closure acceptance criteria

This spike is closed when all of the following remain true:

1. Domain facts, relations, policies, numeric values, warnings, and
   stack/grooming semantics have a canonical formal source.
2. Python changes can implement generic execution mechanics without adding
   supplement names, classes, pair assertions, or placement preferences as
   hidden domain authority.
3. Daily, training, `not_every_day`, `prefer_together`, advisory separation,
   warnings, and deterministic grooming continue to pass their real-scenario
   checks.
4. Formal projection conformance and the final release/CRAP Core gates pass.
5. TypeDB portability requires only a source importer and generic optimizer,
   not semantic archaeology in Python.

All criteria are met. No further ontology-versus-Python spike loop is planned.

## Consciously deferred

The following are intentionally outside this closure:

- dose and recurrence semantics;
- TypeDB deployment;
- an external ontology;
- a new recommendation system; and
- extended grooming or dashboard semantics.

Legacy compatibility is also deferred by design: no compatibility layer or
legacy semantic authority is required to preserve the current product.

## Nonblocking UX follow-up

Future explanations should show declined or unsatisfied soft preferences and
make impossible pillbox trade-offs explicit. This is a separate UX improvement
and does not reopen the ontology-first decision or block release.
