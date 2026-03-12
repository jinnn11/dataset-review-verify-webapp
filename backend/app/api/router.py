from fastapi import APIRouter

from app.api import auth, files, ingest, media, progress, review

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(review.router)
api_router.include_router(files.router)
api_router.include_router(progress.router)
api_router.include_router(media.router)
api_router.include_router(ingest.router)
