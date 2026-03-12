from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.review_decision import ReasonCode, ReviewState

_ALLOWED_REASON_BY_STATE = {
    ReviewState.keep: {ReasonCode.count_matches, ReasonCode.different_class_allowed},
    ReviewState.delete: {ReasonCode.extra_same_class, ReasonCode.policy_violation},
    ReviewState.needs_review: {ReasonCode.uncertain},
}


class DecisionRequest(BaseModel):
    group_id: int
    image_id: int
    state: ReviewState
    reason_code: ReasonCode
    notes: str = ""

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_reason_for_state(self) -> "DecisionRequest":
        allowed = _ALLOWED_REASON_BY_STATE[self.state]
        if self.reason_code not in allowed:
            raise ValueError(f"reason_code {self.reason_code} is not allowed for state {self.state}")
        return self


class DecisionEntry(DecisionRequest):
    pass


class BulkDecisionRequest(BaseModel):
    decisions: list[DecisionEntry] = Field(min_length=1, max_length=200)


class BulkDecisionResponse(BaseModel):
    saved: int
    saved_image_ids: list[int]
    skipped_image_ids: list[int]


class GeneratedImageRecord(BaseModel):
    id: int
    image_path: str
    status: str
    current_state: ReviewState | None = None
    current_reason: ReasonCode | None = None
    current_notes: str = ""
    current_reviewer: str | None = None
    current_decision_at: datetime | None = None


class GroupRecord(BaseModel):
    id: int
    group_key: str
    mask_path: str
    generated_images: list[GeneratedImageRecord]


class QueueResponse(BaseModel):
    items: list[GroupRecord]
    next_cursor: str | None = None


class HistoryItem(BaseModel):
    decision_id: int
    group_id: int
    group_key: str
    mask_path: str
    image_id: int
    image_path: str
    image_status: str
    state: ReviewState
    reason_code: ReasonCode
    reviewer: str | None = None
    decided_at: datetime


class HistoryResponse(BaseModel):
    items: list[HistoryItem]
    next_cursor: str | None = None
