from datetime import datetime

from app.schemas.common import ORMModel


class InsightRead(ORMModel):
    id: int
    insight_type: str
    title: str
    description: str
    severity: str
    data: dict
    generated_at: datetime
    expires_at: datetime | None
