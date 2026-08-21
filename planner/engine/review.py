"""The concise active-stack `review` command."""

from __future__ import annotations

import contextlib
import io as _io
import sys
from pathlib import Path

from planner.engine.results import ReviewResult
from planner.engine.review_model import build_review_model
from planner.engine.review_render import render_review
from planner.ontology.artifacts import OntologyBundle, load_ontology
from planner.ontology.errors import OntologyInfrastructureError
from planner.paths import ROOT, Paths
from planner.schema_validation import validate_schemas


def _review_inner(paths: Paths, bundle: OntologyBundle) -> int:
    try:
        schema_result = validate_schemas(paths, bundle)
        if schema_result != 0:
            return schema_result
        model, errors = build_review_model(paths, bundle)
    except OntologyInfrastructureError as error:
        _print_errors([f"review: ontology infrastructure error: {error}"])
        return 1
    if model is None:
        _print_errors(errors)
        return 1

    render_review(model)
    return 0


def cmd_review(data_root: Path | None = None) -> ReviewResult:
    """Knowledge-section review of concerns, relations, fact memberships, and dashboards."""
    paths = Paths.from_root(data_root) if data_root is not None else Paths.default()
    if data_root is not None:
        stdout_buf = _io.StringIO()
        stderr_buf = _io.StringIO()
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            exit_code = _review_inner(paths, load_ontology(ROOT / "ontology"))
        return ReviewResult(
            exit_code=exit_code,
            output=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
        )

    exit_code = _review_inner(paths, load_ontology(ROOT / "ontology"))
    return ReviewResult(exit_code=exit_code, output="", stderr="")


def _print_errors(errors: list[str]) -> None:
    for error in errors:
        print(error, file=sys.stderr)
