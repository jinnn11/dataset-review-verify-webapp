from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.generated_image import GeneratedImage, ImageStatus
from app.models.mask_group import MaskGroup
from app.models.review_decision import ReasonCode, ReviewDecision, ReviewState


def latest_decision_subquery():
    return (
        select(
            ReviewDecision.image_id,
            func.max(ReviewDecision.id).label("max_decision_id"),
        )
        .group_by(ReviewDecision.image_id)
        .subquery()
    )


def fetch_queue_groups(db: Session, cursor: int | None, limit: int, search: str | None = None):
    query = select(MaskGroup).order_by(MaskGroup.id.asc())
    if cursor:
        query = query.where(MaskGroup.id > cursor)
    if search:
        query = query.where(MaskGroup.group_key.ilike(f"%{search}%"))

    groups = db.scalars(query.limit(limit)).all()
    if not groups:
        return [], None

    group_ids = [group.id for group in groups]
    images = db.scalars(
        select(GeneratedImage)
        .where(GeneratedImage.group_id.in_(group_ids), GeneratedImage.status == ImageStatus.active)
        .order_by(GeneratedImage.id.asc())
    ).all()

    image_ids = [image.id for image in images]
    latest_map = {}
    if image_ids:
        latest_sq = latest_decision_subquery()
        rows = db.execute(
            select(ReviewDecision)
            .join(latest_sq, ReviewDecision.id == latest_sq.c.max_decision_id)
            .where(ReviewDecision.image_id.in_(image_ids))
        ).scalars().all()
        latest_map = {row.image_id: row for row in rows}

    images_by_group: dict[int, list[GeneratedImage]] = {}
    for image in images:
        images_by_group.setdefault(image.group_id, []).append(image)

    next_cursor = groups[-1].id
    return [(group, images_by_group.get(group.id, []), latest_map) for group in groups], next_cursor


def fetch_history_entries(db: Session, cursor: int | None, limit: int, search: str | None = None):
    latest_sq = latest_decision_subquery()
    query = (
        select(ReviewDecision, GeneratedImage, MaskGroup)
        .join(latest_sq, ReviewDecision.id == latest_sq.c.max_decision_id)
        .join(GeneratedImage, GeneratedImage.id == ReviewDecision.image_id)
        .join(MaskGroup, MaskGroup.id == GeneratedImage.group_id)
        .where(ReviewDecision.state.in_([ReviewState.keep, ReviewState.delete]))
        .order_by(ReviewDecision.id.desc())
    )

    if cursor:
        query = query.where(ReviewDecision.id < cursor)
    if search:
        query = query.where(MaskGroup.group_key.ilike(f"%{search}%"))

    rows = db.execute(query.limit(limit + 1)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1][0].id if has_more and rows else None
    return rows, next_cursor


def append_unresolved_decision(
    db: Session,
    *,
    group_id: int,
    image_id: int,
    reviewer_id: int,
    notes: str,
) -> None:
    db.add(
        ReviewDecision(
            group_id=group_id,
            image_id=image_id,
            reviewer_id=reviewer_id,
            state=ReviewState.needs_review,
            reason_code=ReasonCode.uncertain,
            notes=notes,
        )
    )
