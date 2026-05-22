# External Integrations

**Analysis Date:** 2026-05-22

## APIs & External Services

**Runtime services:**
- Not detected - `planner/` imports only standard-library modules plus local modules, PyYAML, and jsonschema; no HTTP clients, API SDKs, cloud SDKs, LLM SDKs, or webhook clients were detected.
  - SDK/Client: Not applicable
  - Auth: Not applicable

**Package registry:**
- PyPI - dependency source recorded in `uv.lock` for packages such as `pyyaml`, `jsonschema`, `pytest`, `ruff`, and `pyright`.
  - SDK/Client: uv, configured by `pyproject.toml` and `uv.lock`
  - Auth: Not detected; `.npmrc`, `.pypirc`, and `.netrc` were not read and no package-auth config was detected.

**CI services:**
- GitHub Actions - `.github/workflows/test.yml` runs tests for pushes to `main` and pull requests.
  - SDK/Client: workflow actions `actions/checkout@v4` and `astral-sh/setup-uv@v4`
  - Auth: repository-provided GitHub Actions token; no custom secret references detected in `.github/workflows/test.yml`.

**Reference URLs in data:**
- Product/source URLs are stored as plain metadata in `data/products/*.yaml` and template examples in `schema/templates/product.yaml`; the runtime search and planner read them locally but do not fetch them.
  - SDK/Client: none
  - Auth: none

## Data Storage

**Databases:**
- Local YAML files only.
  - Connection: local filesystem paths rooted at `data/`, defined by `planner/paths.py`.
  - Client: PyYAML via `planner/yaml_io.py`, `planner/cards/_common.py`, `planner/schedule_writer.py`, and `planner/maintenance.py`.
- No SQLite, PostgreSQL, MySQL, vector database, ORM, or migration framework detected.

**File Storage:**
- Local filesystem only.
- Source data lives in `data/stacks.yaml`, `data/pillboxes.yaml`, `data/relations.yaml`, split trait registries under `data/traits/`, `data/products/`, `data/substances/`, and `data/dashboards/`.
- Schemas live in `schema/*.schema.json`; templates live in `schema/templates/`.
- Generated schedule output is `schedule.yaml`, assembled by `planner/engine/plan.py` and written by `planner/schedule_writer.py`.
- Deterministic maintenance can rewrite card IDs, filenames, and references in `planner/maintenance.py`.

**Caching:**
- In-process YAML parse cache only - `planner/yaml_io.py` uses `functools.lru_cache` keyed by path and mtime.
- Tool caches exist at `.pytest_cache/` and `.ruff_cache/`; they are development artifacts, not application storage.
- No Redis, Memcached, HTTP cache, or persistent application cache detected.

## Authentication & Identity

**Auth Provider:**
- Not applicable - no web app, API server, users, sessions, OAuth, JWT, or password flow detected.
  - Implementation: Local CLI execution through `python -m planner` in `planner/__main__.py`.

## Monitoring & Observability

**Error Tracking:**
- None detected.

**Logs:**
- CLI stdout/stderr only.
- `planner/engine/check.py` prints validation info and errors; `planner/maintenance.py` prints warnings and lock/maintenance failures; `planner/engine/plan.py` prints schedule-write and slot-load summaries.

## CI/CD & Deployment

**Hosting:**
- Not deployed as a hosted service.
- GitHub Actions executes checks on Ubuntu as defined in `.github/workflows/test.yml`.

**CI Pipeline:**
- GitHub Actions in `.github/workflows/test.yml`.
- Pipeline steps: checkout, install uv, `uv sync --group dev`, `uv run ruff check .`, `uv run pyright`, `uv run python -m planner check`, and `uv run pytest tests/`.
- No release, packaging, artifact upload, container build, or production deploy job detected.

## Environment Configuration

**Required env vars:**
- None detected for application runtime.
- No `os.environ`, `os.getenv`, dotenv loader, token, database URL, API key, or secret access was detected in `planner/` or `scripts/`.

**Secrets location:**
- Not applicable.
- No `.env` files detected in repo root or first three directory levels.
- `.claude/settings.local.json` exists and is local tooling configuration; it was not treated as an application secret source.

## Webhooks & Callbacks

**Incoming:**
- None detected - no HTTP server, route handlers, webhook endpoints, socket server, or callback receivers in `planner/`.

**Outgoing:**
- None detected - no runtime HTTP calls, message queues, webhook posts, subprocess network calls, email, Telegram, Slack, cloud, or LLM integrations detected.

---

*Integration audit: 2026-05-22*
