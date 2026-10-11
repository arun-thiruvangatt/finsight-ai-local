from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.schemas.common import Message
from app.schemas.insight import InsightRead
from app.services import anomaly_service, insight_service, recurring_service
from app.utils.serialization import to_jsonable
from app.workers.dispatch import enqueue
from app.workers.tasks.anomaly_detection import detect_anomalies
from app.workers.tasks.insights import generate_monthly_insights
from app.workers.tasks.recurring_detection import detect_recurring_transactions

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("", response_model=list[InsightRead], summary="Generated insights (non-expired)")
def list_insights(user: CurrentUser, session: SessionDep, limit: int = 50):
    return insight_service.list_insights(session, user.id, min(limit, 100))


@router.post("/refresh", response_model=Message, status_code=202,
             summary="Re-run recurring + anomaly detection and insight generation in the background")
def refresh(user: CurrentUser):
    enqueue(detect_recurring_transactions, user.id)
    enqueue(detect_anomalies, user.id)
    enqueue(generate_monthly_insights, user.id)
    return Message(message="Analysis queued.")


@router.get("/recurring", summary="Detected recurring expenses")
def recurring(user: CurrentUser, session: SessionDep):
    return to_jsonable(recurring_service.list_recurring(session, user.id, active_only=False))


@router.get("/anomalies", summary="Transactions flagged as unusual")
def anomalies(user: CurrentUser, session: SessionDep, limit: int = 50, days: int = 90):
    return to_jsonable(anomaly_service.list_anomalies(session, user.id, min(limit, 200), min(days, 365)))
