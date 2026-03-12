import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    reviewer = "reviewer"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.reviewer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    decisions = relationship("ReviewDecision", back_populates="reviewer")
    deletion_operations = relationship(
        "DeletionOperation",
        foreign_keys="DeletionOperation.requested_by",
        back_populates="requester",
    )
    restore_operations = relationship(
        "DeletionOperation",
        foreign_keys="DeletionOperation.restored_by",
        back_populates="restorer",
    )
