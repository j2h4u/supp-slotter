"""Structural view of the ontology bundle used by decoding helpers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from planner.ontology.runtime_program import RuntimeProgram


@runtime_checkable
class OntologyBundleView(Protocol):
    """Read-only bundle shape required by ontology decoding helpers.

    ``decoded`` is keyed by generated artifact filename.  Its values are the
    decoded JSON/YAML objects (or decoded text for textual artifacts), while
    ``runtime_vocabulary`` is the decoded ``runtime-vocabulary.yaml`` mapping.
    This structural view describes data shape only; it does not prove how the
    bundle was loaded or establish verification provenance.
    """

    @property
    def root(self) -> Path:
        ...

    @property
    def decoded(self) -> Mapping[str, object]:
        ...

    @property
    def runtime_vocabulary(self) -> Mapping[str, object]:
        ...

    @property
    def runtime_program(self) -> RuntimeProgram:
        ...
