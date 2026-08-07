"""Trait definitions: flattening, validation, and rendering helpers."""

# pyright: reportUnknownArgumentType=false

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, cast

from planner.contracts import (
    CardLoadError,
    EnforcementCap,
    GovernanceStatus,
    OntologyAssertion,
    Relation,
    RelationSelector,
    RelationType,
    SchedulingConstraint,
    SchedulingPolicy,
    Severity,
    TraitEffect,
    TraitEffectMatch,
)
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.runtime_program import RuntimeProgram
from planner.ontology.schema_enums import schema_enum_values
from planner.paths import ROOT


class _ConstraintMetadata(NamedTuple):
    rationale: str
    semantic_note: str | None
    status: str
    evidence: tuple[str, ...]
    owner: str
    review_by: str
    assertion_type: str


def _build_trait_effect(effect: dict[str, object], runtime: RuntimeProgram) -> TraitEffect:
    match_raw_obj = effect.get("match")
    if not isinstance(match_raw_obj, dict):
        raise CardLoadError(ROOT / "ontology", "policy effect has invalid match")
    match_raw = cast(dict[str, object], match_raw_obj)
    if set(match_raw) - set(runtime.effect_match_dimensions_by_key):
        raise CardLoadError(ROOT / "ontology", "policy effect has unknown match keys")
    if not match_raw:
        raise CardLoadError(ROOT / "ontology", "policy effect match must not be empty")
    match_values: list[tuple[str, str | bool]] = []
    for dimension in runtime.effect_match_dimensions:
        if dimension.key not in match_raw:
            continue
        match_values.append((
            dimension.key,
            _validated_effect_match_value(match_raw[dimension.key], dimension.key, dimension.value_type, runtime),
        ))
    level_raw = effect.get("level")
    block_raw = effect.get("block")
    if set(effect) - {"match", "level", "block"}:
        raise CardLoadError(ROOT / "ontology", "policy effect has unknown fields")
    if level_raw is not None and (not isinstance(level_raw, str) or level_raw not in runtime.effect_score_levels):
        raise CardLoadError(ROOT / "ontology", "policy effect has invalid level")
    if block_raw is not None and not isinstance(block_raw, bool):
        raise CardLoadError(ROOT / "ontology", "policy effect has invalid block")
    if level_raw is not None and block_raw is not None:
        raise CardLoadError(ROOT / "ontology", "policy effect cannot set both level and block")
    level = level_raw if isinstance(level_raw, str) else None
    return TraitEffect(
        match=TraitEffectMatch(tuple(match_values)),
        level=level,
        block=block_raw if isinstance(block_raw, bool) else None,
    )


def _validated_effect_match_value(value: object, key: str, value_type: str, runtime: RuntimeProgram) -> str | bool:
    if value_type == "slot_near":
        if not isinstance(value, str) or value not in runtime.slot_near_values:
            raise CardLoadError(ROOT / "ontology", f"policy effect has invalid {key}")
        return value
    if value_type == "boolean":
        if not isinstance(value, bool):
            raise CardLoadError(ROOT / "ontology", f"policy effect has invalid {key}")
        return value
    raise CardLoadError(ROOT / "ontology", f"policy effect has unsupported match value type {value_type}")


def _required_policy_string(policy: dict[str, object], policy_id: str, key: str) -> str:
    value = policy.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CardLoadError(ROOT / "ontology", f"policy {policy_id!r} has invalid {key}")
    return value


def _validated_scope_value(runtime: RuntimeProgram, key: str, value: str, owner: str) -> None:
    dimension = runtime.scope_by_key.get(key)
    if dimension is None:
        raise CardLoadError(ROOT / "ontology", f"{owner} has unknown scope dimension {key!r}")
    if key != "product" and value not in dimension.values:
        raise CardLoadError(ROOT / "ontology", f"{owner} has unsupported scope value {key}={value!r}")


def _policy_scope(scope: dict[object, object], policy_id: str, runtime: RuntimeProgram) -> tuple[tuple[str, str], ...]:
    values: list[tuple[str, str]] = []
    for key, value in scope.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(value, str) or not value.strip():
            raise CardLoadError(ROOT / "ontology", f"policy {policy_id!r} has invalid scope")
        _validated_scope_value(runtime, key, value, f"policy {policy_id!r}")
        values.append((key, value))
    return tuple(sorted(values))


def _validate_warning_trait_actions(runtime: RuntimeProgram, policies: dict[str, SchedulingPolicy]) -> None:
    unknown_warning_traits = sorted(set(runtime.warning_trait_actions_by_trait) - set(policies))
    if unknown_warning_traits:
        raise CardLoadError(
            ROOT / "ontology",
            "runtime warning_trait_actions reference unknown scheduling policies: " + ", ".join(unknown_warning_traits),
        )


def load_scheduling_policies(bundle: OntologyBundle) -> dict[str, SchedulingPolicy]:
    """Materialize scheduler policies from generated canonical ontology artifacts."""
    vocabulary = bundle.runtime_vocabulary
    runtime = bundle.runtime_program
    raw_policies = vocabulary.get("scheduling_policies")
    if not isinstance(raw_policies, dict):
        raise CardLoadError(ROOT / "ontology", "canonical runtime vocabulary has no scheduling_policies")
    out: dict[str, SchedulingPolicy] = {}
    for tid, policy_obj in raw_policies.items():
        if not isinstance(tid, str) or not isinstance(policy_obj, dict) or ":" not in tid:
            raise CardLoadError(ROOT / "ontology", f"malformed scheduling policy {tid!r}")
        namespace, short_name = tid.split(":", maxsplit=1)
        policy = cast(dict[str, object], policy_obj)
        status_raw = _required_policy_string(policy, tid, "status")
        enforcement_raw = _required_policy_string(policy, tid, "enforcement")
        lifecycle = runtime.lifecycle_decision(status_raw)
        enforcement = runtime.enforcement_decision(enforcement_raw)
        gate = runtime.execution_gate_for(status_raw)
        if (
            lifecycle is None
            or enforcement is None
            or gate is None
            or lifecycle.state != status_raw
            or gate.lifecycle_state != lifecycle.state
            or gate.executable != lifecycle.executable
        ):
            raise CardLoadError(ROOT / "ontology", f"policy {tid!r} has unknown lifecycle/enforcement")
        if not lifecycle.executable or not gate.executable:
            continue
        scope_raw = policy.get("scope")
        if not isinstance(scope_raw, dict):
            raise CardLoadError(ROOT / "ontology", f"policy {tid!r} has invalid scope")
        scope = _policy_scope(scope_raw, tid, runtime)
        effects_raw = policy.get("effects")
        if not isinstance(effects_raw, list):
            raise CardLoadError(ROOT / "ontology", f"policy {tid!r} has invalid effects")
        effects: list[TraitEffect] = []
        for index, effect in enumerate(effects_raw):
            if not isinstance(effect, dict):
                raise CardLoadError(ROOT / "ontology", f"policy {tid!r} effects[{index}] is malformed")
            effects.append(_build_trait_effect(cast(dict[str, object], effect), runtime))
        label = _required_policy_string(policy, tid, "label")
        description = _required_policy_string(policy, tid, "description")
        applies_when = _required_policy_string(policy, tid, "applies_when")
        warning = policy.get("warning")
        if not isinstance(warning, bool):
            raise CardLoadError(ROOT / "ontology", f"policy {tid!r} has invalid warning")
        action = policy.get("action")
        if action is not None and (not isinstance(action, str) or not action.strip()):
            raise CardLoadError(ROOT / "ontology", f"policy {tid!r} has invalid action")
        out[tid] = SchedulingPolicy(
            id=tid,
            namespace=namespace,
            short_name=short_name,
            label=label,
            description=description,
            applies_when=applies_when,
            effects=tuple(effects),
            warning=warning,
            action=action if isinstance(action, str) else None,
            status=cast(GovernanceStatus, status_raw),
            enforcement=cast(EnforcementCap, enforcement_raw),
            scope=scope,
        )
    _validate_warning_trait_actions(runtime, out)
    return out


def load_scheduling_constraints(
    bundle: OntologyBundle,
    *,
    include_retired: bool = False,
) -> tuple[SchedulingConstraint, ...]:
    """Load first-class hard scheduling constraints from generated vocabulary."""
    vocabulary = bundle.runtime_vocabulary
    runtime = bundle.runtime_program
    raw_constraints = vocabulary.get("scheduling_constraints")
    if not isinstance(raw_constraints, dict):
        raise CardLoadError(ROOT / "ontology", "canonical runtime vocabulary has no scheduling_constraints")
    constraints: list[SchedulingConstraint] = []
    constraints_mapping = cast(dict[str, object], raw_constraints)
    for constraint_id, raw_value in constraints_mapping.items():
        raw = _object_mapping(raw_value)
        if not isinstance(constraint_id, str) or not constraint_id.strip() or raw is None:
            raise CardLoadError(ROOT / "ontology", f"malformed scheduling constraint {constraint_id!r}")
        source = _constraint_selector(raw.get("source_selector"))
        target = _constraint_selector(raw.get("target_selector"))
        operation, enforcement = raw.get("operation"), raw.get("enforcement")
        if (
            not isinstance(operation, str)
            or not operation.strip()
            or not isinstance(enforcement, str)
            or not enforcement.strip()
        ):
            raise CardLoadError(ROOT / "ontology", f"constraint {constraint_id!r} has invalid operation/enforcement")
        if runtime.constraint_execution_policy_for(operation) is None:
            raise CardLoadError(ROOT / "ontology", f"constraint {constraint_id!r} has unknown operation {operation!r}")
        metadata = _constraint_metadata(raw, constraint_id, runtime)
        lifecycle = runtime.lifecycle_decision(metadata.status)
        if lifecycle is None:
            raise CardLoadError(ROOT / "ontology", f"constraint {constraint_id!r} has unknown lifecycle")
        if not lifecycle.executable and not include_retired:
            continue
        action = raw.get("action")
        if action is not None and (not isinstance(action, str) or not action.strip()):
            raise CardLoadError(ROOT / "ontology", f"constraint {constraint_id!r} has invalid action")
        constraints.append(
            SchedulingConstraint(
                id=constraint_id,
                source_selector=source,
                target_selector=target,
                operation=operation,
                enforcement=enforcement,
                action=action if isinstance(action, str) else None,
                rationale=metadata.rationale,
                semantic_note=metadata.semantic_note,
                status=metadata.status,
                evidence=metadata.evidence,
                owner=metadata.owner,
                review_by=metadata.review_by,
                assertion_type=metadata.assertion_type,
            )
        )
    return tuple(constraints)


def load_ontology_assertions(bundle: OntologyBundle) -> tuple[OntologyAssertion, ...]:
    """Load non-blocking semantic assertions from generated canonical vocabulary."""
    vocabulary = bundle.runtime_vocabulary
    raw_assertions = vocabulary.get("ontology_assertions")
    if not isinstance(raw_assertions, dict):
        raise CardLoadError(ROOT / "ontology", "canonical runtime vocabulary has no ontology_assertions")
    raw_relation_types = vocabulary.get("relation_types")
    if not isinstance(raw_relation_types, dict) or not raw_relation_types:
        raise CardLoadError(ROOT / "ontology", "canonical runtime vocabulary has no relation_types")
    relation_types = set(raw_relation_types)
    severity_values = frozenset(schema_enum_values(bundle, "Severity"))
    assertions: list[OntologyAssertion] = []
    assertions_mapping = cast(dict[str, object], raw_assertions)
    for assertion_id, raw_value in assertions_mapping.items():
        raw = _object_mapping(raw_value)
        if not isinstance(assertion_id, str) or not assertion_id.strip() or raw is None:
            raise CardLoadError(ROOT / "ontology", f"malformed ontology assertion {assertion_id!r}")
        source = _constraint_selector(raw.get("source_selector"))
        target = _constraint_selector(raw.get("target_selector"))
        relation_type = raw.get("relation_type")
        assertion_kind = raw.get("assertion_kind")
        semantic_family = raw.get("semantic_family")
        reason = raw.get("reason")
        if source is None or target is None:
            raise CardLoadError(ROOT / "ontology", f"assertion {assertion_id!r} has invalid selector")
        if relation_type not in relation_types:
            raise CardLoadError(ROOT / "ontology", f"assertion {assertion_id!r} has invalid relation_type")
        if not isinstance(assertion_kind, str) or not isinstance(semantic_family, str) or not isinstance(reason, str):
            raise CardLoadError(ROOT / "ontology", f"assertion {assertion_id!r} has invalid semantics")
        action, severity = raw.get("action"), raw.get("severity")
        if action is not None and (not isinstance(action, str) or not action.strip()):
            raise CardLoadError(ROOT / "ontology", f"assertion {assertion_id!r} has invalid action")
        if severity is not None and severity not in severity_values:
            raise CardLoadError(ROOT / "ontology", f"assertion {assertion_id!r} has invalid severity")
        assertions.append(
            OntologyAssertion(
                id=assertion_id,
                relation_type=cast(RelationType, relation_type),
                assertion_kind=assertion_kind,
                semantic_family=semantic_family,
                reason=reason,
                source_selector=source,
                target_selector=target,
                action=action if isinstance(action, str) else None,
                severity=cast(Severity | None, severity),
            )
        )
    return tuple(assertions)


def project_ontology_assertions(
    relations: list[Relation],
    bundle: OntologyBundle,
) -> tuple[OntologyAssertion, ...]:
    """Use generated assertions, extending isolated fixtures only with explicit semantics.

    Production records always resolve to the checked generated vocabulary.  A
    non-default data root may contain fixture-only assertion IDs; these remain
    valid only when the YAML supplied both explicit semantic fields, never by
    inferring behaviour from the relation type.
    """
    generated = load_ontology_assertions(bundle)
    generated_ids = {assertion.id for assertion in generated}
    fixture_assertions = tuple(
        OntologyAssertion(
            id=relation.id,
            relation_type=relation.type,
            assertion_kind=relation.assertion_kind,
            semantic_family=relation.semantic_family,
            reason=relation.reason,
            source_selector=relation.source_selector,
            target_selector=relation.target_selector,
            action=relation.action,
            severity=relation.severity,
        )
        for relation in relations
        if relation.id not in generated_ids
        and relation.assertion_kind is not None
        and relation.semantic_family is not None
    )
    return (*generated, *fixture_assertions)


def _constraint_selector(raw: object) -> RelationSelector:
    selector = _object_mapping(raw)
    if selector is None:
        raise CardLoadError(ROOT / "ontology", "constraint selector must be a mapping")
    if "entity" in selector and ({"category", "term"} & set(selector)):
        raise CardLoadError(ROOT / "ontology", "selector must use entity or category/term, not both")
    entity = _object_mapping(selector.get("entity"))
    if entity is not None:
        if set(selector) != {"entity"} or not set(entity).issubset({"id", "name"}):
            raise CardLoadError(ROOT / "ontology", "malformed entity selector")
        entity_id, entity_name = entity.get("id"), entity.get("name")
        if (entity_id is None) == (entity_name is None):
            raise CardLoadError(ROOT / "ontology", "entity selector requires exactly one non-empty id/name")
        value = entity_id if entity_id is not None else entity_name
        if not isinstance(value, str) or not value.strip():
            raise CardLoadError(ROOT / "ontology", "entity selector value must be a non-empty string")
        return RelationSelector(
            entity_id=entity_id if isinstance(entity_id, str) else None,
            entity_name=entity_name if isinstance(entity_name, str) else None,
        )
    category, term = selector.get("category"), selector.get("term")
    if (
        set(selector) != {"category", "term"}
        or not isinstance(category, str)
        or not category.strip()
        or not isinstance(term, str)
        or not term.strip()
    ):
        raise CardLoadError(ROOT / "ontology", "category selector requires non-empty category and term")
    return RelationSelector(category=category, term=term)


def _constraint_metadata(raw: dict[str, object], constraint_id: str, runtime: RuntimeProgram) -> _ConstraintMetadata:
    """Validate and preserve governance metadata emitted by ontology generation."""
    evidence = raw.get("evidence")
    if not isinstance(evidence, list):
        raise CardLoadError(ROOT / "ontology", f"constraint {constraint_id!r} has invalid evidence")
    evidence_values: list[str] = []
    for item in evidence:
        if not isinstance(item, str):
            raise CardLoadError(
                ROOT / "ontology",
                f"constraint {constraint_id!r} evidence[{len(evidence_values)}] must be a string HTTPS URL",
            )
        if not runtime.constraint_governance.evidence_format.accepts(item):
            raise CardLoadError(
                ROOT / "ontology",
                f"constraint {constraint_id!r} evidence[{len(evidence_values)}] must be a string HTTPS URL",
            )
        evidence_values.append(item)
    evidence_gap = raw.get("evidence_gap")
    if evidence_gap is not None and (not isinstance(evidence_gap, str) or not evidence_gap.strip()):
        raise CardLoadError(ROOT / "ontology", f"constraint {constraint_id!r} has invalid evidence_gap")
    enforcement = raw.get("enforcement")
    status = raw.get("status")
    if (
        not isinstance(status, str)
        or not isinstance(enforcement, str)
        or (status, enforcement) not in runtime.constraint_allowed_pairs
    ):
        raise CardLoadError(
            ROOT / "ontology", f"constraint {constraint_id!r} has invalid status/enforcement combination"
        )
    lifecycle = runtime.lifecycle_decision(status)
    gate = runtime.constraint_execution_gate_for(status)
    if lifecycle is None or gate is None:
        raise CardLoadError(ROOT / "ontology", f"constraint {constraint_id!r} has no runtime lifecycle gate")
    if gate.evidence_requirement == "required" and not evidence_values:
        raise CardLoadError(ROOT / "ontology", f"constraint {constraint_id!r} requires non-empty evidence")
    if gate.evidence_requirement == "prohibited" and evidence_values:
        raise CardLoadError(ROOT / "ontology", f"constraint {constraint_id!r} prohibits evidence")
    if gate.evidence_requirement == "evidence_or_gap" and not evidence_values and not evidence_gap:
        raise CardLoadError(ROOT / "ontology", f"constraint {constraint_id!r} requires evidence or evidence_gap")
    return _ConstraintMetadata(
        rationale=_required_constraint_string(raw, constraint_id, "rationale"),
        semantic_note=_optional_constraint_string(raw, constraint_id, "semantic_note"),
        status=_required_constraint_string(raw, constraint_id, "status"),
        evidence=tuple(evidence_values),
        owner=_required_constraint_string(raw, constraint_id, "owner"),
        review_by=_required_constraint_string(raw, constraint_id, "review_by"),
        assertion_type=_required_constraint_string(raw, constraint_id, "assertion_type"),
    )


def _required_constraint_string(raw: dict[str, object], constraint_id: str, key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CardLoadError(ROOT / "ontology", f"constraint {constraint_id!r} has invalid metadata {key}")
    return value


def _optional_constraint_string(raw: dict[str, object], constraint_id: str, key: str) -> str | None:
    value = raw.get(key)
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise CardLoadError(ROOT / "ontology", f"constraint {constraint_id!r} has invalid metadata {key}")
    return value if isinstance(value, str) else None


def _object_mapping(value: object) -> dict[str, object] | None:
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def check_scheduling_policies(policies: dict[str, SchedulingPolicy], traits_path: Path) -> list[str]:
    """Validate trait namespaces.

    Match-key and match-value validation is handled at ontology load time against
    the runtime ``effect_match_dimensions`` table.

    First-class scheduling constraints define separation; assertions do not.
    """
    errors: list[str] = []

    return errors


def grouped_policies(
    policies: dict[str, SchedulingPolicy],
    namespace_order: tuple[str, ...],
) -> dict[str, list[SchedulingPolicy]]:
    """Group SchedulingPolicys by namespace in stable display order.

    Order is supplied by the ontology runtime vocabulary.
    Only namespaces that have at least one registered trait are included;
    the review-substance command is responsible for showing empty-namespace
    headings for namespaces the substance references but that have no traits.
    """
    groups: dict[str, list[SchedulingPolicy]] = {}
    for trait in sorted(policies.values(), key=lambda t: t.id):
        groups.setdefault(trait.namespace, []).append(trait)
    # Emit in canonical order; fall back to sorted for any unrecognised namespaces.
    known = [ns for ns in namespace_order if ns in groups]
    extra = sorted(ns for ns in groups if ns not in namespace_order)
    return {ns: groups[ns] for ns in known + extra}


def format_trait_effect(effect: TraitEffect) -> str:
    parts: list[str] = []
    for key, value in effect.match.values:
        parts.append(f"{key}={value}")
    match_text = " when " + ", ".join(sorted(parts)) if parts else ""
    if effect.block is True:
        return f"blocks slot{match_text}"
    if effect.level is not None:
        return f"{effect.level}{match_text}"
    return ""


def print_policy_details(trait: SchedulingPolicy) -> None:
    if trait.description:
        print(f"      {trait.description}")
    if trait.applies_when:
        print(f"      Applies when: {trait.applies_when}")
    if trait.warning:
        print("      Output: schedule warning")
    rendered = [format_trait_effect(effect) for effect in trait.effects]
    rendered = [text for text in rendered if text]
    if rendered:
        print("      Slot effects: " + "; ".join(rendered))


def readable_policies(
    trait_ids: set[str],
    policies: dict[str, SchedulingPolicy],
    bundle: OntologyBundle,
) -> list[str]:
    """Return display labels for scheduling-narrative use (schedule.yaml review_tags field).

    For full grouped display (all namespaces, used by review-substance), use
    grouped_policies() + print_policy_details() instead. The two paths are
    intentionally distinct:
      readable_policies()       = schedule narrative (scheduling drivers only)
      review-substance output = full audit (all namespaces visible)
    """
    visibility = _review_tag_visibility(bundle)
    labels: list[str] = []
    for trait_id in sorted(trait_ids):
        namespace, separator, _short_name = trait_id.partition(":")
        if not separator or namespace not in visibility.include_namespaces or trait_id in visibility.exclude_policy_ids:
            continue
        trait = policies.get(trait_id)
        labels.append(trait.label if trait and trait.label else trait_id)
    return sorted(labels, key=str.casefold)


class _ReviewTagVisibility(NamedTuple):
    include_namespaces: frozenset[str]
    exclude_policy_ids: frozenset[str]


def _review_tag_visibility(bundle: OntologyBundle) -> _ReviewTagVisibility:
    raw_presentation = bundle.runtime_vocabulary.get("schedule_presentation")
    if not isinstance(raw_presentation, dict):
        raise CardLoadError(ROOT / "ontology", "canonical runtime vocabulary has no schedule_presentation")
    presentation = cast(dict[str, object], raw_presentation)
    raw_review_tags = presentation.get("review_tags")
    if not isinstance(raw_review_tags, dict):
        raise CardLoadError(ROOT / "ontology", "canonical schedule_presentation has no review_tags")
    review_tags = cast(dict[str, object], raw_review_tags)
    include_namespaces = review_tags.get("include_namespaces")
    exclude_policy_ids = review_tags.get("exclude_policy_ids")
    if (
        not isinstance(include_namespaces, list)
        or not all(isinstance(item, str) and item for item in include_namespaces)
        or not isinstance(exclude_policy_ids, list)
        or not all(isinstance(item, str) and item for item in exclude_policy_ids)
    ):
        raise CardLoadError(ROOT / "ontology", "canonical schedule_presentation review_tags is malformed")
    return _ReviewTagVisibility(frozenset(include_namespaces), frozenset(exclude_policy_ids))
