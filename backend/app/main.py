from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_dataset_config, settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.ingestion import run_ingestion

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://localhost", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        init_db()
        if settings.auto_ingest_on_startup:
            try:
                with SessionLocal() as db:
                    result = run_ingestion(db, get_dataset_config())
                logger.info(
                    "Auto-ingest complete: files_scanned=%s errors_count=%s run_id=%s",
                    result.files_scanned,
                    result.errors_count,
                    result.id,
                )
            except Exception:  # noqa: BLE001
                logger.exception("Auto-ingest failed at startup; continuing server boot")

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)
    return app


app = create_app()
