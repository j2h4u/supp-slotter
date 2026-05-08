"""CI-friendly check: every YAML data file in the repo conforms to its schema.

Direct counterpart of `planner.validate_schemas()` against the live `data/`
tree. Failure here is a hard signal that the repo state is structurally broken
— before any cross-reference logic, planner output, or downstream tests run.
"""

from __future__ import annotations

from planner import validate_schemas


def test_repo_passes_schema_validation() -> None:
    assert validate_schemas() == 0, (
        "schema validation failed for files in data/; see stderr for details"
    )
