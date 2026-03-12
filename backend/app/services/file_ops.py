from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil


def normalize_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def ensure_under_root(candidate: Path, root: Path) -> None:
    candidate = candidate.resolve()
    root = root.resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError(f"Path {candidate} is outside dataset root {root}")


def build_trash_path(source: Path, trash_root: Path) -> Path:
    date_folder = datetime.utcnow().strftime("%Y-%m-%d")
    unique_name = f"{datetime.utcnow().strftime('%H%M%S%f')}_{source.name}"
    return trash_root / date_folder / unique_name


def move_to_trash(source: Path, trash_path: Path) -> None:
    trash_path.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        raise FileNotFoundError(f"Source file does not exist: {source}")
    shutil.move(str(source), str(trash_path))


def restore_from_trash(trash_path: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not trash_path.exists():
        raise FileNotFoundError(f"Trash file does not exist: {trash_path}")
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")
    shutil.move(str(trash_path), str(destination))
