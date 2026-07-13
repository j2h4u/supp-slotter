"""Regression coverage for canonical assertion rendering in review-substance."""

from __future__ import annotations

from pathlib import Path

import yaml
from planner.engine.review import cmd_review_substance

from tests.planner_fixture import find_card_path_by_id
from tests.test_review_substance_command import _write_review_substance_fixture


def test_review_substance_renders_resolved_canonical_assertion_endpoints(tmp_path: Path) -> None:
    data_root = _write_review_substance_fixture(tmp_path)
    (data_root / "relations.yaml").write_text(
        yaml.safe_dump(
            {
                "relations": [
                    {
                        "id": "rel_fixture_review",
                        "type": "review_with",
                        "assertion_kind": "clinical_review_signal",
                        "semantic_family": "clinical_review_signal",
                        "source_selector": {"entity": {"id": "sub_bsix000001"}},
                        "target_selector": {"entity": {"name": "Levodopa"}},
                        "reason": "Synthetic review fixture.",
                    }
                ]
            },
            sort_keys=False,
        )
    )
    target = find_card_path_by_id(data_root / "substances", "sub_bsix000001")
    result = cmd_review_substance(
        str(target),
        data_root=tmp_path,
        compact=True,
    )

    assert result.exit_code == 0, result.stderr
    assert "review_with" in result.output
    assert "Vitamin B6 (pyridoxine HCl) -> Levodopa" in result.output
    assert "matched by: source selector" in result.output
