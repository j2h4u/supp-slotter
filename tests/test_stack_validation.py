from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from planner.cards.stacks import check_stack_alignment, normalize_stack_entries, validate_stacks
from planner.paths import Paths


def test_normalization_rejects_product_assigned_to_active_and_inactive_stacks() -> None:
    with pytest.raises(ValueError, match=r"prd_aaa0000001.*multiple partitions"):
        normalize_stack_entries({"daily": ["prd_aaa0000001"], "inactive": ["prd_aaa0000001"]})


def test_tracked_unassigned_requires_complete_reasoned_record_and_never_projects_to_stack_entries() -> None:
    normalized = normalize_stack_entries({
        "daily": ["prd_aaa0000001"],
        "inactive": [],
        "tracked_unassigned": [{"product": "prd_bbb0000002", "reason": "Not currently owned."}],
    })

    assert normalized == {"prd_aaa0000001": {"product": "prd_aaa0000001", "stack": "daily"}}

    with pytest.raises(ValueError, match="reason must be a non-empty string"):
        normalize_stack_entries({"tracked_unassigned": [{"product": "prd_bbb0000002", "reason": ""}]})


def test_partition_rejects_omitted_or_multiply_owned_products(tmp_path: Path) -> None:
    product_ids = {
        "prd_aaa0000001": tmp_path / "a.yaml",
        "prd_bbb0000002": tmp_path / "b.yaml",
    }
    errors, _info = check_stack_alignment(
        {"daily": ["prd_aaa0000001"], "inactive": [], "tracked_unassigned": []},
        product_ids,
        tmp_path / "stacks.yaml",
        "inactive",
    )

    assert len(errors) == 1
    assert "prd_bbb0000002" in errors[0]
    assert "tracked_unassigned" in errors[0]

    with pytest.raises(ValueError, match="multiple partitions"):
        normalize_stack_entries({
            "daily": ["prd_aaa0000001"],
            "tracked_unassigned": [{"product": "prd_aaa0000001", "reason": "Not currently owned."}],
        })


def test_malformed_stack_entry_fails_closed() -> None:
    with pytest.raises(ValueError, match="must be a non-empty product id"):
        normalize_stack_entries({"daily": [{"product": "prd_aaa0000001"}]})


def test_inactive_and_tracked_partitions_are_exempt_but_routable_stack_requires_one_pillbox(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "stacks.yaml").write_text("inactive: []\ndaily: []\ntracked_unassigned: []\n", encoding="utf-8")
    (data / "pillboxes.yaml").write_text("{}\n", encoding="utf-8")

    errors, info = validate_stacks(Paths.from_root(tmp_path), {}, _bundle())  # type: ignore[arg-type]

    assert any("routable stack 'daily' requires exactly one pillbox" in message for message in errors)
    assert not info


def test_duplicate_or_non_routable_pillbox_stack_fails_closed(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "stacks.yaml").write_text("daily: []\ninactive: []\ntracked_unassigned: []\n", encoding="utf-8")
    (data / "pillboxes.yaml").write_text(
        "one:\n  label: One\n  stack: daily\n  slots: {}\ntwo:\n  label: Two\n  stack: daily\n  slots: {}\n",
        encoding="utf-8",
    )

    errors, _info = validate_stacks(Paths.from_root(tmp_path), {}, _bundle())  # type: ignore[arg-type]

    assert any("stack 'daily' has 2 pillboxes" in message for message in errors)


def _bundle() -> SimpleNamespace:
    return SimpleNamespace(
        runtime_program=SimpleNamespace(
            glue_contract=SimpleNamespace(
                inactive_stack_name="inactive",
                stack_partition=SimpleNamespace(routable_stack_names=("daily", "training")),
            )
        )
    )
