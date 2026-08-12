"""Read-only semantic/evidence enrichment grooming queue."""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

from planner.cards.product import load_product_registry
from planner.cards.relations import check_global_relations, load_global_relations
from planner.cards.substance import load_substance_registry
from planner.contracts import CardLoadError, Substance
from planner.engine.results import GroomingCandidate, GroomingResult
from planner.ontology.artifacts import OntologyBundle, load_ontology
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.policies import load_scheduling_policies
from planner.paths import ROOT, Paths
from planner.query_model import build_stack_read_model, stacks_for_read_model
from planner.query_model.surreal import SurrealLoadContext
from planner.schema_validation import validate_schemas
from planner.yaml_io import load_yaml


def cmd_grooming_next(limit: int = 8, data_root: Path | None = None) -> GroomingResult:
    """Return the next deterministic batch without writing cards or schedules."""
    if limit <= 0:
        message = "grooming next: --limit must be a positive integer"
        print(message, file=sys.stderr)
        return GroomingResult(exit_code=1, candidates=[], limit=limit, output="", stderr=message + "\n")

    paths = Paths.from_root(data_root) if data_root is not None else Paths.default()
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        exit_code, candidates = _grooming_next_inner(paths, load_ontology(ROOT / "ontology"), limit)
        if exit_code == 0:
            _render_candidates(candidates)
    return GroomingResult(
        exit_code=exit_code,
        candidates=candidates,
        limit=limit,
        output=stdout_buf.getvalue(),
        stderr=stderr_buf.getvalue(),
    )


def _grooming_next_inner(paths: Paths, bundle: OntologyBundle, limit: int) -> tuple[int, list[GroomingCandidate]]:
    schema_result = validate_schemas(paths, bundle)
    if schema_result != 0:
        return schema_result, []
    try:
        substances = load_substance_registry(paths, bundle)
        products = load_product_registry(paths, bundle)
        relations_data = load_yaml(paths.relations_file)
        relation_errors = check_global_relations(relations_data, substances, paths, bundle)
        if relation_errors:
            _print_errors(relation_errors)
            return 1, []
        relations = load_global_relations(paths, bundle, substances)
        policies = load_scheduling_policies(bundle)
        stacks_data = stacks_for_read_model(paths) if paths.stacks_file.exists() else {}
        read_model = build_stack_read_model(
            substances,
            relations,
            products,
            context=SurrealLoadContext(
                policies=policies,
                stacks_data=stacks_data,
                pillbox_stack_names=None,
                dashboards=None,
            ),
            ontology_bundle=bundle,
        )
    except (CardLoadError, OntologyInfrastructureError) as error:
        _print_errors([f"grooming next: {error.message if isinstance(error, CardLoadError) else error}"])
        return 1, []

    active_ids = read_model.active_substance_ids()
    candidates = [
        GroomingCandidate(substance.id, substance.name, _substance_path(paths, substance))
        for substance in substances.values()
        if substance.id in active_ids and substance.semantic_enrichment_attempted_on is None
    ]
    candidates.sort(key=lambda item: (item.name.casefold(), item.id))
    return 0, candidates[:limit]


def _substance_path(paths: Paths, substance: Substance) -> Path:
    matches = sorted(paths.substances.glob(f"*__{substance.id}.yaml"))
    return matches[0] if matches else paths.substances


def _render_candidates(candidates: list[GroomingCandidate]) -> None:
    print("Grooming queue: semantic/evidence enrichment candidates")
    if not candidates:
        print("  none")
        return
    for candidate in candidates:
        print(f"  {candidate.name} [{candidate.id}]")


def _print_errors(errors: list[str]) -> None:
    for error in errors:
        print(error, file=sys.stderr)
