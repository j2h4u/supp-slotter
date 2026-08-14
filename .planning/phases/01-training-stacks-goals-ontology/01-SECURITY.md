---
phase: 01
slug: training-stacks-goals-ontology
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-05
verified_at: 2026-05-05T16:54:04Z
---

# Phase 01 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| operator -> YAML files | Local filesystem edits only; no network, auth, or PII boundary. | Supplement metadata and schedule YAML |
| operator -> goal/product cards | Local YAML authoring with no external input. | Goal membership and product trait metadata |
| YAML on disk -> planner.py | Local files parsed by CLI; no privileged operations. | Slot, trait, inventory, product, and goal records |
| smoke test -> goal card on disk | Transient local mutation for negative test. | One temporary bogus goal member ref |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-01-01 | Tampering | `data/inventory.yaml` during migration | mitigate | `inventory.schema.json` rejects malformed entries; smoke verification confirms 23 entries, no `active` keys, and stack histogram `daily=11/training=4/inactive=8`. | closed |
| T-01-02 | Information disclosure | inventory contents | accept | Repo-local personal supplement list; no medical PHI, network boundary, or external sharing introduced by this phase. | closed |
| T-01-03 | Tampering | `goal members[].substance` refs drift from card filenames | mitigate | Product-ref existence checks passed for goal cards; `planner.py check_goals()` validates `members[].substance` against loaded product card IDs. | closed |
| T-01-04 | Tampering | mismatched activity trait on substance | mitigate | Product-card assertion verified the expected activity trait for all four training substances. | closed |
| T-01-05 | Tampering | stale `active:` key silently bypassing new stack filter | mitigate | `inventory.schema.json` has `additionalProperties: false`; `uv run planner.py check` passes and direct inventory audit found `active_keys=0`. | closed |
| T-01-06 | Information disclosure | check error messages echo local file paths | accept | Local CLI for the operator's own repo; paths are not sensitive under this threat model. | closed |
| T-01-07 | Denial of service | malformed goal YAML crashes `cmd_check` | mitigate | `check_goals()` catches YAML parse errors, empty files, and non-mapping top levels before schema/ref checks. | closed |
| T-01-08 | Tampering | negative test corrupts `vascular_health.yaml` and forgets to revert | mitigate | Negative test used original bytes plus `try/finally` restore and a post-revert `uv run planner.py check` exit-0 assertion. | closed |
| T-01-09 | Repudiation | smoke test passes false-positive | mitigate | Smoke test includes both positive topology assertions and a negative bogus-ref failure-path assertion. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01-01 | T-01-02 | Inventory contents remain repo-local personal supplement metadata with no PHI classification or external exposure added by Phase 1. | GSD security audit | 2026-05-05 |
| AR-01-02 | T-01-06 | Local path disclosure in CLI errors is acceptable for a single-operator local tool. | GSD security audit | 2026-05-05 |

*Accepted risks do not resurface in future audit runs.*

---

## Verification Evidence

- `uv run planner.py check` exits 0 with final `All checks passed.`
- Direct inventory audit: `active_keys=0`, stack histogram `daily=11/training=4/inactive=8`.
- Direct product audit: all four training products carry the expected `activity:*` trait.
- Direct goal audit: all `members[].substance` refs resolve to `data/products/{ref}.yaml`.
- Code audit: `check_goals()` handles YAML parse errors, empty files, non-mapping top levels, schema validation, and missing product refs.
- Plan 01-04 negative test proved `bogus_substance_xyz` fails with `no matching product card` and restores `vascular_health.yaml` cleanly.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-05 | 9 | 9 | 0 | Codex / GSD secure-phase |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-05
