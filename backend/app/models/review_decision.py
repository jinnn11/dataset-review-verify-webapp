import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReviewState(str, enum.Enum):
    keep = "keep"
    delete = "delete"
    needs_review = "needs_review"


class ReasonCode(str, enum.Enum):
    count_matches = "count_matches"
    different_class_allowed = "different_class_allowed"
    extra_same_class = "extra_same_class"
    policy_violation = "policy_violation"
    uncertain = "uncertain"


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("mask_groups.id"), nullable=False, index=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("generated_images.id"), nullable=False, index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    state: Mapped[ReviewState] = mapped_column(Enum(ReviewState), nullable=False, index=True)
    reason_code: Mapped[ReasonCode] = mapped_column(Enum(ReasonCode), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    group = relationship("MaskGroup", back_populates="decisions")
    image = relationship("GeneratedImage", back_populates="decisions")
    reviewer = relationship("User", back_populates="decisions")
