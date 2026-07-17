"""`review` and `review-substance` commands."""

from __future__ import annotations

import contextlib
import io as _io
import sys
from pathlib import Path

from planner.engine.results import ReviewResult
from planner.engine.review_model import build_review_model
from planner.engine.review_render import render_review
from planner.engine.review_substance_model import (
    build_substance_review_model,
    resolve_substance_review_path,
)
from planner.engine.review_substance_render import render_substance_review
from planner.ontology.artifacts import load_ontology
from planner.ontology.artifacts import OntologyBundle
from planner.paths import ROOT, Paths
from planner.schema_validation import validate_schemas


def _review_inner(paths: Paths, bundle: OntologyBundle) -> int:
    schema_result = validate_schemas(paths, bundle)
    if schema_result != 0:
        return schema_result

    model, errors = build_review_model(paths, bundle)
    if model is None:
        _print_errors(errors)
        return 1

    render_review(model)
    return 0


def cmd_review(data_root: Path | None = None) -> ReviewResult:
    """Knowledge-section review of concerns, relations, risks, pathways, and dashboards."""
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


def cmd_review_substance(
    target: str,
    data_root: Path | None = None,
    *,
    compact: bool = False,
) -> ReviewResult:
    """Show a grouped trait checklist for one substance card."""
    paths = Paths.from_root(data_root) if data_root is not None else Paths.default()
    stdout_buf = _io.StringIO()
    with contextlib.redirect_stdout(stdout_buf):
        exit_code = _review_substance_inner(
            target, paths, load_ontology(ROOT / "ontology"), compact=compact
        )
    return ReviewResult(
        exit_code=exit_code,
        output=stdout_buf.getvalue(),
        stderr="",
    )


def _review_substance_inner(
    target: str, paths: Paths, bundle: OntologyBundle, *, compact: bool
) -> int:
    path, path_error = resolve_substance_review_path(target, paths)
    if path is None:
        print(path_error, file=sys.stderr)
        return 1

    schema_result = validate_schemas(paths, bundle)
    if schema_result != 0:
        return schema_result

    model, errors = build_substance_review_model(path, paths, bundle)
    if model is None:
        _print_errors(errors)
        return 1

    render_substance_review(model, compact=compact)
    return 0


def _print_errors(errors: list[str]) -> None:
    for error in errors:
        print(error, file=sys.stderr)
