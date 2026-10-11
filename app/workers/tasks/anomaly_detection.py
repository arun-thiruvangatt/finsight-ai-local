from sqlmodel import Session

from app.db.engine import engine
from app.services import anomaly_service
from app.workers.celery_app import celery_app
from app.workers.tasks._common import user_ids


@celery_app.task(name="finsight.detect_anomalies")
def detect_anomalies(user_id: int | None = None) -> dict:
    flagged = 0
    with Session(engine) as session:
        for uid in user_ids(session, user_id):
            flagged += len(anomaly_service.detect_anomalies(session, uid))
    return {"flagged": flagged}
