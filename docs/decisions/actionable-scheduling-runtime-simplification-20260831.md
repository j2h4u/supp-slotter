# Actionable Scheduling Runtime Simplification — 2026-08-31

## Decision

The runtime accepts only typed canonical world facts and universal laws, then
derives normalized pressures, an exact result, and a concise proof trace.
Historical candidate/disposition adjudications remain review provenance; they
are not runtime data or user-facing schedule output.

Accordingly, the runtime candidate catalog, coverage closure/certificates,
grooming command and receipts, candidate/disposition output, and
passive-relation exclusion output are rejected. `1600312` removed the initial
implementation and `5a7368c` completed the cleanup, including its CLI and
tests. No compatibility or no-op replacement remains.

## Why

Those surfaces duplicated adjudication as operational stored answers and made
catalog completeness a precondition for an otherwise formally valid schedule.
They did not add a world fact, inference law, or exact-optimizer guarantee.
Their removal keeps the only scheduling path small and auditable:

`typed fact + universal law -> normalized pressure -> exact proof`.

## Preserved boundaries

- Every admitted directed claim remains a typed fact with exact applicability
  and law path; weak evidence is provenance, not a lower objective weight.
- The lexicographic exact optimizer, global-optimum requirement, and
  contradiction-to-layout-free-`Indeterminate` behavior are unchanged.
- Generic card `notes` remain schema-rejected after the one-time migration.
- The current real-shelf recovery witness remains `Optimal` with eight
  normalized pressures and ten balance-only placements, strictly below the
  baseline 14.

## Supersession and future work

This supersedes only the runtime catalog, coverage-certificate, grooming, and
related user-output requirements in the earlier actionable-knowledge coverage
boundary, its corresponding domain-model passages, and the former recovery
plan. The prior source receipts and adjudications remain historical semantic
evidence. A future directed claim may be admitted only by authoring a justified
typed fact in the closed vocabulary; a new fact family or law still requires an
accepted V-left contract.
