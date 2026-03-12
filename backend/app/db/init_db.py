from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import engine
from app.models import (  # noqa: F401
    DeletionOperation,
    GeneratedImage,
    IngestionRun,
    MaskGroup,
    ReviewDecision,
)
from app.models import User, UserRole


def _apply_schema_upgrades() -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "deletion_operations" not in inspector.get_table_names():
            return

        columns = {column["name"] for column in inspector.get_columns("deletion_operations")}
        if "restored_by" not in columns:
            if connection.dialect.name == "postgresql":
                connection.execute(
                    text("ALTER TABLE deletion_operations ADD COLUMN restored_by INTEGER REFERENCES users(id)")
                )
            else:
                connection.execute(text("ALTER TABLE deletion_operations ADD COLUMN restored_by INTEGER"))

        indexes = {index["name"] for index in inspector.get_indexes("deletion_operations")}
        if "ix_deletion_operations_restored_by" not in indexes:
            connection.execute(
                text("CREATE INDEX ix_deletion_operations_restored_by ON deletion_operations (restored_by)")
            )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _apply_schema_upgrades()

    with Session(engine) as db:
        existing_admin = db.scalar(select(User).where(User.username == settings.admin_username))
        if existing_admin:
            return

        admin = User(
            username=settings.admin_username,
            password_hash=hash_password(settings.admin_password),
            role=UserRole.admin,
        )
        db.add(admin)
        db.commit()
