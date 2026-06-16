"""`plan` command: build schedule.yaml via slot-assignment search."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

from planner.domain_constants import PREFER_WITH_BONUS
from planner.engine._plan_active_index import (
    build_active_index,
    resolve_prefer_pairs,
)
from planner.engine._plan_feasibility import build_feasibility_index
from planner.engine._plan_inputs import load_plan_inputs
from planner.engine._plan_output import ScheduleOutputInput, build_schedule_output
from planner.engine._plan_search import PlanSearchInput, run_plan_search
from planner.engine._types import ScheduleWarning
from planner.engine.check import cmd_check
from planner.engine.results import PlanResult
from planner.paths import Paths
from planner.query_model import build_stack_read_model, dashboards_for_read_model
from planner.schedule_writer import schedule_slot_loads, write_schedule_file


def cmd_plan(data_root: Path | None = None) -> PlanResult:
    """Build schedule.yaml via slot-assignment search; returns a PlanResult with raw warning dicts."""
    paths = Paths.from_root(data_root) if data_root is not None else Paths.default()
    return _cmd_plan_inner(paths)


def _failed_plan_result(
    exit_code: int,
    errors: list[str],
    *,
    warnings: list[ScheduleWarning] | None = None,
    prefer_pairs_declared: int = 0,
    prefer_pairs_together: int = 0,
) -> PlanResult:
    return PlanResult(
        exit_code=exit_code,
        schedule_written=False,
        warnings=warnings or [],
        slot_loads={},
        prefer_pairs_declared=prefer_pairs_declared,
        prefer_pairs_together=prefer_pairs_together,
        errors=errors,
    )


def _cmd_plan_inner(paths: Paths) -> PlanResult:
    errors: list[str] = []
    print("=== running check ===")
    check_result = cmd_check(data_root=paths.root)
    if check_result.exit_code != 0:
        print("plan: skipped (check failed; see errors above)", file=sys.stderr)
        return _failed_plan_result(check_result.exit_code, list(check_result.errors))
    print("=== check passed; building schedule ===")

    inputs = load_plan_inputs(paths)
    if inputs is None:
        return _failed_plan_result(1, errors)
    slots = inputs.slots
    substances = inputs.substances
    products = inputs.products
    trait_defs = inputs.trait_defs

    read_model = build_stack_read_model(
        inputs.substances,
        inputs.global_relations,
        inputs.products,
        trait_defs=inputs.trait_defs,
        dashboards=dashboards_for_read_model(paths),
    )
    competes_pairs = read_model.relation_substance_pairs("competes")

    active = build_active_index(
        inputs.stack_entries,
        inputs.products,
        inputs.substances,
        inputs.trait_defs,
        inputs.slots,
        errors=errors,
        read_model=read_model,
    )
    if active is None:
        return _failed_plan_result(1, errors)

    prefer_pairs, ambiguous_prefer_with_warnings, _ = resolve_prefer_pairs(
        active.active_components, active.item_products, substances
    )

    feasibility = build_feasibility_index(slots, active, trait_defs, errors)
    if feasibility is None:
        return _failed_plan_result(1, errors)

    best_assignment, best_metrics = run_plan_search(
        PlanSearchInput(
            slots=slots,
            items_by_scheduling_priority=feasibility.items_by_scheduling_priority,
            item_id_sequence=feasibility.item_id_sequence,
            item_traits=active.item_traits,
            item_stacks=active.item_stacks,
            feasible_slots_by_item=feasibility.feasible_slots_by_item,
            remaining_score_upper_bound=feasibility.remaining_score_upper_bound,
            prefer_pairs=prefer_pairs,
            active_components=active.active_components,
            substances=substances,
            global_relations=inputs.global_relations,
            competes_pairs=competes_pairs,
        )
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
        return _failed_plan_result(1, errors)

    assignment = best_assignment
    _final_total, _slot_score_sum, prefer_bonus, _balance_penalty = best_metrics

    schedule, raw_warnings = build_schedule_output(
        ScheduleOutputInput(
            assignment=assignment,
            slots=slots,
            active=active,
            item_id_sequence=feasibility.item_id_sequence,
            products=products,
            substances=substances,
            trait_defs=trait_defs,
            prefer_pairs=prefer_pairs,
            stack_entries=inputs.stack_entries,
            dashboard_files=inputs.dashboard_files,
            pillboxes=inputs.pillboxes,
            warnings_prefix=cast(list[ScheduleWarning], ambiguous_prefer_with_warnings),
            read_model=read_model,
        )
    )

    try:
        write_schedule_file(paths.schedule_file, schedule)
    except OSError as e:
        msg = f"plan: failed to write {paths.schedule_file}: {e}"
        print(msg, file=sys.stderr)
        errors.append(msg)
        return _failed_plan_result(
            1,
            errors,
            warnings=raw_warnings,
            prefer_pairs_declared=len(prefer_pairs),
            prefer_pairs_together=prefer_bonus // PREFER_WITH_BONUS,
        )

    slot_loads = schedule_slot_loads(schedule)
    print(f"\nschedule written to {paths.schedule_file}")
    print(f"slot loads: {slot_loads}")
    print(f"kept_together pairs: {len(prefer_pairs)} declared, {prefer_bonus // PREFER_WITH_BONUS} together")
    print(f"warnings: {len(schedule['warnings'])}")
    return PlanResult(
        exit_code=0,
        schedule_written=True,
        warnings=raw_warnings,
        slot_loads=slot_loads,
        prefer_pairs_declared=len(prefer_pairs),
        prefer_pairs_together=prefer_bonus // PREFER_WITH_BONUS,
        errors=errors,
    )
