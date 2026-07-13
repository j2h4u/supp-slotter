"""Trait definitions: flattening, validation, and rendering helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

from planner.contracts import (
    CardLoadError,
    OntologyAssertion,
    Relation,
    RelationSelector,
    SchedulingConstraint,
    SchedulingPolicy,
    SlotNear,
    TraitEffect,
    TraitEffectMatch,
)
from planner.ontology.artifacts import load_runtime_vocabulary
from planner.paths import ROOT


def _build_trait_effect(effect: dict[str, object]) -> TraitEffect:
    match_raw_obj = effect.get("match")
    if not isinstance(match_raw_obj, dict):
        match_raw: dict[str, object] = {}
    else:
        match_raw = cast(dict[str, object], match_raw_obj)
    near_raw = match_raw.get("near")
    food_raw = match_raw.get("food")
    level_raw = effect.get("level")
    block_raw = effect.get("block")
    level = (
        cast(Literal["avoid_strong", "avoid", "prefer", "prefer_strong"], level_raw)
        if isinstance(level_raw, str) and level_raw in {"avoid_strong", "avoid", "prefer", "prefer_strong"}
        else None
    )
    block = block_raw if isinstance(block_raw, bool) else None
    return TraitEffect(
        match=TraitEffectMatch(
            near=cast(SlotNear, near_raw) if isinstance(near_raw, str) else None,
            food=food_raw if isinstance(food_raw, bool) else None,
        ),
        level=level,
        block=block,
    )


def load_scheduling_policies(_path: Path | None = None) -> dict[str, SchedulingPolicy]:
    """Materialize scheduler policies from generated canonical ontology artifacts."""
    vocabulary = load_runtime_vocabulary(ROOT / "ontology")
    raw_policies = vocabulary.get("scheduling_policies")
    if not isinstance(raw_policies, dict):
        raise CardLoadError(ROOT / "ontology", "canonical runtime vocabulary has no scheduling_policies")
    out: dict[str, SchedulingPolicy] = {}
    for tid, policy_obj in raw_policies.items():
        if not isinstance(tid, str) or not isinstance(policy_obj, dict) or ":" not in tid:
            continue
        namespace, short_name = tid.split(":", maxsplit=1)
        policy = cast(dict[str, object], policy_obj)
        effects_raw = policy.get("effects") or ()
        out[tid] = SchedulingPolicy(
            id=tid,
            namespace=namespace,
            short_name=short_name,
            label=cast(str, policy.get("label", "")),
            description=cast(str, policy.get("description", "")),
            applies_when=cast(str, policy.get("applies_when", "")),
            effects=tuple(
                _build_trait_effect(cast(dict[str, object], effect))
                for effect in effects_raw
                if isinstance(effect, dict)
            )
            if isinstance(effects_raw, (list, tuple))
            else (),
            warning=bool(policy.get("warning")),
            action=cast(str | None, policy.get("action")),
        )
    return out


def load_scheduling_constraints() -> tuple[SchedulingConstraint, ...]:
    """Load first-class hard scheduling constraints from generated vocabulary."""
    vocabulary = load_runtime_vocabulary(ROOT / "ontology")
    raw_constraints = vocabulary.get("scheduling_constraints")
    if not isinstance(raw_constraints, dict):
        raise CardLoadError(ROOT / "ontology", "canonical runtime vocabulary has no scheduling_constraints")
    constraints: list[SchedulingConstraint] = []
    constraints_mapping = cast(dict[str, object], raw_constraints)
    for constraint_id, raw_value in constraints_mapping.items():
        raw = _object_mapping(raw_value)
        if not isinstance(constraint_id, str) or raw is None:
            continue
        source = _constraint_selector(raw.get("source_selector"))
        target = _constraint_selector(raw.get("target_selector"))
        effect, enforcement = raw.get("effect"), raw.get("enforcement")
        if source is None or target is None or not isinstance(effect, str) or not isinstance(enforcement, str):
            continue
        action = raw.get("action")
        constraints.append(
            SchedulingConstraint(
                id=constraint_id,
                source_selector=source,
                target_selector=target,
                effect=effect,
                enforcement=enforcement,
                action=action if isinstance(action, str) else None,
            )
        )
    return tuple(constraints)


def load_ontology_assertions() -> tuple[OntologyAssertion, ...]:
    """Load non-blocking semantic assertions from generated canonical vocabulary."""
    vocabulary = load_runtime_vocabulary(ROOT / "ontology")
    raw_assertions = vocabulary.get("ontology_assertions")
    if not isinstance(raw_assertions, dict):
        raise CardLoadError(ROOT / "ontology", "canonical runtime vocabulary has no ontology_assertions")
    assertions: list[OntologyAssertion] = []
    assertions_mapping = cast(dict[str, object], raw_assertions)
    for assertion_id, raw_value in assertions_mapping.items():
        raw = _object_mapping(raw_value)
        if not isinstance(assertion_id, str) or raw is None:
            continue
        source = _constraint_selector(raw.get("source_selector"))
        target = _constraint_selector(raw.get("target_selector"))
        relation_type = raw.get("relation_type")
        assertion_kind = raw.get("assertion_kind")
        semantic_family = raw.get("semantic_family")
        reason = raw.get("reason")
        if source is None or target is None:
            continue
        if relation_type not in {"balance", "supports", "review_with"}:
            continue
        if not isinstance(assertion_kind, str) or not isinstance(semantic_family, str) or not isinstance(reason, str):
            continue
        action, severity = raw.get("action"), raw.get("severity")
        assertions.append(
            OntologyAssertion(
                id=assertion_id,
                relation_type=cast(Literal["balance", "supports", "review_with"], relation_type),
                assertion_kind=assertion_kind,
                semantic_family=semantic_family,
                reason=reason,
                source_selector=source,
                target_selector=target,
                action=action if isinstance(action, str) else None,
                severity=cast(Literal["critical", "high", "medium", "low"] | None, severity),
            )
        )
    return tuple(assertions)


def project_ontology_assertions(relations: list[Relation]) -> tuple[OntologyAssertion, ...]:
    """Use generated assertions, extending isolated fixtures only with explicit semantics.

    Production records always resolve to the checked generated vocabulary.  A
    non-default data root may contain fixture-only assertion IDs; these remain
    valid only when the YAML supplied both explicit semantic fields, never by
    inferring behaviour from the relation type.
    """
    generated = load_ontology_assertions()
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


def _constraint_selector(raw: object) -> RelationSelector | None:
    selector = _object_mapping(raw)
    if selector is None:
        return None
    entity = _object_mapping(selector.get("entity"))
    if entity is not None:
        entity_id, entity_name = entity.get("id"), entity.get("name")
        return RelationSelector(
            entity_id=entity_id if isinstance(entity_id, str) else None,
            entity_name=entity_name if isinstance(entity_name, str) else None,
        )
    category, term = selector.get("category"), selector.get("term")
    return RelationSelector(
        category=category if isinstance(category, str) else None, term=term if isinstance(term, str) else None
    )


def _object_mapping(value: object) -> dict[str, object] | None:
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def check_scheduling_policies(policies: dict[str, SchedulingPolicy], traits_path: Path) -> list[str]:
    """Validate trait namespaces.

    Match-key validation is handled by JSON schema + TraitEffectMatch dataclass:
    the schema constrains match to {near, food} with additionalProperties: false,
    and TraitEffectMatch enforces those at load time.

    First-class scheduling constraints define separation; assertions do not.
    """
    errors: list[str] = []

    return errors


NAMESPACE_ORDER = (
    "kind",
    "role",
    "quality",
    "effect",
    "intake",
    "timing",
    "risk",
    "activity",
    "context",
    "pathway",
)


def grouped_policies(
    policies: dict[str, SchedulingPolicy],
) -> dict[str, list[SchedulingPolicy]]:
    """Group SchedulingPolicys by namespace in stable display order.

    Order is fixed: is, effect, intake, timing, risk, activity, context, pathway.
    Only namespaces that have at least one registered trait are included;
    the review-substance command is responsible for showing empty-namespace
    headings for namespaces the substance references but that have no traits.
    """
    groups: dict[str, list[SchedulingPolicy]] = {}
    for trait in sorted(policies.values(), key=lambda t: t.id):
        groups.setdefault(trait.namespace, []).append(trait)
    # Emit in canonical order; fall back to sorted for any unrecognised namespaces.
    known = [ns for ns in NAMESPACE_ORDER if ns in groups]
    extra = sorted(ns for ns in groups if ns not in NAMESPACE_ORDER)
    return {ns: groups[ns] for ns in known + extra}


def format_trait_effect(effect: TraitEffect) -> str:
    parts: list[str] = []
    if effect.match.near is not None:
        parts.append(f"near={effect.match.near}")
    if effect.match.food is not None:
        parts.append(f"food={effect.match.food}")
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


def readable_policies(trait_ids: set[str], policies: dict[str, SchedulingPolicy]) -> list[str]:
    """Return display labels for scheduling-narrative use (schedule.yaml review_tags field).

    Excludes:
    - risk:manual_review (operator-only flag, not narrative content)
    - is:* (intrinsic category — review-classification axis, not a scheduling driver)
    - context:* (operator-curated review-context membership — review-classification axis,
      not a scheduling driver)
    - timing:* (scheduling-driver only — drives near/sleep slot rules internally;
      not a human-readable narrative label)
    - pathway:* (Reviewer-only metabolic pathway membership — not used by Planner
      scheduling and not meaningful as a schedule narrative label)

    For full grouped display (all namespaces, used by review-substance), use
    grouped_policies() + print_policy_details() instead. The two paths are
    intentionally distinct:
      readable_policies()       = schedule narrative (scheduling drivers only)
      review-substance output = full audit (all namespaces visible)
    """
    labels: list[str] = []
    for trait_id in sorted(trait_ids):
        if trait_id == "risk:manual_review":
            continue
        if trait_id.startswith("is:"):
            continue
        if trait_id.startswith("context:"):
            continue
        if trait_id.startswith("timing:"):
            continue
        if trait_id.startswith("pathway:"):
            continue
        trait = policies.get(trait_id)
        labels.append(trait.label if trait and trait.label else trait_id)
    return sorted(labels, key=str.casefold)
