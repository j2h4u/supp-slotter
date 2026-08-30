# Canonical Runtime Independent Panel and Convergence — 2026-08-31

## Status

**Superseded — non-final.** This preserves the historical `SHIP` findings for
the reviewed heads below. Fresh-auditor remediation at
`b8bd5de0d256c211c66116b880c8db5deb7ffb98` invalidated it as final convergence;
the independent panel, fresh-context audit, and same-optics convergence must be
repeated for the remediated candidate.

## Reviewed scope

- Documentation head: `fb84f3c8fcf1c30ee22ccf92b631d4775cbc3beb`.
- Runtime parent and release receipt: `db5c36c199d11e66e1e72d4f00170d96dca01f9a`;
  `just release` exit `0`, 430 passing tests, 82% coverage, zero CRAP
  violations at threshold 30, and a conforming corpus projection.
- Governing contract: [domain model](../domain-model.md) and
  [canonical-instance boundary](canonical-instance-inference-boundary-20260822.md).

## Independent same-optics verdicts

| Optic | Verdict | Closed concern and evidence |
| --- | --- | --- |
| Product | SHIP | A stale `schedule.yaml` cannot drive output: `show` recomputes through plan and replaces the disposable output. [Domain contract](../domain-model.md); `planner/engine/show.py`; `planner/schedule_writer.py`. |
| Ontology | SHIP | Applicability is exact-role or all equal-substance roles; satisfaction is slot-anchor equality; provenance and canonical IDs fail closed. `ontology/runtime-policy.yaml`; `tests/test_runtime_contract_v2.py::test_engine_semantic_strategies_are_closed_exact_values`; `tests/test_runtime_contract_v2.py::test_runtime_envelope_and_canonical_ids_fail_closed`. |
| Portability | SHIP | The generic v2 runtime program remains the executable authority, with no family-specific Python extension required. `ontology/generated/runtime-program.json`; `tests/test_canonical_fact_catalog_runtime.py::test_annotation_and_manifest_ranges_admit_a_new_family_without_python_changes`. |
| QA | SHIP | The prior publication-source-validation false positive is corrected by mutation-specific expected failures. `db5c36c`; `tests/test_canonical_publication.py::test_invalid_source_mapping_product_domain_or_slot_publishes_nothing`; `scripts/run_unit_gate.py`. |

Kaizen: **PASS**. The convergence closed the stated product, ontology, and QA
concerns without adding compatibility, migration, or runtime ceremony.

## Consciously out of scope

This decision does not approve new fact families, change the canonical-instance
boundary, validate clinical or medical claims, execute a live production
schedule, or implement another runtime backend. Those require their own
accepted contract and evidence.

## Decision

The historical panel and same-optics convergence completed for the reviewed
heads only. This record does not close any final-review hold for the remediated
candidate; see the current [cutover checklist](../plans/canonical-runtime-cutover-checklist-20260830.md).
