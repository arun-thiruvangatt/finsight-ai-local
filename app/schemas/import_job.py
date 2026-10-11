from datetime import datetime

from app.schemas.common import ORMModel


class ImportJobRead(ORMModel):
    id: int
    account_id: int
    filename: str
    status: str
    total_rows: int
    processed_rows: int
    successful_rows: int
    failed_rows: int
    duplicate_rows: int
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
