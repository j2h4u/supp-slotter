"""Read-only deterministic grooming for active candidate coverage."""

from __future__ import annotations

import contextlib
import io
from collections.abc import Mapping
from pathlib import Path

from planner.card_ids import composition_role_id
from planner.cards.product import load_product_registry
from planner.cards.relations import load_global_relations
from planner.cards.stacks import normalize_stack_entries
from planner.cards.substance import load_substance_registry
from planner.contracts import CardLoadError, Product, Substance
from planner.engine.results import GroomResult, GroomWorkItem
from planner.ontology.artifacts import OntologyBundle, load_ontology
from planner.ontology.candidate_catalog import load_candidate_catalog
from planner.ontology.coverage import load_coverage_closure, validate_coverage_closure
from planner.ontology.errors import OntologyInfrastructureError
from planner.paths import ROOT, Paths
from planner.schema_validation import validate_schemas
from planner.yaml_io import load_yaml


def cmd_groom(data_root: Path | None = None) -> GroomResult:
    """Show the next canonical coverage item, or a stale global closure."""
    bundle = load_ontology(ROOT / "ontology")
    stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        try:
            paths = Paths.from_root(data_root) if data_root is not None else Paths.default()
            schema_result = validate_schemas(paths, bundle)
            if schema_result != 0:
                return GroomResult(schema_result, None, 0, stderr=stderr_buf.getvalue())
            selected, eligible_count = _select_work_items(paths, bundle)
            work_item = selected[0] if selected else None
            _render(selected, eligible_count)
            return GroomResult(0, work_item, eligible_count, stdout_buf.getvalue(), stderr_buf.getvalue())
        except (CardLoadError, OntologyInfrastructureError, ValueError) as error:
            message = error.message if isinstance(error, CardLoadError) else str(error)
            return GroomResult(1, None, 0, stderr=message + "\n")


def _select_work_items(paths: Paths, bundle: OntologyBundle) -> tuple[tuple[GroomWorkItem, ...], int]:
    substances = load_substance_registry(paths, bundle)
    products = load_product_registry(paths, bundle)
    catalog = load_candidate_catalog(paths.data / "scheduling-candidates.yaml")
    relations = load_global_relations(paths, bundle, substances)
    roles = _component_roles(products, substances)
    active_role_ids = _active_role_ids(paths, products, bundle)
    active_roles = [roles[role_id] for role_id in active_role_ids if role_id in roles]
    closure = load_coverage_closure(paths.data / "coverage-closure.yaml")
    closure_errors = validate_coverage_closure(
        closure,
        catalog,
        active_roles,
        substances=substances,
        relations=relations,
    )
    if closure_errors:
        raise ValueError("groom: coverage closure stale/unclosed source class: " + "; ".join(closure_errors))
    # A closed empty candidate set is deliberate evidence, not a fake role
    # candidate and not an optimizer input.
    return (), 0


def _component_roles(products: Mapping[str, Product], substances: Mapping[str, Substance]) -> dict[str, GroomWorkItem]:
    roles: dict[str, GroomWorkItem] = {}
    for product in products.values():
        for component in product.components:
            substance = substances.get(component.substance)
            if substance is None:
                continue
            role_id = component.id or composition_role_id(product.id, substance.id)
            if role_id in roles:
                raise CardLoadError(Path("data/products"), f"duplicate composition role {role_id!r}")
            roles[role_id] = GroomWorkItem(role_id, product.id, product.name, substance.id, substance.name)
    return roles


def _active_role_ids(paths: Paths, products: Mapping[str, Product], bundle: OntologyBundle) -> set[str]:
    raw = load_yaml(paths.stacks_file)
    if not isinstance(raw, Mapping):
        raise CardLoadError(paths.stacks_file, "stacks must be a mapping")
    try:
        entries = normalize_stack_entries(raw, bundle.runtime_program)
    except ValueError as error:
        raise CardLoadError(paths.stacks_file, str(error)) from error
    routable = set(bundle.runtime_program.glue_contract.stack_partition.routable_stack_names)
    active_products = {entry["product"] for entry in entries.values() if entry["stack"] in routable}
    return {
        component.id or composition_role_id(product.id, component.substance)
        for product_id, product in products.items()
        if product_id in active_products
        for component in product.components
    }


def _render(items: tuple[GroomWorkItem, ...], eligible_count: int) -> None:
    print(f"Grooming queue: {eligible_count} eligible, showing {len(items)}")
    for item in items:
        print(f"  role {item.composition_role_id}")
        print(f"    product: {item.product_id} — {item.product_name}")
        print(f"    substance: {item.substance_id} — {item.substance_name}")
        if item.candidate_id is not None:
            print(f"    candidate: {item.candidate_id} ({item.candidate_disposition})")
        print(
            "    collection boundary: identify evidence or applicability gaps only; do not author or adjudicate facts."
        )


__all__ = ["cmd_groom"]
