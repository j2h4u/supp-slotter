"""Audit queries for the SurrealDB-backed planner read model.

Set-difference arithmetic stays in Python where it is clearer. SurrealQL owns
the cross-reference collection across heterogeneous sources: product
components, resolved relation endpoints, substance prefer_with arrays, and
dashboard selectors resolution.

`similar_names` stays in Python because it depends on SequenceMatcher fuzzy
matching, which has no native SurrealQL equivalent.
"""

from __future__ import annotations

from typing import cast

from planner.cards.substance import format_substance_name
from planner.cards.substance_similarity import collect_similar_substances
from planner.contracts import Substance
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.glue_capabilities import ONTOLOGY_COMPOSITE_KEY_SEPARATOR
from planner.query_model.session import SurrealSession, id_str, string_list


def collect_cleanup_sections(
    db: SurrealSession,
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> dict[str, list[str]]:
    """Return cleanup-candidate sections for `planner audit`."""
    all_substance_ids = {id_str(row["id"]) for row in db.query("SELECT id FROM substance")}
    product_substance_refs, prefer_with_refs, relation_refs = _referenced_substance_ids(db)

    knowledge_only_substances = [
        _format_substance_audit_entry(substances[substance_id])
        for substance_id in sorted(all_substance_ids - product_substance_refs - prefer_with_refs - relation_refs)
        if substance_id in substances
    ]

    all_product_ids = {id_str(row["id"]) for row in db.query("SELECT id FROM product")}
    stack_products: set[str] = set()
    for row in db.query("SELECT products FROM stack"):
        stack_products.update(string_list(row.get("products")))
    products_without_stack = _products_without_stack_messages(db, all_product_ids - stack_products)

    empty_stacks, stacks_without_pillboxes, pillboxes_without_stack = _stack_cleanup_sections(
        db,
        ontology_bundle.runtime_program.glue_contract.inactive_stack_name,
    )
    similar_names = collect_similar_substances(substances)

    return {
        "diagnostics": [
            *knowledge_only_substances,
            *products_without_stack,
            *_unused_scheduling_policies(db, ontology_bundle),
            *empty_stacks,
            *stacks_without_pillboxes,
            *pillboxes_without_stack,
            *similar_names,
            *_empty_dashboard_cluster_messages(db),
        ]
    }


def _referenced_substance_ids(db: SurrealSession) -> tuple[set[str], set[str], set[str]]:
    product_substance_refs: set[str] = set()
    for row in db.query("SELECT components FROM product"):
        product_substance_refs.update(string_list(row.get("components")))

    prefer_with_refs: set[str] = set()
    for row in db.query("SELECT id, prefer_with FROM substance WHERE array::len(prefer_with) > 0"):
        prefer_with_refs.add(id_str(row["id"]))
        prefer_with_refs.update(string_list(row.get("prefer_with")))

    relation_refs: set[str] = set()
    for row in db.query("SELECT src_substances, tgt_substances FROM ontology_assertion"):
        relation_refs.update(string_list(row.get("src_substances")))
        relation_refs.update(string_list(row.get("tgt_substances")))

    return product_substance_refs, prefer_with_refs, relation_refs


def _unused_scheduling_policies(db: SurrealSession, ontology_bundle: OntologyBundle) -> list[str]:
    """Report canonical scheduling policies with no card assignment."""
    policy_ids = _canonical_policy_ids(ontology_bundle)
    assigned = _assigned_policy_ids(db, ontology_bundle)
    schedule_assignment_ids = _schedule_assignment_ids(db, ontology_bundle)
    unknown_assignments = sorted(schedule_assignment_ids - set(policy_ids))
    if unknown_assignments:
        raise _audit_policy_error(
            ontology_bundle,
            "substance schedule_assertions reference unknown policies: " + ", ".join(unknown_assignments),
        )
    return sorted(policy_id for policy_id in policy_ids if policy_id not in assigned)


def _canonical_policy_ids(bundle: OntologyBundle) -> tuple[str, ...]:
    policies = bundle.runtime_vocabulary.get("scheduling_policies")
    if not isinstance(policies, dict):
        raise _audit_policy_error(bundle, "canonical runtime vocabulary has no scheduling_policies")
    policy_mapping = cast(dict[object, object], policies)
    if any(
        not isinstance(policy_id, str) or not isinstance(policy, dict) for policy_id, policy in policy_mapping.items()
    ):
        raise _audit_policy_error(bundle, "canonical scheduling_policies contains malformed entries")
    return tuple(cast(str, policy_id) for policy_id in policy_mapping)


def _assigned_policy_ids(db: SurrealSession, bundle: OntologyBundle) -> set[str]:
    assigned: set[str] = set()
    for row in db.query("SELECT term_refs FROM substance"):
        raw_terms = row.get("term_refs")
        raw_terms_list = cast(list[object], raw_terms) if isinstance(raw_terms, list) else None
        if raw_terms_list is None or not all(isinstance(item, str) for item in raw_terms_list):
            raise _audit_policy_error(bundle, "substance term_refs contain malformed policy references")
        assigned.update(cast(list[str], raw_terms_list))
    return assigned


def _schedule_assignment_ids(db: SurrealSession, bundle: OntologyBundle) -> set[str]:
    assignment_ids: set[str] = set()
    for row in db.query("SELECT schedule_assertions FROM substance"):
        assignments = row.get("schedule_assertions")
        assignments_list = cast(list[object], assignments) if isinstance(assignments, list) else None
        if assignments_list is None:
            raise _audit_policy_error(bundle, "substance schedule_assertions are malformed")
        for assignment in assignments_list:
            if not isinstance(assignment, dict):
                raise _audit_policy_error(bundle, "substance schedule_assertions contain malformed entries")
            assignment_map = cast(dict[str, object], assignment)
            axis = assignment_map.get("schedule_axis")
            value = assignment_map.get("schedule_value")
            if not isinstance(axis, str) or not axis.strip() or not isinstance(value, str) or not value.strip():
                raise _audit_policy_error(bundle, "substance schedule_assertions contain malformed values")
            assignment_ids.add(f"{axis}{ONTOLOGY_COMPOSITE_KEY_SEPARATOR}{value}")
    return assignment_ids


def _audit_policy_error(bundle: OntologyBundle, message: str) -> OntologyInfrastructureError:
    source = bundle.root / "generated" / "runtime-vocabulary.yaml"
    return OntologyInfrastructureError(f"{message} [source: {source}]", code=MALFORMED, path=source)


def _products_without_stack_messages(db: SurrealSession, product_ids: set[str]) -> list[str]:
    rows_by_id = {
        id_str(row["id"]): cast(str, row.get("display_name") or row["id"])
        for row in db.query("SELECT id, display_name FROM product")
    }
    return [f"{rows_by_id.get(product_id, product_id)} ({product_id})" for product_id in sorted(product_ids)]


def _stack_cleanup_sections(db: SurrealSession, inactive_stack_name: str) -> tuple[list[str], list[str], list[str]]:
    empty_stacks = sorted(
        cast(str, row["name"]) for row in db.query("SELECT name FROM stack WHERE array::len(products) == 0")
    )
    all_stack_names: set[str] = {cast(str, row["name"]) for row in db.query("SELECT name FROM stack")}
    pillbox_stack_names: set[str] = {cast(str, row["stack_name"]) for row in db.query("SELECT stack_name FROM pillbox")}
    stacks_without_pillboxes = sorted(all_stack_names - pillbox_stack_names - {inactive_stack_name})
    pillboxes_without_stack = sorted(pillbox_stack_names - all_stack_names)
    return empty_stacks, stacks_without_pillboxes, pillboxes_without_stack


def _empty_dashboard_cluster_messages(db: SurrealSession) -> list[str]:
    messages: list[str] = []
    for dash in db.query("SELECT id, source_path, from_terms FROM dashboard"):
        dashboard_id = id_str(dash["id"])
        source_path = dash.get("source_path")
        diagnostic_path = (
            cast(str, source_path)
            if isinstance(source_path, str) and source_path
            else f"data/dashboards/{dashboard_id}.yaml"
        )
        pairs = cast("list[str]", dash.get("from_terms") or [])
        if pairs:
            members = db.query(
                "SELECT id FROM substance WHERE term_refs ANYINSIDE $pairs",
                {"pairs": pairs},
            )
            if members:
                continue
        messages.append(
            f"Empty cluster: {diagnostic_path} selectors resolves to "
            f"zero member substances (using union resolution: OR across all listed "
            f"(namespace, slug) pairs). Resolution: update selectors to match "
            f"substance ontology terms, OR remove the dashboard yaml if abandoned."
        )
    return messages


def _format_substance_audit_entry(substance: Substance) -> str:
    return f"{format_substance_name(substance)} ({substance.id})"
