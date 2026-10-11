from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.services import budget_service, insight_service

router = APIRouter(prefix="/notifications", tags=["Insights"])


class Notification(BaseModel):
    kind: str
    severity: str
    title: str
    message: str
    created_at: datetime | None = None


@router.get("", response_model=list[Notification], summary="Live alerts: budget warnings and important insights")
def notifications(user: CurrentUser, session: SessionDep):
    out: list[Notification] = []
    for st in budget_service.all_statuses(session, user.id):
        if st["warnings"]:
            out.append(Notification(kind="BUDGET_WARNING",
                                    severity="CRITICAL" if st["spent"] > st["budget"] else "WARNING",
                                    title=f"Budget: {st['name']}", message=" ".join(st["warnings"])))
    cutoff = datetime.now(UTC) - timedelta(days=14)
    for i in insight_service.list_insights(session, user.id, 50):
        if i.severity in {"WARNING", "CRITICAL"} and i.generated_at >= cutoff and i.insight_type != "BUDGET_WARNING":
            out.append(Notification(kind=i.insight_type, severity=i.severity, title=i.title,
                                    message=i.description, created_at=i.generated_at))
    return out[:20]
