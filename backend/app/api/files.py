from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession, require_admin, require_csrf
from app.core.config import get_dataset_config, settings
from app.models.deletion_operation import DeletionOperation
from app.models.generated_image import GeneratedImage, ImageStatus
from app.models.review_decision import ReasonCode, ReviewDecision, ReviewState
from app.models.user import User
from app.schemas.file_ops import DeletionOperationResponse
from app.services.file_ops import (
    build_trash_path,
    ensure_under_root,
    move_to_trash,
    restore_from_trash,
)
from app.services.review_service import append_unresolved_decision

router = APIRouter(prefix="/files", tags=["files"])


def _to_response(operation: DeletionOperation) -> DeletionOperationResponse:
    return DeletionOperationResponse(
        operation_id=operation.id,
        image_id=operation.image_id,
        source_path=operation.source_path,
        trash_path=operation.trash_path,
        restored_by=operation.restored_by,
        executed_at=operation.executed_at,
        restored_at=operation.restored_at,
    )


def _raise_file_error(exc: Exception) -> None:
    if isinstance(exc, ValueError | FileExistsError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    raise exc


def _resolve_under_root(path_value: str, root: Path) -> Path:
    path = Path(path_value).resolve()
    try:
        ensure_under_root(path, root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return path


def _commit_with_compensation(db: DbSession, compensate: Callable[[], None], *, action_name: str) -> None:
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        try:
            compensate()
        except Exception as rollback_exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{action_name} failed and file rollback also failed: {rollback_exc}",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{action_name} failed and file move was rolled back",
        ) from exc


@router.post("/soft-delete/{image_id}", response_model=DeletionOperationResponse)
def soft_delete(
    image_id: int,
    db: DbSession,
    user: Annotated[User, Depends(require_admin)],
    _: Annotated[dict[str, str], Depends(require_csrf)],
) -> DeletionOperationResponse:
    if not settings.enable_soft_delete:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Soft delete is disabled in current rollout phase",
        )

    image = db.scalar(select(GeneratedImage).where(GeneratedImage.id == image_id).with_for_update())
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    if image.status != ImageStatus.active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Image already trashed")

    active_delete = db.scalar(
        select(DeletionOperation.id)
        .where(DeletionOperation.image_id == image.id, DeletionOperation.restored_at.is_(None))
        .limit(1)
        .with_for_update()
    )
    if active_delete:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Image already has an active delete operation")

    cfg = get_dataset_config()
    source = _resolve_under_root(image.image_path, cfg.root_path)
    trash_path = build_trash_path(source, cfg.trash_path).resolve()
    try:
        ensure_under_root(trash_path, cfg.root_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        move_to_trash(source, trash_path)
    except Exception as exc:  # noqa: BLE001
        _raise_file_error(exc)

    operation = DeletionOperation(
        image_id=image.id,
        source_path=str(source),
        trash_path=str(trash_path),
        requested_by=user.id,
        executed_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    image.status = ImageStatus.trashed

    db.add(operation)
    db.add(
        ReviewDecision(
            group_id=image.group_id,
            image_id=image.id,
            reviewer_id=user.id,
            state=ReviewState.delete,
            reason_code=ReasonCode.extra_same_class,
            notes="Auto decision from soft delete",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    _commit_with_compensation(
        db,
        compensate=lambda: restore_from_trash(trash_path, source),
        action_name="Soft delete persistence",
    )
    db.refresh(operation)
    return _to_response(operation)


@router.post("/restore/{operation_id}", response_model=DeletionOperationResponse)
def restore(
    operation_id: int,
    db: DbSession,
    user: Annotated[User, Depends(require_admin)],
    _: Annotated[dict[str, str], Depends(require_csrf)],
) -> DeletionOperationResponse:
    operation = db.scalar(select(DeletionOperation).where(DeletionOperation.id == operation_id).with_for_update())
    if not operation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation not found")
    if operation.restored_at:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Operation already restored")

    cfg = get_dataset_config()
    trash_path = _resolve_under_root(operation.trash_path, cfg.root_path)
    source_path = _resolve_under_root(operation.source_path, cfg.root_path)
    try:
        restore_from_trash(trash_path, source_path)
    except Exception as exc:  # noqa: BLE001
        _raise_file_error(exc)

    operation.restored_at = datetime.now(timezone.utc).replace(tzinfo=None)
    operation.restored_by = user.id

    image = db.scalar(select(GeneratedImage).where(GeneratedImage.id == operation.image_id).with_for_update())
    if image:
        image.status = ImageStatus.active
        append_unresolved_decision(
            db,
            group_id=image.group_id,
            image_id=image.id,
            reviewer_id=user.id,
            notes="Auto-reset after restore",
        )

    _commit_with_compensation(
        db,
        compensate=lambda: move_to_trash(source_path, trash_path),
        action_name="Restore persistence",
    )
    db.refresh(operation)
    return _to_response(operation)


@router.post("/undo/{image_id}", response_model=DeletionOperationResponse)
def undo_latest_for_image(
    image_id: int,
    db: DbSession,
    user: Annotated[User, Depends(require_admin)],
    _: Annotated[dict[str, str], Depends(require_csrf)],
) -> DeletionOperationResponse:
    operation = db.scalar(
        select(DeletionOperation)
        .where(DeletionOperation.image_id == image_id, DeletionOperation.restored_at.is_(None))
        .order_by(DeletionOperation.id.desc())
        .limit(1)
        .with_for_update()
    )
    if not operation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active delete operation for this image")

    cfg = get_dataset_config()
    trash_path = _resolve_under_root(operation.trash_path, cfg.root_path)
    source_path = _resolve_under_root(operation.source_path, cfg.root_path)
    try:
        restore_from_trash(trash_path, source_path)
    except Exception as exc:  # noqa: BLE001
        _raise_file_error(exc)

    operation.restored_at = datetime.now(timezone.utc).replace(tzinfo=None)
    operation.restored_by = user.id
    image = db.scalar(select(GeneratedImage).where(GeneratedImage.id == operation.image_id).with_for_update())
    if image:
        image.status = ImageStatus.active
        append_unresolved_decision(
            db,
            group_id=image.group_id,
            image_id=image.id,
            reviewer_id=user.id,
            notes="Auto-reset after undo",
        )

    _commit_with_compensation(
        db,
        compensate=lambda: move_to_trash(source_path, trash_path),
        action_name="Undo persistence",
    )
    db.refresh(operation)
    return _to_response(operation)
