"""Strict access to the authored review presentation contract."""

from __future__ import annotations

import re
import threading
import weakref
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from planner.ontology.bundle_view import OntologyBundleView
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.verification import is_registered_bundle

_CANONICAL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_TERM_FIELDS = frozenset({
    "slug",
    "label",
    "description",
    "semantic_category",
    "allowed_predicates",
    "ontoclean_profile",
})
_CATEGORY_FIELDS = frozenset({"allowed_predicates", "ontoclean_profile", "multivalued"})
_CATEGORY_PREDICATE_NAMESPACES = frozenset({"knowledge"})
_ONTOCLEAN_PROFILE_FIELDS = frozenset({"id", "rigidity", "supplies_identity", "dependence"})
_ONTOCLEAN_RIGIDITY_VALUES = frozenset({"rigid", "anti_rigid"})
_ONTOCLEAN_DEPENDENCE_VALUES = frozenset({"independent", "dependent"})


class _VerifiedBundleCache[T]:
    """Reuse one immutable decoder result for one live verified bundle."""

    def __init__(self) -> None:
        self._entries: dict[int, tuple[weakref.ReferenceType[OntologyBundleView], T]] = {}
        self._lock: threading.Lock = threading.Lock()

    def get(self, bundle: OntologyBundleView, decoder: Callable[[OntologyBundleView], T]) -> T:
        if not is_registered_bundle(bundle):
            return decoder(bundle)
        identity = id(bundle)
        with self._lock:
            entry = self._entries.get(identity)
            if entry is not None and entry[0]() is bundle:
                return entry[1]
            if entry is not None:
                del self._entries[identity]

        value = decoder(bundle)

        def discard(reference: weakref.ReferenceType[OntologyBundleView]) -> None:
            with self._lock:
                current = self._entries.get(identity)
                if current is not None and current[0] is reference:
                    del self._entries[identity]

        reference = weakref.ref(bundle, discard)
        with self._lock:
            current = self._entries.get(identity)
            if current is not None and current[0]() is bundle:
                return current[1]
            self._entries[identity] = (reference, value)
        return value


@dataclass(frozen=True, slots=True)
class OntoCleanProfile:
    """One canonical, executable OntoClean profile from the verified catalog."""

    id: str
    rigidity: str
    supplies_identity: bool
    dependence: str


@dataclass(frozen=True, slots=True)
class RelationPresentation:
    """Authored display metadata for one canonical relation type."""

    label: str
    order: int
    directional: bool


@dataclass(frozen=True, slots=True)
class _TermContext:
    source: object
    categories: Mapping[str, tuple[str, ...]]
    profiles: Mapping[str, OntoCleanProfile]
    raw_categories: Mapping[str, object]


def load_ontoclean_profiles(bundle: OntologyBundleView) -> Mapping[str, OntoCleanProfile]:
    """Strictly decode the complete profile catalog without fallback records."""

    return _PROFILE_CACHE.get(bundle, _decode_ontoclean_profiles)


def _decode_ontoclean_profiles(bundle: OntologyBundleView) -> Mapping[str, OntoCleanProfile]:
    """Decode the complete profile catalog without consulting the cache."""

    source = bundle.root / "generated" / "runtime-vocabulary.yaml"
    raw_profiles = bundle.runtime_vocabulary.get("ontoclean_profiles")
    catalog = _mapping(raw_profiles, "ontoclean_profiles", source)
    if not catalog:
        raise _error("ontology runtime vocabulary ontoclean_profiles must be a non-empty mapping", source)
    profiles: dict[str, OntoCleanProfile] = {}
    for profile_id, raw_profile in catalog.items():
        profiles[profile_id] = _decode_profile(profile_id, raw_profile, source)
    return MappingProxyType(dict(sorted(profiles.items())))


def _decode_profile(profile_id: str, raw_profile: object, source: object) -> OntoCleanProfile:
    if not _CANONICAL_NAME_PATTERN.fullmatch(profile_id):
        raise _error(f"ontoclean_profiles contains non-canonical key {profile_id!r}", source)
    profile = _mapping(raw_profile, f"ontoclean_profiles.{profile_id}", source)
    if set(profile) != _ONTOCLEAN_PROFILE_FIELDS:
        raise _error(f"ontoclean_profiles.{profile_id} has unsupported or missing fields", source)
    if profile.get("id") != profile_id:
        raise _error(f"ontoclean_profiles.{profile_id}.id must equal its canonical key", source)
    rigidity, dependence, supplies_identity = (
        profile.get("rigidity"),
        profile.get("dependence"),
        profile.get("supplies_identity"),
    )
    if not isinstance(rigidity, str) or rigidity not in _ONTOCLEAN_RIGIDITY_VALUES:
        raise _error(f"ontoclean_profiles.{profile_id}.rigidity is invalid", source)
    if not isinstance(dependence, str) or dependence not in _ONTOCLEAN_DEPENDENCE_VALUES:
        raise _error(f"ontoclean_profiles.{profile_id}.dependence is invalid", source)
    if not isinstance(supplies_identity, bool):
        raise _error(f"ontoclean_profiles.{profile_id}.supplies_identity must be boolean", source)
    _validate_profile_semantics(profile_id, rigidity, dependence, supplies_identity, source)
    return OntoCleanProfile(profile_id, rigidity, supplies_identity, dependence)


def _validate_profile_semantics(
    profile_id: str, rigidity: str, dependence: str, supplies_identity: bool, source: object
) -> None:
    if rigidity == "anti_rigid" and supplies_identity:
        raise _error(f"ontoclean_profiles.{profile_id} is anti-rigid but supplies identity", source)
    if dependence == "independent" and not supplies_identity:
        raise _error(f"ontoclean_profiles.{profile_id} is independent but does not supply identity", source)
    if supplies_identity and (rigidity != "rigid" or dependence != "independent"):
        raise _error(f"ontoclean_profiles.{profile_id} identity supply has invalid semantics", source)
    if rigidity == "anti_rigid" and dependence != "dependent":
        raise _error(f"ontoclean_profiles.{profile_id} anti-rigid semantics require dependence", source)


_PROFILE_CACHE = _VerifiedBundleCache[Mapping[str, OntoCleanProfile]]()
_CATEGORY_CACHE = _VerifiedBundleCache[Mapping[str, tuple[str, ...]]]()
_TERM_CACHE = _VerifiedBundleCache[tuple[Mapping[str, object], ...]]()
_TERM_LABEL_CACHE = _VerifiedBundleCache[Mapping[tuple[str, str], str]]()
_RELATION_PRESENTATION_CACHE = _VerifiedBundleCache[Mapping[str, RelationPresentation]]()


def load_term_labels(bundle: OntologyBundleView) -> Mapping[tuple[str, str], str]:
    """Return the complete authored term-label catalog after strict decoding.

    The runtime vocabulary is generated from the formal ontology registry, but
    runtime callers still validate its decoded shape at their boundary.  A
    missing or empty catalog must never become an empty fact index: that would
    hide a broken ontology artifact as valid data.
    """

    return _TERM_LABEL_CACHE.get(bundle, _decode_term_labels)


def authored_term_label(term_id: str, bundle: OntologyBundleView) -> str:
    """Resolve a ``namespace:slug`` term through its authored label."""
    namespace, separator, slug = term_id.partition(":")
    if not separator or not namespace or not slug:
        raise ValueError(f"ontology term id {term_id!r} is malformed; raw id is diagnostic only")
    try:
        return load_term_labels(bundle)[(namespace, slug)]
    except KeyError as error:
        raise ValueError(f"ontology term {term_id!r} has no authored label; raw id is diagnostic only") from error


def authored_relation_label(relation_type: str, bundle: OntologyBundleView) -> str:
    """Resolve a relation type through its authored presentation catalog."""
    return authored_relation_presentation(relation_type, bundle).label


def authored_relation_presentation(relation_type: str, bundle: OntologyBundleView) -> RelationPresentation:
    """Resolve closed relation presentation metadata from the verified catalog."""
    try:
        return load_relation_presentations(bundle)[relation_type]
    except KeyError as error:
        raise ValueError(f"ontology relation type {relation_type!r} has no authored presentation") from error


def load_relation_presentations(bundle: OntologyBundleView) -> Mapping[str, RelationPresentation]:
    return _RELATION_PRESENTATION_CACHE.get(bundle, _decode_relation_presentations)


def _decode_relation_presentations(bundle: OntologyBundleView) -> Mapping[str, RelationPresentation]:
    source = bundle.root / "generated" / "runtime-vocabulary.yaml"
    relation_types = bundle.runtime_vocabulary.get("relation_types")
    if not isinstance(relation_types, Mapping) or not relation_types:
        raise _error("ontology relation_types presentation catalog is missing", source)
    decoded: dict[str, RelationPresentation] = {}
    seen_orders: set[int] = set()
    for relation_type, raw_relation in relation_types.items():
        if (
            not isinstance(relation_type, str)
            or not _CANONICAL_NAME_PATTERN.fullmatch(relation_type)
            or not isinstance(raw_relation, Mapping)
        ):
            raise _error("ontology relation_types presentation catalog is malformed", source)
        relation = cast(Mapping[str, object], raw_relation)
        if set(relation) != {"id", "label", "order", "directional", "source_selector_forms", "target_selector_forms"}:
            raise _error(f"ontology relation type {relation_type!r} has invalid presentation shape", source)
        label, order, directional = relation.get("label"), relation.get("order"), relation.get("directional")
        if relation.get("id") != relation_type or not isinstance(label, str) or not label.strip():
            raise _error(f"ontology relation type {relation_type!r} has invalid identity or label", source)
        if isinstance(order, bool) or not isinstance(order, int) or order < 0 or order in seen_orders:
            raise _error(f"ontology relation type {relation_type!r} has invalid or duplicate order", source)
        if not isinstance(directional, bool):
            raise _error(f"ontology relation type {relation_type!r} has invalid directional flag", source)
        seen_orders.add(order)
        decoded[relation_type] = RelationPresentation(label, order, directional)
    return MappingProxyType(decoded)


def _decode_term_labels(bundle: OntologyBundleView) -> Mapping[tuple[str, str], str]:
    return MappingProxyType({
        (str(term["semantic_category"]), str(term["slug"])): str(term["label"]) for term in load_term_catalog(bundle)
    })


def load_term_catalog(
    bundle: OntologyBundleView,
) -> tuple[Mapping[str, object], ...]:
    """Return the canonical generated term registry after strict decoding."""

    return _TERM_CACHE.get(bundle, _decode_term_catalog)


def _decode_term_catalog(
    bundle: OntologyBundleView,
) -> tuple[Mapping[str, object], ...]:
    """Decode the canonical generated term registry without consulting the cache."""

    source = bundle.root / "generated" / "runtime-vocabulary.yaml"
    raw_terms = bundle.runtime_vocabulary.get("terms")
    if raw_terms is None:
        raise _error("ontology runtime vocabulary terms catalog is missing", source)
    if not isinstance(raw_terms, list):
        raise _error("ontology runtime vocabulary terms must be a list", source)
    raw_terms = cast(list[object], raw_terms)
    if not raw_terms:
        raise _error("ontology runtime vocabulary terms must not be empty", source)
    categories = load_category_predicates(bundle)
    profiles = load_ontoclean_profiles(bundle)
    raw_categories = _mapping(bundle.runtime_vocabulary.get("categories"), "categories", source)
    context = _TermContext(source, categories, profiles, raw_categories)
    terms: list[Mapping[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw_term in enumerate(raw_terms):
        term = _decode_term(index, raw_term, context)
        namespace, slug = cast(str, term["semantic_category"]), cast(str, term["slug"])
        key = (cast(str, namespace), cast(str, slug))
        if key in seen:
            raise _error(f"terms contains duplicate key {key[0]}:{key[1]}", source)
        seen.add(key)
        terms.append(MappingProxyType(dict(term)))
    return tuple(terms)


def _decode_term(
    index: int,
    raw_term: object,
    context: _TermContext,
) -> Mapping[str, object]:
    source, categories = context.source, context.categories
    term = _mapping(raw_term, f"terms[{index}]", source)
    namespace, _slug = _term_identity(term, index, source, categories)
    _term_profile(term, index, namespace, context)
    if not isinstance(term.get("allowed_predicates"), list) or cast(list[str], term["allowed_predicates"]) != list(
        categories[namespace]
    ):
        raise _error(f"terms[{index}].allowed_predicates disagrees with category", source)
    return MappingProxyType(dict(term))


def _term_identity(
    term: Mapping[str, object], index: int, source: object, categories: Mapping[str, tuple[str, ...]]
) -> tuple[str, str]:
    if set(term) != _TERM_FIELDS:
        raise _error(f"terms[{index}] has unsupported or missing fields", source)
    namespace, slug = term.get("semantic_category"), term.get("slug")
    for field, value in (("semantic_category", namespace), ("slug", slug), ("label", term.get("label"))):
        if not isinstance(value, str) or not value.strip():
            raise _error(f"terms[{index}].{field} must be a non-empty string", source)
    if not _CANONICAL_NAME_PATTERN.fullmatch(cast(str, namespace)):
        raise _error(f"terms[{index}].semantic_category is not canonical", source)
    if not _CANONICAL_NAME_PATTERN.fullmatch(cast(str, slug)):
        raise _error(f"terms[{index}].slug is not canonical", source)
    if cast(str, namespace) not in categories:
        raise _error(f"terms[{index}] references unknown semantic category", source)
    return cast(str, namespace), cast(str, slug)


def _term_profile(
    term: Mapping[str, object],
    index: int,
    namespace: str,
    context: _TermContext,
) -> None:
    source, profiles, raw_categories = context.source, context.profiles, context.raw_categories
    if not isinstance(term.get("description"), str) or not str(term["description"]).strip():
        raise _error(f"terms[{index}].description must be a non-empty string", source)
    profile_id = term.get("ontoclean_profile")
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise _error(f"terms[{index}].ontoclean_profile must be a non-empty string", source)
    if profile_id not in profiles:
        raise _error(f"terms[{index}] references unknown OntoClean profile", source)
    category_metadata = _mapping(raw_categories.get(namespace), f"categories.{namespace}", source)
    category_profile = category_metadata.get("ontoclean_profile")
    if not isinstance(category_profile, str) or category_profile not in profiles:
        raise _error(f"terms[{index}] semantic category has an unknown OntoClean profile", source)
    if profile_id != category_profile:
        raise _error(f"terms[{index}].ontoclean_profile disagrees with semantic category", source)


def load_category_predicates(
    bundle: OntologyBundleView,
) -> Mapping[str, tuple[str, ...]]:
    """Return category predicates after strict structural identity validation."""

    return _CATEGORY_CACHE.get(bundle, _decode_category_predicates)


def _decode_category_predicates(
    bundle: OntologyBundleView,
) -> Mapping[str, tuple[str, ...]]:
    """Decode category predicates without consulting the cache."""

    source = bundle.root / "generated" / "runtime-vocabulary.yaml"
    raw_categories = bundle.runtime_vocabulary.get("categories")
    if not isinstance(raw_categories, Mapping) or not raw_categories:
        raise _error("ontology runtime vocabulary categories must be a non-empty mapping", source)
    raw_categories = cast(Mapping[object, object], raw_categories)
    profiles = load_ontoclean_profiles(bundle)
    result: dict[str, tuple[str, ...]] = {}
    for category, raw in raw_categories.items():
        if not isinstance(category, str) or not _CANONICAL_NAME_PATTERN.fullmatch(category):
            raise _error(f"categories contains non-canonical key {category!r}", source)
        result[category] = _decode_category(category, raw, source, profiles)
    return MappingProxyType(result)


def _decode_category(
    category: str, raw: object, source: object, profiles: Mapping[str, OntoCleanProfile]
) -> tuple[str, ...]:
    metadata = _mapping(raw, f"categories.{category}", source)
    if set(metadata) != _CATEGORY_FIELDS:
        raise _error(f"categories.{category} has unsupported or missing fields", source)
    profile_id = metadata.get("ontoclean_profile")
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise _error(f"categories.{category}.ontoclean_profile must be a non-empty string", source)
    if profile_id not in profiles:
        raise _error(f"categories.{category} references unknown OntoClean profile", source)
    if not isinstance(metadata.get("multivalued"), bool):
        raise _error(f"categories.{category}.multivalued must be boolean", source)
    predicates = metadata.get("allowed_predicates")
    if not isinstance(predicates, list) or not predicates:
        raise _error(f"categories.{category}.allowed_predicates must be a non-empty list", source)
    values = [
        _decode_category_predicate(category, index, predicate, source)
        for index, predicate in enumerate(cast(list[object], predicates))
    ]
    if len(set(values)) != len(values):
        raise _error(f"categories.{category}.allowed_predicates contains duplicates", source)
    if len({value.split(".", maxsplit=1)[0] for value in values}) != 1:
        raise _error(f"categories.{category}.allowed_predicates must be homogeneous", source)
    return tuple(values)


def _decode_category_predicate(category: str, index: int, predicate: object, source: object) -> str:
    if not isinstance(predicate, str) or predicate.count(".") != 1:
        raise _error(f"categories.{category}.allowed_predicates[{index}] is malformed", source)
    namespace, suffix = predicate.split(".", maxsplit=1)
    if namespace not in _CATEGORY_PREDICATE_NAMESPACES or not _CANONICAL_NAME_PATTERN.fullmatch(suffix):
        raise _error(f"categories.{category}.allowed_predicates[{index}] is not canonical", source)
    if suffix != category:
        raise _error(f"category {category!r} does not match predicate suffix {suffix!r}", source)
    return predicate


def validate_runtime_catalog(bundle: OntologyBundleView) -> None:
    """Validate all runtime vocabulary registry records before card loaders run."""

    load_ontoclean_profiles(bundle)
    categories = load_category_predicates(bundle)
    del categories
    load_term_catalog(bundle)


def _mapping(value: object, path: str, source: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) or not key.strip() for key in value):
        raise _error(f"{path} must be a mapping with non-empty string keys", source)
    return cast(Mapping[str, object], value)


def _error(message: str, source: object) -> OntologyInfrastructureError:
    return OntologyInfrastructureError(f"{message} [source: {source}]", code=MALFORMED, path=source)
