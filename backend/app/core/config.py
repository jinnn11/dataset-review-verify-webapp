from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    app_name: str = "Dataset Review Tool"
    environment: str = "dev"
    secret_key: str = "change-me"
    database_url: str = "postgresql+psycopg2://review:review@postgres:5432/review_db"
    session_cookie_name: str = "review_session"
    session_cookie_secure: bool = False
    session_max_age_seconds: int = 60 * 60 * 8
    csrf_header_name: str = "X-CSRF-Token"
    enable_soft_delete: bool = False
    auto_ingest_on_startup: bool = True
    app_config_path: str = "/app/app_config.yaml"
    admin_username: str = "admin"
    admin_password: str = "change-admin-password"


class DatasetConfig(BaseSettings):
    root_dir: str = "/data"
    masks_dir: str = "masks"
    generated_dir: str = "generated"
    trash_dir: str = ".trash"
    mask_regex: str = r"^(?P<group_key>.+)_mask\.(png|jpg|jpeg|webp)$"
    generated_regex: str = r"^(?P<group_key>.+)_gen_[0-9]+\.(png|jpg|jpeg|webp)$"
    allowed_extensions: list[str] = [".png", ".jpg", ".jpeg", ".webp"]

    @property
    def root_path(self) -> Path:
        return Path(self.root_dir).resolve()

    @property
    def masks_path(self) -> Path:
        return (self.root_path / self.masks_dir).resolve()

    @property
    def generated_path(self) -> Path:
        return (self.root_path / self.generated_dir).resolve()

    @property
    def trash_path(self) -> Path:
        return (self.root_path / self.trash_dir).resolve()


settings = Settings()


@lru_cache(maxsize=1)
def get_dataset_config() -> DatasetConfig:
    cfg_path = Path(settings.app_config_path)
    if not cfg_path.exists():
        local_fallback = Path(__file__).resolve().parents[3] / "app_config.yaml"
        cfg_path = local_fallback if local_fallback.exists() else cfg_path

    content: dict[str, Any] = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text()) or {}
        content = raw.get("dataset", raw)

    env_override = {
        "root_dir": os.getenv("DATASET_ROOT_DIR"),
        "masks_dir": os.getenv("DATASET_MASKS_DIR"),
        "generated_dir": os.getenv("DATASET_GENERATED_DIR"),
        "trash_dir": os.getenv("DATASET_TRASH_DIR"),
        "mask_regex": os.getenv("DATASET_MASK_REGEX"),
        "generated_regex": os.getenv("DATASET_GENERATED_REGEX"),
    }
    for key, value in env_override.items():
        if value:
            content[key] = value

    return DatasetConfig(**content)
