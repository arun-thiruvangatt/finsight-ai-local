from datetime import datetime

from app.schemas.common import ORMModel


class DocumentRead(ORMModel):
    id: int
    title: str
    filename: str
    doc_type: str
    status: str
    chunk_count: int
    error_message: str | None
    created_at: datetime
