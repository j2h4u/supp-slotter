"""Canonical typed-selector relation loading and validation."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal, NamedTuple, cast

from planner.contracts import (
    CardLoadError,
    Relation,
    RelationSelector,
    RelationType,
    ResearchState,
    Severity,
    Substance,
)
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.selector import (
    RelationTypeContract,
    hydrate_selector,
    load_relation_type_contracts,
    resolve_selector,
    selector_identity_key,
    validate_relation_selector_form,
)
from planner.ontology.schema_enums import schema_enum_values
from planner.paths import Paths
from planner.schema_validation import schema_errors
from planner.yaml_io import YamlValue, load_yaml


class _ValidationContext(NamedTuple):
    substances: Mapping[str, Substance]
    relation_types: Mapping[str, RelationTypeContract]


class _SelectorContext(NamedTuple):
    substances: Mapping[str, Substance]
    bundle: OntologyBundle


def load_global_relations(
    paths: Paths,
    bundle: OntologyBundle,
    substances: Mapping[str, Substance],
) -> list[Relation]:
    """Load authored ontology relations without endpoint aliases or fallback decoding."""
    # Relation endpoint identity is checked against the complete card registry,
    # not the active stack.  Every caller must supply that registry explicitly.
    data = load_yaml(paths.relations_file)
    if not isinstance(data, dict):
        raise CardLoadError(paths.relations_file, f"{paths.relations_file}: relations top-level must be a mapping")
    result: list[Relation] = []
    if "relations" not in data:
        raise CardLoadError(paths.relations_file, f"{paths.relations_file}: missing required field 'relations'")
    entries = data["relations"]
    if not isinstance(entries, list):
        raise CardLoadError(paths.relations_file, f"{paths.relations_file}: relations must be a list")
    relation_types = load_relation_type_contracts(bundle)
    selector_context = _SelectorContext(substances, bundle)
    seen_directionless: dict[tuple[str, frozenset[str]], int] = {}
    for index, raw_entry in enumerate(entries):
        path = f"{paths.relations_file}: relations[{index}]"
        entry = _validated_relation_entry(raw_entry, paths.relations_file, path, bundle)
        relation_type = entry.get("relation_type")
        if not isinstance(relation_type, str) or relation_type not in relation_types:
            raise CardLoadError(
                paths.relations_file,
                f"{path}.relation_type {relation_type!r} is not in ontology relation_types",
            )
        typed_relation = _relation_from_mapping(
            cast(RelationType, relation_type),
            entry,
            paths.relations_file,
            index,
            selector_context,
            relation_types[relation_type],
        )
        _validate_direction_usage(
            typed_relation,
            relation_types[relation_type],
            substances,
            bundle,
            seen_directionless,
            index,
            paths.relations_file,
        )
        result.append(typed_relation)
    errors = schema_errors(data, "relations", paths.relations_file, bundle)
    if errors:
        raise CardLoadError(paths.relations_file, errors[0])
    return result


def _validated_relation_entry(
    raw: object, path: Path, label: str, bundle: OntologyBundle
) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise CardLoadError(path, f"{label} must be a mapping")
    entry = cast(dict[str, object], raw)
    required = ("id", "relation_type", "source_selector", "target_selector", "reason")
    missing = tuple(field for field in required if field not in entry)
    if missing:
        raise CardLoadError(path, f"{label} missing required field(s): {', '.join(missing)}")
    for field in ("id", "reason"):
        value = entry[field]
        if not isinstance(value, str) or not value.strip():
            raise CardLoadError(path, f"{label}.{field} must be a non-empty string")
    for field in ("action", "severity", "assertion_kind", "semantic_family", "research_state"):
        value = entry.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise CardLoadError(path, f"{label}.{field} must be a non-empty string when present")
    state = entry.get("research_state", "unassessed")
    state_values = frozenset(schema_enum_values(bundle, "ResearchState"))
    if state not in state_values:
        raise CardLoadError(path, f"{label}.research_state is not in ontology ResearchState")
    sources = entry.get("sources", [])
    if not isinstance(sources, list) or any(
        not isinstance(source, str) or not source.strip() for source in sources
    ):
        raise CardLoadError(path, f"{label}.sources must be a list of non-empty strings")
    if state != "unassessed" and not sources:
        raise CardLoadError(path, f"{label}.sources must be non-empty for research_state {state!r}")
    return entry


def _relation_from_mapping(  # noqa: PLR0913, PLR0917
    relation_type: RelationType,
    relation: dict[str, object],
    path: Path,
    index: int,
    selector_context: _SelectorContext,
    contract: RelationTypeContract,
) -> Relation:
    source = _selector_from_mapping(
        relation.get("source_selector"),
        path,
        f"relations[{index}].source_selector",
        selector_context.substances,
        selector_context.bundle,
    )
    target = _selector_from_mapping(
        relation.get("target_selector"),
        path,
        f"relations[{index}].target_selector",
        selector_context.substances,
        selector_context.bundle,
    )
    validate_relation_selector_form(
        source,
        contract=contract,
        side="source",
        path=path,
        label=f"relations[{index}].source_selector",
    )
    validate_relation_selector_form(
        target,
        contract=contract,
        side="target",
        path=path,
        label=f"relations[{index}].target_selector",
    )
    return Relation(
        id=cast(str, relation.get("id", "")),
        type=relation_type,
        reason=cast(str, relation.get("reason", "")),
        source_selector=source,
        target_selector=target,
        action=_optional_str(relation.get("action")),
        severity=cast(Severity | None, relation.get("severity")),
        assertion_kind=_optional_str(relation.get("assertion_kind")),
        semantic_family=_optional_str(relation.get("semantic_family")),
        research_state=cast(ResearchState, relation.get("research_state", "unassessed")),
        sources=tuple(cast(list[str], relation.get("sources", []))),
    )


def _selector_from_mapping(
    raw: object,
    path: Path,
    label: str,
    substances: Mapping[str, Substance],
    bundle: OntologyBundle,
) -> RelationSelector:
    selector = hydrate_selector(
        raw,
        path=path,
        label=label,
        allow_entity_name=True,
    )
    resolution = resolve_selector(selector, substances, bundle)
    if resolution.outcome not in {"resolved", "empty"}:
        raise CardLoadError(path, _selector_resolution_error(selector, label, resolution.outcome))
    return selector


def _selector_resolution_error(selector: RelationSelector, label: str, outcome: str) -> str:
    if selector.entity_id is not None:
        return f"{label}.entity.entity_id '{selector.entity_id}' has no matching substance card"
    if selector.entity_name is not None:
        return f"{label}.entity.name '{selector.entity_name}' has no matching substance name"
    if selector.category is not None and selector.term is not None:
        return f"{label} term '{selector.category}:{selector.term}' is not in canonical ontology vocabulary"
    return f"{label} cannot resolve selector ({outcome})"


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def check_global_relations(  # noqa: C901
    relations_data: YamlValue, substances: dict[str, Substance], paths: Paths, bundle: OntologyBundle
) -> list[str]:
    """Validate selector shape and every entity/term reference against canonical vocabulary."""
    errors = schema_errors(relations_data, "relations", paths.relations_file, bundle)
    if errors or not isinstance(relations_data, dict):
        return errors
    relation_types = load_relation_type_contracts(bundle)
    context = _ValidationContext(substances, relation_types)
    entries = relations_data.get("relations")
    if "relations" not in relations_data:
        errors.append(f"{paths.relations_file}: missing required field 'relations'")
        return errors
    if not isinstance(entries, list):
        errors.append(f"{paths.relations_file}: relations must be a list")
        return errors
    seen_directionless: dict[tuple[str, frozenset[str]], int] = {}
    for index, raw in enumerate(entries):
        if not isinstance(raw, dict):
            errors.append(f"{paths.relations_file}: relations[{index}] must be a mapping")
            continue
        relation = cast(dict[str, object], raw)
        path = f"{paths.relations_file}: relations[{index}]"
        relation_type = relation.get("relation_type")
        contract = relation_types.get(relation_type) if isinstance(relation_type, str) else None
        if contract is None:
            errors.append(f"{path}.relation_type {relation_type!r} is not in ontology relation_types")
        for side in ("source", "target"):
            errors.extend(
                _selector_errors(
                    relation.get(f"{side}_selector"),
                    side,
                    path,
                    context,
                    bundle,
                    contract,
                )
            )
        if contract is not None and not contract.directional:
            try:
                source = _selector_from_mapping(
                    relation.get("source_selector"),
                    Path(path),
                    f"{path}.source_selector",
                    context.substances,
                    bundle,
                )
                target = _selector_from_mapping(
                    relation.get("target_selector"),
                    Path(path),
                    f"{path}.target_selector",
                    context.substances,
                    bundle,
                )
            except CardLoadError:
                continue
            key = (
                contract.id,
                frozenset((
                    _selector_identity_key(source, context.substances, bundle),
                    _selector_identity_key(target, context.substances, bundle),
                )),
            )
            previous = seen_directionless.get(key)
            if previous is not None:
                errors.append(
                    f"{path} uses direction for non-directional relation type {contract.id!r}; "
                    f"its endpoints duplicate the unordered relation at relations[{previous}]"
                )
            else:
                seen_directionless[key] = index
    return errors


def _selector_errors(  # noqa: PLR0913, PLR0917
    raw: object,
    side: str,
    path: str,
    context: _ValidationContext,
    bundle: OntologyBundle,
    contract: RelationTypeContract | None,
) -> list[str]:
    label = f"{path}.{side}_selector"
    try:
        selector = _selector_from_mapping(raw, Path(path), label, context.substances, bundle)
        if contract is not None:
            validate_relation_selector_form(
                selector,
                contract=contract,
                side=cast("Literal['source', 'target']", side),
                path=Path(path),
                label=label,
            )
    except CardLoadError as error:
        return [error.message]
    return []


def _validate_direction_usage(  # noqa: PLR0913, PLR0917
    relation: Relation,
    contract: RelationTypeContract,
    substances: Mapping[str, Substance],
    bundle: OntologyBundle,
    seen_directionless: dict[tuple[str, frozenset[str]], int],
    index: int,
    path: Path,
) -> None:
    """Reject reversed duplicates where the authored type is directionless."""

    if contract.directional:
        return
    source_key = _selector_identity_key(relation.source_selector, substances, bundle)
    target_key = _selector_identity_key(relation.target_selector, substances, bundle)
    key = (contract.id, frozenset((source_key, target_key)))
    previous = seen_directionless.get(key)
    if previous is not None:
        raise CardLoadError(
            path,
            f"relations[{index}] uses direction for non-directional relation type {contract.id!r}; "
            f"its endpoints duplicate the unordered relation at relations[{previous}]",
        )
    seen_directionless[key] = index


def _selector_identity_key(
    selector: RelationSelector,
    substances: Mapping[str, Substance],
    bundle: OntologyBundle,
) -> str:
    return selector_identity_key(selector, substances, bundle)
