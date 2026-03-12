from pathlib import Path

import pytest

from app.services.file_ops import ensure_under_root


def test_path_guard_accepts_in_root(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    inside = root / "generated" / "a.png"
    inside.parent.mkdir(parents=True)
    inside.touch()

    ensure_under_root(inside, root)


def test_path_guard_rejects_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    outside = tmp_path / "other" / "b.png"
    outside.parent.mkdir(parents=True)
    outside.touch()

    with pytest.raises(ValueError):
        ensure_under_root(outside, root)
