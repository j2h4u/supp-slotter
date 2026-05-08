"""Cards subpackage: re-exports for back-compat with the previous monolithic cards.py."""

from planner.cards._common import (
    connected_components,
    generate_stable_id,
    load_card,
    normalize_filename_part,
    normalize_similarity_text,
    similarity_score,
)
from planner.cards.search import (
    collect_search_strings,
    combined_search_score,
    format_find_result,
    search_score,
    search_words,
    word_match_score,
)
from planner.cards.pillboxes import (
    build_empty_schedule_pillboxes,
    check_pillbox_slot_ids,
    derive_slot_fields,
    flatten_pillbox_slots,
)
from planner.cards.traits import (
    check_traits,
    flatten_trait_defs,
    format_trait_effect,
    grouped_trait_defs,
    print_trait_details,
    readable_traits,
)
from planner.cards.stacks import (
    check_stack_alignment,
    check_stack_duplicate_items,
    normalize_stack_entries,
    validate_stacks,
)
from planner.cards.substance import (
    canonical_substance_filename,
    check_substances,
    collect_active_substance_names,
    collect_similar_substances,
    find_substance_results,
    format_substance_candidate,
    format_substance_name,
    load_substance,
    load_substance_registry,
    substance_cluster_label,
    substance_display_name,
    substance_is_covered_by_active_name,
    substance_name_key,
    substance_names,
    substance_similarity_terms,
    substance_slug,
)
from planner.cards.product import (
    canonical_product_filename,
    check_product_formulas,
    collect_product_substance_refs,
    find_product_results,
    format_item_product_name,
    format_product_name,
    load_product,
    load_product_registry,
    product_brand_slug,
    product_component_substances,
    product_name_slug,
)
from planner.cards.relations import (
    check_global_relations,
    collect_intra_product_relation_conflicts,
    collect_missing_balance_relations,
    collect_missing_support_relations,
    collect_substance_relation_matches,
    component_sets_have_relation,
    components_have_global_relation,
    format_relation_warning,
    global_relation_matches,
    global_relation_refs,
    load_global_relations,
    print_central_relation_matches,
    relation_endpoint_display,
    relation_endpoint_is_active,
    relation_endpoint_match_label,
    relation_endpoint_value,
    substance_matches_relation_endpoint,
)
from planner.cards.dashboards import (
    build_dashboard_review,
    check_dashboards,
    collect_dashboard_substance_refs,
)
from planner.cards.warnings import (
    build_review_contexts,
    collect_active_unmatched_concerns,
    humanize_warning,
    is_generic_manual_review_warning,
    review_context_key,
    warning_action,
    warning_subject,
)
from planner.cards.schedule import (
    build_action_points,
    build_placement_notes,
    build_schedule_summary,
)
