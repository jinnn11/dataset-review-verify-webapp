import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ImageStatus(str, enum.Enum):
    active = "active"
    trashed = "trashed"


class GeneratedImage(Base):
    __tablename__ = "generated_images"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("mask_groups.id"), nullable=False, index=True)
    image_path: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    status: Mapped[ImageStatus] = mapped_column(Enum(ImageStatus), default=ImageStatus.active, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    group = relationship("MaskGroup", back_populates="generated_images")
    decisions = relationship("ReviewDecision", back_populates="image")
    deletion_operations = relationship("DeletionOperation", back_populates="image")
