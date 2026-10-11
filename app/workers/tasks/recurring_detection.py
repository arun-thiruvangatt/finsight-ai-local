from sqlmodel import Session

from app.db.engine import engine
from app.services import recurring_service
from app.workers.celery_app import celery_app
from app.workers.tasks._common import user_ids


@celery_app.task(name="finsight.detect_recurring_transactions")
def detect_recurring_transactions(user_id: int | None = None) -> dict:
    found = 0
    with Session(engine) as session:
        for uid in user_ids(session, user_id):
            found += len(recurring_service.detect_recurring(session, uid))
    return {"detected": found}
