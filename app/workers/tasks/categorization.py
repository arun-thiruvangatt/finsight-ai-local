from sqlmodel import Session

from app.core.config import get_settings
from app.db.engine import engine
from app.services import categorization_service
from app.workers.celery_app import celery_app


@celery_app.task(name="finsight.categorize_transactions")
def categorize_transactions(user_id: int, tx_ids: list[int] | None = None) -> dict:
    with Session(engine) as session:
        return categorization_service.categorize_transactions(
            session, user_id, tx_ids, use_llm=get_settings().AUTO_CATEGORIZE_WITH_LLM)
