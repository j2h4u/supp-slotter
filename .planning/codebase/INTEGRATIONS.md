# External Integrations

**Analysis Date:** 2026-05-05

## APIs & External Services

**Runtime APIs:**
- Not detected - `planner.py` imports only standard library modules plus `jsonschema` and `yaml`; no `requests`, `httpx`, `urllib`, sockets, SDK clients, or service-specific packages are used.

**Schema Standards:**
- JSON Schema Draft 2020-12 - Local schema files in `schema/*.schema.json` declare `"$schema": "https://json-schema.org/draft/2020-12/schema"`.
  - SDK/Client: `jsonschema` package in `planner.py`.
  - Auth: Not applicable; schema URL is a standards identifier, not a runtime API call.

**Package Resolution:**
- Python package index access may be used by `uv run planner.py ...` to resolve inline dependencies from `planner.py` when the environment is cold.
  - SDK/Client: `uv` command invoked by tests in `tests/test_phase_01.py`.
  - Auth: Not detected; no `.pypirc`, `.netrc`, `.npmrc`, or package credential file detected.

## Data Storage

**Databases:**
- Not detected - no SQLite, PostgreSQL, MySQL, Redis, SQLAlchemy, ORM, database URL, migration directory, or database client is used in `planner.py`.
  - Connection: Not applicable.
  - Client: Not applicable.

**File Storage:**
- Local filesystem only.
- Source data lives in `data/slots.yaml`, `data/traits.yaml`, `data/inventory.yaml`, `data/products/*.yaml`, and `data/goals/*.yaml`.
- Validation schemas live in `schema/goal.schema.json`, `schema/inventory.schema.json`, `schema/product.schema.json`, `schema/slots.schema.json`, and `schema/traits.schema.json`.
- Generated output lives in `schedule.yaml`; `planner.py` writes it during the `plan` subcommand.
- Inventory refresh mutates `data/inventory.yaml`; `planner.py` writes it during the `refresh` subcommand.

**Caching:**
- No application cache detected in `planner.py`.
- `.pytest_cache/` exists as pytest tooling cache, not application runtime storage.

## Authentication & Identity

**Auth Provider:**
- Not detected.
  - Implementation: `planner.py` has no user identity, session, token, OAuth, API key, or auth middleware code.

## Monitoring & Observability

**Error Tracking:**
- None detected.

**Logs:**
- CLI stdout/stderr only.
- `planner.py` prints validation info and success messages to stdout through `report(...)`.
- `planner.py` prints errors, warnings, and planning progress to stderr in `cmd_check(...)`, `cmd_refresh(...)`, and `cmd_plan(...)`.
- Tests assert stdout/stderr behavior through `subprocess.run(..., capture_output=True)` in `tests/test_phase_01.py`.

## CI/CD & Deployment

**Hosting:**
- None detected - the project is a local CLI and data repository; no web server, function runtime, container, or hosted deployment config exists.

**CI Pipeline:**
- None detected - no `.github/workflows/`, GitLab CI, CircleCI, or other CI config detected in the repository file list.

## Environment Configuration

**Required env vars:**
- None detected - `planner.py` uses no `os.environ` access and no environment variable names were found.

**Secrets location:**
- Not applicable - no `.env`, secret, credential, certificate, SSH key, or package-auth file detected in the scanned repository scope.

## Webhooks & Callbacks

**Incoming:**
- None detected - no HTTP server, route handler, webhook endpoint, or callback handler exists in `planner.py`.

**Outgoing:**
- None detected - `planner.py` performs no HTTP calls, message publishing, email delivery, SDK calls, or callbacks.

---

*Integration audit: 2026-05-05*
