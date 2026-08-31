"""Core result records for exact canonical optimization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DiagnosticCode = Literal[
    "invalid_input",
    "contradiction",
    "timeout",
    "interrupted",
    "resource_exhausted",
    "proof_failed",
    "infrastructure_failed",
    "publication_failed",
]


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Closed failure diagnostic emitted by a canonical planning boundary."""

    code: DiagnosticCode
    message: str


@dataclass(frozen=True, slots=True)
class CanonicalObjective:
    """The exact observable objective of a proved layout."""

    satisfied_pressures: int
    squared_load: int
    assignment_key: tuple[tuple[int, str], ...]


@dataclass(frozen=True, slots=True)
class Optimal:
    """A proved globally optimal layout."""

    assignments: dict[str, str]
    objective: CanonicalObjective
    proofs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Indeterminate:
    """A layout-free result when optimality cannot be proved."""

    diagnostic: Diagnostic


CanonicalOptimizerResult = Optimal | Indeterminate
