# Actionable scheduling status

Supp Slotter turns typed supplement facts into a safe daily layout. The product
purpose is to publish only a proved globally optimal layout, or a layout-free
`Indeterminate` result when the proof cannot be established or facts conflict.

## Current architecture

The pipeline is **formal typed facts -> identity-free universal laws -> unique
pressures -> exact global optimizer -> derived output**. Python is glue: it
loads, validates, infers, optimizes, proves, and renders the formal model. The
canonical contract is [the domain model](domain-model.md), governed by the
[canonical instance and inference boundary](decisions/canonical-instance-inference-boundary-20260822.md).

The closed vocabulary has six fact families and currently 13 facts. The active
shelf contains 18 current products: 10 unique pressures are satisfied, eight
products are balance-only, and the exact integer squared load is 62. B5 and
VitaMeal C are newly product-scoped `with_food` facts. Nattokinase, Tadalafil,
Lion's Mane + choline, Magnesium, and Picamilon have researched balance-only
dispositions; they do not add scheduling pressures.

There are no notes, weights, catalog or coverage workflows, grooming state,
SurrealDB runtime, legacy compatibility, dose semantics, or capacity semantics
in the scheduling model. Slots remain unbounded logical intake groups.

## Readiness

Product readiness requires a fresh real planner run to produce an exact global
`Optimal` result with the stated pressure, squared-load, and stable assignment
semantics; contradictions must remain layout-free `Indeterminate`; and the
formal source, runtime, and publication contracts must conform. Current
observed evidence is a fresh real planner run in 3.2s, all checks passing, and
exact global `Optimal`. The latest full `just release` at source HEAD `4bf2887`
exited 0, covering 14 smoke checks, ontology 37+31+54, runtime 57, CRAP 245
at threshold 30 with 82% coverage, and corpus conformance.

The remaining debt is nonblocking: the release harness takes about 13 minutes,
mainly for coverage and SHACL; the normal planner path is about 3 seconds.
Current docs-only descendants do not change runtime behavior.
