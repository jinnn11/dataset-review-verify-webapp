from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import DatasetConfig
from app.models.generated_image import GeneratedImage, ImageStatus
from app.models.ingestion_run import IngestionRun
from app.models.mask_group import MaskGroup
from app.services.parser import FilenameParser


def _iter_files(base_dir: Path) -> list[Path]:
    if not base_dir.exists():
        return []
    return [path for path in base_dir.rglob("*") if path.is_file()]


def run_ingestion(db: Session, config: DatasetConfig) -> IngestionRun:
    parser = FilenameParser(config)
    run = IngestionRun(started_at=datetime.utcnow(), files_scanned=0, errors_count=0)
    db.add(run)
    db.flush()

    masks = _iter_files(config.masks_path)
    generated = _iter_files(config.generated_path)

    run.files_scanned = len(masks) + len(generated)

    groups_by_key: dict[str, MaskGroup] = {}

    for mask_path in masks:
        group_key = parser.parse_mask_group_key(mask_path)
        if not group_key:
            continue

        normalized = str(mask_path.resolve())
        existing_group = db.scalar(select(MaskGroup).where(MaskGroup.group_key == group_key))
        if existing_group:
            existing_group.mask_path = normalized
            groups_by_key[group_key] = existing_group
            continue

        group = MaskGroup(group_key=group_key, mask_path=normalized)
        db.add(group)
        db.flush()
        groups_by_key[group_key] = group

    # Ensure all existing groups are available for generated image linking.
    existing_groups = db.scalars(select(MaskGroup)).all()
    for group in existing_groups:
        groups_by_key.setdefault(group.group_key, group)

    discovered_generated_paths: set[str] = set()

    for image_path in generated:
        group_key = parser.parse_generated_group_key(image_path)
        if not group_key:
            continue

        group = groups_by_key.get(group_key)
        if not group:
            run.errors_count += 1
            continue

        normalized = str(image_path.resolve())
        discovered_generated_paths.add(normalized)
        existing_image = db.scalar(select(GeneratedImage).where(GeneratedImage.image_path == normalized))
        if existing_image:
            existing_image.group_id = group.id
            existing_image.status = ImageStatus.active
            continue

        db.add(GeneratedImage(group_id=group.id, image_path=normalized))

    # Reconcile stale DB rows when files were removed from dataset folders.
    active_images = db.scalars(select(GeneratedImage).where(GeneratedImage.status == ImageStatus.active)).all()
    for image in active_images:
        if image.image_path in discovered_generated_paths:
            continue
        if Path(image.image_path).exists():
            continue
        image.status = ImageStatus.trashed
        run.errors_count += 1

    run.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(run)
    return run
