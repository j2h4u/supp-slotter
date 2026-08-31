# Actionable Scheduling Knowledge Recovery — 2026-08-31

## Status and governing direction

This plan is reconciled to the accepted Kaizen simplification recorded in the
[runtime simplification decision](../decisions/actionable-scheduling-runtime-simplification-20260831.md).
The historical candidate/disposition adjudications remain useful provenance and
semantic review evidence. They are not a runtime catalog, a planning preflight,
or user-facing schedule output.

The recovery is now a narrow vertical slice: author only justified, typed world
facts; derive their normalized pressures through universal laws; prove the exact
result; and publish a concise derived trace. It does not attempt to close every
unknown scheduling question before the shelf may be scheduled.

## Product invariants

1. Every admitted directed scheduling claim is a formal typed fact with exact
   applicability and a universal-law path. A source, candidate record,
   disposition, relation, note, or explanation is never a scheduling input by
   itself.
2. Each normalized pressure `(item_id, dimension, value)` is unique. Any
   admitted pressure, including one supported by weak or anecdotal evidence,
   outranks balance without a numeric evidence weight.
3. The exact objective is unchanged: maximize satisfied unique pressures, then
   minimize integer `sum(load(slot)^2)`, then apply the stable assignment
   tie-break. Only a globally proved `Optimal` result may contain a layout;
   otherwise the result is layout-free `Indeterminate`.
4. Opposing values for the same item and dimension are a direct contradiction
   and fail closed to `Indeterminate`; the runtime never cancels, averages,
   weights, or balances around them.
5. Generic `notes` are schema-rejected on product, substance, and component
   cards. The completed one-time migration receipts preserve their historic
   source provenance without restoring a notes field, parser, or compatibility
   surface.
6. Pairwise, supports, balance, contextual, and other passive relations have
   no scheduling effect unless a future accepted typed world fact and universal
   law formally derive a pressure. The published trace does not enumerate
   passive-relation non-effects.
7. The real-shelf witness must remain strictly below the frozen baseline of 14
   balance-only placements. The current evidenced witness is 18 active
   products, eight normalized pressures, and ten balance-only placements.
8. Schedule output is concise derived proof: status, assignments, objective,
   normalized pressure matches and their fact/law/applicability/provenance
   paths, plus `pressure_evidence` or `balance_and_tie_break_only`. It exposes
   neither candidate IDs/dispositions nor coverage certificates.

## Rejected runtime machinery

The following are intentionally absent, not deferred work:

| Rejected surface | Reason |
| --- | --- |
| Runtime candidate catalog and disposition loader | It duplicated historical semantic adjudication as mutable operational state without contributing a world fact or universal law. |
| Coverage closure and per-role certificates | They turned absence of a catalog entry into a publication blocker and added stored assessment answers beside the exact solver. |
| Grooming command, receipt workflow, and queue | They created a user workflow for managing candidate dispositions rather than authoring formal facts. |
| Passive-relation exclusions in schedule output | Absence of an inference is not useful scheduling proof and would make the output noisy. |
| Candidate/disposition fields in user output | These are review artifacts, not derived schedule facts or explanations. |

If a future active-shelf claim matters, collect and adjudicate it outside the
runtime. Either author a justified fact in the closed vocabulary or leave it
out of the schedule. A new fact family, pairwise mechanism, or law still needs
an accepted V-left contract before implementation.

## Direct implementation and evidence cut

This plan records evidence through `75a2b86`; later commits require their own
review and do not silently satisfy an unchecked item below.

| Evidence | What it directly establishes |
| --- | --- |
| `68c7750`, consolidated adjudication, and the dated source receipts | The one-time semantic review is retained as provenance; it is not a runtime scheduling input. |
| `aed15d8` | Closed product-specific food-instruction facts and laws compile to formal pressures. |
| `bb9739a` and `f141a89` | Historic notes were migrated to typed destinations/discard receipts and the canonical card schema rejects `notes`. |
| `1600312` and `5a7368c` | The runtime candidate catalog, coverage closure/certificates, grooming command/workflow, receipts, CLI surface, and their tests were removed. |
| `75a2b86` and `docs/evidence/actionable-scheduling-recovery-difference-20260831.yaml` | The real-shelf trace is `Optimal`, has eight normalized pressures and ten balance-only placements, explains all four changed placements, and is strictly below the 14-placement baseline. |

## Completed recovery work

- [x] Freeze the baseline and individually adjudicate the historical directed
  source claims as semantic evidence, without treating adjudication records as
  canonical facts or schedule output.
  - Evidence: `33360a0`, `68c7750`, and
    [consolidated adjudication](../decisions/actionable-scheduling-adjudication-consolidated-20260831.md).

- [x] Admit the justified active product food instruction through closed typed
  facts and universal laws, preserving exact product/role applicability and no
  numeric evidence weight.
  - Evidence: `aed15d8` and `tests/test_product_food_instruction.py`.

- [x] Complete the one-time note migration and reject generic notes at every
  canonical card position.
  - Evidence: `bb9739a`, `f141a89`,
    [note-migration aggregate](../evidence/actionable-scheduling-note-migration-20260831.yaml),
    and `tests/test_loader_fail_closed.py`.

- [x] Remove the rejected runtime catalog, coverage, and grooming machinery
  rather than preserving a compatibility or no-op path.
  - Evidence: the initial and cumulative cleanup diffs `1600312` and `5a7368c`
    remove 3,240 and 3,289 lines respectively, including the catalog, coverage,
    grooming CLI, receipts, and their focused tests.

- [x] Record a compact current-shelf publication trace and recovery-difference
  witness instead of rendering candidate dispositions, certificates, or
  passive-relation exclusions.
  - Evidence: `75a2b86`,
    [recovery difference witness](../evidence/actionable-scheduling-recovery-difference-20260831.yaml),
    and `tests/test_actionable_scheduling_publication_trace.py`.

## Remaining finite release steps

- [x] Run the targeted `just` witnesses for the simplified boundary in one
  bounded gate at a time: formal fact-to-pressure derivation; an admitted weak
  pressure beating balance; contradiction-to-`Indeterminate`; notes rejection;
  exact global optimum; and the 18-product trace with ten balance-only
  placements. Confirm removed catalog, coverage, and grooming modules/CLI
  surfaces are absent rather than testing their former behavior.
  - Evidence required: exact commands, exit statuses, HEAD, and bounded output.
  - Evidence: [targeted witness receipt](../evidence/actionable-scheduling-targeted-witnesses-20260831.yaml)

- [ ] Perform an exact-head data and architecture audit: every currently
  admitted directed input is a typed fact/law path; no stored preference,
  placement, action, numeric evidence weight, candidate catalog, coverage
  certificate, grooming receipt, or notes field reaches planning or output.
  - Evidence required: reviewed input/output map and negative-boundary receipt.

- [ ] Run `just release` once only after the focused simplified-boundary
  witnesses are green.
  - Evidence required: exact-head release receipt, stage results,
  corpus/quality output, and clean checkout.

- [ ] Obtain an independent product/ontology review of the simplified
  architecture: formal directed facts, pressure-before-balance, exact
  global-optimum proof, contradiction fail-closed behavior, notes rejection,
  and the less-than-14 real-shelf witness. It must not reintroduce a review
  requirement for catalog coverage, certificates, grooming, candidate output,
  or passive-relation output.
  - Evidence required: exact-head verdict with zero actionable Critical, High,
  or Medium findings and explicit disposition of every finding.

- [ ] Obtain an independent Kaizen/YAGNI review that the deletion remains the
  smallest valid architecture: no migration, compatibility, parser/heuristic,
  general engine, or replacement workflow has returned.
  - Evidence required: exact-head verdict with the rejected surfaces checked
  for absence.

- [ ] Have a fresh-context auditor verify every checked item against commits,
  receipts, and current source, then mark the recovery complete only if no
  unchecked release item remains.
  - Evidence required: exact-head COMPLETE/STOP record.

- [ ] Push only `feature/actionable-scheduling-knowledge` after the preceding
  release and independent reviews pass; leave `main` unchanged.
  - Evidence required: clean worktree, exact SHA/remote comparison, and push
  receipt.

## Stop line

Stop after the simplified release evidence is complete. Do not add new fact
families, a generic relation engine, candidate/disposition runtime state,
coverage gates, grooming workflow, notes compatibility, clinical or dose
behavior, UI work, migrations, or storage backends without a new accepted
product contract.
