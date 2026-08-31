"""Canonical ``plan`` command: prove a layout, then publish it."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import NamedTuple

from planner.canonical_optimizer import Indeterminate
from planner.canonical_optimizer_result import Diagnostic, DiagnosticCode
from planner.engine._plan_active_index import ActiveIndexInput, build_active_index
from planner.engine._plan_inputs import load_plan_inputs
from planner.engine._plan_types import ActiveIndex, PlanInputs
from planner.engine.check import _cmd_check_inner
from planner.engine.results import PlanResult
from planner.ontology.artifacts import OntologyBundle, load_ontology
from planner.ontology.canonical_inference import Conflict, SameDimensionPressureConflict, Success
from planner.ontology.errors import OntologyInfrastructureError
from planner.paths import ROOT, Paths
from planner.schedule_types import CanonicalPublicationSource
from planner.schedule_writer import invalidate_schedule_file, schedule_slot_loads, write_schedule_file


class _PlanRuntime(NamedTuple):
    inputs: PlanInputs
    active: ActiveIndex


def cmd_plan(data_root: Path | None = None) -> PlanResult:
    """Build and atomically publish a proved canonical schedule."""
    paths = Paths.from_root(data_root) if data_root is not None else Paths.default()
    try:
        invalidate_schedule_file(paths.schedule_file)
        bundle = load_ontology(ROOT / "ontology")
        return _cmd_plan_inner(paths, bundle)
    except (KeyboardInterrupt, MemoryError) as error:
        return _boundary_failure(error)
    except OntologyInfrastructureError as error:
        message = f"plan: ontology: {error}"
        print(message, file=sys.stderr)
        return _failed_plan_result(1, [message], Diagnostic("infrastructure_failed", message))
    except Exception as error:  # noqa: BLE001
        message = f"plan: failed closed: {error}"
        print(message, file=sys.stderr)
        return _failed_plan_result(1, [message], Diagnostic("infrastructure_failed", message))


def _boundary_failure(error: KeyboardInterrupt | MemoryError) -> PlanResult:
    code: DiagnosticCode = "interrupted" if isinstance(error, KeyboardInterrupt) else "resource_exhausted"
    message = "plan: interrupted" if code == "interrupted" else "plan: resource exhausted"
    print(message, file=sys.stderr)
    return _failed_plan_result(1, [message], Diagnostic(code, message))


def _failed_plan_result(exit_code: int, errors: list[str], diagnostic: Diagnostic | None = None) -> PlanResult:
    return PlanResult(
        exit_code=exit_code,
        schedule_written=False,
        slot_loads={},
        errors=errors,
        diagnostic=diagnostic,
    )


def _cmd_plan_inner(paths: Paths, bundle: OntologyBundle) -> PlanResult:
    errors: list[str] = []
    inputs_or_failure = _checked_plan_inputs(paths, errors, bundle)
    if isinstance(inputs_or_failure, PlanResult):
        return inputs_or_failure
    runtime_or_failure = _build_plan_runtime(paths, errors, inputs_or_failure)
    if isinstance(runtime_or_failure, PlanResult):
        return runtime_or_failure
    return _publish_plan(paths, errors, runtime_or_failure)


def _build_plan_runtime(paths: Paths, errors: list[str], inputs: PlanInputs) -> _PlanRuntime | PlanResult:
    """Build only the canonical active index; legacy scheduler state is absent."""
    del paths
    try:
        active = build_active_index(
            inputs.stack_entries,
            ActiveIndexInput(
                runtime_program=inputs.runtime_program,
                products=inputs.products,
                substances=inputs.substances,
            ),
        )
    except KeyboardInterrupt, MemoryError:
        raise
    except Exception as error:  # noqa: BLE001
        message = f"plan: canonical input failed closed: {error}"
        print(message, file=sys.stderr)
        errors.append(message)
        return _failed_plan_result(1, errors, Diagnostic("invalid_input", message))
    if isinstance(active.canonical_inference, Conflict):
        errors.extend(
            _canonical_inference_conflict_diagnostic(conflict)
            for conflict in sorted(
                active.canonical_inference.conflicts,
                key=lambda item: (item.item_id, item.dimension, item.values),
            )
        )
        return _failed_plan_result(
            1,
            errors,
            Diagnostic("contradiction", "canonical inference found contradictory pressure facts"),
        )
    return _PlanRuntime(inputs=inputs, active=active)


def _canonical_inference_conflict_diagnostic(conflict: SameDimensionPressureConflict) -> str:
    """Render one stable diagnostic for a same-axis canonical conflict."""
    values = ",".join(sorted(str(value) for value in conflict.values))
    return (
        f"plan: canonical_inference_conflict item_id={str(conflict.item_id)!r} "
        f"dimension={str(conflict.dimension)!r} values=({values})"
    )


def _publish_plan(
    paths: Paths,
    errors: list[str],
    runtime: _PlanRuntime,
) -> PlanResult:
    """Freeze answer-free facts and hand them to the solver-owned writer."""
    inference = runtime.active.canonical_inference
    if not isinstance(inference, Success):
        message = "plan: canonical publication requires successful inference"
        errors.append(message)
        return _failed_plan_result(1, errors, Diagnostic("proof_failed", message))
    try:
        source = CanonicalPublicationSource(
            item_products=runtime.active.item_products,
            item_domains=runtime.active.item_stacks,
            slots={
                slot_id: slot
                for slot_id, slot in runtime.inputs.slots.items()
                if slot.stack in set(runtime.active.item_stacks.values())
            },
            inference=inference,
            products=runtime.inputs.products,
            pressure_values_by_dimension=runtime.inputs.runtime_program.canonical_scheduling.pressure_values_by_dimension,
            pressure_satisfaction_strategy=(
                runtime.inputs.runtime_program.engine_contract.pressure_satisfaction_strategy
            ),
        )
        published = write_schedule_file(paths.schedule_file, source)
        if isinstance(published, Indeterminate):
            errors.append(f"plan: {published.diagnostic.message}")
            return _failed_plan_result(1, errors, published.diagnostic)
        slot_loads = schedule_slot_loads(published.document)
        return PlanResult(
            exit_code=0,
            schedule_written=True,
            slot_loads=slot_loads,
            schedule=published.document,
        )
    except KeyboardInterrupt, MemoryError:
        raise
    except Exception as error:  # noqa: BLE001
        message = f"plan: canonical publication failed closed: {error}"
        print(message, file=sys.stderr)
        errors.append(message)
        return _failed_plan_result(1, errors, Diagnostic("publication_failed", message))


def _checked_plan_inputs(paths: Paths, errors: list[str], bundle: OntologyBundle) -> PlanInputs | PlanResult:
    print("=== running check ===")
    check_result = _cmd_check_inner(paths, bundle)
    if check_result.exit_code != 0:
        print("plan: skipped (check failed; see errors above)", file=sys.stderr)
        return _failed_plan_result(
            check_result.exit_code,
            list(check_result.errors),
            Diagnostic("invalid_input", "input check failed"),
        )
    print("=== check passed; building canonical schedule ===")
    inputs = load_plan_inputs(paths, bundle)
    if inputs is None:
        return _failed_plan_result(1, errors, Diagnostic("invalid_input", "could not load canonical plan inputs"))
    return inputs


__all__ = ["cmd_plan"]
