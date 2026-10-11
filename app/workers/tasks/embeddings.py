from sqlmodel import Session

from app.ai import rag
from app.db.engine import engine
from app.workers.celery_app import celery_app


@celery_app.task(name="finsight.generate_embeddings", bind=True, max_retries=2, default_retry_delay=15)
def generate_embeddings(self, document_id: int) -> int:
    with Session(engine) as session:
        return rag.ingest_document(session, document_id)
