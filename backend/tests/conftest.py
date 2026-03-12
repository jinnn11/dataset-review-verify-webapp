from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.api.router import api_router
from app.core.config import get_dataset_config, settings
from app.core.security import hash_password
from app.db.base import Base
from app.models.deletion_operation import DeletionOperation  # noqa: F401
from app.models.generated_image import GeneratedImage
from app.models.ingestion_run import IngestionRun  # noqa: F401
from app.models.mask_group import MaskGroup
from app.models.review_decision import ReviewDecision  # noqa: F401
from app.models.user import User, UserRole


@pytest.fixture()
def dataset_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "data"
    masks = root / "masks"
    generated = root / "generated"
    trash = root / ".trash"
    masks.mkdir(parents=True, exist_ok=True)
    generated.mkdir(parents=True, exist_ok=True)
    trash.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DATASET_ROOT_DIR", str(root))
    monkeypatch.setenv("DATASET_MASKS_DIR", "masks")
    monkeypatch.setenv("DATASET_GENERATED_DIR", "generated")
    monkeypatch.setenv("DATASET_TRASH_DIR", ".trash")
    monkeypatch.setattr(settings, "session_cookie_secure", False)
    get_dataset_config.cache_clear()
    return root


@pytest.fixture()
def client(dataset_root: Path) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    (dataset_root / "masks" / "alpha_mask.png").write_bytes(b"mask-alpha")
    (dataset_root / "masks" / "beta_mask.png").write_bytes(b"mask-beta")
    (dataset_root / "generated" / "alpha_gen_1.png").write_bytes(b"img-alpha-1")
    (dataset_root / "generated" / "alpha_gen_2.png").write_bytes(b"img-alpha-2")
    (dataset_root / "generated" / "beta_gen_1.png").write_bytes(b"img-beta-1")

    with Session(engine) as db:
        user = User(username="reviewer", password_hash=hash_password("pass123"), role=UserRole.reviewer)
        admin = User(username="admin", password_hash=hash_password("pass123"), role=UserRole.admin)
        db.add_all([user, admin])
        db.flush()

        group1 = MaskGroup(group_key="alpha", mask_path=str((dataset_root / "masks" / "alpha_mask.png").resolve()))
        group2 = MaskGroup(group_key="beta", mask_path=str((dataset_root / "masks" / "beta_mask.png").resolve()))
        db.add_all([group1, group2])
        db.flush()

        db.add_all(
            [
                GeneratedImage(group_id=group1.id, image_path=str((dataset_root / "generated" / "alpha_gen_1.png").resolve())),
                GeneratedImage(group_id=group1.id, image_path=str((dataset_root / "generated" / "alpha_gen_2.png").resolve())),
                GeneratedImage(group_id=group2.id, image_path=str((dataset_root / "generated" / "beta_gen_1.png").resolve())),
            ]
        )
        db.commit()

    app = FastAPI()
    app.include_router(api_router)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    get_dataset_config.cache_clear()
