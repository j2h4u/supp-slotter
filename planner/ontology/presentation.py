"""Strict access to the authored review/schedule presentation contract."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from planner.contracts import CardLoadError
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.glue_capabilities import ONTOLOGY_COMPOSITE_KEY_SEPARATOR
from planner.ontology.schema_enums import schema_enum_values

_CANONICAL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_TERM_FIELDS = frozenset({
    "slug",
    "label",
    "description",
    "semantic_category",
    "allowed_predicates",
    "ontoclean_profile",
})
_CATEGORY_PREDICATE_NAMESPACES = frozenset({"knowledge", "schedule"})
_ONTOCLEAN_PROFILE_FIELDS = frozenset({"id", "rigidity", "supplies_identity", "dependence"})
_ONTOCLEAN_RIGIDITY_VALUES = frozenset({"rigid", "anti_rigid"})
_ONTOCLEAN_DEPENDENCE_VALUES = frozenset({"independent", "dependent"})


@dataclass(frozen=True, slots=True)
class OntoCleanProfile:
    """One canonical, executable OntoClean profile from the verified catalog."""

    id: str
    rigidity: str
    supplies_identity: bool
    dependence: str


def load_ontoclean_profiles(bundle: OntologyBundle) -> Mapping[str, OntoCleanProfile]:  # noqa: C901
    """Decode the complete profile catalog without fallback/default records."""

    source = bundle.root / "generated" / "runtime-vocabulary.yaml"
    raw_profiles = bundle.runtime_vocabulary.get("ontoclean_profiles")
    catalog = _mapping(raw_profiles, "ontoclean_profiles", source)
    if not catalog:
        raise _error("ontology runtime vocabulary ontoclean_profiles must be a non-empty mapping", source)
    profiles: dict[str, OntoCleanProfile] = {}
    for profile_id, raw_profile in catalog.items():
        if not _CANONICAL_NAME_PATTERN.fullmatch(profile_id):
            raise _error(f"ontoclean_profiles contains non-canonical key {profile_id!r}", source)
        profile = _mapping(raw_profile, f"ontoclean_profiles.{profile_id}", source)
        if set(profile) != _ONTOCLEAN_PROFILE_FIELDS:
            raise _error(
                f"ontoclean_profiles.{profile_id} has unsupported or missing fields",
                source,
            )
        embedded_id = profile.get("id")
        if embedded_id != profile_id:
            raise _error(
                f"ontoclean_profiles.{profile_id}.id must equal its canonical key",
                source,
            )
        rigidity = profile.get("rigidity")
        dependence = profile.get("dependence")
        supplies_identity = profile.get("supplies_identity")
        if not isinstance(rigidity, str) or rigidity not in _ONTOCLEAN_RIGIDITY_VALUES:
            raise _error(f"ontoclean_profiles.{profile_id}.rigidity is invalid", source)
        if not isinstance(dependence, str) or dependence not in _ONTOCLEAN_DEPENDENCE_VALUES:
            raise _error(f"ontoclean_profiles.{profile_id}.dependence is invalid", source)
        if not isinstance(supplies_identity, bool):
            raise _error(f"ontoclean_profiles.{profile_id}.supplies_identity must be boolean", source)
        if rigidity == "anti_rigid" and supplies_identity:
            raise _error(f"ontoclean_profiles.{profile_id} is anti-rigid but supplies identity", source)
        if dependence == "independent" and not supplies_identity:
            raise _error(f"ontoclean_profiles.{profile_id} is independent but does not supply identity", source)
        if supplies_identity and (rigidity != "rigid" or dependence != "independent"):
            raise _error(f"ontoclean_profiles.{profile_id} identity supply has invalid semantics", source)
        if rigidity == "anti_rigid" and dependence != "dependent":
            raise _error(f"ontoclean_profiles.{profile_id} anti-rigid semantics require dependence", source)
        profiles[profile_id] = OntoCleanProfile(
            id=profile_id,
            rigidity=rigidity,
            supplies_identity=supplies_identity,
            dependence=dependence,
        )
    return dict(sorted(profiles.items()))


@dataclass(frozen=True, slots=True)
class ReviewPresentation:
    """Validated presentation metadata and its formal registry boundaries."""

    concern_kinds: tuple[str, ...]
    concern_labels: Mapping[str, str]
    review_tag_namespaces: tuple[str, ...]
    excluded_policy_ids: tuple[str, ...]
    active_fact_namespaces: tuple[str, ...]
    active_fact_labels: Mapping[str, str]
    namespace_order: tuple[str, ...]
    zero_effect_condition: str
    zero_effect_template: str

    def label(self, section: str, key: str) -> str:
        """Return an authored label, rejecting unknown presentation keys."""

        labels: Mapping[str, str]
        if section == "concern_annotations":
            labels = self.concern_labels
        elif section == "active_fact_index":
            labels = self.active_fact_labels
        else:
            raise OntologyInfrastructureError(
                f"ontology schedule_presentation has unsupported label section {section!r}",
                code=MALFORMED,
            )
        try:
            return labels[key]
        except KeyError as error:
            raise OntologyInfrastructureError(
                f"ontology schedule_presentation {section} has no label for {key!r}",
                code=MALFORMED,
            ) from error


def load_term_labels(bundle: OntologyBundle) -> Mapping[tuple[str, str], str]:
    """Return the complete authored term-label catalog from the verified bundle.

    The runtime vocabulary is generated from the formal ontology registry, but
    runtime callers still validate its decoded shape at their boundary.  A
    missing or empty catalog must never become an empty fact index: that would
    hide a broken ontology artifact as valid data.
    """

    # Real bundles are strict; the lightweight synthetic object retained by
    # the label unit seam has only the three legacy label fields.
    strict = isinstance(bundle, OntologyBundle)
    return {
        (str(term["semantic_category"]), str(term["slug"])): str(term["label"])
        for term in load_term_catalog(bundle, strict=strict)
    }


def load_term_catalog(  # noqa: C901, PLR0912
    bundle: OntologyBundle,
    *,
    strict: bool = True,
) -> tuple[Mapping[str, object], ...]:
    """Return the canonical generated term registry.

    ``strict`` is used only by the compatibility label unit seam, whose tiny
    synthetic bundles predate the full generated record shape.  Real bundles
    are always registered through ``validate_runtime_catalog`` below.
    """

    source = bundle.root / "generated" / "runtime-vocabulary.yaml"
    raw_terms = bundle.runtime_vocabulary.get("terms")
    if raw_terms is None:
        raise _error("ontology runtime vocabulary terms catalog is missing", source)
    if not isinstance(raw_terms, list):
        raise _error("ontology runtime vocabulary terms must be a list", source)
    if not raw_terms:
        raise _error("ontology runtime vocabulary terms must not be empty", source)
    categories = load_category_predicates(bundle, strict=strict) if strict else {}
    profiles = load_ontoclean_profiles(bundle) if strict else {}
    terms: list[Mapping[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw_term in enumerate(raw_terms):
        term = _mapping(raw_term, f"terms[{index}]", source)
        if strict and set(term) != _TERM_FIELDS:
            raise _error(f"terms[{index}] has unsupported or missing fields", source)
        namespace = term.get("semantic_category")
        slug = term.get("slug")
        label = term.get("label")
        for field, value in (("semantic_category", namespace), ("slug", slug), ("label", label)):
            if not isinstance(value, str) or not value.strip():
                raise _error(f"terms[{index}].{field} must be a non-empty string", source)
        if strict:
            if not _CANONICAL_NAME_PATTERN.fullmatch(cast(str, namespace)):
                raise _error(f"terms[{index}].semantic_category is not canonical", source)
            if not _CANONICAL_NAME_PATTERN.fullmatch(cast(str, slug)):
                raise _error(f"terms[{index}].slug is not canonical", source)
            if cast(str, namespace) not in categories:
                raise _error(f"terms[{index}] references unknown semantic category", source)
            if (
                term.get("description") is None
                or not isinstance(term.get("description"), str)
                or not str(term["description"]).strip()
            ):
                raise _error(f"terms[{index}].description must be a non-empty string", source)
            if (
                term.get("ontoclean_profile") is None
                or not isinstance(term.get("ontoclean_profile"), str)
                or not str(term["ontoclean_profile"]).strip()
            ):
                raise _error(f"terms[{index}].ontoclean_profile must be a non-empty string", source)
            profile_id = cast(str, term["ontoclean_profile"])
            if profile_id not in profiles:
                raise _error(f"terms[{index}] references unknown OntoClean profile", source)
            raw_categories = _mapping(bundle.runtime_vocabulary.get("categories"), "categories", source)
            category_metadata = _mapping(raw_categories.get(cast(str, namespace)), f"categories.{namespace}", source)
            category_profile = category_metadata.get("ontoclean_profile")
            if not isinstance(category_profile, str) or category_profile not in profiles:
                raise _error(f"terms[{index}] semantic category has an unknown OntoClean profile", source)
            if profile_id != category_profile:
                raise _error(f"terms[{index}].ontoclean_profile disagrees with semantic category", source)
            if term.get("allowed_predicates") != list(categories[cast(str, namespace)]):
                raise _error(f"terms[{index}].allowed_predicates disagrees with category", source)
        key = (cast(str, namespace), cast(str, slug))
        if key in seen:
            raise _error(f"terms contains duplicate key {key[0]}:{key[1]}", source)
        seen.add(key)
        terms.append(term)
    return tuple(terms)


def load_category_predicates(  # noqa: C901, PLR0912
    bundle: OntologyBundle,
    *,
    strict: bool = True,
) -> Mapping[str, tuple[str, ...]]:
    """Return category-to-predicate declarations after identity validation."""

    source = bundle.root / "generated" / "runtime-vocabulary.yaml"
    raw_categories = bundle.runtime_vocabulary.get("categories")
    if not isinstance(raw_categories, Mapping) or not raw_categories:
        raise _error("ontology runtime vocabulary categories must be a non-empty mapping", source)
    profiles = load_ontoclean_profiles(bundle) if strict else {}
    result: dict[str, tuple[str, ...]] = {}
    for category, raw in raw_categories.items():
        if not isinstance(category, str) or not _CANONICAL_NAME_PATTERN.fullmatch(category):
            raise _error(f"categories contains non-canonical key {category!r}", source)
        metadata = _mapping(raw, f"categories.{category}", source)
        if strict:
            profile_id = metadata.get("ontoclean_profile")
            if not isinstance(profile_id, str) or not profile_id.strip():
                raise _error(f"categories.{category}.ontoclean_profile must be a non-empty string", source)
            if profile_id not in profiles:
                raise _error(f"categories.{category} references unknown OntoClean profile", source)
        predicates = metadata.get("allowed_predicates")
        if not isinstance(predicates, list) or not predicates:
            raise _error(f"categories.{category}.allowed_predicates must be a non-empty list", source)
        values: list[str] = []
        for index, predicate in enumerate(predicates):
            if not isinstance(predicate, str) or predicate.count(".") != 1:
                raise _error(f"categories.{category}.allowed_predicates[{index}] is malformed", source)
            namespace, suffix = predicate.split(".", maxsplit=1)
            if namespace not in _CATEGORY_PREDICATE_NAMESPACES or not _CANONICAL_NAME_PATTERN.fullmatch(suffix):
                raise _error(f"categories.{category}.allowed_predicates[{index}] is not canonical", source)
            if suffix != category:
                raise _error(f"category {category!r} does not match predicate suffix {suffix!r}", source)
            values.append(predicate)
        if len(set(values)) != len(values):
            raise _error(f"categories.{category}.allowed_predicates contains duplicates", source)
        if strict and len({value.split(".", maxsplit=1)[0] for value in values}) != 1:
            raise _error(f"categories.{category}.allowed_predicates must be homogeneous", source)
        result[category] = tuple(values)
    return result


def validate_runtime_catalog(bundle: OntologyBundle) -> None:
    """Validate all runtime vocabulary registry records before card loaders run."""

    load_ontoclean_profiles(bundle)
    categories = load_category_predicates(bundle, strict=True)
    del categories
    load_term_catalog(bundle, strict=True)


def load_review_presentation(bundle: OntologyBundle) -> ReviewPresentation:  # noqa: PLR0914
    """Decode complete review presentation metadata against formal registries.

    The compiler validates authored source, but runtime callers must also fail
    closed when a verified artifact is mutated or a non-canonical bundle is
    supplied.  This accessor intentionally has no fallback vocabulary.
    """

    source = bundle.root / "generated" / "runtime-vocabulary.yaml"
    vocabulary = bundle.runtime_vocabulary
    raw_presentation = vocabulary.get("schedule_presentation")
    presentation = _mapping(raw_presentation, "schedule_presentation", source)
    _exact_keys(
        presentation,
        {"concern_annotations", "review_tags", "active_fact_index", "zero_effect"},
        "schedule_presentation",
        source,
    )

    concern = _mapping(presentation.get("concern_annotations"), "schedule_presentation.concern_annotations", source)
    _exact_keys(concern, {"include_kinds", "labels"}, "schedule_presentation.concern_annotations", source)
    concern_kinds = _strings(
        concern.get("include_kinds"), "schedule_presentation.concern_annotations.include_kinds", source
    )
    try:
        concern_registry = schema_enum_values(bundle, "ConcernKind")
    except CardLoadError as error:
        raise _error(f"formal ConcernKind registry is unavailable: {error}", source) from error
    _unique_registry(concern_registry, "formal ConcernKind registry", source)
    _complete(concern_kinds, concern_registry, "concern kind", source)
    concern_labels = _labels(
        concern.get("labels"),
        concern_kinds,
        "schedule_presentation.concern_annotations.labels",
        source,
    )

    tags = _mapping(presentation.get("review_tags"), "schedule_presentation.review_tags", source)
    _exact_keys(tags, {"include_namespaces", "exclude_policy_ids"}, "schedule_presentation.review_tags", source)
    review_namespaces = _strings(
        tags.get("include_namespaces"),
        "schedule_presentation.review_tags.include_namespaces",
        source,
    )
    excluded_policy_ids = _strings(
        tags.get("exclude_policy_ids"),
        "schedule_presentation.review_tags.exclude_policy_ids",
        source,
    )
    policies = _mapping(vocabulary.get("scheduling_policies"), "scheduling_policies", source)
    policy_ids = _registry_keys(policies, "scheduling policy", source)
    policy_namespaces = {
        identifier.split(ONTOLOGY_COMPOSITE_KEY_SEPARATOR, maxsplit=1)[0]
        for identifier in policy_ids
        if ONTOLOGY_COMPOSITE_KEY_SEPARATOR in identifier
    }
    _known(review_namespaces, policy_namespaces, "review tag namespace", source)
    _known(excluded_policy_ids, set(policy_ids), "excluded scheduling policy", source)

    active = _mapping(presentation.get("active_fact_index"), "schedule_presentation.active_fact_index", source)
    _exact_keys(active, {"include_namespaces", "labels"}, "schedule_presentation.active_fact_index", source)
    active_namespaces = _strings(
        active.get("include_namespaces"),
        "schedule_presentation.active_fact_index.include_namespaces",
        source,
    )
    categories = _mapping(vocabulary.get("categories"), "categories", source)
    category_names = _registry_keys(categories, "semantic category", source)
    knowledge_namespaces = {
        category for category in category_names if _is_knowledge_category(categories[category], category, source)
    }
    _known(active_namespaces, knowledge_namespaces, "active fact namespace", source)
    active_labels = _labels(
        active.get("labels"),
        active_namespaces,
        "schedule_presentation.active_fact_index.labels",
        source,
    )
    zero_effect = _mapping(presentation.get("zero_effect"), "schedule_presentation.zero_effect", source)
    _exact_keys(zero_effect, {"condition", "template"}, "schedule_presentation.zero_effect", source)
    zero_effect_condition = zero_effect.get("condition")
    zero_effect_template = zero_effect.get("template")
    if zero_effect_condition != "no_nonzero_effects":
        raise _error(
            "schedule_presentation.zero_effect.condition must be 'no_nonzero_effects'",
            source,
        )
    if not isinstance(zero_effect_template, str) or not zero_effect_template.strip():
        raise _error("schedule_presentation.zero_effect.template must be a non-empty string", source)

    axes = tuple(
        row.axis for row in sorted(bundle.runtime_program.assignment_axes, key=lambda row: (row.order, row.id))
    )
    _unique_registry(axes, "runtime program assignment_axes", source)
    namespace_order = tuple(dict.fromkeys(review_namespaces + axes + category_names))
    return ReviewPresentation(
        concern_kinds=concern_kinds,
        concern_labels=concern_labels,
        review_tag_namespaces=review_namespaces,
        excluded_policy_ids=excluded_policy_ids,
        active_fact_namespaces=active_namespaces,
        active_fact_labels=active_labels,
        namespace_order=namespace_order,
        zero_effect_condition=cast(str, zero_effect_condition),
        zero_effect_template=zero_effect_template,
    )


def load_relation_type_order(bundle: OntologyBundle) -> tuple[str, ...]:
    """Return relation types in authored runtime presentation order.

    The generated runtime vocabulary is the verified runtime form of the
    authored relation registry.  Relation IDs are the deterministic tie-break
    when authors assign the same presentation order.
    """

    source = bundle.root / "generated" / "runtime-vocabulary.yaml"
    raw_relation_types = bundle.runtime_vocabulary.get("relation_types")
    if not isinstance(raw_relation_types, Mapping) or not raw_relation_types:
        raise _error("ontology runtime vocabulary relation_types must be a non-empty mapping", source)

    rows: list[tuple[int, str]] = []
    for relation_id, raw_relation in raw_relation_types.items():
        if not isinstance(relation_id, str) or not relation_id.strip():
            raise _error("relation_types contains a non-canonical ID", source)
        relation = _mapping(raw_relation, f"relation_types.{relation_id}", source)
        embedded_id = relation.get("id")
        if embedded_id != relation_id:
            raise _error(f"relation_types.{relation_id}.id must equal its canonical key", source)
        order = relation.get("order")
        if not isinstance(order, int) or isinstance(order, bool):
            raise _error(f"relation_types.{relation_id}.order must be an integer", source)
        rows.append((order, relation_id))
    return tuple(relation_id for _order, relation_id in sorted(rows, key=lambda row: (row[0], row[1])))


def _mapping(value: object, path: str, source: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) or not key.strip() for key in value):
        raise _error(f"{path} must be a mapping with non-empty string keys", source)
    return cast(Mapping[str, object], value)


def _exact_keys(value: Mapping[str, object], expected: set[str], path: str, source: object) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        details = []
        if missing:
            details.append("missing " + ", ".join(repr(item) for item in missing))
        if unknown:
            details.append("unknown " + ", ".join(repr(item) for item in unknown))
        raise _error(f"{path} has unsupported fields ({'; '.join(details)})", source)


def _strings(value: object, path: str, source: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise _error(f"{path} must be a list of non-empty strings", source)
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise _error(f"{path}[{index}] must be a non-empty string", source)
        result.append(item)
    if len(result) != len(set(result)):
        raise _error(f"{path} contains duplicate values", source)
    return tuple(result)


def _labels(value: object, expected: tuple[str, ...], path: str, source: object) -> Mapping[str, str]:
    if not isinstance(value, list):
        raise _error(f"{path} must be a list", source)
    labels: dict[str, str] = {}
    for index, item in enumerate(value):
        row = _mapping(item, f"{path}[{index}]", source)
        _exact_keys(row, {"key", "label"}, f"{path}[{index}]", source)
        key = row.get("key")
        label = row.get("label")
        if not isinstance(key, str) or not key.strip():
            raise _error(f"{path}[{index}].key must be a non-empty string", source)
        if not isinstance(label, str) or not label.strip():
            raise _error(f"{path}[{index}].label must be a non-empty string", source)
        if key in labels:
            raise _error(f"{path} contains duplicate key {key!r}", source)
        labels[key] = label
    _complete(tuple(labels), expected, "presentation label", source)
    return labels


def _registry_keys(value: Mapping[str, object], kind: str, source: object) -> tuple[str, ...]:
    keys = tuple(value)
    if any(not isinstance(key, str) or not key.strip() for key in keys):
        raise _error(f"{kind} registry contains an empty or non-string key", source)
    if len(keys) != len(set(keys)):
        raise _error(f"{kind} registry contains duplicate keys", source)
    return keys


def _unique_registry(values: tuple[str, ...], kind: str, source: object) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise _error(f"{kind} contains an empty or non-string value", source)
    if len(values) != len(set(values)):
        raise _error(f"{kind} contains duplicate values", source)


def _complete(actual: tuple[str, ...], expected: tuple[str, ...], kind: str, source: object) -> None:
    missing = sorted(set(expected) - set(actual))
    unknown = sorted(set(actual) - set(expected))
    if missing or unknown:
        details = []
        if missing:
            details.append("missing " + ", ".join(repr(item) for item in missing))
        if unknown:
            details.append("unknown " + ", ".join(repr(item) for item in unknown))
        raise _error(f"{kind} metadata is incomplete ({'; '.join(details)})", source)


def _known(actual: tuple[str, ...], expected: set[str], kind: str, source: object) -> None:
    unknown = sorted(set(actual) - expected)
    if unknown:
        raise _error(f"{kind} metadata contains unknown values: " + ", ".join(repr(item) for item in unknown), source)


def _is_knowledge_category(value: object, category: str, source: object) -> bool:
    metadata = _mapping(value, f"categories.{category}", source)
    predicates = metadata.get("allowed_predicates")
    if not isinstance(predicates, list) or any(not isinstance(item, str) or not item.strip() for item in predicates):
        raise _error(f"categories.{category}.allowed_predicates must be a list of non-empty strings", source)
    return f"knowledge.{category}" in predicates


def _error(message: str, source: object) -> OntologyInfrastructureError:
    return OntologyInfrastructureError(f"{message} [source: {source}]", code=MALFORMED, path=source)
