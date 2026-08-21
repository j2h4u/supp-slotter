"""Policy-driven, read-only substance-card grooming selection."""

from __future__ import annotations

import contextlib
import io
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from planner.cards.product import load_product_registry
from planner.cards.relations import check_global_relations, load_global_relations
from planner.cards.substance import load_substance_registry
from planner.contracts import CardLoadError, Product, Relation, Substance
from planner.engine.results import (
    GroomAssessment,
    GroomKnowledge,
    GroomProduct,
    GroomRelation,
    GroomResult,
    GroomSchedule,
    GroomWorkItem,
)
from planner.ontology.artifacts import OntologyBundle, load_ontology
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import RuntimeGroomingRankFieldPolicy
from planner.ontology.selector import resolve_selector
from planner.paths import ROOT, Paths
from planner.schema_validation import validate_schemas
from planner.yaml_io import load_yaml, load_yaml_mapping


def cmd_groom(data_root: Path | None = None) -> GroomResult:
    """Select exactly one policy-ranked substance-card dossier, or none."""
    bundle = load_ontology(ROOT / "ontology")
    stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        try:
            paths = Paths.from_root(data_root) if data_root is not None else Paths.default()
            schema_result = validate_schemas(paths, bundle)
            if schema_result != 0:
                return GroomResult(schema_result, None, 0, stderr=stderr_buf.getvalue())
            work_item, eligible_count = _select_work_item(paths, bundle)
            _render(work_item, eligible_count, bundle.runtime_program.grooming_policy.selection_count)
            return GroomResult(0, work_item, eligible_count, stdout_buf.getvalue(), stderr_buf.getvalue())
        except (CardLoadError, OntologyInfrastructureError) as error:
            message = error.message if isinstance(error, CardLoadError) else str(error)
            return GroomResult(1, None, 0, stderr=message + "\n")


def _select_work_item(paths: Paths, bundle: OntologyBundle) -> tuple[GroomWorkItem | None, int]:
    loaded = _load_inputs(paths, bundle)
    if loaded is None:
        raise CardLoadError(paths.relations_file, "relation validation failed")
    substances, products, relations, stacks = loaded
    active_products = _active_products(products, stacks, bundle)
    active_ids = {
        component.substance
        for product in active_products
        for component in product.components
        if component.substance in substances
    }
    owned_relations = _owned_open_relations(relations, substances, active_ids, bundle)
    candidates = [
        (substance, active_products, owned_relations.get(substance.id, ()))
        for substance in substances.values()
        if substance.id in active_ids
        and _open_knowledge_count(substance) + len(owned_relations.get(substance.id, ())) > 0
    ]
    policy = bundle.runtime_program.grooming_policy
    metrics: dict[str, dict[str, object]] = {
        substance.id: {
            "active_unique_product_count": len(
                {product.id for product in active_products if _has_substance(product, substance.id)}
            ),
            "open_owned_item_count": _open_knowledge_count(substance) + len(owned_relations.get(substance.id, ())),
            "substance_id": substance.id,
        }
        for substance, active_products, _ in candidates
    }
    ordered = sorted(candidates, key=lambda row: _rank_key(metrics[row[0].id], policy.rank_fields))
    selected = ordered[: policy.selection_count]
    work_item = (
        _build_work_item(selected[0][0], selected[0][1], selected[0][2], paths, bundle)
        if selected
        else None
    )
    return work_item, len(ordered)


def _load_inputs(
    paths: Paths, bundle: OntologyBundle
) -> tuple[dict[str, Substance], dict[str, Product], list[Relation], dict[str, list[str]]] | None:
    substances = load_substance_registry(paths, bundle)
    products = load_product_registry(paths, bundle)
    relations_data = load_yaml(paths.relations_file)
    relation_errors = check_global_relations(relations_data, substances, paths, bundle)
    if relation_errors:
        _print_errors(relation_errors)
        return None
    relations = load_global_relations(paths, bundle, substances)
    return substances, products, relations, _stacks(paths)


def _stacks(paths: Paths) -> dict[str, list[str]]:
    raw = load_yaml_mapping(paths.stacks_file)
    return {
        name: [item for item in cast(list[object], values) if isinstance(item, str)]
        for name, values in raw.items()
        if isinstance(values, list)
    }


def _active_products(
    products: Mapping[str, Product], stacks: Mapping[str, list[str]], bundle: OntologyBundle
) -> tuple[Product, ...]:
    inactive = bundle.runtime_program.glue_contract.inactive_stack_name
    active_ids = {
        product_id
        for stack_name, product_ids in stacks.items()
        if stack_name != inactive
        for product_id in product_ids
    }
    return tuple(product for product in products.values() if product.id in active_ids)


def _has_substance(product: Product, substance_id: str) -> bool:
    return any(component.substance == substance_id for component in product.components)


def _open_knowledge_count(substance: Substance) -> int:
    return sum(assertion.research_state == "unassessed" for assertion in substance.knowledge_assertions)


def _owned_open_relations(
    relations: tuple[Relation, ...] | list[Relation],
    substances: Mapping[str, Substance],
    active_ids: set[str],
    bundle: OntologyBundle,
) -> dict[str, tuple[GroomRelation, ...]]:
    owned: dict[str, list[GroomRelation]] = {}
    for relation in relations:
        if relation.research_state != "unassessed":
            continue
        source_ids = set(resolve_selector(relation.source_selector, substances, bundle).substance_ids)
        target_ids = set(resolve_selector(relation.target_selector, substances, bundle).substance_ids)
        endpoint_ids = tuple(sorted((source_ids | target_ids) & active_ids))
        if not endpoint_ids:
            continue
        owner = endpoint_ids[0]
        owned.setdefault(owner, []).append(
            GroomRelation(
                id=relation.id,
                relation_type=relation.type,
                source=_selector_label(relation.source_selector),
                target=_selector_label(relation.target_selector),
                reason=relation.reason,
                research_state=relation.research_state,
                sources=relation.sources,
                active_endpoint_ids=endpoint_ids,
            )
        )
    return {key: tuple(sorted(rows, key=lambda row: row.id)) for key, rows in owned.items()}


def _selector_label(selector: object) -> str:
    if isinstance(selector, Mapping):
        mapping = cast(Mapping[str, object], selector)
        return str(mapping.get("entity_id") or mapping.get("entity_name") or mapping.get("term") or "")
    return str(
        getattr(selector, "entity_id", None)
        or getattr(selector, "entity_name", None)
        or getattr(selector, "term", None)
        or ""
    )


def _rank_key(
    metrics: Mapping[str, object], fields: tuple[RuntimeGroomingRankFieldPolicy, ...]
) -> tuple[object, ...]:
    key: list[object] = []
    for field in fields:
        name = field.field
        value = metrics[name]
        key.append(-value if field.direction == "descending" and isinstance(value, int) else value)
    return tuple(key)


def _build_work_item(
    substance: Substance,
    active_products: tuple[Product, ...],
    open_relations: tuple[GroomRelation, ...],
    paths: Paths,
    bundle: OntologyBundle,
) -> GroomWorkItem:
    products = tuple(
        GroomProduct(
            id=product.id,
            name=product.name,
            brand=product.brand,
            notes=product.notes,
            use_pattern=product.use_pattern,
            components=tuple(
                (component.substance, component.label, component.amount, component.notes)
                for component in product.components
            ),
        )
        for product in sorted(active_products, key=lambda item: item.id)
        if _has_substance(product, substance.id)
    )
    knowledge = tuple(
        GroomKnowledge(row.category, row.value, row.research_state, row.sources)
        for row in substance.knowledge_assertions
    )
    schedule = tuple(GroomSchedule(row.axis, row.value) for row in substance.schedule_assertions)
    authored_assessments = {row.axis: row for row in substance.scheduling_assessments}
    assessments = tuple(
        GroomAssessment(
            axis=axis.axis,
            conclusion=(authored_assessments[axis.axis].conclusion if axis.axis in authored_assessments else "unassessed"),
            policy=(authored_assessments[axis.axis].policy if axis.axis in authored_assessments else None),
            sources=(authored_assessments[axis.axis].sources if axis.axis in authored_assessments else ()),
            summary=(authored_assessments[axis.axis].summary if axis.axis in authored_assessments else "Open: no authored scheduling assessment."),
        )
        for axis in sorted(bundle.runtime_program.assignment_axes, key=lambda row: (row.order, row.id))
    )
    return GroomWorkItem(
        substance_id=substance.id,
        name=substance.name,
        path=_substance_path(paths, substance),
        aliases=substance.aliases,
        form=substance.form,
        notes=substance.notes,
        active_unique_product_count=len(products),
        open_owned_item_count=_open_knowledge_count(substance) + len(open_relations),
        active_products=products,
        knowledge=knowledge,
        open_relations=open_relations,
        schedule_assertions=schedule,
        scheduling_assessments=assessments,
    )


def _substance_path(paths: Paths, substance: Substance) -> Path:
    matches = sorted(paths.substances.glob(f"*__{substance.id}.yaml"))
    return matches[0] if matches else paths.substances


def _render(item: GroomWorkItem | None, eligible_count: int, selection_count: int) -> None:
    print(f"Grooming queue: {eligible_count} eligible, showing {1 if item else 0} (selection_count={selection_count})")
    if item is None:
        print("  none")
        return
    print(f"  card {item.substance_id} — {item.name}")
    print(f"    path: {item.path}")
    print(f"    form: {item.form or '—'}")
    print(f"    aliases: {', '.join(item.aliases) or '—'}")
    print(f"    notes: {item.notes or '—'}")
    print(f"    active_unique_product_count: {item.active_unique_product_count}")
    print(f"    open_owned_item_count: {item.open_owned_item_count}")
    print("    active products:")
    for product in item.active_products:
        print(f"      - {product.id}: {product.brand + ' - ' if product.brand else ''}{product.name}")
        for substance, label, amount, notes in product.components:
            context = ", ".join(value for value in (label, amount, notes) if value) or "—"
            print(f"        component {substance}: {context}")
    print("    knowledge assertions:")
    for row in item.knowledge:
        marker = "OPEN" if row.open else row.research_state
        print(f"      - {marker} {row.category}={row.value} sources={', '.join(row.sources) or '—'}")
    print("    owned open relation leads:")
    for row in item.open_relations:
        print(f"      - OPEN {row.id} {row.relation_type}: {row.source} -> {row.target} ({row.reason})")
    if not item.open_relations:
        print("      - none")
    print("    schedule assertions:")
    for row in item.schedule_assertions:
        print(f"      - {row.axis}={row.value}")
    print("    scheduling assessments:")
    for row in item.scheduling_assessments:
        marker = "OPEN" if row.open else row.conclusion
        print(f"      - {marker} {row.axis}: {row.summary} sources={', '.join(row.sources) or '—'}")


def _print_errors(errors: list[str]) -> None:
    for error in errors:
        print(error, file=sys.stderr)
