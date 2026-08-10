"""Generated ontology artifact contract checks."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.ontology.artifacts import load_runtime_program
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.glue_capabilities import (
    IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS,
    IMPLEMENTED_SOURCE_KIND_ROLES,
)
from planner.ontology.runtime_program import decode_runtime_program

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"


def _copy_repository_shape(tmp_path: Path) -> Path:  # noqa: PLR0912, PLR0914
    repository = tmp_path / "repo"
    copied = repository / "ontology"
    shutil.copytree(ONTOLOGY, copied)
    manifest = cast(dict[str, object], yaml.safe_load((ONTOLOGY / "manifest.yaml").read_text(encoding="utf-8")))
    paths: set[str] = set()
    for field in (
        "linkml_root",
        "linkml_modules",
        "policy_sources",
        "constraint_sources",
        "assertion_sources",
        "custom_shapes",
    ):
        value = manifest.get(field)
        if isinstance(value, str):
            paths.add(value)
        elif isinstance(value, list):
            paths.update(item for item in value if isinstance(item, str))
    catalogs = cast(list[dict[str, object]], manifest.get("catalogs", []))
    for catalog in catalogs:
        path = catalog.get("path")
        if isinstance(path, str):
            paths.add(path)
    projection = manifest.get("repository_projection")
    if isinstance(projection, dict):
        projection_map = cast(dict[str, object], projection)
        for source in cast(list[object], projection_map.get("sources", [])):
            if not isinstance(source, dict):
                continue
            source_map = cast(dict[str, object], source)
            locator = source_map.get("locator")
            if not isinstance(locator, dict):
                continue
            locator_map = cast(dict[str, object], locator)
            kind = locator_map.get("kind")
            if kind == "flat_root":
                value = locator_map.get("path")
                if isinstance(value, str):
                    source_dir = ROOT / value
                    paths.update(
                        (Path(value) / child.name).as_posix()
                        for child in source_dir.iterdir()
                        if child.is_file() and child.suffix == ".yaml"
                    )
            elif kind == "explicit_path":
                value = locator_map.get("path")
                if isinstance(value, str):
                    paths.add(value)
            elif kind == "explicit_paths":
                values = locator_map.get("paths")
                if isinstance(values, list):
                    paths.update(item for item in values if isinstance(item, str))
    for relative in paths:
        source = ROOT / relative
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return copied


def test_committed_runtime_program_decodes() -> None:
    runtime = load_runtime_program(ONTOLOGY)
    assert runtime.effect_scoring.prefer_with_bonus > 0
    assert runtime.constraint_execution_policy_for("separate_products_same_slot") is not None
    declared_roles = set(runtime.glue_contract.source_kind_roles)
    assert runtime.glue_contract.source_kind_roles == IMPLEMENTED_SOURCE_KIND_ROLES
    assert all(set(row.applies_to) <= declared_roles for row in runtime.source_kind_values)


def test_dashboard_state_rows_are_role_free_and_truth_table_driven() -> None:
    runtime = load_runtime_program(ONTOLOGY)
    payload = _runtime_payload()
    projection = cast(dict[str, object], payload["projection"])
    catalog = cast(dict[str, object], projection["dashboard_state_catalog"])

    assert all(not hasattr(row, "stack_source") for row in runtime.dashboard_state_catalog.usage_states)
    assert all(not hasattr(row, "stack_source") for row in runtime.dashboard_state_catalog.product_tracking_states)
    for section in ("usage_states", "product_tracking_states", "usage_truth_table", "product_tracking_truth_table"):
        rows = cast(list[dict[str, object]], catalog[section])
        assert all("stack_source" not in row for row in rows)


def test_runtime_decode_rejects_duplicate_dashboard_state_labels() -> None:
    payload = _runtime_payload()
    projection = cast(dict[str, object], payload["projection"])
    catalog = cast(dict[str, object], projection["dashboard_state_catalog"])
    rows = cast(list[dict[str, object]], catalog["usage_states"])
    rows[1]["label"] = rows[0]["label"]

    with pytest.raises(OntologyInfrastructureError, match="state labels"):
        decode_runtime_program(payload)


def test_slot_near_values_are_authored_runtime_observations() -> None:
    runtime = load_runtime_program(ONTOLOGY)

    assert runtime.slot_near_values == (
        "wake",
        "breakfast",
        "day_meal",
        "sleep",
        "workout_before",
        "workout_after",
    )


def test_runtime_decode_rejects_invalid_slot_near_values() -> None:
    payload = cast(
        dict[str, object],
        json.loads((ONTOLOGY / "generated/runtime-program.json").read_text(encoding="utf-8")),
    )
    projection = cast(dict[str, object], payload["projection"])
    projection["slot_near_values"] = []

    with pytest.raises(OntologyInfrastructureError, match="slot_near_values"):
        decode_runtime_program(payload)


def test_runtime_decode_rejects_unimplemented_objective_contract() -> None:
    payload = cast(
        dict[str, object],
        json.loads((ONTOLOGY / "generated/runtime-program.json").read_text(encoding="utf-8")),
    )
    projection = cast(dict[str, object], payload["projection"])
    scoring = cast(dict[str, object], projection["effect_scoring"])
    scoring["objective_function"] = "unimplemented_objective"

    with pytest.raises(OntologyInfrastructureError, match="not implemented"):
        decode_runtime_program(payload)


def test_runtime_decode_requires_exact_executable_capability_parity() -> None:
    payload = _runtime_payload()
    projection = cast(dict[str, object], payload["projection"])
    glue = cast(dict[str, object], projection["glue_contract"])
    capability_field = sorted(IMPLEMENTED_GLUE_CONTRACT_CAPABILITY_SETS)[0]
    values = cast(list[object], glue[capability_field])
    values.pop()

    with pytest.raises(OntologyInfrastructureError, match=f"glue_contract\\.{capability_field}"):
        decode_runtime_program(payload)


def test_runtime_derives_presence_active_side_from_endpoint_truth_state() -> None:
    runtime = load_runtime_program(ONTOLOGY)
    assert {(row.source_active, row.target_active): row.active_side for row in runtime.relation_presence_statuses} == {
        (False, False): "none",
        (False, True): "target",
        (True, False): "source",
        (True, True): "both",
    }


def _runtime_payload() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((ONTOLOGY / "generated/runtime-program.json").read_text(encoding="utf-8")),
    )


@pytest.mark.parametrize(
    ("section",),
    [
        ("source_kind_values",),
    ],
)
def test_runtime_decode_rejects_duplicate_semantic_keys_with_distinct_ids(section: str) -> None:
    payload = _runtime_payload()
    projection = cast(dict[str, object], payload["projection"])
    rows = cast(list[dict[str, object]], projection[section])
    rows.append({**rows[0], "id": f"{rows[0]['id']}_collision"})

    with pytest.raises(OntologyInfrastructureError, match="duplicate semantic key"):
        decode_runtime_program(payload)


def test_runtime_decode_rejects_duplicate_relation_rule_match_with_distinct_id() -> None:
    payload = _runtime_payload()
    projection = cast(dict[str, object], payload["projection"])
    rows = cast(list[dict[str, object]], projection["relation_warning_rules"])
    rows.append({**rows[0], "id": f"{rows[0]['id']}_collision"})

    with pytest.raises(OntologyInfrastructureError, match="duplicate semantic key"):
        decode_runtime_program(payload)


def test_runtime_decode_rejects_non_boolean_truth_table_values() -> None:
    payload = _runtime_payload()
    projection = cast(dict[str, object], payload["projection"])
    glue = cast(dict[str, object], projection["glue_contract"])
    truth = cast(list[dict[str, object]], glue["relation_presence_truth_table"])
    truth[0]["source_active"] = "false"

    with pytest.raises(OntologyInfrastructureError, match="must be boolean"):
        decode_runtime_program(payload)


def test_runtime_decode_requires_exact_unique_four_state_truth_table() -> None:
    payload = _runtime_payload()
    projection = cast(dict[str, object], payload["projection"])
    glue = cast(dict[str, object], projection["glue_contract"])
    truth = cast(list[dict[str, object]], glue["relation_presence_truth_table"])
    truth.pop()

    with pytest.raises(OntologyInfrastructureError, match="exact unique four-state coverage"):
        decode_runtime_program(payload)


def test_runtime_decode_requires_presence_status_for_each_truth_state() -> None:
    payload = _runtime_payload()
    projection = cast(dict[str, object], payload["projection"])
    statuses = cast(list[dict[str, object]], projection["relation_presence_statuses"])
    statuses.pop()

    with pytest.raises(OntologyInfrastructureError, match="relation_presence_statuses"):
        decode_runtime_program(payload)


def test_runtime_decode_rejects_unsupported_relation_endpoint_selector_kind() -> None:
    payload = _runtime_payload()
    projection = cast(dict[str, object], payload["projection"])
    endpoints = cast(list[dict[str, object]], projection["selector_form_capabilities"])
    endpoints[0]["endpoint_kind"] = "category"

    with pytest.raises(OntologyInfrastructureError, match="endpoint kinds"):
        decode_runtime_program(payload)


def test_runtime_decode_rejects_unsupported_selector_form() -> None:
    payload = _runtime_payload()
    projection = cast(dict[str, object], payload["projection"])
    capabilities = cast(list[dict[str, object]], projection["selector_form_capabilities"])
    capabilities[0]["selector_form"] = "category"

    with pytest.raises(OntologyInfrastructureError, match="selector forms"):
        decode_runtime_program(payload)
