---
phase: 02
slug: substance-product-yaml-model-split
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-05
verified: 2026-05-05T20:55:00Z
---

# Phase 02 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| local operator -> YAML files | Manual local edits define supplement data, products, inventory, slots, traits, and goals. | Local YAML content; personal supplement inventory. |
| YAML files -> validator | Local YAML is untrusted until schema and reference validation completes. | Parsed YAML mappings, ids, references, and trait metadata. |
| validated YAML -> scheduler | Scheduler consumes local files only after `cmd_check` passes. | Validated registries and active inventory items. |
| tests -> generated artifacts | Tests and CLI smoke commands may regenerate `schedule.yaml` locally. | Deterministic local generated YAML. |
| CLI target path -> validator | Single-file target checks narrow the checked file but still depend on full registries for references. | Target file path and registry-backed references. |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-02-01-01 | Tampering | YAML migration | mitigate | Strict schemas use `additionalProperties: false`, required fields, enums, and `uv run planner.py check` validates migrated YAML and references. | closed |
| T-02-01-02 | Information disclosure | inventory contents | mitigate | Phase remains repo-local: no network endpoint, server, database, auth path, or import workflow was introduced. | closed |
| T-02-01-03 | Safety | product formula conflicts | mitigate | Product formulas preserve component lists; scheduler aggregates component traits into one physical item and emits intra-product conflict warnings without splitting components. | closed |
| T-02-02-01 | Tampering | product component refs | mitigate | `check_product_formulas` rejects missing `components[].substance` refs before planning; regression covers bogus component refs. | closed |
| T-02-02-02 | Tampering | inventory product refs | mitigate | `check_inventory_alignment` rejects missing inventory `product` refs before planning. | closed |
| T-02-02-03 | Safety | goal ref ambiguity | mitigate | `check_goals` validates goal `members[].substance` refs against substance cards; candidates may remain name-only by schema. | closed |
| T-02-03-01 | Safety | product component scheduling | mitigate | `cmd_plan` schedules inventory item ids and records `product` plus `components` in explanations; tests assert multicomponent nattokinase schedules as one item. | closed |
| T-02-03-02 | Safety | hidden warning source | mitigate | Warning entries include item, product, substance or component trait context; tests assert intra-product and ambiguous `prefer_with` warning payloads. | closed |
| T-02-03-03 | Tampering | generated schedule | mitigate | `cmd_plan` runs `cmd_check` first and regenerates deterministic local `schedule.yaml` from checked YAML. | closed |
| T-02-04-01 | Tampering | regression tests | mitigate | Tests assert old shape is absent, split refs are valid, and Phase 1 topology still holds after migration. | closed |
| T-02-04-02 | Safety | multicomponent scheduling regression | mitigate | Regression tests assert multicomponent products remain inseparable and warn on internal component conflicts. | closed |
| T-02-04-03 | Reliability | stale schedule output | mitigate | Final and security smoke runs execute `uv run planner.py plan`, which checks data and rewrites `schedule.yaml`. | closed |
| T-02-05-01 | Denial of service | `planner.py::validate_inventory` | mitigate | Inventory alignment and override checks skip non-mapping supplement entries, so malformed YAML reports schema errors without traceback. | closed |
| T-02-05-02 | Tampering | `planner.py::cmd_check(target)` | mitigate | Target substance checks validate `prefer_with` refs against the full substance registry via `prefer_with_registry`. | closed |
| T-02-05-03 | Repudiation | `tests/test_phase_02.py` | mitigate | Regressions cover target-mode `creatine.yaml` validation and malformed inventory handling, preserving executable evidence. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

No accepted risks.

---

## Verification Evidence

| Check | Result |
|-------|--------|
| `uv run planner.py check` | Passed; `All checks passed.` |
| `uv run pytest -q` | Passed; 17 tests. |
| `uv run planner.py check data/substances/creatine.yaml` | Passed; target-mode `prefer_with` registry resolution verified. |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-05 | 15 | 15 | 0 | Codex inline GSD security audit |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-05
