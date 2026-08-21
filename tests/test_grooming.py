"""Focused acceptance checks for the formal card-grooming contract."""

from dataclasses import replace
from types import SimpleNamespace

import planner.engine.grooming as grooming
from planner.contracts import KnowledgeAssertion, Product, ProductComponent, Relation, RelationSelector, Substance
from planner.engine import cmd_groom
from planner.ontology.artifacts import load_ontology
from planner.paths import ROOT, Paths


def test_groom_selects_one_complete_deterministic_dossier() -> None:
    first = cmd_groom()
    second = cmd_groom()

    assert first.exit_code == 0, first.stderr
    assert second.exit_code == 0, second.stderr
    assert first.work_item is not None
    assert first.work_item == second.work_item
    assert first.eligible_count >= 1
    assert first.output.count("card ") == 1
    assert first.work_item.active_unique_product_count == len(first.work_item.active_products)
    assert "use_pattern:" in first.output and "notes:" in first.output
    assert all(relation.owner_id in relation.active_endpoint_ids for relation in first.work_item.open_relations)
    assert all(first.output.count(relation.id) == 1 for relation in first.work_item.open_relations)


def test_groom_policy_is_closed_and_formal() -> None:
    policy = load_ontology(ROOT / "ontology").runtime_program.grooming_policy

    assert policy.require_active_reachable is True
    assert policy.open_research_state == "unassessed"
    assert [(row.field, row.direction) for row in policy.rank_fields] == [
        ("active_unique_product_count", "descending"),
        ("open_owned_item_count", "descending"),
        ("substance_id", "ascending"),
    ]
    assert policy.selection_count == 1
    assert policy.relation_owner_field == "substance_id"
    assert policy.relation_owner_direction == "ascending"


def test_groom_policy_rank_fields_are_executable_structural_inputs() -> None:
    policy = load_ontology(ROOT / "ontology").runtime_program.grooming_policy
    metrics_a = {"active_unique_product_count": 1, "open_owned_item_count": 9, "substance_id": "sub_a"}
    metrics_b = {"active_unique_product_count": 2, "open_owned_item_count": 1, "substance_id": "sub_b"}
    from planner.engine.grooming import _rank_key

    normal = sorted((metrics_a, metrics_b), key=lambda row: _rank_key(row, policy.rank_fields))
    toggled = tuple(reversed(policy.rank_fields))
    changed = sorted((metrics_a, metrics_b), key=lambda row: _rank_key(row, toggled))
    assert normal != changed


def _fixture(tmp_path):
    a, b = "sub_aaaaaaaaaa", "sub_bbbbbbbbbb"
    substances = {
        a: Substance(a, "Alpha", knowledge_assertions=(KnowledgeAssertion("kind", "x"),)),
        b: Substance(
            b,
            "Beta",
            knowledge_assertions=(KnowledgeAssertion("kind", "y"),),
        ),
    }
    product = Product(
        "prd_aaaaaaaaaa",
        "Active product",
        (ProductComponent(a, "label", "1 mg", "context"),),
        notes="product notes",
        use_pattern="not_every_day",
    )
    relation = Relation(
        "rel_fixture",
        "review_with",
        "lead",
        RelationSelector(entity_id=a),
        RelationSelector(entity_id=b),
        research_state="unassessed",
        sources=("stored-source",),
    )
    paths = Paths.from_root(tmp_path)
    return paths, substances, {product.id: product}, [relation], {"daily": [product.id]}, a, b


def _fixture_bundle(policy):
    bundle = load_ontology(ROOT / "ontology")
    runtime = replace(bundle.runtime_program, grooming_policy=policy)
    return SimpleNamespace(runtime_program=runtime)


def test_policy_eligibility_and_open_state_change_execution(tmp_path, monkeypatch) -> None:  # noqa: PLR0914
    paths, substances, products, relations, stacks, _a, _b = _fixture(tmp_path)
    base = load_ontology(ROOT / "ontology").runtime_program.grooming_policy
    monkeypatch.setattr(grooming, "_load_inputs", lambda _paths, _bundle: (substances, products, relations, stacks))

    selected, eligible = grooming._select_work_items(paths, _fixture_bundle(base))
    assert eligible == 1 and len(selected) == 1
    unreachable = replace(base, require_active_reachable=False)
    selected_unreachable, eligible_unreachable = grooming._select_work_items(paths, _fixture_bundle(unreachable))
    assert eligible_unreachable == 2 and len(selected_unreachable) == 1
    supported_open = replace(base, open_research_state="supported")
    selected_supported, eligible_supported = grooming._select_work_items(paths, _fixture_bundle(supported_open))
    assert eligible_supported == 0 and not selected_supported


def test_policy_selection_count_and_owner_direction_change_execution(tmp_path, monkeypatch, capsys) -> None:
    paths, substances, products, relations, stacks, a, b = _fixture(tmp_path)
    base = load_ontology(ROOT / "ontology").runtime_program.grooming_policy
    monkeypatch.setattr(grooming, "_load_inputs", lambda _paths, _bundle: (substances, products, relations, stacks))

    product = products["prd_aaaaaaaaaa"]
    products[product.id] = replace(
        product, components=(*product.components, ProductComponent(b, "peer", "2 mg", "peer context"))
    )
    two = replace(base, selection_count=2)
    selected, _ = grooming._select_work_items(paths, _fixture_bundle(two))
    assert len(selected) == 2
    grooming._render(selected, 2, 2)
    assert capsys.readouterr().out.count("card ") == 2

    descending = replace(base, relation_owner_direction="descending")
    selected_desc, _ = grooming._select_work_items(paths, _fixture_bundle(descending))
    assert selected_desc[0].open_relations[0].owner_id == b
    assert selected_desc[0].open_relations[0].active_endpoint_ids == (b, a)
    assert a != b


def test_relation_sources_render_populated_and_empty(tmp_path, monkeypatch, capsys) -> None:
    paths, substances, products, relations, stacks, _a, _b = _fixture(tmp_path)
    base = load_ontology(ROOT / "ontology").runtime_program.grooming_policy
    monkeypatch.setattr(grooming, "_load_inputs", lambda _paths, _bundle: (substances, products, relations, stacks))
    selected, _ = grooming._select_work_items(paths, _fixture_bundle(base))
    grooming._render(selected, 1, 1)
    assert "sources=stored-source" in capsys.readouterr().out
    relations[0] = replace(relations[0], sources=())
    selected_empty, _ = grooming._select_work_items(paths, _fixture_bundle(base))
    grooming._render(selected_empty, 1, 1)
    assert "sources=—" in capsys.readouterr().out
