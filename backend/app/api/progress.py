from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import DbSession, get_current_user
from app.models.generated_image import GeneratedImage, ImageStatus
from app.models.review_decision import ReviewDecision, ReviewState
from app.models.user import User
from app.schemas.progress import ProgressSummary
from app.services.review_service import latest_decision_subquery

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/summary", response_model=ProgressSummary)
def summary(db: DbSession, user: Annotated[User, Depends(get_current_user)]) -> ProgressSummary:
    _ = user

    # Progress is based on full dataset size, not only currently active files.
    total_images = db.scalar(select(func.count(GeneratedImage.id))) or 0
    active_images = db.scalar(select(func.count(GeneratedImage.id)).where(GeneratedImage.status == ImageStatus.active)) or 0
    trashed_images = db.scalar(select(func.count(GeneratedImage.id)).where(GeneratedImage.status == ImageStatus.trashed)) or 0

    latest_sq = latest_decision_subquery()
    latest_states = db.execute(
        select(ReviewDecision.state)
        .join(latest_sq, ReviewDecision.id == latest_sq.c.max_decision_id)
    ).scalars().all()

    keep = sum(1 for state in latest_states if state == ReviewState.keep)
    delete = sum(1 for state in latest_states if state == ReviewState.delete)
    needs_review = sum(1 for state in latest_states if state == ReviewState.needs_review)
    # In current UI flow, only keep/delete are considered completed review states.
    reviewed = keep + delete
    remaining = max(total_images - reviewed, 0)

    return ProgressSummary(
        total_images=total_images,
        active_images=active_images,
        trashed_images=trashed_images,
        reviewed=reviewed,
        keep=keep,
        delete=delete,
        needs_review=needs_review,
        remaining=remaining,
    )
