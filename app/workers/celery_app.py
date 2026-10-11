import logging

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_failure

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.metrics import CELERY_FAILURES

settings = get_settings()
setup_logging(settings.DEBUG)
log = logging.getLogger(__name__)

celery_app = Celery(
    "finsight", broker=settings.REDIS_URL, backend=settings.REDIS_URL,
    include=[
        "app.workers.tasks.imports", "app.workers.tasks.categorization", "app.workers.tasks.embeddings",
        "app.workers.tasks.insights", "app.workers.tasks.anomaly_detection",
        "app.workers.tasks.recurring_detection", "app.workers.tasks.maintenance",
    ],
)
celery_app.conf.update(
    task_serializer="json", result_serializer="json", accept_content=["json"],
    result_expires=3600, task_track_started=True, task_acks_late=True, worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True, timezone="UTC", enable_utc=True,
    beat_schedule={
        "detect-recurring-nightly": {"task": "finsight.detect_recurring_transactions", "schedule": crontab(hour=1, minute=0)},
        "detect-anomalies-nightly": {"task": "finsight.detect_anomalies", "schedule": crontab(hour=1, minute=30)},
        "monthly-insights-daily": {"task": "finsight.generate_monthly_insights", "schedule": crontab(hour=2, minute=0)},
        "cleanup-daily": {"task": "finsight.cleanup_expired_data", "schedule": crontab(hour=3, minute=0)},
    },
)


@task_failure.connect
def _on_task_failure(sender=None, exception=None, **_):
    name = getattr(sender, "name", "unknown")
    CELERY_FAILURES.labels(name).inc()
    log.error("celery task failed", extra={"task": name, "error": type(exception).__name__})
