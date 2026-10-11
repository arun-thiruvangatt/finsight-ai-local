import logging

from app.core.config import get_settings
from app.core.exceptions import AppError

log = logging.getLogger(__name__)


def enqueue(task, *args) -> None:
    """Queue a Celery task (or run inline when CELERY_EAGER=true, e.g. tests / no worker)."""
    if get_settings().CELERY_EAGER:
        task.apply(args=args)
        return
    try:
        task.delay(*args)
    except Exception as exc:  # broker down etc.
        log.exception("failed to enqueue task")
        raise AppError("Background processing is temporarily unavailable.", code="QUEUE_UNAVAILABLE",
                       status_code=503) from exc
