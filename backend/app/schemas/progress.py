from pydantic import BaseModel


class ProgressSummary(BaseModel):
    total_images: int
    active_images: int
    trashed_images: int
    reviewed: int
    keep: int
    delete: int
    needs_review: int
    remaining: int
