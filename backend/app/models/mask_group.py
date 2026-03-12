from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MaskGroup(Base):
    __tablename__ = "mask_groups"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    group_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    mask_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    generated_images = relationship("GeneratedImage", back_populates="group")
    decisions = relationship("ReviewDecision", back_populates="group")
