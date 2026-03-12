from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DbSession, require_admin, require_csrf
from app.core.config import get_dataset_config
from app.models.user import User
from app.services.ingestion import run_ingestion

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/run")
def ingest(
    db: DbSession,
    user: Annotated[User, Depends(require_admin)],
    _: Annotated[dict[str, str], Depends(require_csrf)],
) -> dict[str, int | str | None]:
    _ = user
    result = run_ingestion(db, get_dataset_config())
    return {
        "run_id": result.id,
        "files_scanned": result.files_scanned,
        "errors_count": result.errors_count,
        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
    }
