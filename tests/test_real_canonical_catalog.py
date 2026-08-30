"""Real-catalog loading and canonical pressure inference smoke tests."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from planner.cards.product import load_product_registry
from planner.cards.substance import load_substance_registry
from planner.ontology.artifacts import load_ontology
from planner.ontology.canonical_facts import composition_roles_for_products, validate_canonical_fact_catalog
from planner.ontology.canonical_inference import Conflict, execute_canonical_inference
from planner.ontology.runtime_program import RuntimeFoodEffect, RuntimePreExercisePerformanceEffect
from planner.paths import Paths

ROOT = Path(__file__).resolve().parents[1]


def _real_catalog():
    bundle = load_ontology(ROOT / "ontology")
    paths = Paths.from_root(ROOT)
    substances = load_substance_registry(paths, bundle)
    products = load_product_registry(paths, bundle)
    catalog = bundle.runtime_program.canonical_fact_catalog
    validate_canonical_fact_catalog(catalog, substances, products)
    return bundle, catalog, products


def test_real_catalog_loads_six_admitted_facts_with_exact_references() -> None:
    _, catalog, products = _real_catalog()

    assert {role.id for role in composition_roles_for_products(products)} >= {
        "cmp_prd_eb6337a6dc__sub_2476bf9d4b",
        "cmp_prd_bb212cffc2__sub_67fc2be8aa",
        "cmp_prd_htuhz2s2gt__sub_sunkcr05vl",
        "cmp_prd_cfce0b36b6__sub_3918fe347e",
        "cmp_prd_io1peb9syp__sub_85w45nbob4",
        "cmp_prd_io1peb9syp__sub_iu7b8h87g2",
    }
    assert {source.id for source in catalog.evidence_sources} == {
        "src_pubmed_25441954",
        "src_pubmed_20200983",
        "src_doi_10_1002_jps_2600550305",
        "src_doi_10_1002_jps_2600560112",
        "src_solgar_triple_strength_omega3",
        "src_pubmed_2847723",
        "src_pubmed_30799231",
        "src_pubmed_17953788",
        "src_pubmed_39662304",
        "src_pmc_13304508",
        "src_card_sub_85w45nbob4_notes",
        "src_card_sub_iu7b8h87g2_notes",
    }
    facts = (*catalog.food_effects, *catalog.pre_exercise_performance_effects)
    assert {fact.id for fact in facts} == {
        "fact_food_prd_eb6337a6dc_sub_2476bf9d4b",
        "fact_food_prd_bb212cffc2_sub_67fc2be8aa",
        "fact_food_prd_htuhz2s2gt_sub_sunkcr05vl",
        "fact_food_prd_io1peb9syp_sub_85w45nbob4",
        "fact_food_prd_io1peb9syp_sub_iu7b8h87g2",
        "fact_pre_exercise_performance_prd_cfce0b36b6_sub_3918fe347e",
    }
    assert len(catalog.food_effects) == 5
    assert len(catalog.pre_exercise_performance_effects) == 1
    assert catalog.acute_alertness_effects == ()
    assert catalog.acute_sleep_effects == ()
    assert catalog.post_exercise_recovery_effects == ()

    food_by_id = {fact.id: fact for fact in catalog.food_effects}
    expected_food = {
        "fact_food_prd_eb6337a6dc_sub_2476bf9d4b": (
            "sub_2476bf9d4b",
            "cmp_prd_eb6337a6dc__sub_2476bf9d4b",
            {
                ("src_pubmed_25441954", "https://pubmed.ncbi.nlm.nih.gov/25441954/"),
                ("src_pubmed_20200983", "https://pubmed.ncbi.nlm.nih.gov/20200983/"),
            },
        ),
        "fact_food_prd_bb212cffc2_sub_67fc2be8aa": (
            "sub_67fc2be8aa",
            "cmp_prd_bb212cffc2__sub_67fc2be8aa",
            {
                ("src_doi_10_1002_jps_2600550305", "https://doi.org/10.1002/jps.2600550305"),
                ("src_doi_10_1002_jps_2600560112", "https://doi.org/10.1002/jps.2600560112"),
            },
        ),
        "fact_food_prd_htuhz2s2gt_sub_sunkcr05vl": (
            "cmp_prd_htuhz2s2gt__sub_sunkcr05vl",
            "cmp_prd_htuhz2s2gt__sub_sunkcr05vl",
            {
                (
                    "src_solgar_triple_strength_omega3",
                    "https://www.solgar.com/products/solgar-triple-strength-omega-3-950-mg-softgels",
                ),
                ("src_pubmed_2847723", "https://pubmed.ncbi.nlm.nih.gov/2847723/"),
                ("src_pubmed_30799231", "https://pubmed.ncbi.nlm.nih.gov/30799231/"),
            },
        ),
    }
    for fact_id, (subject_id, _applicability, provenance) in expected_food.items():
        fact = food_by_id[fact_id]
        assert isinstance(fact, RuntimeFoodEffect)
        if fact_id == "fact_food_prd_htuhz2s2gt_sub_sunkcr05vl":
            assert fact.subject.substance is None
            assert fact.subject.composition_role == subject_id
        else:
            assert fact.subject.substance == subject_id
            assert fact.subject.composition_role is None
        assert fact.applicability.target_id == subject_id
        assert fact.applicability.target_kind == (
            "composition_role" if fact_id == "fact_food_prd_htuhz2s2gt_sub_sunkcr05vl" else "substance"
        )
        assert {(row.source, row.locator) for row in fact.provenance} == provenance
        assert all(row.quotation is None for row in fact.provenance)
        assert fact.value == "bioavailability_increases"

    expected_quoted_food = {
        "fact_food_prd_io1peb9syp_sub_85w45nbob4": (
            "sub_85w45nbob4",
            "cmp_prd_io1peb9syp__sub_85w45nbob4",
            "src_card_sub_85w45nbob4_notes",
            "data/substances/l_glutamine__sub_85w45nbob4.yaml#/notes",
            "Empty stomach preferred for systemic absorption away from food amino-acid competition.",
            "5d278171dddbd56fd61561d5bfc1b641bbef696fa152340b25fc71344cd5f81f",
        ),
        "fact_food_prd_io1peb9syp_sub_iu7b8h87g2": (
            "sub_iu7b8h87g2",
            "cmp_prd_io1peb9syp__sub_iu7b8h87g2",
            "src_card_sub_iu7b8h87g2_notes",
            "data/substances/alpha_lipoic_acid__sub_iu7b8h87g2.yaml#/notes",
            "food may reduce absorption.",
            "2dfc3b0b2c1fc3eb77961a671deeeaf2207dab435de913346e83d89151658f64",
        ),
    }
    for fact_id, (subject, _applicability, source, locator, quotation, quotation_hash) in expected_quoted_food.items():
        fact = food_by_id[fact_id]
        assert fact.subject.substance == subject
        assert fact.subject.composition_role is None
        assert fact.applicability.target_id == subject
        assert fact.applicability.target_kind == "substance"
        assert len(fact.provenance) == 1
        provenance = fact.provenance[0]
        assert (provenance.source, provenance.locator, provenance.quotation) == (source, locator, quotation)
        assert sha256(quotation.encode()).hexdigest() == quotation_hash
        assert fact.value == "bioavailability_decreases"

    citrulline = catalog.pre_exercise_performance_effects[0]
    assert isinstance(citrulline, RuntimePreExercisePerformanceEffect)
    assert citrulline.subject.substance is None
    assert citrulline.subject.composition_role == "cmp_prd_cfce0b36b6__sub_3918fe347e"
    assert citrulline.applicability.target_kind == "composition_role"
    assert citrulline.applicability.target_id == "cmp_prd_cfce0b36b6__sub_3918fe347e"
    assert {(row.source, row.locator) for row in citrulline.provenance} == {
        ("src_pubmed_17953788", "https://pubmed.ncbi.nlm.nih.gov/17953788/"),
        ("src_pubmed_39662304", "https://pubmed.ncbi.nlm.nih.gov/39662304/"),
        ("src_pmc_13304508", "https://pmc.ncbi.nlm.nih.gov/articles/PMC13304508/"),
    }
    assert all(row.quotation is None for row in citrulline.provenance)
    assert citrulline.value == "performance_improves"

    rejected_substances = {
        "sub_249199f726",  # astaxanthin
        "sub_vcnaasc800",  # sodium ascorbate
        "sub_646e568f61",  # krill oil
        "sub_9c0908e7f7",  # creatine
    }
    assert all(
        fact.subject.substance not in rejected_substances for fact in facts if fact.subject.substance is not None
    )


def test_real_catalog_reports_conflicting_product_level_pressures_without_placement_assertions() -> None:
    bundle, catalog, products = _real_catalog()

    result = execute_canonical_inference(
        catalog,
        {
            "item_d3": "prd_eb6337a6dc",
            "item_b2": "prd_bb212cffc2",
            "item_fish_oil": "prd_htuhz2s2gt",
            "item_citrulline": "prd_cfce0b36b6",
            "item_opti_men": "prd_io1peb9syp",
            "item_creatine": "prd_2ca842627a",
        },
        bundle.runtime_program.canonical_laws,
        composition_roles=composition_roles_for_products(products),
    )

    assert isinstance(result, Conflict)
    assert {(conflict.item_id, conflict.dimension, conflict.values) for conflict in result.conflicts} == {
        ("item_opti_men", "meal_context", ("with_food", "without_food")),
    }
    assert all(
        derivation.path.product_id != "prd_2ca842627a"
        for conflict in result.conflicts
        for derivation in conflict.derivations
    )
