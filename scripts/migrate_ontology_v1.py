#!/usr/bin/env python3
"""One-shot, deterministic migration of legacy card facts to ontology v1.

This is deliberately an explicit migration program, not a runtime adapter.  It
refuses unknown legacy predicates/endpoints and records every term/relation
conversion in reviewed mapping files under ``ontology/migrations``.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml
from planner.yaml_io import YamlValue, load_yaml_mapping

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ONTOLOGY = ROOT / "ontology"
MIGRATIONS = ONTOLOGY / "migrations"

# These are the only non-kind interpretations from the former catch-all `is`
# namespace.  Keeping this table here and emitting it into v1-term-map makes
# the decision reviewable and prevents a label-based classifier.
IS_CATEGORIES = {
    "adaptogen": "role",
    "antioxidant": "role",
    "ergogenic": "role",
    "nootropic": "role",
    "pharmaceutical": "role",
    "electrolyte": "quality",
    "fat_soluble": "quality",
}


def load(path: Path) -> dict[str, YamlValue]:
    return load_yaml_mapping(path)


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")


def registry_terms() -> dict[str, dict[str, dict[str, YamlValue]]]:
    sources = {
        "is": DATA / "traits/classes.yaml",
        "effect": DATA / "traits/effects.yaml",
        "risk": DATA / "traits/risks.yaml",
        "pathway": DATA / "traits/pathways.yaml",
        "schedule": DATA / "traits/schedule.yaml",
    }
    result: dict[str, dict[str, dict[str, YamlValue]]] = {}
    for legacy_namespace, path in sources.items():
        source = load(path)
        if legacy_namespace == "schedule":
            for predicate, values in source.items():
                if not isinstance(values, dict):
                    raise ValueError(f"{path}: {predicate} must be a mapping")
                result[f"schedule.{predicate}"] = cast(dict[str, dict[str, YamlValue]], values)
        else:
            values = source.get(legacy_namespace)
            if not isinstance(values, dict):
                raise ValueError(f"{path}: missing {legacy_namespace}")
            result[legacy_namespace] = cast(dict[str, dict[str, YamlValue]], values)
    # Context was never a registry, but it is a closed set of authored
    # extensional facts. Derive its vocabulary from cards and dashboards.
    contexts: set[str] = set()
    for card in (DATA / "substances").glob("*.yaml"):
        knowledge = load(card).get("knowledge")
        if isinstance(knowledge, dict):
            contexts.update(_strings(knowledge.get("context")))
    for dashboard in (DATA / "dashboards").glob("*.yaml"):
        selectors = load(dashboard).get("from_traits")
        if isinstance(selectors, dict):
            contexts.update(_strings(selectors.get("context")))
    result["context"] = {
        slug: {"label": slug.replace("_", " ").title(), "description": "Curated dashboard context."}
        for slug in sorted(contexts)
    }
    return result


def category_for(legacy_namespace: str, slug: str) -> str:
    if legacy_namespace == "is":
        return IS_CATEGORIES.get(slug, "kind")
    if legacy_namespace.startswith("schedule."):
        return "schedule_rule"
    if legacy_namespace in {"effect", "risk", "pathway", "context"}:
        return legacy_namespace
    raise ValueError(f"Unknown legacy namespace: {legacy_namespace}")


def canonical_predicate(category: str, legacy_namespace: str) -> str:
    if category == "schedule_rule":
        return legacy_namespace
    return f"knowledge.{category}"


def term_map_and_vocabulary() -> dict[tuple[str, str], tuple[str, str]]:
    terms = registry_terms()
    mapping: dict[tuple[str, str], tuple[str, str]] = {}
    map_entries: list[dict[str, str]] = []
    vocabulary_terms: list[dict[str, str]] = []
    for namespace in sorted(terms):
        for slug, metadata in sorted(terms[namespace].items()):
            category = category_for(namespace, slug)
            predicate = canonical_predicate(category, namespace)
            mapping[(namespace, slug)] = (category, slug)
            map_entries.append({
                "source": f"{namespace}:{slug}",
                "target_category": category,
                "target_predicate": predicate,
                "target_slug": slug,
                "rationale": "Explicit v1 semantic placement from reviewed legacy registry.",
            })
            vocabulary_terms.append({
                "slug": slug,
                "label": _string(metadata.get("label"), slug.replace("_", " ").title()),
                "description": _string(metadata.get("description")),
                "semantic_category": category,
            })
    dump(MIGRATIONS / "v1-term-map.yaml", {"version": 1, "entries": map_entries})
    vocabulary = load(ONTOLOGY / "vocabulary.yaml")
    vocabulary["terms"] = cast(YamlValue, vocabulary_terms)
    dump(ONTOLOGY / "vocabulary.yaml", vocabulary)
    return mapping


def migrate_cards(mapping: dict[tuple[str, str], tuple[str, str]]) -> None:
    for card_path in sorted((DATA / "substances").glob("*.yaml")):
        card = load(card_path)
        old_knowledge = card.get("knowledge", {})
        if not isinstance(old_knowledge, dict):
            raise ValueError(f"{card_path}: knowledge must be a mapping")
        knowledge: dict[str, list[str]] = {}
        for namespace, slugs in old_knowledge.items():
            if namespace not in {"is", "effect", "risk", "pathway", "context"}:
                raise ValueError(f"{card_path}: unknown knowledge namespace {namespace}")
            if not isinstance(slugs, list):
                raise ValueError(f"{card_path}: {namespace} must be a list")
            for slug in slugs:
                if not isinstance(slug, str) or (namespace, slug) not in mapping:
                    raise ValueError(f"{card_path}: unmapped fact {namespace}:{slug}")
                category, mapped_slug = mapping[(namespace, slug)]
                knowledge.setdefault(category, []).append(mapped_slug)
        if knowledge:
            card["knowledge"] = cast(YamlValue, dict(sorted(knowledge.items())))
        elif "knowledge" in card:
            card["knowledge"] = {}
        dump(card_path, card)


def selector(value: str, mapping: dict[tuple[str, str], tuple[str, str]]) -> dict[str, object]:
    if ":" not in value:
        raise ValueError(f"Trait selector lacks namespace: {value}")
    namespace, slug = value.split(":", 1)
    category, mapped_slug = mapping[(namespace, slug)]
    return {"category": category, "term": mapped_slug}


def relation_selector(
    record: dict[str, YamlValue], side: str, mapping: dict[tuple[str, str], tuple[str, str]]
) -> dict[str, object]:
    candidates = [
        (f"{side}_name", "name"),
        (f"{side}_substance", "id"),
        (f"{side}_trait", "trait"),
        (f"{side}_class", "class"),
    ]
    found = [(field, form) for field, form in candidates if field in record]
    if len(found) != 1:
        raise ValueError(f"relation endpoint {side} must have exactly one legacy form: {record}")
    field, form = found[0]
    value = record[field]
    if not isinstance(value, str):
        raise ValueError(f"relation endpoint {field} must be a string")
    if form == "name":
        return {"entity": {"name": value}}
    if form == "id":
        return {"entity": {"id": value}}
    return selector(("is:" if form == "class" else "") + value, mapping)


def migrate_relations(mapping: dict[tuple[str, str], tuple[str, str]]) -> None:
    legacy = load(DATA / "relations.yaml")
    entries: list[dict[str, object]] = []
    relation_map: list[dict[str, object]] = []
    for relation_type, records in legacy.items():
        if relation_type.startswith("#"):
            continue
        if not isinstance(records, list):
            continue
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError("relation record must be mapping")
            typed_record = cast(dict[str, YamlValue], record)
            relation_id = f"rel_{relation_type}_{index + 1:03d}"
            source = relation_selector(typed_record, "source", mapping)
            target = relation_selector(typed_record, "target", mapping)
            canonical: dict[str, object] = {
                key: value for key, value in typed_record.items() if not key.startswith(("source_", "target_"))
            }
            canonical.update({
                "id": relation_id,
                "type": relation_type,
                "source_selector": source,
                "target_selector": target,
            })
            entries.append(canonical)
            relation_map.append({
                "source_record": f"{relation_type}[{index}]",
                "target_id": relation_id,
                "type": relation_type,
                "source_selector": source,
                "target_selector": target,
            })
    dump(DATA / "relations.yaml", {"relations": entries})
    dump(MIGRATIONS / "v1-relation-map.yaml", {"version": 1, "entries": relation_map})


def migrate_dashboards(mapping: dict[tuple[str, str], tuple[str, str]]) -> None:
    for path in sorted((DATA / "dashboards").glob("*.yaml")):
        dashboard = load(path)
        old = dashboard.pop("from_traits", {})
        if not isinstance(old, dict):
            raise ValueError(f"{path}: from_traits must be mapping")
        selectors: list[dict[str, object]] = []
        contexts: list[str] = []
        for namespace, slugs in sorted(old.items()):
            if not isinstance(slugs, list):
                raise ValueError(f"{path}: dashboard selector values must be lists")
            for slug in slugs:
                if not isinstance(slug, str):
                    raise ValueError(f"{path}: dashboard selector must be a string")
                category, mapped_slug = mapping[(namespace, slug)]
                selectors.append({"category": category, "term": mapped_slug})
                if category == "context":
                    contexts.append(mapped_slug)
        dashboard["id"] = path.stem
        dashboard["selectors"] = cast(YamlValue, selectors)
        if contexts:
            dashboard["declares_context"] = cast(YamlValue, contexts)
        dump(path, dashboard)


def main() -> int:
    mapping = term_map_and_vocabulary()
    migrate_cards(mapping)
    migrate_relations(mapping)
    migrate_dashboards(mapping)
    return 0


def _string(value: YamlValue | None, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _strings(value: YamlValue | None) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


if __name__ == "__main__":
    raise SystemExit(main())
