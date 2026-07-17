"""Ontology-specific failures with an explicit fail-closed boundary."""

MISSING = "missing"
STALE = "stale"
UNSAFE_PATH = "unsafe_path"
MALFORMED = "malformed"
UNSUPPORTED = "unsupported"


class OntologyInfrastructureError(RuntimeError):
    """Raised when ontology generation, artifact loading, or SHACL cannot run.

    ``code`` is intentionally a small, stable vocabulary.  Command boundaries
    must turn this into a non-zero result; callers must not turn it into an
    empty list of validation errors.
    """

    def __init__(self, message: str, *, code: str = MALFORMED, path: object | None = None) -> None:
        self.code: str = code
        # ``violation_code`` is retained as a descriptive alias for callers
        # that use the terminology from the artifact contract.
        self.violation_code: str = code
        self.path: object | None = path
        super().__init__(message)
