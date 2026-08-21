"""Trait definitions: flattening, validation, and rendering helpers."""

# pyright: reportUnknownArgumentType=false

from __future__ import annotations

from typing import NamedTuple, cast

from planner.contracts import (
    CardLoadError,
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
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.glue_capabilities import (
    IMPLEMENTED_EFFECT_MATCH_VALUE_HANDLERS,
    ONTOLOGY_COMPOSITE_KEY_SEPARATOR,
)
from planner.ontology.presentation import load_review_presentation
from planner.ontology.runtime_program import RuntimeProgram
from planner.ontology.schema_enums import schema_enum_values
from planner.ontology.selector import hydrate_selector
from planner.paths import ROOT


def _policy_error(bundle: OntologyBundle, message: str) -> OntologyInfrastructureError:
    """Report malformed generated policy data with its immutable source."""
    source = bundle.root / "generated" / "runtime-vocabulary.yaml"
    return OntologyInfrastructureError(f"{message} [source: {source}]", code=MALFORMED, path=source)


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
    if set(effect) - {"match", "level"}:
        raise CardLoadError(ROOT / "ontology", "policy effect has unknown fields")
    if level_raw is not None and (not isinstance(level_raw, str) or level_raw not in runtime.effect_score_levels):
        raise CardLoadError(ROOT / "ontology", "policy effect has invalid level")
    level = level_raw if isinstance(level_raw, str) else None
    if level is None:
        raise CardLoadError(ROOT / "ontology", "policy effect must declare a soft score level")
    return TraitEffect(match=TraitEffectMatch(tuple(match_values)), level=level)


def _validated_effect_match_value(value: object, key: str, value_type: str, runtime: RuntimeProgram) -> str | bool:
    handler = IMPLEMENTED_EFFECT_MATCH_VALUE_HANDLERS.get(value_type)
    if handler is None:
        raise CardLoadError(ROOT / "ontology", f"policy effect has unsupported match value type {value_type}")
    if handler == "boolean":
        if not isinstance(value, bool):
            raise CardLoadError(ROOT / "ontology", f"policy effect has invalid {key}")
        return value
    if handler == "capability_values":
        if not isinstance(value, str) or value not in runtime.slot_near_values:
            raise CardLoadError(ROOT / "ontology", f"policy effect has invalid {key}")
        return value
    raise CardLoadError(ROOT / "ontology", f"policy effect has unsupported match handler {handler}")


def _required_policy_string(policy: dict[str, object], policy_id: str, key: str) -> str:
    value = policy.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CardLoadError(ROOT / "ontology", f"policy {policy_id!r} has invalid {key}")
    return value


def _validate_warning_trait_actions(runtime: RuntimeProgram, policies: dict[str, SchedulingPolicy]) -> None:
    unknown_warning_traits = sorted(set(runtime.warning_trait_actions_by_trait) - set(policies))
    if unknown_warning_traits:
        raise CardLoadError(
            ROOT / "ontology",
            "runtime warning_trait_actions reference unknown scheduling policies: " + ", ".join(unknown_warning_traits),
        )


def _canonical_policy_categories(bundle: OntologyBundle) -> dict[str, object]:
    categories = bundle.runtime_vocabulary.get("categories")
    if not isinstance(categories, dict) or not categories:
        raise _policy_error(bundle, "canonical runtime vocabulary has no semantic categories")
    return cast(dict[str, object], categories)


def load_scheduling_policies(bundle: OntologyBundle) -> dict[str, SchedulingPolicy]:
    """Materialize scheduler policies from generated canonical ontology artifacts."""
    vocabulary = bundle.runtime_vocabulary
    runtime = bundle.runtime_program
    raw_policies = vocabulary.get("scheduling_policies")
    if not isinstance(raw_policies, dict):
        raise _policy_error(bundle, "canonical runtime vocabulary has no scheduling_policies")
    categories = _canonical_policy_categories(bundle)
    out: dict[str, SchedulingPolicy] = {}
    for tid, policy_obj in raw_policies.items():
        if not isinstance(tid, str) or not isinstance(policy_obj, dict) or ONTOLOGY_COMPOSITE_KEY_SEPARATOR not in tid:
            raise _policy_error(bundle, f"malformed scheduling policy {tid!r}")
        namespace, short_name = tid.split(ONTOLOGY_COMPOSITE_KEY_SEPARATOR, maxsplit=1)
        if namespace not in categories:
            raise _policy_error(bundle, f"policy {tid!r} uses unknown canonical category {namespace!r}")
        policy = cast(dict[str, object], policy_obj)
        effects_raw = policy.get("effects")
        if not isinstance(effects_raw, list):
            raise _policy_error(bundle, f"policy {tid!r} has invalid effects")
        effects: list[TraitEffect] = []
        for index, effect in enumerate(effects_raw):
            if not isinstance(effect, dict):
                raise _policy_error(bundle, f"policy {tid!r} effects[{index}] is malformed")
            try:
                effects.append(_build_trait_effect(cast(dict[str, object], effect), runtime))
            except CardLoadError as error:
                raise _policy_error(bundle, str(error)) from error
        try:
            label = _required_policy_string(policy, tid, "label")
            description = _required_policy_string(policy, tid, "description")
            applies_when = _required_policy_string(policy, tid, "applies_when")
        except CardLoadError as error:
            raise _policy_error(bundle, str(error)) from error
        warning = policy.get("warning")
        if not isinstance(warning, bool):
            raise _policy_error(bundle, f"policy {tid!r} has invalid warning")
        action = policy.get("action")
        if action is not None and (not isinstance(action, str) or not action.strip()):
            raise _policy_error(bundle, f"policy {tid!r} has invalid action")
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
        )
    try:
        _validate_warning_trait_actions(runtime, out)
    except CardLoadError as error:
        raise _policy_error(bundle, str(error)) from error
    return out


def load_scheduling_constraints(
    bundle: OntologyBundle,
) -> tuple[SchedulingConstraint, ...]:
    """Load first-class hard scheduling constraints from generated vocabulary."""
    vocabulary = bundle.runtime_vocabulary
    runtime = bundle.runtime_program
    raw_constraints = vocabulary.get("scheduling_constraints")
    if not isinstance(raw_constraints, dict):
        raise _policy_error(bundle, "canonical runtime vocabulary has no scheduling_constraints")
    required_string_fields = _required_constraint_string_fields(bundle)
    constraints: list[SchedulingConstraint] = []
    constraints_mapping = cast(dict[str, object], raw_constraints)
    for constraint_id, raw_value in constraints_mapping.items():
        raw = _object_mapping(raw_value)
        if not isinstance(constraint_id, str) or not constraint_id.strip() or raw is None:
            raise _policy_error(bundle, f"malformed scheduling constraint {constraint_id!r}")
        try:
            source = _constraint_selector(raw.get("source_selector"))
            target = _constraint_selector(raw.get("target_selector"))
        except CardLoadError as error:
            raise _policy_error(bundle, f"constraint {constraint_id!r}: {error}") from error
        operation = raw.get("operation")
        if not isinstance(operation, str) or not operation.strip():
            raise _policy_error(bundle, f"constraint {constraint_id!r} has invalid operation")
        if runtime.constraint_execution_policy_for(operation) is None:
            raise _policy_error(bundle, f"constraint {constraint_id!r} has unknown operation {operation!r}")
        required_strings: dict[str, str] = {}
        for field in required_string_fields:
            value = raw.get(field)
            if not isinstance(value, str) or not value.strip():
                raise _policy_error(bundle, f"constraint {constraint_id!r} has invalid {field}")
            required_strings[field] = value
        action = required_strings["action"]
        blocks_slots = raw.get("blocks_slots")
        if not isinstance(blocks_slots, bool):
            blocks_slots = None
        scores_advisory = raw.get("scores_advisory")
        if not isinstance(scores_advisory, bool):
            scores_advisory = None
        score_delta = raw.get("score_delta")
        if isinstance(score_delta, bool) or not isinstance(score_delta, int):
            score_delta = None
        constraints.append(
            SchedulingConstraint(
                id=constraint_id,
                source_selector=source,
                target_selector=target,
                operation=operation,
                action=action,
                rationale=required_strings["rationale"],
                blocks_slots=blocks_slots,
                scores_advisory=scores_advisory,
                score_delta=score_delta,
            )
        )
    return tuple(constraints)


def _required_constraint_string_fields(bundle: OntologyBundle) -> tuple[str, ...]:
    """Read required string metadata from the generated formal schema.

    The runtime vocabulary is generated from ``SchedulingConstraintRecord``;
    keeping this check driven by the committed schema prevents the loader from
    silently drifting when the formal model adds another required string field.
    """
    schema = bundle.decoded.get("schema.json")
    if not isinstance(schema, dict):
        raise _policy_error(bundle, "generated schema has no mapping")
    schema = cast(dict[str, object], schema)
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        raise _policy_error(bundle, "generated schema has no definitions")
    definitions = cast(dict[str, object], definitions)
    definition = definitions.get("SchedulingConstraintRecord__identifier_optional")
    if not isinstance(definition, dict):
        raise _policy_error(bundle, "generated schema has no scheduling constraint record definition")
    definition = cast(dict[str, object], definition)
    required = definition.get("required")
    properties = definition.get("properties")
    if (
        not isinstance(required, list)
        or any(not isinstance(field, str) for field in required)
        or not isinstance(properties, dict)
    ):
        raise _policy_error(bundle, "generated scheduling constraint record metadata is malformed")
    required = cast(list[object], required)
    properties = cast(dict[str, object], properties)
    string_fields: list[str] = []
    for field in cast(list[str], required):
        property_schema = properties.get(field)
        if isinstance(property_schema, dict) and cast(dict[str, object], property_schema).get("type") == "string":
            string_fields.append(field)
    if not string_fields:
        raise _policy_error(bundle, "generated scheduling constraint record declares no required string metadata")
    if not {"action", "rationale"} <= set(string_fields):
        raise _policy_error(bundle, "generated scheduling constraint record must require action and rationale")
    return tuple(string_fields)


def load_ontology_assertions(bundle: OntologyBundle) -> tuple[OntologyAssertion, ...]:
    """Load non-blocking semantic assertions from generated canonical vocabulary."""
    vocabulary = bundle.runtime_vocabulary
    raw_assertions = vocabulary.get("ontology_assertions")
    if not isinstance(raw_assertions, dict):
        raise _policy_error(bundle, "canonical runtime vocabulary has no ontology_assertions")
    raw_relation_types = vocabulary.get("relation_types")
    if not isinstance(raw_relation_types, dict) or not raw_relation_types:
        raise _policy_error(bundle, "canonical runtime vocabulary has no relation_types")
    relation_types = set(raw_relation_types)
    severity_values = frozenset(schema_enum_values(bundle, "Severity"))
    assertions: list[OntologyAssertion] = []
    assertions_mapping = cast(dict[str, object], raw_assertions)
    for assertion_id, raw_value in assertions_mapping.items():
        raw = _object_mapping(raw_value)
        if not isinstance(assertion_id, str) or not assertion_id.strip() or raw is None:
            raise _policy_error(bundle, f"malformed ontology assertion {assertion_id!r}")
        try:
            source = _assertion_selector(raw.get("source_selector"))
            target = _assertion_selector(raw.get("target_selector"))
        except CardLoadError as error:
            raise _policy_error(bundle, f"assertion {assertion_id!r}: {error}") from error
        relation_type = raw.get("relation_type")
        assertion_kind = raw.get("assertion_kind")
        semantic_family = raw.get("semantic_family")
        reason = raw.get("reason")
        if source is None or target is None:
            raise _policy_error(bundle, f"assertion {assertion_id!r} has invalid selector")
        if relation_type not in relation_types:
            raise _policy_error(bundle, f"assertion {assertion_id!r} has invalid relation_type")
        if not isinstance(assertion_kind, str) or not isinstance(semantic_family, str) or not isinstance(reason, str):
            raise _policy_error(bundle, f"assertion {assertion_id!r} has invalid semantics")
        action, severity = raw.get("action"), raw.get("severity")
        if action is not None and (not isinstance(action, str) or not action.strip()):
            raise _policy_error(bundle, f"assertion {assertion_id!r} has invalid action")
        if severity is not None and severity not in severity_values:
            raise _policy_error(bundle, f"assertion {assertion_id!r} has invalid severity")
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
                research_state=cast(str, raw.get("research_state", "unassessed")),
                sources=tuple(item for item in raw.get("sources", []) if isinstance(item, str)),
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
    _validate_relation_ids_before_projection(relations)
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
            research_state=relation.research_state,
            sources=relation.sources,
        )
        for relation in relations
        if relation.id not in generated_ids
        and relation.assertion_kind is not None
        and relation.semantic_family is not None
    )
    return (*generated, *fixture_assertions)


def _validate_relation_ids_before_projection(relations: list[Relation]) -> None:
    """Reject malformed relation identities before read-model projection.

    YAML loaders normally enforce this through the generated relation schema's
    keyed uniqueness contract.  Keep the projection boundary fail-closed for
    callers that construct typed relations directly (fixtures and integrations)
    so duplicate IDs cannot become duplicate read-model assertions.
    """
    seen: dict[str, int] = {}
    for index, relation in enumerate(relations):
        identifier = relation.id
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f"relations[{index}].id must be a non-empty string")
        previous = seen.get(identifier)
        if previous is not None:
            raise ValueError(
                f"relations[{index}].id duplicates {identifier!r}; previously declared at relations[{previous}].id"
            )
        seen[identifier] = index


def _constraint_selector(raw: object) -> RelationSelector:
    selector = hydrate_selector(
        raw,
        path=ROOT / "ontology",
        label="constraint",
        allow_entity_name=True,
        allow_scope=True,
    )
    if selector.scope not in {None, "exact_form"}:
        raise CardLoadError(ROOT / "ontology", "constraint selector has unsupported scope")
    if selector.scope is not None and selector.entity_id is None:
        raise CardLoadError(ROOT / "ontology", "constraint selector scope requires entity_id")
    return selector


def _assertion_selector(raw: object) -> RelationSelector:
    return hydrate_selector(raw, path=ROOT / "ontology", label="assertion", allow_entity_name=True)


def _object_mapping(value: object) -> dict[str, object] | None:
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def check_scheduling_policies(policies: dict[str, SchedulingPolicy]) -> list[str]:
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
    for trait_id in sorted(trait_ids, key=str):
        if not isinstance(trait_id, str):
            raise _policy_error(bundle, f"schedule output references malformed policy id {trait_id!r}")
        namespace, separator, _short_name = trait_id.partition(ONTOLOGY_COMPOSITE_KEY_SEPARATOR)
        if not separator:
            raise _policy_error(bundle, f"schedule output references malformed policy id {trait_id!r}")
        if namespace not in visibility.include_namespaces or trait_id in visibility.exclude_policy_ids:
            continue
        trait = policies.get(trait_id)
        if trait is None:
            raise _policy_error(bundle, f"schedule output references unknown policy {trait_id!r}")
        labels.append(trait.label)
    return sorted(labels, key=str.casefold)


class _ReviewTagVisibility(NamedTuple):
    include_namespaces: frozenset[str]
    exclude_policy_ids: frozenset[str]


def _review_tag_visibility(bundle: OntologyBundle) -> _ReviewTagVisibility:
    presentation = load_review_presentation(bundle)
    return _ReviewTagVisibility(
        frozenset(presentation.review_tag_namespaces),
        frozenset(presentation.excluded_policy_ids),
    )
