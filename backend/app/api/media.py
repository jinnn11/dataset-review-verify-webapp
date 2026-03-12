from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.api.deps import DbSession, get_current_user
from app.core.config import get_dataset_config
from app.models.generated_image import GeneratedImage
from app.models.mask_group import MaskGroup
from app.models.user import User
from app.services.file_ops import ensure_under_root

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/mask/{group_id}")
def mask_image(
    group_id: int,
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    _ = user
    group = db.get(MaskGroup, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mask group not found")

    cfg = get_dataset_config()
    path = Path(group.mask_path).resolve()
    ensure_under_root(path, cfg.root_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mask file missing")

    return FileResponse(path)


@router.get("/image/{image_id}")
def generated_image(
    image_id: int,
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    _ = user
    image = db.get(GeneratedImage, image_id)
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    cfg = get_dataset_config()
    path = Path(image.image_path).resolve()
    ensure_under_root(path, cfg.root_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image file missing")

    return FileResponse(path)
