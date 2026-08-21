from pathlib import Path

import pytest
from planner.contracts import CardLoadError
from planner.paths import Paths
from planner.query_model.loaders import pillbox_stack_names


def _write_pillboxes(root: Path, content: str) -> Paths:
    data = root / "data"
    data.mkdir()
    (data / "pillboxes.yaml").write_text(content, encoding="utf-8")
    return Paths.from_root(root)


def test_pillbox_stack_names_returns_authored_unique_stack_references(tmp_path: Path) -> None:
    paths = _write_pillboxes(tmp_path, "daily:\n  stack: daily\ntraining:\n  stack: daily\n")

    assert pillbox_stack_names(paths) == {"daily"}


@pytest.mark.parametrize(
    "content",
    (
        "'':\n  stack: daily\n",
        "daily: []\n",
        "daily:\n  stack: ''\n",
    ),
)
def test_pillbox_stack_names_rejects_malformed_authored_references(tmp_path: Path, content: str) -> None:
    paths = _write_pillboxes(tmp_path, content)

    with pytest.raises(CardLoadError):
        pillbox_stack_names(paths)
