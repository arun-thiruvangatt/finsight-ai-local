from pydantic import Field
from sqlmodel import Session

from app.ai.tools.base import ToolArgs, register
from app.services import anomaly_service


class AnomalyArgs(ToolArgs):
    limit: int = Field(default=10, ge=1, le=50)
    days: int = Field(default=90, ge=1, le=365)


@register("get_anomalies", "Transactions flagged as unusual by the statistical detector, with score and reason.",
          AnomalyArgs)
def get_anomalies(session: Session, user_id: int, a: AnomalyArgs):
    return {"anomalies": anomaly_service.list_anomalies(session, user_id, a.limit, a.days)}
