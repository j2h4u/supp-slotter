"""Ontology-specific failures with an explicit fail-closed boundary."""

from __future__ import annotations


class OntologyInfrastructureError(RuntimeError):
    """Raised when ontology generation, artifact loading, or SHACL cannot run.

    This is deliberately distinct from a semantic data violation.  Command
    boundaries must turn it into a non-zero result; callers must not turn it
    into an empty list of validation errors.
    """
