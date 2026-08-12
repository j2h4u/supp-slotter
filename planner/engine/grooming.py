"""Read-only semantic/evidence enrichment grooming queue."""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path
from typing import cast

from planner.cards.product import load_product_registry
from planner.cards.relations import check_global_relations, load_global_relations
from planner.cards.substance import load_substance_registry
from planner.contracts import CardLoadError, Product, Substance
from planner.engine.results import GroomingCandidate, GroomingResult
from planner.ontology.artifacts import OntologyBundle, load_ontology
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.policies import load_scheduling_policies
from planner.ontology.runtime_program import (
    SUPPORTED_GROOMING_ELIGIBILITY,
    RuntimeSemanticEnrichmentGroomingPolicy,
)
from planner.paths import ROOT, Paths
from planner.query_model import build_stack_read_model
from planner.query_model.surreal import SurrealLoadContext
from planner.schema_validation import validate_schemas
from planner.yaml_io import load_yaml, load_yaml_mapping


def cmd_grooming_next(limit: int | None = None, data_root: Path | None = None) -> GroomingResult:
    """Return the next deterministic batch without writing cards or schedules."""
    if limit is not None and limit <= 0:
        message = "grooming next: --limit must be a positive integer"
        print(message, file=sys.stderr)
        return GroomingResult(
            exit_code=1,
            candidates=[],
            limit=limit or 0,
            total_remaining=0,
            shown=0,
            output="",
            stderr=message + "\n",
        )

    paths = Paths.from_root(data_root) if data_root is not None else Paths.default()
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        exit_code, candidates, total_remaining, resolved_limit = _grooming_next_inner(
            paths, load_ontology(ROOT / "ontology"), limit
        )
        if exit_code == 0:
            _render_candidates(candidates, total_remaining)
    return GroomingResult(
        exit_code=exit_code,
        candidates=candidates,
        limit=resolved_limit,
        total_remaining=total_remaining,
        shown=len(candidates),
        output=stdout_buf.getvalue(),
        stderr=stderr_buf.getvalue(),
    )


def _grooming_next_inner(
    paths: Paths, bundle: OntologyBundle, limit: int | None
) -> tuple[int, list[GroomingCandidate], int, int]:
    resolved_limit = limit if limit is not None else bundle.runtime_program.semantic_enrichment_grooming.default_batch_size
    schema_result = validate_schemas(paths, bundle)
    if schema_result != 0:
        return schema_result, [], 0, resolved_limit
    try:
        substances = load_substance_registry(paths, bundle)
        products = load_product_registry(paths, bundle)
        relations_data = load_yaml(paths.relations_file)
        relation_errors = check_global_relations(relations_data, substances, paths, bundle)
        if relation_errors:
            _print_errors(relation_errors)
            return 1, [], 0, resolved_limit
        relations = load_global_relations(paths, bundle, substances)
        policies = load_scheduling_policies(bundle)
        stacks_data = _stacks_for_grooming_read_model(paths)
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
        return 1, [], 0, resolved_limit

    grooming_policy = bundle.runtime_program.semantic_enrichment_grooming
    active_ids = read_model.active_substance_ids()
    product_ids_by_substance = _product_ids_by_substance(products)
    inactive_stack_name = bundle.runtime_program.glue_contract.inactive_stack_name
    active_product_ids = {
        product_id
        for stack_name, product_ids in stacks_data.items()
        if stack_name != inactive_stack_name
        for product_id in product_ids
    }
    all_candidates = [
        GroomingCandidate(
            substance.id,
            substance.name,
            _substance_path(paths, substance),
            total_product_count=len(product_ids_by_substance.get(substance.id, set())),
            active_product_count=len(product_ids_by_substance.get(substance.id, set()) & active_product_ids),
        )
        for substance in substances.values()
        if _grooming_eligible(grooming_policy, substance.id, active_ids, substance.semantic_enrichment_attempted_on)
    ]
    all_candidates.sort(key=lambda item: _grooming_sort_key(item, grooming_policy.roi_order_desc))
    return 0, all_candidates[:resolved_limit], len(all_candidates), resolved_limit


def _grooming_eligible(
    policy: RuntimeSemanticEnrichmentGroomingPolicy,
    substance_id: str,
    active_ids: set[str],
    semantic_enrichment_attempted_on: str | None,
) -> bool:
    if policy.eligibility != SUPPORTED_GROOMING_ELIGIBILITY:
        raise ValueError(f"unsupported semantic enrichment grooming eligibility {policy.eligibility!r}")
    return substance_id in active_ids and semantic_enrichment_attempted_on is None


def _product_ids_by_substance(products: dict[str, Product]) -> dict[str, set[str]]:
    product_ids_by_substance: dict[str, set[str]] = {}
    for product in products.values():
        for component in product.components:
            product_ids_by_substance.setdefault(component.substance, set()).add(product.id)
    return product_ids_by_substance


def _grooming_metric(candidate: GroomingCandidate, metric: str) -> int:
    if metric == "active_unique_product_count":
        return candidate.active_product_count
    if metric == "total_unique_product_count":
        return candidate.total_product_count
    raise ValueError(f"unsupported semantic enrichment grooming metric {metric!r}")


def _grooming_sort_key(candidate: GroomingCandidate, roi_order_desc: tuple[str, ...]) -> tuple[object, ...]:
    metric_key = tuple(-_grooming_metric(candidate, metric) for metric in roi_order_desc)
    return (*metric_key, candidate.name.casefold(), candidate.id)


def _stacks_for_grooming_read_model(paths: Paths) -> dict[str, list[str]]:
    """Load schema-validated stacks without collapsing repeated memberships."""
    raw = load_yaml_mapping(paths.stacks_file)
    return {
        name: [item for item in cast(list[object], items) if isinstance(item, str)]
        for name, items in raw.items()
        if isinstance(items, list)
    }


def _substance_path(paths: Paths, substance: Substance) -> Path:
    matches = sorted(paths.substances.glob(f"*__{substance.id}.yaml"))
    return matches[0] if matches else paths.substances


def _render_candidates(candidates: list[GroomingCandidate], total_remaining: int) -> None:
    print(f"Grooming queue: {total_remaining} remaining, showing {len(candidates)}")
    if not candidates:
        print("  none")
        return
    for candidate in candidates:
        print(
            f"  {candidate.name} [{candidate.id}] — "
            f"{candidate.active_product_count} active unique products, "
            f"{candidate.total_product_count} total unique products"
        )


def _print_errors(errors: list[str]) -> None:
    for error in errors:
        print(error, file=sys.stderr)
