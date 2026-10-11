from sqlmodel import Session

from app.db.engine import engine
from app.services import insight_service
from app.workers.celery_app import celery_app
from app.workers.tasks._common import user_ids


@celery_app.task(name="finsight.generate_monthly_insights")
def generate_monthly_insights(user_id: int | None = None) -> dict:
    created = 0
    with Session(engine) as session:
        for uid in user_ids(session, user_id):
            created += insight_service.generate_monthly_insights(session, uid)
    return {"created": created}
