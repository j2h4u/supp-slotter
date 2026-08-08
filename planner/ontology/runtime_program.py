"""Typed view of the executable scheduling and review ontology projection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from planner.ontology.errors import MALFORMED, OntologyInfrastructureError


def _error(label: str, message: str) -> OntologyInfrastructureError:
    return OntologyInfrastructureError(f"runtime program {label} {message}", code=MALFORMED)


def _map(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise _error(label, "must be a mapping with string keys")
    return cast(Mapping[str, object], value)


def _str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise _error(label, "must be a non-empty string")
    return value


def _bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise _error(label, "must be boolean")
    return value


def _int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _error(label, "must be an integer")
    return value


def _number(value: object, label: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error(label, "must be a number")
    return value


def _rows(value: object, label: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _error(label, "must be a list")
    result: list[Mapping[str, object]] = []
    ids: set[str] = set()
    for index, item in enumerate(value):
        row = _map(item, f"{label}[{index}]")
        identifier = _str(row.get("id"), f"{label}[{index}].id")
        if identifier in ids:
            raise _error(label, f"has duplicate id {identifier!r}")
        ids.add(identifier)
        result.append(row)
    return tuple(result)


def _strings(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _error(label, "must be a list of strings")
    return tuple(_str(item, f"{label}[{index}]") for index, item in enumerate(value))


@dataclass(frozen=True, slots=True)
class RuntimeGlueContract:
    id: str
    inactive_stack_name: str
    source_kinds: tuple[str, ...]
    source_kind_roles: tuple[str, ...]
    scope_fact_adapters: tuple[str, ...]
    relation_warning_filter_fields: tuple[str, ...]
    relation_warning_active_sides: tuple[str, ...]
    relation_presence_active_sides: tuple[str, ...]
    relation_presence_truth_table: tuple[tuple[bool, bool], ...]
    relation_review_status_ids: tuple[str, ...]
    relation_endpoint_selector_kinds: tuple[str, ...]
    concern_membership_roles: tuple[str, ...]
    active_concern_role: str
    inactive_concern_role: str
    product_concern_fallback_role: str
    substance_concern_fallback_role: str
    warning_emitter_ids: tuple[str, ...]
    prefer_with_source_fields: tuple[str, ...]
    prefer_with_target_resolutions: tuple[str, ...]
    prefer_with_pair_modes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeFactField:
    id: str
    field: str
    value_type: str


@dataclass(frozen=True, slots=True)
class RuntimeSourceKindValuePolicy:
    id: str
    source_kind: str
    applies_to: tuple[str, ...]
    description: str


@dataclass(frozen=True, slots=True)
class RuntimeEffectMatchDimension:
    id: str
    key: str
    slot_field: str
    value_type: str


@dataclass(frozen=True, slots=True)
class RuntimeAssignmentAxis:
    id: str
    axis: str
    order: int
    assignment_source: str
    assignment_field: str


@dataclass(frozen=True, slots=True)
class RuntimeNearModel:
    id: str
    near: str
    model: str


@dataclass(frozen=True, slots=True)
class RuntimeCapabilityRule:
    id: str
    planner: str
    food_model: str
    base_slot_models: tuple[str, ...]
    slot_models: tuple[str, ...]
    product_scope: tuple[str, ...]
    formulations: tuple[str, ...]
    near_to_model: tuple[RuntimeNearModel, ...]


@dataclass(frozen=True, slots=True)
class RuntimeEffectScore:
    id: str
    level: str
    score: float | int


@dataclass(frozen=True, slots=True)
class RuntimeEffectScoring:
    id: str
    scores: tuple[RuntimeEffectScore, ...]
    balance_weight: float | int
    prefer_with_bonus: int
    advisory_constraint_score_delta: int
    advisory_match_direction: str

    @property
    def scores_by_level(self) -> Mapping[str, RuntimeEffectScore]:
        return MappingProxyType({row.level: row for row in self.scores})


@dataclass(frozen=True, slots=True)
class RuntimePreferWithPolicy:
    id: str
    source_field: str
    target_resolution: str
    pair_mode: str


@dataclass(frozen=True, slots=True)
class RuntimeConstraintExecutionPolicy:
    id: str
    operation: str
    match_direction: str
    aggregation: str
    selector_resolution: str
    blocks_slots: bool
    scores_advisory: bool
    score_delta: int


@dataclass(frozen=True, slots=True)
class RuntimeWarningTypePolicy:
    id: str
    warning_type: str
    label: str
    action_text: str


@dataclass(frozen=True, slots=True)
class RuntimeWarningEmitterPolicy:
    id: str
    emitter: str
    warning_type: str
    default_message: str


@dataclass(frozen=True, slots=True)
class RuntimeWarningTraitAction:
    id: str
    trait_id: str
    action_text: str


@dataclass(frozen=True, slots=True)
class RuntimeConcernWarningRule:
    id: str
    concern_kind: str
    warning_type: str


@dataclass(frozen=True, slots=True)
class RuntimeNonWarningConcernKindPolicy:
    id: str
    concern_kind: str
    review_surface: str
    description: str


@dataclass(frozen=True, slots=True)
class RuntimeConcernReviewStatusPolicy:
    id: str
    status: str
    rank: int
    membership_role: str
    description: str


@dataclass(frozen=True, slots=True)
class RuntimeRelationWarningRule:
    id: str
    relation_kind: str
    filter_field: str
    filter_value: str
    active_side: str
    warning_type: str
    review_status: str
    reverse_output: bool


@dataclass(frozen=True, slots=True)
class RuntimeRelationReviewStatusPolicy:
    id: str
    status: str
    rank: int
    description: str


@dataclass(frozen=True, slots=True)
class RuntimeRelationPresenceStatusPolicy:
    id: str
    status: str
    source_active: bool
    target_active: bool
    active_side: str
    default_review_status: str
    description: str


@dataclass(frozen=True, slots=True)
class RuntimeRelationEndpointPolicy:
    id: str
    selector_kind: str
    broad_endpoint: bool
    show_match_details: bool
    audit_member_limit: int
    label: str


@dataclass(frozen=True, slots=True)
class RuntimeProgram:
    format_version: str
    schema_version: str
    source_hash: str
    glue_contract: RuntimeGlueContract
    fact_fields: tuple[RuntimeFactField, ...]
    source_kind_values: tuple[RuntimeSourceKindValuePolicy, ...]
    assignment_axes: tuple[RuntimeAssignmentAxis, ...]
    effect_match_dimensions: tuple[RuntimeEffectMatchDimension, ...]
    effect_scoring: RuntimeEffectScoring
    prefer_with_policy: RuntimePreferWithPolicy
    capability_rules: tuple[RuntimeCapabilityRule, ...]
    constraint_execution_policies: tuple[RuntimeConstraintExecutionPolicy, ...]
    warning_types: tuple[RuntimeWarningTypePolicy, ...]
    warning_emitters: tuple[RuntimeWarningEmitterPolicy, ...]
    warning_trait_actions: tuple[RuntimeWarningTraitAction, ...]
    concern_warning_rules: tuple[RuntimeConcernWarningRule, ...]
    non_warning_concern_kinds: tuple[RuntimeNonWarningConcernKindPolicy, ...]
    concern_review_statuses: tuple[RuntimeConcernReviewStatusPolicy, ...]
    relation_warning_rules: tuple[RuntimeRelationWarningRule, ...]
    relation_review_statuses: tuple[RuntimeRelationReviewStatusPolicy, ...]
    relation_presence_statuses: tuple[RuntimeRelationPresenceStatusPolicy, ...]
    relation_endpoint_policies: tuple[RuntimeRelationEndpointPolicy, ...]

    @property
    def slot_near_values(self) -> frozenset[str]:
        return frozenset(item.near for row in self.capability_rules for item in row.near_to_model)

    @property
    def effect_score_levels(self) -> frozenset[str]:
        return frozenset(item.level for item in self.effect_scoring.scores)

    @property
    def effect_match_dimensions_by_key(self) -> Mapping[str, RuntimeEffectMatchDimension]:
        return MappingProxyType({item.key: item for item in self.effect_match_dimensions})

    @property
    def warning_types_by_type(self) -> Mapping[str, RuntimeWarningTypePolicy]:
        return MappingProxyType({item.warning_type: item for item in self.warning_types})

    @property
    def warning_emitters_by_emitter(self) -> Mapping[str, RuntimeWarningEmitterPolicy]:
        return MappingProxyType({item.emitter: item for item in self.warning_emitters})

    @property
    def concern_review_statuses_by_membership_role(self) -> Mapping[str, RuntimeConcernReviewStatusPolicy]:
        return MappingProxyType({item.membership_role: item for item in self.concern_review_statuses})

    @property
    def concern_review_status_order(self) -> tuple[str, ...]:
        return tuple(item.status for item in sorted(self.concern_review_statuses, key=lambda row: (row.rank, row.id)))

    @property
    def relation_review_statuses_by_status(self) -> Mapping[str, RuntimeRelationReviewStatusPolicy]:
        return MappingProxyType({item.status: item for item in self.relation_review_statuses})

    @property
    def relation_review_status_order(self) -> tuple[str, ...]:
        return tuple(item.status for item in sorted(self.relation_review_statuses, key=lambda row: (row.rank, row.id)))

    @property
    def relation_presence_statuses_by_status(self) -> Mapping[str, RuntimeRelationPresenceStatusPolicy]:
        return MappingProxyType({item.status: item for item in self.relation_presence_statuses})

    @property
    def relation_presence_statuses_by_active_side(self) -> Mapping[str, RuntimeRelationPresenceStatusPolicy]:
        return MappingProxyType({item.active_side: item for item in self.relation_presence_statuses})

    @property
    def relation_endpoint_policies_by_selector_kind(self) -> Mapping[str, RuntimeRelationEndpointPolicy]:
        return MappingProxyType({item.selector_kind: item for item in self.relation_endpoint_policies})

    @property
    def warning_trait_actions_by_trait(self) -> Mapping[str, RuntimeWarningTraitAction]:
        return MappingProxyType({item.trait_id: item for item in self.warning_trait_actions})

    @property
    def warning_type_by_concern_kind(self) -> Mapping[str, str]:
        return MappingProxyType({item.concern_kind: item.warning_type for item in self.concern_warning_rules})

    @property
    def non_warning_concern_kinds_by_kind(self) -> Mapping[str, RuntimeNonWarningConcernKindPolicy]:
        return MappingProxyType({item.concern_kind: item for item in self.non_warning_concern_kinds})

    def constraint_execution_policy_for(self, operation: str) -> RuntimeConstraintExecutionPolicy | None:
        return next((item for item in self.constraint_execution_policies if item.operation == operation), None)

    def relation_endpoint_selector_kind_for(self, *, broad_endpoint: bool) -> str:
        matches = tuple(item.selector_kind for item in self.relation_endpoint_policies if item.broad_endpoint is broad_endpoint)
        if len(matches) != 1:
            raise _error("relation_endpoint_policies", "endpoint breadth must resolve uniquely")
        return matches[0]

    @property
    def concrete_relation_endpoint_selector_kind(self) -> str:
        return self.relation_endpoint_selector_kind_for(broad_endpoint=False)

    @property
    def term_relation_endpoint_selector_kind(self) -> str:
        return self.relation_endpoint_selector_kind_for(broad_endpoint=True)


def _typed_rows(value: object, label: str, factory: object) -> tuple[object, ...]:
    result: list[object] = []
    for index, row in enumerate(_rows(value, label)):
        result.append(cast(object, factory(row, f"{label}[{index}]")))
    return tuple(result)


def _fact(row: Mapping[str, object], label: str) -> RuntimeFactField:
    return RuntimeFactField(_str(row["id"], f"{label}.id"), _str(row["field"], f"{label}.field"), _str(row["value_type"], f"{label}.value_type"))


def _source_kind(row: Mapping[str, object], label: str) -> RuntimeSourceKindValuePolicy:
    return RuntimeSourceKindValuePolicy(_str(row["id"], f"{label}.id"), _str(row["source_kind"], f"{label}.source_kind"), _strings(row["applies_to"], f"{label}.applies_to"), _str(row["description"], f"{label}.description"))


def _axis(row: Mapping[str, object], label: str) -> RuntimeAssignmentAxis:
    return RuntimeAssignmentAxis(_str(row["id"], f"{label}.id"), _str(row["axis"], f"{label}.axis"), _int(row["order"], f"{label}.order"), _str(row["assignment_source"], f"{label}.assignment_source"), _str(row["assignment_field"], f"{label}.assignment_field"))


def _dimension(row: Mapping[str, object], label: str) -> RuntimeEffectMatchDimension:
    return RuntimeEffectMatchDimension(_str(row["id"], f"{label}.id"), _str(row["key"], f"{label}.key"), _str(row["slot_field"], f"{label}.slot_field"), _str(row["value_type"], f"{label}.value_type"))


def _capability(row: Mapping[str, object], label: str) -> RuntimeCapabilityRule:
    near = tuple(RuntimeNearModel(_str(item["id"], f"{label}.near_to_model.id"), _str(item["near"], f"{label}.near_to_model.near"), _str(item["model"], f"{label}.near_to_model.model")) for item in cast(tuple[Mapping[str, object], ...], _rows(row["near_to_model"], f"{label}.near_to_model")))
    return RuntimeCapabilityRule(_str(row["id"], f"{label}.id"), _str(row["planner"], f"{label}.planner"), _str(row["food_model"], f"{label}.food_model"), _strings(row["base_slot_models"], f"{label}.base_slot_models"), _strings(row["slot_models"], f"{label}.slot_models"), _strings(row["product_scope"], f"{label}.product_scope"), _strings(row["formulations"], f"{label}.formulations"), near)


def _policy(row: Mapping[str, object], label: str) -> RuntimeConstraintExecutionPolicy:
    return RuntimeConstraintExecutionPolicy(_str(row["id"], f"{label}.id"), _str(row["operation"], f"{label}.operation"), _str(row["match_direction"], f"{label}.match_direction"), _str(row["aggregation"], f"{label}.aggregation"), _str(row["selector_resolution"], f"{label}.selector_resolution"), _bool(row["blocks_slots"], f"{label}.blocks_slots"), _bool(row["scores_advisory"], f"{label}.scores_advisory"), _int(row["score_delta"], f"{label}.score_delta"))


def _score(row: Mapping[str, object], label: str) -> RuntimeEffectScore:
    return RuntimeEffectScore(_str(row["id"], f"{label}.id"), _str(row["level"], f"{label}.level"), _number(row["score"], f"{label}.score"))


def _warning_type(row: Mapping[str, object], label: str) -> RuntimeWarningTypePolicy:
    return RuntimeWarningTypePolicy(_str(row["id"], f"{label}.id"), _str(row["warning_type"], f"{label}.warning_type"), _str(row["label"], f"{label}.label"), _str(row["action_text"], f"{label}.action_text"))


def _warning_emitter(row: Mapping[str, object], label: str) -> RuntimeWarningEmitterPolicy:
    return RuntimeWarningEmitterPolicy(_str(row["id"], f"{label}.id"), _str(row["emitter"], f"{label}.emitter"), _str(row["warning_type"], f"{label}.warning_type"), _str(row["default_message"], f"{label}.default_message"))


def _warning_trait(row: Mapping[str, object], label: str) -> RuntimeWarningTraitAction:
    return RuntimeWarningTraitAction(_str(row["id"], f"{label}.id"), _str(row["trait_id"], f"{label}.trait_id"), _str(row["action_text"], f"{label}.action_text"))


def _concern_warning(row: Mapping[str, object], label: str) -> RuntimeConcernWarningRule:
    return RuntimeConcernWarningRule(_str(row["id"], f"{label}.id"), _str(row["concern_kind"], f"{label}.concern_kind"), _str(row["warning_type"], f"{label}.warning_type"))


def _non_warning(row: Mapping[str, object], label: str) -> RuntimeNonWarningConcernKindPolicy:
    return RuntimeNonWarningConcernKindPolicy(_str(row["id"], f"{label}.id"), _str(row["concern_kind"], f"{label}.concern_kind"), _str(row["review_surface"], f"{label}.review_surface"), _str(row["description"], f"{label}.description"))


def _concern_status(row: Mapping[str, object], label: str) -> RuntimeConcernReviewStatusPolicy:
    return RuntimeConcernReviewStatusPolicy(_str(row["id"], f"{label}.id"), _str(row["status"], f"{label}.status"), _int(row["rank"], f"{label}.rank"), _str(row["membership_role"], f"{label}.membership_role"), _str(row["description"], f"{label}.description"))


def _relation_warning(row: Mapping[str, object], label: str) -> RuntimeRelationWarningRule:
    return RuntimeRelationWarningRule(_str(row["id"], f"{label}.id"), _str(row["relation_kind"], f"{label}.relation_kind"), _str(row["filter_field"], f"{label}.filter_field"), _str(row["filter_value"], f"{label}.filter_value"), _str(row["active_side"], f"{label}.active_side"), _str(row["warning_type"], f"{label}.warning_type"), _str(row["review_status"], f"{label}.review_status"), _bool(row["reverse_output"], f"{label}.reverse_output"))


def _relation_status(row: Mapping[str, object], label: str) -> RuntimeRelationReviewStatusPolicy:
    return RuntimeRelationReviewStatusPolicy(_str(row["id"], f"{label}.id"), _str(row["status"], f"{label}.status"), _int(row["rank"], f"{label}.rank"), _str(row["description"], f"{label}.description"))


def _presence(row: Mapping[str, object], label: str) -> RuntimeRelationPresenceStatusPolicy:
    return RuntimeRelationPresenceStatusPolicy(_str(row["id"], f"{label}.id"), _str(row["status"], f"{label}.status"), _bool(row["source_active"], f"{label}.source_active"), _bool(row["target_active"], f"{label}.target_active"), _str(row["active_side"], f"{label}.active_side"), _str(row["default_review_status"], f"{label}.default_review_status"), _str(row["description"], f"{label}.description"))


def _endpoint(row: Mapping[str, object], label: str) -> RuntimeRelationEndpointPolicy:
    return RuntimeRelationEndpointPolicy(_str(row["id"], f"{label}.id"), _str(row["selector_kind"], f"{label}.selector_kind"), _bool(row["broad_endpoint"], f"{label}.broad_endpoint"), _bool(row["show_match_details"], f"{label}.show_match_details"), _int(row["audit_member_limit"], f"{label}.audit_member_limit"), _str(row["label"], f"{label}.label"))


def _raw_projection(payload: Mapping[str, object]) -> Mapping[str, object]:
    root = _map(payload, "")
    projection = _map(root.get("projection"), "projection")
    return projection


def decode_runtime_program(payload: Mapping[str, object]) -> RuntimeProgram:
    """Decode a compiler-verified runtime snapshot."""
    root = _map(payload, "")
    projection = _raw_projection(payload)
    glue_raw = _map(projection.get("glue_contract"), "glue_contract")
    truth = tuple((bool(_map(item, "truth")["source_active"]), bool(_map(item, "truth")["target_active"])) for item in cast(Sequence[object], glue_raw["relation_presence_truth_table"]))
    glue = RuntimeGlueContract(
        _str(glue_raw["id"], "glue_contract.id"), _str(glue_raw["inactive_stack_name"], "glue_contract.inactive_stack_name"), _strings(glue_raw["source_kinds"], "glue_contract.source_kinds"), _strings(glue_raw["source_kind_roles"], "glue_contract.source_kind_roles"), _strings(glue_raw["scope_fact_adapters"], "glue_contract.scope_fact_adapters"), _strings(glue_raw["relation_warning_filter_fields"], "glue_contract.relation_warning_filter_fields"), _strings(glue_raw["relation_warning_active_sides"], "glue_contract.relation_warning_active_sides"), _strings(glue_raw["relation_presence_active_sides"], "glue_contract.relation_presence_active_sides"), truth, _strings(glue_raw["relation_review_status_ids"], "glue_contract.relation_review_status_ids"), _strings(glue_raw["relation_endpoint_selector_kinds"], "glue_contract.relation_endpoint_selector_kinds"), _strings(glue_raw["concern_membership_roles"], "glue_contract.concern_membership_roles"), _str(glue_raw["active_concern_role"], "glue_contract.active_concern_role"), _str(glue_raw["inactive_concern_role"], "glue_contract.inactive_concern_role"), _str(glue_raw["product_concern_fallback_role"], "glue_contract.product_concern_fallback_role"), _str(glue_raw["substance_concern_fallback_role"], "glue_contract.substance_concern_fallback_role"), _strings(glue_raw["warning_emitter_ids"], "glue_contract.warning_emitter_ids"), _strings(glue_raw["prefer_with_source_fields"], "glue_contract.prefer_with_source_fields"), _strings(glue_raw["prefer_with_target_resolutions"], "glue_contract.prefer_with_target_resolutions"), _strings(glue_raw["prefer_with_pair_modes"], "glue_contract.prefer_with_pair_modes"),
    )
    scoring = _map(projection.get("effect_scoring"), "effect_scoring")
    scoring_obj = RuntimeEffectScoring(_str(scoring["id"], "effect_scoring.id"), cast(tuple[RuntimeEffectScore, ...], _typed_rows(scoring["scores"], "effect_scoring.scores", _score)), _number(scoring["balance_weight"], "effect_scoring.balance_weight"), _int(scoring["prefer_with_bonus"], "effect_scoring.prefer_with_bonus"), _int(scoring["advisory_constraint_score_delta"], "effect_scoring.advisory_constraint_score_delta"), _str(scoring["advisory_match_direction"], "effect_scoring.advisory_match_direction"))
    prefer = _map(projection.get("prefer_with_policy"), "prefer_with_policy")
    prefer_obj = RuntimePreferWithPolicy(_str(prefer["id"], "prefer_with_policy.id"), _str(prefer["source_field"], "prefer_with_policy.source_field"), _str(prefer["target_resolution"], "prefer_with_policy.target_resolution"), _str(prefer["pair_mode"], "prefer_with_policy.pair_mode"))
    typed = {
        "fact_fields": cast(tuple[RuntimeFactField, ...], _typed_rows(projection["fact_fields"], "fact_fields", _fact)),
        "source_kind_values": cast(tuple[RuntimeSourceKindValuePolicy, ...], _typed_rows(projection["source_kind_values"], "source_kind_values", _source_kind)),
        "assignment_axes": cast(tuple[RuntimeAssignmentAxis, ...], _typed_rows(projection["assignment_axes"], "assignment_axes", _axis)),
        "effect_match_dimensions": cast(tuple[RuntimeEffectMatchDimension, ...], _typed_rows(projection["effect_match_dimensions"], "effect_match_dimensions", _dimension)),
        "capability_rules": cast(tuple[RuntimeCapabilityRule, ...], _typed_rows(projection["capability_rules"], "capability_rules", _capability)),
        "constraint_execution_policies": cast(tuple[RuntimeConstraintExecutionPolicy, ...], _typed_rows(projection["constraint_execution_policies"], "constraint_execution_policies", _policy)),
        "warning_types": cast(tuple[RuntimeWarningTypePolicy, ...], _typed_rows(projection["warning_types"], "warning_types", _warning_type)),
        "warning_emitters": cast(tuple[RuntimeWarningEmitterPolicy, ...], _typed_rows(projection["warning_emitters"], "warning_emitters", _warning_emitter)),
        "warning_trait_actions": cast(tuple[RuntimeWarningTraitAction, ...], _typed_rows(projection["warning_trait_actions"], "warning_trait_actions", _warning_trait)),
        "concern_warning_rules": cast(tuple[RuntimeConcernWarningRule, ...], _typed_rows(projection["concern_warning_rules"], "concern_warning_rules", _concern_warning)),
        "non_warning_concern_kinds": cast(tuple[RuntimeNonWarningConcernKindPolicy, ...], _typed_rows(projection["non_warning_concern_kinds"], "non_warning_concern_kinds", _non_warning)),
        "concern_review_statuses": cast(tuple[RuntimeConcernReviewStatusPolicy, ...], _typed_rows(projection["concern_review_statuses"], "concern_review_statuses", _concern_status)),
        "relation_warning_rules": cast(tuple[RuntimeRelationWarningRule, ...], _typed_rows(projection["relation_warning_rules"], "relation_warning_rules", _relation_warning)),
        "relation_review_statuses": cast(tuple[RuntimeRelationReviewStatusPolicy, ...], _typed_rows(projection["relation_review_statuses"], "relation_review_statuses", _relation_status)),
        "relation_presence_statuses": cast(tuple[RuntimeRelationPresenceStatusPolicy, ...], _typed_rows(projection["relation_presence_statuses"], "relation_presence_statuses", _presence)),
        "relation_endpoint_policies": cast(tuple[RuntimeRelationEndpointPolicy, ...], _typed_rows(projection["relation_endpoint_policies"], "relation_endpoint_policies", _endpoint)),
    }
    return RuntimeProgram(_str(root["format_version"], "format_version"), _str(root["schema_version"], "schema_version"), _str(root["source_hash"], "source_hash"), glue, typed["fact_fields"], typed["source_kind_values"], typed["assignment_axes"], typed["effect_match_dimensions"], scoring_obj, prefer_obj, typed["capability_rules"], typed["constraint_execution_policies"], typed["warning_types"], typed["warning_emitters"], typed["warning_trait_actions"], typed["concern_warning_rules"], typed["non_warning_concern_kinds"], typed["concern_review_statuses"], typed["relation_warning_rules"], typed["relation_review_statuses"], typed["relation_presence_statuses"], typed["relation_endpoint_policies"])


def relation_presence_policy_for_active_side(
    active_side: str,
    relation_presence_by_active_side: Mapping[str, RuntimeRelationPresenceStatusPolicy],
) -> RuntimeRelationPresenceStatusPolicy:
    try:
        return relation_presence_by_active_side[active_side]
    except KeyError as error:
        raise ValueError(f"unknown relation active side {active_side!r}") from error
