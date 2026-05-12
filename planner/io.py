"""I/O primitives, repo-root constants, schema validation."""

from __future__ import annotations

import functools
import json
import sys
from pathlib import Path
from typing import Any, cast

# jsonschema is imported lazily inside schema_errors() so that importing planner
# as a module (e.g. from a pytest environment without jsonschema installed) does
# not require the schema-validation dependency.
import yaml

from planner.contracts import CardLoadError

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SCHEMA_DIR = ROOT / "schema"
SUBSTANCES_DIR = DATA_DIR / "substances"
PRODUCTS_DIR = DATA_DIR / "products"
DASHBOARDS_DIR = DATA_DIR / "dashboards"
STACKS_PATH = DATA_DIR / "stacks.yaml"
RELATIONS_PATH = DATA_DIR / "relations.yaml"
SCHEDULE_PATH = ROOT / "schedule.yaml"
MAINTENANCE_LOCK_DIR = ROOT / ".planner-maintenance.lock"

VALID_LEVELS = {"avoid_strong", "avoid", "prefer", "prefer_strong"}
REGISTERED_NAMESPACES = {
    "intake",
    "effect",
    "is",
    "risk",
    "activity",
    "dashboard",
}
SLOT_META_FIELDS = {"label", "order"}

LEVEL_SCORES = {
    "prefer_strong": 4,
    "prefer": 2,
    "avoid": -2,
    "avoid_strong": -4,
}

# SECONDARY_TRAIT_WEIGHT — slot-score multiplier for traits carried only by
# non-primary (companion) components in a multi-component product.
#
# Design constraint: a primary component's preference must always beat a
# secondary component's preference. Worst case to defeat: primary says
# `prefer` in slot A and `avoid` in slot B; a secondary says `prefer_strong`
# in slot B and `avoid_strong` in slot A. We need score(A) >= score(B):
#
#   prefer  - prefer_strong * w  >=  avoid + prefer_strong * w
#   (prefer - avoid) >= 2 * prefer_strong * w
#   w <= (prefer - avoid) / (2 * prefer_strong)         # upper bound
#
# Take half the upper bound for a comfortable margin:
#   w = (prefer - avoid) / (4 * prefer_strong)
#     = (2 - (-2)) / (4 * 4)
#     = 0.25
#
# Self-adjusts if LEVEL_SCORES is ever retuned.
SECONDARY_TRAIT_WEIGHT = (
    LEVEL_SCORES["prefer"] - LEVEL_SCORES["avoid"]
) / (4 * LEVEL_SCORES["prefer_strong"])

BALANCE_WEIGHT = 0.5
PREFER_WITH_BONUS = 3
NANOID_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
STABLE_ID_SIZE = 10
SIMILAR_SUBSTANCE_THRESHOLD = 0.86
FIND_MIN_SCORE = 0.55
FIND_MIN_WORD_SCORE = 0.65


@functools.lru_cache(maxsize=512)
def _parse_yaml_cached(path: Path, mtime_ns: int) -> object:
    try:
        return yaml.safe_load(path.read_text())
    except OSError as e:
        raise CardLoadError(path, f"{path}: {e}") from e
    except yaml.YAMLError as e:
        raise CardLoadError(path, f"{path}: invalid YAML: {e}") from e


def load_yaml(path: Path) -> object:
    """Read and parse a YAML file; returns the raw Python object (may be any type — callers must guard).

    Cached by (path, mtime_ns) — repeated reads of unchanged files are free.
    Raises CardLoadError with a message naming the file on OSError or parse failure.
    """
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError as e:
        raise CardLoadError(path, f"{path}: {e}") from e
    return _parse_yaml_cached(path, mtime_ns)

def load_yaml_mapping(path: Path) -> dict[str, Any]:
    """Load a YAML file and require the top-level to be a mapping.

    Raises CardLoadError if the file is not a mapping.
    """
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise CardLoadError(
            path, f"{path}: expected mapping, got {type(data).__name__}"
        )
    return cast(dict[str, Any], data)

def load_schema(name: str) -> dict[str, Any]:
    """Load a JSON schema by name from SCHEMA_DIR.

    Raises RuntimeError naming the schema file on read or parse failure.
    """
    schema_path = SCHEMA_DIR / f"{name}.schema.json"
    try:
        text = schema_path.read_text()
    except OSError as e:
        raise RuntimeError(f"could not read schema {schema_path}: {e}") from e
    try:
        return cast(dict[str, Any], json.loads(text))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"could not parse schema {schema_path}: {e}") from e

def schema_errors(data: object, schema_name: str, file_path: Path) -> list[str]:
    """Validate `data` against the named JSON schema; returns a list of `path: location: message` strings (empty = valid)."""
    import jsonschema
    schema = load_schema(schema_name)
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )
    out: list[str] = []
    for err in validator.iter_errors(data):  # type: ignore[arg-type]
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{file_path}: {loc}: {err.message}")
    return out

def strip_root_prefix(message: str) -> str:
    root = str(ROOT.resolve())
    return message.replace(f"{root}/", "")

def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)

SCHEDULE_COMMENTS = {
    "summary": [
        "Generated by `uv run python -m planner plan`; edit source cards under data/, not this file.",
        "Short human-facing summary.",
        "`take` is grouped by pillbox so daily and training products do not read as one regimen.",
        "Review `action_points` before using the schedule.",
    ],
    "action_points": [
        "Highest-signal review actions from warnings and planner constraints.",
        "These are prompts for human review, not medical advice.",
    ],
    "review_contexts": [
        "Grouped review checklist derived from warnings.",
        "Use this to scan practical concern areas before reading detailed warnings.",
    ],
    "placement_notes": [
        "Non-warning placement compromises.",
        "These explain acceptable but imperfect slot choices; they are not safety warnings.",
    ],
    "pillboxes": [
        "Planned pillboxes and their intake slots.",
        "`products` lists scheduled product names; `substances` expands those products for human review.",
    ],
    "benefits": [
        "Benefit coverage overview.",
        "`coverage_percent` counts taking benefit-cluster substances currently active in scheduled stacks.",
    ],
    "risks": [
        "Risk load overview.",
        "`active_count` counts taking risk-cluster substances currently active in scheduled stacks.",
    ],
    "warnings": [
        "Detailed review warnings behind action_points.",
        "Warnings are prompts for human review; they are not medical advice.",
    ],
    "kept_together": [
        "Product pairs the planner tried to place in the same slot.",
        "`together` says whether they landed together.",
    ],
    "explanations": [
        "Per-product placement explanation.",
        "`slot` is the chosen slot; `components` lists the product substances that drove scheduling.",
        "`why_here` summarizes why this slot was selected.",
        "`review_tags` are readable traits aggregated from the product substances.",
    ],
}

def dump_schedule_yaml(schedule: dict[str, Any]) -> str:
    """Serialise schedule to YAML and inject human-readable comment blocks above each top-level key."""
    rendered = yaml.safe_dump(
        schedule,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    lines: list[str] = []
    for line in rendered.splitlines():
        key = line.split(":", 1)[0] if line and not line.startswith(" ") else ""
        if key in SCHEDULE_COMMENTS:
            lines.extend(f"# {comment}" for comment in SCHEDULE_COMMENTS[key])
        lines.append(line)
    return "\n".join(lines) + "\n"

WARNING_CATEGORY_LABELS = {
    "intra_product_relation_conflict": "Component conflict inside one product",
    "intra_product_trait_conflict": "Timing conflict inside one product",
    "ambiguous_prefer_with": "Companion product is ambiguous",
    "missing_balance_substance": "Missing balancing substance",
    "missing_support_substance": "Missing supporting substance",
    "antagonizes_substance_present": "Active antagonist pairing",
    "safety_concern": "Safety concern",
    "risk_cluster_load": "Risk load",
}

REVIEW_CONTEXTS = {
    "bleeding_context": "Bleeding context",
    "blood_pressure": "Blood pressure / vasodilation",
    "cholinergic_load": "Cholinergic load",
    "intra_product_conflicts": "Intra-product conflicts",
    "missing_pairings": "Missing balance/support pairings",
    "narrow_window_minerals": "Narrow-window minerals",
    "potassium_medication": "Potassium / medication context",
    "timing_conflicts": "Timing conflicts",
    "safety_concerns": "Safety concerns",
}

def report(errors: list[str], info: list[str]) -> int:
    """Print info lines to stdout and error lines to stderr; returns 1 if any errors, 0 otherwise."""
    for msg in info:
        print(f"INFO: {strip_root_prefix(msg)}")
    if errors:
        for e in errors:
            print(f"ERROR: {strip_root_prefix(e)}", file=sys.stderr)
        print(f"\n{len(errors)} error(s) found", file=sys.stderr)
        return 1
    print("All checks passed.")
    return 0

def validate_schemas() -> int:
    """Validate every YAML data file against its JSON Schema.

    Pure structural validation — does not run cross-reference checks, housekeeping,
    or auto-rename. Use as a fail-fast guard at the start of every command so the
    application refuses to operate on schema-broken data. Returns 0 on success,
    non-zero with errors printed to stderr otherwise.
    """
    errors: list[str] = []

    singular_files = [
        (DATA_DIR / "pillboxes.yaml", "pillboxes"),
        (DATA_DIR / "traits.yaml", "traits"),
        (RELATIONS_PATH, "relations"),
        (STACKS_PATH, "stacks"),
    ]
    for path, schema_name in singular_files:
        if not path.exists():
            errors.append(f"missing: {path}")
            continue
        data = load_yaml(path)
        errors.extend(schema_errors(data, schema_name, path))

    collections = [
        (SUBSTANCES_DIR, "substance"),
        (PRODUCTS_DIR, "product"),
        (DASHBOARDS_DIR, "dashboard"),
    ]
    for directory, schema_name in collections:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            data = load_yaml(path)
            errors.extend(schema_errors(data, schema_name, path))

    if errors:
        for e in errors:
            print(f"ERROR: {strip_root_prefix(e)}", file=sys.stderr)
        print(f"\n{len(errors)} schema error(s) found", file=sys.stderr)
        return 1
    return 0
