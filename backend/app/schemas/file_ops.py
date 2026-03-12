from datetime import datetime

from pydantic import BaseModel


class DeletionOperationResponse(BaseModel):
    operation_id: int
    image_id: int
    source_path: str
    trash_path: str
    restored_by: int | None = None
    executed_at: datetime
    restored_at: datetime | None = None
