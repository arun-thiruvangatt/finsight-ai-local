import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlmodel import Session

from app.core.constants import ImportStatus
from app.db.engine import engine
from app.db.models import AIInsight, ImportJob, RefreshToken
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="finsight.cleanup_expired_data")
def cleanup_expired_data() -> dict:
    now = datetime.now(UTC)
    with Session(engine) as session:
        insights = session.execute(delete(AIInsight).where(AIInsight.expires_at < now)).rowcount
        tokens = session.execute(delete(RefreshToken).where(
            (RefreshToken.expires_at < now) | (RefreshToken.revoked == True))).rowcount  # noqa: E712
        files = 0
        old = session.execute(select(ImportJob).where(
            ImportJob.completed_at < now - timedelta(days=7),
            ImportJob.status.in_([ImportStatus.COMPLETED.value, ImportStatus.PARTIAL.value,
                                  ImportStatus.FAILED.value]))).scalars().all()
        for job in old:
            p = Path(job.storage_path)
            if p.exists():
                p.unlink(missing_ok=True)
                files += 1
        session.commit()
    log.info("cleanup done", extra={"task": "cleanup_expired_data"})
    return {"insights": insights, "refresh_tokens": tokens, "files": files}
