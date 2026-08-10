"""Focused contract tests for the Wave B compiler output inventory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeGuard, cast

import pytest
import yaml
from planner.ontology.errors import OntologyInfrastructureError
from rdflib import RDF, Graph, Namespace
from scripts.ontology_compiler import compile_ontology

from tests.test_ontology_artifacts import _copy_repository_shape

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"
EXPECTED = {
    "card.schema.json",
    "dashboard.schema.json",
    "pillboxes.schema.json",
    "product.schema.json",
    "relations.schema.json",
    "schema.json",
    "stacks.schema.json",
    "ontology.ttl",
    "shapes.ttl",
    "context.json",
    "projection-map.json",
    "runtime-program.json",
    "runtime-vocabulary.yaml",
    "artifact-lock.json",
}


type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonMapping = dict[str, JsonValue]


def _is_json_value(value: object) -> TypeGuard[JsonValue]:
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, list):
        items = cast(list[object], value)
        return all(_is_json_value(item) for item in items)
    if isinstance(value, dict):
        items = cast(dict[object, object], value)
        return all(isinstance(key, str) and _is_json_value(item) for key, item in items.items())
    return False


def _is_json_mapping(value: object) -> TypeGuard[JsonMapping]:
    return isinstance(value, dict) and _is_json_value(cast(object, value))


def _is_json_list(value: object) -> TypeGuard[list[JsonValue]]:
    return isinstance(value, list) and _is_json_value(cast(object, value))


def _json_mapping(value: object) -> JsonMapping:
    assert _is_json_mapping(value), "expected a JSON object"
    return value


def _json_mapping_list(value: object) -> list[JsonMapping]:
    assert _is_json_list(value) and all(_is_json_mapping(item) for item in value), "expected a JSON object list"
    return cast(list[JsonMapping], value)


def _json_string(value: object) -> str:
    assert isinstance(value, str), "expected a JSON string"
    return value


def _json(name: str) -> JsonMapping:
    value = cast(object, json.loads((ONTOLOGY / "generated" / name).read_bytes()))
    return _json_mapping(value)


def test_compilation_is_byte_identical_and_has_exact_inventory() -> None:
    first = compile_ontology(ONTOLOGY)
    second = compile_ontology(ONTOLOGY)
    assert first == second
    assert {path.name for path in first} == EXPECTED


def test_authored_zero_effect_template_is_compiled_without_runtime_rewording(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    source_path = root / "policies.yaml"
    source = cast(dict[str, object], yaml.safe_load(source_path.read_text(encoding="utf-8")))
    presentation = cast(dict[str, object], source["schedule_presentation"])
    zero_effect = cast(dict[str, object], presentation["zero_effect"])
    zero_effect["template"] = "A source-authored neutral placement explanation."
    source_path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")

    artifacts = compile_ontology(root)
    runtime = cast(dict[str, object], yaml.safe_load(artifacts[Path("runtime-vocabulary.yaml")].decode("utf-8")))
    compiled_presentation = cast(dict[str, object], runtime["schedule_presentation"])
    compiled_zero_effect = cast(dict[str, object], compiled_presentation["zero_effect"])
    assert compiled_zero_effect == {
        "condition": "no_nonzero_effects",
        "template": "A source-authored neutral placement explanation.",
    }


def test_compiler_preserves_name_family_selector_for_future_same_name_form(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    future_form = root.parent / "data" / "substances" / "future_zinc_form.yaml"
    future_form.write_text("id: sub_zinc_future\nname: Zinc\n", encoding="utf-8")

    artifacts = compile_ontology(root)
    runtime = cast(
        dict[str, object],
        yaml.safe_load(artifacts[Path("runtime-vocabulary.yaml")].decode("utf-8")),
    )
    assertions = cast(dict[str, dict[str, object]], runtime["ontology_assertions"])
    zinc_selector = cast(dict[str, object], assertions["rel_balance_001"]["source_selector"])

    assert zinc_selector == {"entity": {"name": "Zinc"}}


def test_committed_projection_matches_schema_and_authored_policy() -> None:
    schema = _json("schema.json")
    effect_schema = _json_mapping(_json_mapping(schema["$defs"])["SchedulingPolicyEffectRecord"])
    assert "level" in cast(list[JsonValue], effect_schema["required"])
    assert "block" not in _json_mapping(effect_schema["properties"])
    rooted_schemas = {
        "card.schema.json": "SubstanceCard",
        "product.schema.json": "ProductCard",
        "relations.schema.json": "RelationAssertionCatalog",
    }
    for artifact, root_class in rooted_schemas.items():
        rooted = _json(artifact)
        assert rooted["$ref"] == f"#/$defs/{root_class}"
        assert _json_string(rooted["$id"]).endswith(f"generated/{artifact}")
    for artifact in ("dashboard.schema.json", "stacks.schema.json"):
        assert _json_string(_json(artifact)["$id"]).endswith(f"generated/{artifact}")
    projection = _json("projection-map.json")
    assert {_json_string(item["name"]) for item in _json_mapping_list(projection["classes"])} <= set(
        _json_mapping(schema["$defs"])
    )

    runtime_program = _json("runtime-program.json")
    assert runtime_program["format_version"] == "ontology-runtime-program-v1"
    assert runtime_program["schema_version"] == "2"
    assert isinstance(runtime_program["source_hash"], str) and len(runtime_program["source_hash"]) == 64
    provenance = _json_mapping(runtime_program["provenance"])
    assert provenance["source"] == "ontology/runtime-policy.yaml"
    runtime_projection = _json_mapping(runtime_program["projection"])
    assert _json_mapping_list(runtime_projection["constraint_execution_policies"])
    assert _is_json_list(runtime_projection["slot_near_values"])
    assert all(isinstance(value, str) and value for value in runtime_projection["slot_near_values"])
    assert set(runtime_program) == {"format_version", "schema_version", "source_hash", "provenance", "projection"}
    scoring = _json_mapping(runtime_projection["effect_scoring"])
    authored_policy = cast(
        dict[str, object],
        yaml.safe_load((ONTOLOGY / "runtime-policy.yaml").read_text(encoding="utf-8")),
    )
    authored_scoring = cast(dict[str, object], authored_policy["effect_scoring"])
    for key in ("prefer_with_bonus",):
        assert scoring[key] == authored_scoring[key]

    authored_constraints = cast(list[dict[str, object]], authored_policy["constraint_execution_policies"])
    runtime_constraints = cast(list[dict[str, object]], runtime_projection["constraint_execution_policies"])
    assert runtime_constraints == authored_constraints


def test_generated_constraint_schema_preserves_required_metadata_contract() -> None:
    schema = _json("schema.json")
    definition = _json_mapping(_json_mapping(schema["$defs"])["SchedulingConstraintRecord__identifier_optional"])
    required = set(cast(list[str], definition["required"]))
    properties = _json_mapping(definition["properties"])

    assert {"action", "rationale"} <= required
    assert properties["action"] == {"type": "string"}
    assert properties["rationale"] == {"type": "string"}


def test_rdf_scheduling_policy_records_emit_their_canonical_term() -> None:
    graph = Graph()
    graph.parse(data=(ONTOLOGY / "generated/ontology.ttl").read_text(encoding="utf-8"), format="turtle")
    ss = Namespace("https://j2h4u.github.io/supp-slotter/ontology/v1/")
    records = set(graph.subjects(RDF.type, ss.SchedulingPolicyRecord))
    assert records
    for record in records:
        terms = list(graph.objects(record, ss["term"]))
        assert len(terms) == 1
        policy_id = next(iter(graph.objects(record, ss.id)))
        category, slug = str(policy_id).split(":", maxsplit=1)
        assert str(terms[0]).endswith(f"term/{category}/{slug}")


def test_rdf_semantic_categories_are_typed_and_link_their_profiles() -> None:
    graph = Graph()
    graph.parse(data=(ONTOLOGY / "generated/ontology.ttl").read_text(encoding="utf-8"), format="turtle")
    ss = Namespace("https://j2h4u.github.io/supp-slotter/ontology/v1/")
    categories = set(graph.subjects(RDF.type, ss.SemanticCategory))
    profiles = set(graph.subjects(RDF.type, ss.OntoCleanProfile))
    assert categories
    assert profiles
    assert all(list(graph.objects(category, ss.ontoclean_profile)) for category in categories)
    assert all(next(iter(graph.objects(category, ss.ontoclean_profile))) in profiles for category in categories)
    terms = set(graph.subjects(RDF.type, ss.OntologyTerm))
    assert terms
    assert all(
        next(iter(graph.objects(term, ss.ontoclean_profile)))
        in set(graph.objects(next(iter(graph.objects(term, ss.semantic_category))), ss.ontoclean_profile))
        for term in terms
    )


def test_generated_pillbox_schema_projects_authored_effect_dimensions() -> None:
    """Pillbox observations come from effect-dimension projection metadata."""
    pillboxes = _json("pillboxes.schema.json")
    runtime_program = _json("runtime-program.json")
    projection = _json_mapping(runtime_program["projection"])
    dimensions = _json_mapping_list(projection["effect_match_dimensions"])
    expected_fields = {"label", "order", *(_json_string(row["slot_field"]) for row in dimensions)}

    pattern = _json_mapping(pillboxes["patternProperties"])
    pillbox = _json_mapping(pattern["^[a-z][a-z0-9_]*$"])
    slots = _json_mapping(_json_mapping(pillbox["properties"])["slots"])
    slot = _json_mapping(_json_mapping(slots["additionalProperties"]))

    assert set(cast(list[str], slot["required"])) == expected_fields
    assert set(_json_mapping(slot["properties"])) >= expected_fields


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing", "requires a terms catalog"),
        ("empty", "terms must not be empty"),
        ("blank_label", "label"),
        ("duplicate", "Duplicate ontology term"),
        ("bad_slug", "canonical namespace/slug"),
        ("category_identity", "does not match predicate suffix"),
        ("mixed_predicates", "must declare homogeneous predicates"),
    ],
)
def test_compiler_rejects_malformed_term_and_category_catalogs(tmp_path: Path, mutation: str, message: str) -> None:
    root = _copy_repository_shape(tmp_path)
    path = root / "vocabulary.yaml"
    source = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    terms = cast(list[dict[str, object]], source["terms"])
    categories = cast(dict[str, dict[str, object]], source["semantic_categories"])
    if mutation == "missing":
        source.pop("terms")
    elif mutation == "empty":
        source["terms"] = []
    elif mutation == "blank_label":
        terms[0]["label"] = "  "
    elif mutation == "duplicate":
        terms.append(dict(terms[0]))
    elif mutation == "bad_slug":
        terms[0]["slug"] = "BadSlug"
    elif mutation == "category_identity":
        categories["kind"]["allowed_predicates"] = ["knowledge.role"]
    elif mutation == "mixed_predicates":
        categories["kind"]["allowed_predicates"] = ["knowledge.kind", "schedule.kind"]
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")

    with pytest.raises(OntologyInfrastructureError, match=message):
        compile_ontology(root)


@pytest.mark.parametrize(
    "section",
    [
        "source_kind_values",
        "effect_match_dimensions",
        "assignment_axes",
        "constraint_execution_policies",
        "warning_types",
        "warning_emitters",
        "warning_trait_actions",
        "concern_catalog",
        "relation_warning_rules",
        "relation_presence_statuses",
        "selector_form_capabilities",
    ],
)
def test_compiler_rejects_runtime_semantic_collision_with_distinct_id(tmp_path: Path, section: str) -> None:
    root = _copy_repository_shape(tmp_path)
    path = root / "runtime-policy.yaml"
    source = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    rows = cast(list[dict[str, object]], source[section])
    rows.append({**rows[0], "id": f"{rows[0]['id']}_collision"})
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")

    with pytest.raises(OntologyInfrastructureError, match="duplicate semantic key"):
        compile_ontology(root)


@pytest.mark.parametrize("value", ["false", "true", 0, 1, None])
def test_compiler_rejects_non_boolean_runtime_presence_truth_values(tmp_path: Path, value: object) -> None:
    root = _copy_repository_shape(tmp_path)
    path = root / "runtime-policy.yaml"
    source = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    glue = cast(dict[str, object], source["glue_contract"])
    truth = cast(list[dict[str, object]], glue["relation_presence_truth_table"])
    truth[0]["source_active"] = value
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")

    with pytest.raises(OntologyInfrastructureError, match=r"strict booleans|boolean"):
        compile_ontology(root)


def test_compiler_rejects_incomplete_runtime_presence_statuses(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    path = root / "runtime-policy.yaml"
    source = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    statuses = cast(list[dict[str, object]], source["relation_presence_statuses"])
    statuses.pop()
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")

    with pytest.raises(OntologyInfrastructureError, match="exact unique four-state coverage"):
        compile_ontology(root)


def test_compiler_rejects_unsupported_relation_endpoint_selector_kind(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    path = root / "runtime-policy.yaml"
    source = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    endpoints = cast(list[dict[str, object]], source["selector_form_capabilities"])
    endpoints[0]["endpoint_kind"] = "category"
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")

    with pytest.raises(OntologyInfrastructureError, match="endpoint kinds"):
        compile_ontology(root)


def test_compiler_rejects_unsupported_selector_form(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    path = root / "runtime-policy.yaml"
    source = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    capabilities = cast(list[dict[str, object]], source["selector_form_capabilities"])
    capabilities[0]["selector_form"] = "category"
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")

    with pytest.raises(OntologyInfrastructureError, match="selector forms"):
        compile_ontology(root)


@pytest.mark.parametrize("capability_field", ["relation_warning_filter_fields", "warning_emitter_ids"])
def test_compiler_requires_exact_executable_capability_parity(tmp_path: Path, capability_field: str) -> None:
    root = _copy_repository_shape(tmp_path)
    path = root / "runtime-policy.yaml"
    source = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    glue = cast(dict[str, object], source["glue_contract"])
    values = cast(list[object], glue[capability_field])
    values.pop()
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")

    with pytest.raises(OntologyInfrastructureError, match=f"glue_contract {capability_field}"):
        compile_ontology(root)


def test_generated_runtime_vocabulary_proves_canonical_term_reachability() -> None:
    vocabulary = cast(
        dict[str, object],
        yaml.safe_load((ONTOLOGY / "generated/runtime-vocabulary.yaml").read_text(encoding="utf-8")),
    )
    categories = cast(dict[str, dict[str, object]], vocabulary["categories"])
    terms = cast(list[dict[str, object]], vocabulary["terms"])
    assert terms
    keys: set[tuple[str, str]] = set()
    for term in terms:
        category = cast(str, term["semantic_category"])
        slug = cast(str, term["slug"])
        assert (category, slug) not in keys
        keys.add((category, slug))
        predicates = cast(list[str], term["allowed_predicates"])
        category_predicates = cast(list[str], categories[category]["allowed_predicates"])
        assert predicates == category_predicates
        assert all(predicate.rsplit(".", maxsplit=1)[-1] == category for predicate in predicates)
