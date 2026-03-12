from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbSession, get_current_user, require_csrf
from app.models.generated_image import GeneratedImage, ImageStatus
from app.models.mask_group import MaskGroup
from app.models.review_decision import ReviewDecision, ReviewState
from app.models.user import User
from app.schemas.review import (
    BulkDecisionRequest,
    BulkDecisionResponse,
    DecisionRequest,
    GeneratedImageRecord,
    GroupRecord,
    HistoryItem,
    HistoryResponse,
    QueueResponse,
)
from app.services.review_service import append_unresolved_decision, fetch_history_entries, fetch_queue_groups, latest_decision_subquery

router = APIRouter(prefix="/review", tags=["review"])


def _encode_cursor(value: int) -> str:
    return base64.urlsafe_b64encode(str(value).encode("utf-8")).decode("utf-8")


def _decode_cursor(value: str | None) -> int | None:
    if not value:
        return None
    try:
        decoded = base64.urlsafe_b64decode(value.encode("utf-8")).decode("utf-8")
        return int(decoded)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor") from exc


def _build_group_record(
    db: DbSession,
    group_id: int,
    latest_map: dict[int, ReviewDecision] | None = None,
) -> GroupRecord | None:
    group = db.scalar(select(MaskGroup).where(MaskGroup.id == group_id))
    if not group:
        return None

    images = db.scalars(
        select(GeneratedImage)
        .where(GeneratedImage.group_id == group_id, GeneratedImage.status == ImageStatus.active)
        .order_by(GeneratedImage.id.asc())
    ).all()

    image_ids = [image.id for image in images]
    local_latest_map: dict[int, ReviewDecision] = latest_map or {}
    if image_ids and not latest_map:
        latest_sq = latest_decision_subquery()
        latest_rows = db.execute(
            select(ReviewDecision)
            .join(latest_sq, ReviewDecision.id == latest_sq.c.max_decision_id)
            .where(ReviewDecision.image_id.in_(image_ids))
        ).scalars().all()
        local_latest_map = {row.image_id: row for row in latest_rows}

    reviewer_ids = {local_latest_map[image_id].reviewer_id for image_id in local_latest_map}
    reviewers = (
        {
            row.id: row.username
            for row in db.scalars(select(User).where(User.id.in_(reviewer_ids))).all()
        }
        if reviewer_ids
        else {}
    )

    image_records: list[GeneratedImageRecord] = []
    for image in images:
        latest = local_latest_map.get(image.id)
        image_records.append(
            GeneratedImageRecord(
                id=image.id,
                image_path=image.image_path,
                status=image.status.value,
                current_state=latest.state if latest else None,
                current_reason=latest.reason_code if latest else None,
                current_notes=latest.notes if latest else "",
                current_reviewer=reviewers.get(latest.reviewer_id) if latest else None,
                current_decision_at=latest.created_at if latest else None,
            )
        )

    return GroupRecord(
        id=group.id,
        group_key=group.group_key,
        mask_path=group.mask_path,
        generated_images=image_records,
    )


@router.get("/queue", response_model=QueueResponse)
def queue(
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
) -> QueueResponse:
    _ = user
    decoded_cursor = _decode_cursor(cursor)
    rows, next_cursor_id = fetch_queue_groups(db, decoded_cursor, limit, search)

    reviewer_ids = {
        latest_map[image.id].reviewer_id
        for _, images, latest_map in rows
        for image in images
        if image.id in latest_map
    }
    reviewers = {
        row.id: row.username
        for row in db.scalars(select(User).where(User.id.in_(reviewer_ids))).all()
    } if reviewer_ids else {}

    items: list[GroupRecord] = []
    for group, images, latest_map in rows:
        image_records: list[GeneratedImageRecord] = []
        for image in images:
            latest = latest_map.get(image.id)
            image_records.append(
                GeneratedImageRecord(
                    id=image.id,
                    image_path=image.image_path,
                    status=image.status.value,
                    current_state=latest.state if latest else None,
                    current_reason=latest.reason_code if latest else None,
                    current_notes=latest.notes if latest else "",
                    current_reviewer=reviewers.get(latest.reviewer_id) if latest else None,
                    current_decision_at=latest.created_at if latest else None,
                )
            )
        items.append(
            GroupRecord(
                id=group.id,
                group_key=group.group_key,
                mask_path=group.mask_path,
                generated_images=image_records,
            )
        )

    return QueueResponse(items=items, next_cursor=_encode_cursor(next_cursor_id) if next_cursor_id else None)


@router.get("/group/{group_id}", response_model=GroupRecord)
def group_by_id(
    group_id: int,
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> GroupRecord:
    _ = user
    group_record = _build_group_record(db, group_id)
    if not group_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return group_record


@router.get("/history", response_model=HistoryResponse)
def history(
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    search: str | None = Query(default=None, max_length=255),
) -> HistoryResponse:
    _ = user
    decoded_cursor = _decode_cursor(cursor)
    rows, next_cursor_id = fetch_history_entries(db, decoded_cursor, limit, search)
    reviewer_ids = {decision.reviewer_id for decision, _, _ in rows}
    reviewers = {
        row.id: row.username
        for row in db.scalars(select(User).where(User.id.in_(reviewer_ids))).all()
    } if reviewer_ids else {}

    items: list[HistoryItem] = []
    for decision, image, group in rows:
        items.append(
            HistoryItem(
                decision_id=decision.id,
                group_id=group.id,
                group_key=group.group_key,
                mask_path=group.mask_path,
                image_id=image.id,
                image_path=image.image_path,
                image_status=image.status.value,
                state=decision.state,
                reason_code=decision.reason_code,
                reviewer=reviewers.get(decision.reviewer_id),
                decided_at=decision.created_at,
            )
        )

    return HistoryResponse(items=items, next_cursor=_encode_cursor(next_cursor_id) if next_cursor_id else None)


@router.post("/decision")
def decide(
    payload: DecisionRequest,
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    _: Annotated[dict[str, str], Depends(require_csrf)],
) -> dict[str, str]:
    if payload.state == ReviewState.delete:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Delete decisions must use soft-delete endpoint",
        )

    image = db.get(GeneratedImage, payload.image_id)
    if not image or image.status != ImageStatus.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    if image.group_id != payload.group_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image/group mismatch")

    decision = ReviewDecision(
        group_id=payload.group_id,
        image_id=payload.image_id,
        reviewer_id=user.id,
        state=payload.state,
        reason_code=payload.reason_code,
        notes=payload.notes,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(decision)
    db.commit()
    return {"status": "ok"}


@router.post("/decision/bulk", response_model=BulkDecisionResponse)
def decide_bulk(
    payload: BulkDecisionRequest,
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    _: Annotated[dict[str, str], Depends(require_csrf)],
) -> BulkDecisionResponse:
    if any(item.state == ReviewState.delete for item in payload.decisions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Delete decisions must use soft-delete endpoint",
        )

    saved = 0
    saved_image_ids: list[int] = []
    skipped_image_ids: list[int] = []
    for decision_payload in payload.decisions:
        image = db.get(GeneratedImage, decision_payload.image_id)
        if not image or image.status != ImageStatus.active:
            skipped_image_ids.append(decision_payload.image_id)
            continue
        if image.group_id != decision_payload.group_id:
            skipped_image_ids.append(decision_payload.image_id)
            continue

        db.add(
            ReviewDecision(
                group_id=decision_payload.group_id,
                image_id=decision_payload.image_id,
                reviewer_id=user.id,
                state=decision_payload.state,
                reason_code=decision_payload.reason_code,
                notes=decision_payload.notes,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        saved += 1
        saved_image_ids.append(decision_payload.image_id)

    db.commit()
    return BulkDecisionResponse(
        saved=saved,
        saved_image_ids=saved_image_ids,
        skipped_image_ids=skipped_image_ids,
    )


@router.post("/undo/{image_id}")
def undo_decision(
    image_id: int,
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    _: Annotated[dict[str, str], Depends(require_csrf)],
) -> dict[str, str]:
    image = db.get(GeneratedImage, image_id)
    if not image or image.status != ImageStatus.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    append_unresolved_decision(
        db,
        group_id=image.group_id,
        image_id=image.id,
        reviewer_id=user.id,
        notes="Undo decision",
    )
    db.commit()
    return {"status": "ok"}
