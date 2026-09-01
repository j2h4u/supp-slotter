"""Shared immutable compiler output for tests of the canonical ontology."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import cast

from scripts.ontology_compiler import compile_ontology

ONTOLOGY = Path(__file__).resolve().parents[1] / "ontology"


@cache
def _runtime_program_bytes() -> bytes:
    return compile_ontology(ONTOLOGY)[Path("runtime-program.json")]


def compiled_runtime_payload() -> dict[str, object]:
    """Return a fresh mutable decode of one cached immutable compilation."""

    return cast(dict[str, object], json.loads(_runtime_program_bytes()))
