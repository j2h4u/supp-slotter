"""Human-facing output for `planner check`."""

from __future__ import annotations

import sys

from planner.paths import strip_root_prefix


def report(errors: list[str], info: list[str]) -> int:
    """Print info lines to stdout and error lines to stderr."""
    for message in info:
        print(f"INFO: {strip_root_prefix(message)}")
    if errors:
        for error in errors:
            print(f"ERROR: {strip_root_prefix(error)}", file=sys.stderr)
        print(f"\n{len(errors)} error(s) found", file=sys.stderr)
        return 1
    print("All checks passed.")
    return 0
