"""`plan` command: build schedule.yaml via slot-assignment search."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import NamedTuple

from planner.domain_constants import PREFER_WITH_BONUS
from planner.engine._plan_active_index import (
    ActiveIndexInput,
    build_active_index,
    resolve_prefer_pairs,
)
from planner.engine._plan_feasibility import FeasibilityIndex, build_feasibility_index
from planner.engine._plan_inputs import load_plan_inputs
from planner.engine._plan_output import ScheduleOutputInput, build_schedule_output
from planner.engine._plan_search import PlanSearchInput, run_plan_search
from planner.engine._plan_types import ActiveIndex, PlanInputs
from planner.engine.check import _cmd_check_inner
from planner.engine.results import PlanResult
from planner.ontology.artifacts import OntologyBundle, load_ontology
from planner.ontology.errors import OntologyInfrastructureError
from planner.paths import ROOT, Paths
from planner.query_model import StackReadModel, build_stack_read_model, dashboards_for_read_model
from planner.query_model.surreal import SurrealLoadContext
from planner.schedule_types import ScheduleWarning
from planner.schedule_writer import schedule_slot_loads, write_schedule_file


class _PlanRuntime(NamedTuple):
    inputs: PlanInputs
    read_model: StackReadModel
    active: ActiveIndex
    prefer_pairs: set[frozenset[str]]
    ambiguous_prefer_with_warnings: list[ScheduleWarning]
    feasibility: FeasibilityIndex


class _SuccessfulSearch(NamedTuple):
    assignment: dict[str, str]
    prefer_bonus: int


def cmd_plan(data_root: Path | None = None) -> PlanResult:
    """Build schedule.yaml via slot-assignment search; returns a PlanResult with raw warning dicts."""
    paths = Paths.from_root(data_root) if data_root is not None else Paths.default()
    try:
        bundle = load_ontology(ROOT / "ontology")
    except OntologyInfrastructureError as e:
        message = f"plan: ontology: {e}"
        print(message, file=sys.stderr)
        return _failed_plan_result(1, [message])
    return _cmd_plan_inner(paths, bundle)


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


def _cmd_plan_inner(paths: Paths, bundle: OntologyBundle) -> PlanResult:
    errors: list[str] = []
    inputs_or_failure = _checked_plan_inputs(paths, errors, bundle)
    if isinstance(inputs_or_failure, PlanResult):
        return inputs_or_failure

    runtime_or_failure = _build_plan_runtime(paths, errors, inputs_or_failure)
    if isinstance(runtime_or_failure, PlanResult):
        return runtime_or_failure
    runtime = runtime_or_failure

    search_or_failure = _run_successful_plan_search(errors, runtime)
    if isinstance(search_or_failure, PlanResult):
        return search_or_failure
    return _write_successful_plan(paths, errors, runtime, search_or_failure)


def _build_plan_runtime(paths: Paths, errors: list[str], inputs: PlanInputs) -> _PlanRuntime | PlanResult:
    read_model = build_stack_read_model(
        inputs.substances,
        inputs.global_relations,
        inputs.products,
        context=SurrealLoadContext(
            policies=inputs.policies,
            stacks_data=None,
            pillbox_stack_names=None,
            dashboards=dashboards_for_read_model(paths, inputs.ontology_bundle),
            scheduling_constraints=inputs.scheduling_constraints,
        ),
        ontology_bundle=inputs.ontology_bundle,
    )
    active = build_active_index(
        inputs.stack_entries,
        ActiveIndexInput(
            products=inputs.products,
            substances=inputs.substances,
            policies=inputs.policies,
            read_model=read_model,
            scheduling_constraints=inputs.scheduling_constraints,
        ),
        inputs.slots,
        errors,
    )
    if active is None:
        return _failed_plan_result(1, errors)

    prefer_pairs, ambiguous_prefer_with_warnings, _ = resolve_prefer_pairs(
        active.active_components, active.item_products, inputs.substances
    )
    feasibility = build_feasibility_index(inputs.slots, active, inputs.policies, errors)
    if feasibility is None:
        return _failed_plan_result(1, errors)

    return _PlanRuntime(
        inputs=inputs,
        read_model=read_model,
        active=active,
        prefer_pairs=prefer_pairs,
        ambiguous_prefer_with_warnings=ambiguous_prefer_with_warnings,
        feasibility=feasibility,
    )


def _run_successful_plan_search(errors: list[str], runtime: _PlanRuntime) -> _SuccessfulSearch | PlanResult:
    best_assignment, best_metrics = run_plan_search(
        PlanSearchInput(
            slots=runtime.inputs.slots,
            items_by_scheduling_priority=runtime.feasibility.items_by_scheduling_priority,
            item_id_sequence=runtime.feasibility.item_id_sequence,
            item_stacks=runtime.active.item_stacks,
            feasible_slots_by_item=runtime.feasibility.feasible_slots_by_item,
            remaining_score_upper_bound=runtime.feasibility.remaining_score_upper_bound,
            prefer_pairs=runtime.prefer_pairs,
            active_components=runtime.active.active_components,
            substances=runtime.inputs.substances,
            scheduling_constraints=runtime.inputs.scheduling_constraints,
        )
    )

    if best_assignment is None or best_metrics is None:
        return _failed_search_plan_result(errors, runtime.feasibility.feasible_slots_by_item)
    _final_total, _slot_score_sum, prefer_bonus, _balance_penalty = best_metrics
    return _SuccessfulSearch(assignment=best_assignment, prefer_bonus=prefer_bonus)


def _write_successful_plan(
    paths: Paths,
    errors: list[str],
    runtime: _PlanRuntime,
    search: _SuccessfulSearch,
) -> PlanResult:
    schedule, raw_warnings = build_schedule_output(
        ScheduleOutputInput(
            assignment=search.assignment,
            slots=runtime.inputs.slots,
            active=runtime.active,
            item_id_sequence=runtime.feasibility.item_id_sequence,
            products=runtime.inputs.products,
            substances=runtime.inputs.substances,
            policies=runtime.inputs.policies,
            prefer_pairs=runtime.prefer_pairs,
            stack_entries=runtime.inputs.stack_entries,
            dashboard_files=runtime.inputs.dashboard_files,
            pillboxes=runtime.inputs.pillboxes,
            warnings_prefix=runtime.ambiguous_prefer_with_warnings,
            read_model=runtime.read_model,
            candidate_traces_by_item=runtime.feasibility.candidate_traces_by_item,
            ontology_bundle=runtime.inputs.ontology_bundle,
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
            prefer_pairs_declared=len(runtime.prefer_pairs),
            prefer_pairs_together=search.prefer_bonus // PREFER_WITH_BONUS,
        )

    slot_loads = schedule_slot_loads(schedule)
    print(f"\nschedule written to {paths.schedule_file}")
    print(f"slot loads: {slot_loads}")
    print(
        f"kept_together pairs: {len(runtime.prefer_pairs)} declared, "
        f"{search.prefer_bonus // PREFER_WITH_BONUS} together"
    )
    print(f"warnings: {len(schedule['warnings'])}")
    return PlanResult(
        exit_code=0,
        schedule_written=True,
        warnings=raw_warnings,
        slot_loads=slot_loads,
        prefer_pairs_declared=len(runtime.prefer_pairs),
        prefer_pairs_together=search.prefer_bonus // PREFER_WITH_BONUS,
        errors=errors,
    )


def _checked_plan_inputs(
    paths: Paths, errors: list[str], bundle: OntologyBundle
) -> PlanInputs | PlanResult:
    print("=== running check ===")
    check_result = _cmd_check_inner(paths, bundle)
    if check_result.exit_code != 0:
        print("plan: skipped (check failed; see errors above)", file=sys.stderr)
        return _failed_plan_result(check_result.exit_code, list(check_result.errors))
    print("=== check passed; building schedule ===")

    inputs = load_plan_inputs(paths, bundle)
    if inputs is None:
        return _failed_plan_result(1, errors)
    return inputs


def _failed_search_plan_result(
    errors: list[str],
    feasible_slots_by_item: dict[str, list[tuple[str, int, list[str]]]],
) -> PlanResult:
    tight_items = [
        (item_id, [name for name, _score, _reasons in candidates])
        for item_id, candidates in sorted(feasible_slots_by_item.items())
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
