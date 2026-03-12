from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DeletionOperation(Base):
    __tablename__ = "deletion_operations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("generated_images.id"), nullable=False, index=True)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    trash_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    restored_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    image = relationship("GeneratedImage", back_populates="deletion_operations")
    requester = relationship("User", foreign_keys=[requested_by], back_populates="deletion_operations")
    restorer = relationship("User", foreign_keys=[restored_by], back_populates="restore_operations")
