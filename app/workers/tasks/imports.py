from sqlmodel import Session

from app.db.engine import engine
from app.services import import_service
from app.workers.celery_app import celery_app


@celery_app.task(name="finsight.process_csv_import", bind=True, max_retries=2, default_retry_delay=10)
def process_csv_import(self, job_id: int) -> dict:
    with Session(engine) as session:
        job = import_service.run_import(session, job_id)
        result = {"job_id": job.id, "status": job.status, "successful": job.successful_rows,
                  "duplicates": job.duplicate_rows, "failed": job.failed_rows}
        user_id, imported = job.user_id, job.successful_rows
    if imported:  # follow-up pipeline stages
        from app.workers.dispatch import enqueue
        from app.workers.tasks.anomaly_detection import detect_anomalies
        from app.workers.tasks.categorization import categorize_transactions
        from app.workers.tasks.recurring_detection import detect_recurring_transactions
        enqueue(categorize_transactions, user_id, None)
        enqueue(detect_recurring_transactions, user_id)
        enqueue(detect_anomalies, user_id)
    return result
