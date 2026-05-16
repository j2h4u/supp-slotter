"""`plan` command: build schedule.yaml via slot-assignment search."""

from __future__ import annotations

import sys
from pathlib import Path

from planner.cards.relations_surreal import (
    build_surreal_db,
    dashboards_for_surreal,
    relation_substance_pairs,
)
from planner.engine._plan_inputs import (
    build_active_index,
    load_plan_inputs,
    resolve_prefer_pairs,
)
from planner.engine._plan_output import build_schedule_output
from planner.engine._plan_search import build_feasibility_index, run_plan_search
from planner.engine._root_patch import maybe_patch_root
from planner.engine.check import cmd_check
from planner.engine.results import PlanResult
from planner.io import (
    DATA_DIR,
    PREFER_WITH_BONUS,
    SCHEDULE_PATH,
    dump_schedule_yaml,
)


def cmd_plan(data_root: Path | None = None) -> PlanResult:
    """Build schedule.yaml via slot-assignment search; returns a PlanResult with raw warning dicts."""
    with maybe_patch_root(data_root):
        return _cmd_plan_inner()


def _cmd_plan_inner() -> PlanResult:
    errors: list[str] = []
    print("=== running check ===")
    check_result = cmd_check()
    if check_result.exit_code != 0:
        print("plan: skipped (check failed; see errors above)", file=sys.stderr)
        return PlanResult(
            exit_code=check_result.exit_code,
            schedule_written=False,
            warnings=[],
            slot_loads={},
            prefer_pairs_declared=0,
            prefer_pairs_together=0,
            errors=list(check_result.errors),
        )
    print("=== check passed; building schedule ===")

    inputs = load_plan_inputs(DATA_DIR)
    if inputs is None:
        return PlanResult(
            exit_code=1,
            schedule_written=False,
            warnings=[],
            slot_loads={},
            prefer_pairs_declared=0,
            prefer_pairs_together=0,
            errors=errors,
        )
    slots = inputs.slots
    substances = inputs.substances
    products = inputs.products
    trait_defs = inputs.trait_defs

    db = build_surreal_db(
        inputs.substances, inputs.global_relations, inputs.products,
        trait_defs=inputs.trait_defs,
        dashboards=dashboards_for_surreal(),
    )
    competes_pairs = relation_substance_pairs(db, "competes")

    active = build_active_index(
        inputs.stack_entries, inputs.products, inputs.substances,
        inputs.trait_defs, inputs.global_relations, inputs.slots,
        errors=errors,
        db=db,
    )
    if active is None:
        return PlanResult(
            exit_code=1,
            schedule_written=False,
            warnings=[],
            slot_loads={},
            prefer_pairs_declared=0,
            prefer_pairs_together=0,
            errors=errors,
        )

    prefer_pairs, ambiguous_prefer_with_warnings, substance_to_active_items = (
        resolve_prefer_pairs(active.active_components, active.item_products, substances)
    )

    feasibility = build_feasibility_index(slots, active, trait_defs, errors)
    if feasibility is None:
        return PlanResult(
            exit_code=1,
            schedule_written=False,
            warnings=[],
            slot_loads={},
            prefer_pairs_declared=0,
            prefer_pairs_together=0,
            errors=errors,
        )

    best_assignment, best_metrics = run_plan_search(
        slots=slots,
        items_by_scheduling_priority=feasibility.items_by_scheduling_priority,
        item_id_sequence=feasibility.item_id_sequence,
        item_traits=active.item_traits,
        item_stacks=active.item_stacks,
        feasible_slots_by_item=feasibility.feasible_slots_by_item,
        slot_score_lookup=feasibility.slot_score_lookup,
        remaining_score_upper_bound=feasibility.remaining_score_upper_bound,
        prefer_pairs=prefer_pairs,
        active_components=active.active_components,
        substances=substances,
        trait_defs=trait_defs,
        global_relations=inputs.global_relations,
        competes_pairs=competes_pairs,
    )

    if best_assignment is None or best_metrics is None:
        tight_items = [
            (item_id, [name for name, _score, _reasons in candidates])
            for item_id, candidates in sorted(feasibility.feasible_slots_by_item.items())
            if len(candidates) <= 1
        ]
        if tight_items:
            header = "plan: items with ≤1 feasible slot (likely cause):"
            print(header, file=sys.stderr)
            errors.append(header)
            for item_id, slot_names in tight_items:
                slot_list = ", ".join(slot_names) if slot_names else "(none)"
                line = f"  - {item_id}: {slot_list}"
                print(line, file=sys.stderr)
                errors.append(line)
        no_assign_msg = "plan: no valid global assignment under slot conflict constraints."
        print(no_assign_msg, file=sys.stderr)
        errors.append(no_assign_msg)
        return PlanResult(
            exit_code=1,
            schedule_written=False,
            warnings=[],
            slot_loads={},
            prefer_pairs_declared=0,
            prefer_pairs_together=0,
            errors=errors,
        )

    assignment = best_assignment
    _final_total, _slot_score_sum, prefer_bonus, _balance_penalty = best_metrics

    schedule, raw_warnings = build_schedule_output(
        assignment=assignment,
        best_metrics=best_metrics,
        slots=slots,
        active=active,
        item_id_sequence=feasibility.item_id_sequence,
        products=products,
        substances=substances,
        relations=inputs.global_relations,
        trait_defs=trait_defs,
        prefer_pairs=prefer_pairs,
        substance_to_active_items=substance_to_active_items,
        stack_entries=inputs.stack_entries,
        dashboard_files=inputs.dashboard_files,
        pillboxes=inputs.pillboxes,
        warnings_prefix=ambiguous_prefer_with_warnings,
        db=db,
    )

    schedule_written = False
    try:
        SCHEDULE_PATH.write_text(dump_schedule_yaml(schedule))
        schedule_written = True
    except OSError as e:
        msg = f"plan: failed to write {SCHEDULE_PATH}: {e}"
        print(msg, file=sys.stderr)
        errors.append(msg)
        return PlanResult(
            exit_code=1,
            schedule_written=False,
            warnings=raw_warnings,
            slot_loads={},
            prefer_pairs_declared=len(prefer_pairs),
            prefer_pairs_together=prefer_bonus // PREFER_WITH_BONUS,
            errors=errors,
        )

    slot_loads = {
        f"{pillbox_name}.{slot_name}": len(slot_entry["products"])
        for pillbox_name, pillbox in schedule["pillboxes"].items()
        for slot_name, slot_entry in pillbox["slots"].items()
    }
    print(f"\nschedule written to {SCHEDULE_PATH}")
    print(f"slot loads: {slot_loads}")
    print(
        f"kept_together pairs: {len(prefer_pairs)} declared, "
        f"{prefer_bonus // PREFER_WITH_BONUS} together"
    )
    print(f"warnings: {len(schedule['warnings'])}")
    return PlanResult(
        exit_code=0,
        schedule_written=schedule_written,
        warnings=raw_warnings,
        slot_loads=slot_loads,
        prefer_pairs_declared=len(prefer_pairs),
        prefer_pairs_together=prefer_bonus // PREFER_WITH_BONUS,
        errors=errors,
    )
