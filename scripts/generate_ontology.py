"""Generate or freshness-check the canonical ontology artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import cast

# ``python scripts/generate_ontology.py`` puts ``scripts/`` rather than the
# repository root on sys.path.  Keep this standalone CI entrypoint usable
# without requiring callers to set PYTHONPATH.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from planner.ontology.errors import OntologyInfrastructureError  # noqa: E402
from planner.ontology.generate import generate_ontology  # noqa: E402


def main() -> int:
    """Run the deterministic ontology generator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if committed artifacts are stale")
    parser.add_argument("--ontology-root", type=Path, default=Path("ontology"))
    values = cast(dict[str, object], vars(parser.parse_args()))
    ontology_root = values["ontology_root"]
    check = values["check"]
    if not isinstance(ontology_root, Path) or not isinstance(check, bool):
        parser.error("Invalid ontology generator arguments")
    try:
        generate_ontology(ontology_root, check=check)
    except OntologyInfrastructureError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
