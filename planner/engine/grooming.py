"""Read-only canonical-coverage grooming for active component roles."""

from __future__ import annotations

import contextlib
import io
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

from planner.cards.product import composition_role_id, load_product_registry
from planner.cards.substance import load_substance_registry
from planner.contracts import CardLoadError, Product, Substance
from planner.engine.results import GroomResult, GroomWorkItem
from planner.ontology.artifacts import OntologyBundle, load_ontology
from planner.ontology.errors import OntologyInfrastructureError
from planner.paths import ROOT, Paths
from planner.schema_validation import validate_schemas
from planner.yaml_io import load_yaml

_RECEIPTS_FORMAT = "supp-slotter.grooming-receipts/v1"
_OUTCOMES = frozenset({"no_supported_fact"})
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True, slots=True)
class _Receipt:
    composition_role: str
    assessed_on: str
    outcome: str


def cmd_groom(data_root: Path | None = None) -> GroomResult:
    """Select one active component role without a completed grooming receipt."""
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
        except (CardLoadError, OntologyInfrastructureError) as error:
            message = error.message if isinstance(error, CardLoadError) else str(error)
            return GroomResult(1, None, 0, stderr=message + "\n")


def _select_work_items(paths: Paths, bundle: OntologyBundle) -> tuple[tuple[GroomWorkItem, ...], int]:
    substances = load_substance_registry(paths, bundle)
    products = load_product_registry(paths, bundle)
    all_roles = _component_roles(products, substances)
    fact_role_ids = _canonical_fact_role_ids(bundle, all_roles)
    receipts = _load_receipts(
        paths.data / "grooming-receipts.yaml",
        known_role_ids=set(all_roles),
        fact_role_ids=fact_role_ids,
    )
    completed_role_ids = {receipt.composition_role for receipt in receipts}
    active_role_ids = _active_role_ids(paths, products, bundle)
    candidates = tuple(all_roles[role_id] for role_id in sorted(active_role_ids - fact_role_ids - completed_role_ids))
    return candidates[:1], len(candidates)


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
    active_product_ids = {
        product_id
        for stack_name, product_ids in raw.items()
        if stack_name != bundle.runtime_program.glue_contract.inactive_stack_name and isinstance(product_ids, list)
        for product_id in product_ids
        if isinstance(product_id, str)
    }
    return {
        component.id or composition_role_id(product.id, component.substance)
        for product_id, product in products.items()
        if product_id in active_product_ids
        for component in product.components
    }


def _canonical_fact_role_ids(bundle: OntologyBundle, roles: Mapping[str, GroomWorkItem]) -> set[str]:
    catalog = bundle.runtime_program.canonical_fact_catalog
    return {
        role_id
        for family in (
            catalog.food_effects,
            catalog.acute_alertness_effects,
            catalog.acute_sleep_effects,
            catalog.pre_exercise_performance_effects,
            catalog.post_exercise_recovery_effects,
        )
        for fact in family
        for role_id, role in roles.items()
        if (
            fact.applicability.substance == role.substance_id
            if fact.applicability.substance is not None
            else fact.applicability.composition_role == role_id
        )
    }


def _load_receipts(path: Path, *, known_role_ids: set[str], fact_role_ids: set[str]) -> tuple[_Receipt, ...]:
    try:
        raw = load_yaml(path)
    except (CardLoadError, ValueError) as error:
        raise CardLoadError(path, f"invalid grooming receipts: {error}") from error
    if not isinstance(raw, Mapping) or set(raw) != {"format", "assessments"}:
        raise CardLoadError(path, "grooming receipts must contain exactly format and assessments")
    if raw["format"] != _RECEIPTS_FORMAT:
        raise CardLoadError(path, f"grooming receipts format must be {_RECEIPTS_FORMAT!r}")
    rows = raw["assessments"]
    if not isinstance(rows, list):
        raise CardLoadError(path, "grooming receipts assessments must be a list")
    receipts = tuple(_receipt(row, path, index) for index, row in enumerate(rows))
    receipt_roles = [receipt.composition_role for receipt in receipts]
    if len(receipt_roles) != len(set(receipt_roles)):
        raise CardLoadError(path, "grooming receipts must not contain duplicate composition_role values")
    unknown = sorted(set(receipt_roles) - known_role_ids)
    if unknown:
        raise CardLoadError(path, f"grooming receipts reference unknown composition role(s): {', '.join(unknown)}")
    covered = sorted(receipt.composition_role for receipt in receipts if receipt.composition_role in fact_role_ids)
    if covered:
        raise CardLoadError(
            path,
            "grooming receipt no_supported_fact is newly covered by canonical applicability for role(s): "
            + ", ".join(covered),
        )
    return receipts


def _receipt(row: object, path: Path, index: int) -> _Receipt:
    label = f"assessments[{index}]"
    if not isinstance(row, Mapping):
        raise CardLoadError(
            path, f"grooming receipt {label} must contain exactly composition_role, assessed_on, and outcome"
        )
    receipt = cast(Mapping[object, object], row)
    if set(receipt) != {"composition_role", "assessed_on", "outcome"}:
        raise CardLoadError(
            path, f"grooming receipt {label} must contain exactly composition_role, assessed_on, and outcome"
        )
    role = receipt["composition_role"]
    assessed_on = receipt["assessed_on"]
    outcome = receipt["outcome"]
    if not isinstance(role, str) or not role:
        raise CardLoadError(path, f"grooming receipt {label}.composition_role must be a non-empty string")
    if not isinstance(assessed_on, str) or _DATE.fullmatch(assessed_on) is None:
        raise CardLoadError(path, f"grooming receipt {label}.assessed_on must be a quoted YYYY-MM-DD string")
    try:
        date.fromisoformat(assessed_on)
    except ValueError as error:
        raise CardLoadError(path, f"grooming receipt {label}.assessed_on must be a valid calendar date") from error
    if outcome not in _OUTCOMES:
        raise CardLoadError(path, f"grooming receipt {label}.outcome must be one of {sorted(_OUTCOMES)!r}")
    return _Receipt(role, assessed_on, cast(str, outcome))


def _render(items: tuple[GroomWorkItem, ...], eligible_count: int) -> None:
    print(f"Grooming queue: {eligible_count} eligible, showing {len(items)}")
    for item in items:
        print(f"  role {item.composition_role_id}")
        print(f"    product: {item.product_id} — {item.product_name}")
        print(f"    substance: {item.substance_id} — {item.substance_name}")
        print(
            "    collection boundary: identify evidence or applicability gaps only; do not author or adjudicate facts."
        )
