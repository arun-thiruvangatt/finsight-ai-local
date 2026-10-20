from fastapi import APIRouter, Depends

from app.ai import memory, orchestrator, rag
from app.api.deps import CurrentUser, SessionDep, rate_limit
from app.core.constants import AI_DISCLAIMER
from app.schemas.ai import (
    AskRequest,
    AskResponse,
    ConversationRead,
    MessageRead,
    SearchHit,
    SearchRequest,
)
from app.utils.serialization import to_jsonable

router = APIRouter(prefix="/ai", tags=["AI"])
ai_limit = Depends(rate_limit("ai", "RATE_LIMIT_AI_PER_MINUTE"))


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask a natural-language question about your finances",
    dependencies=[ai_limit],
)
async def ask(body: AskRequest, user: CurrentUser, session: SessionDep):
    result = await orchestrator.ask(
        session, user.id, body.question, body.conversation_id
    )
    return AskResponse(
        answer=result.answer,
        tools_used=result.tools_used,
        data=to_jsonable(result.data),
        conversation_id=result.conversation_id,
        source=result.source,
        disclaimer=AI_DISCLAIMER,
        unverified_numbers=result.unverified_numbers,
    )


@router.post(
    "/search",
    response_model=list[SearchHit],
    summary="Semantic search over your documents",
    dependencies=[ai_limit],
)
async def search(body: SearchRequest, user: CurrentUser, session: SessionDep):
    return await rag.search(session, user.id, body.query, body.k)


@router.get(
    "/conversations", response_model=list[ConversationRead], summary="My conversations"
)
def conversations(user: CurrentUser, session: SessionDep):
    return memory.list_conversations(session, user.id)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageRead],
    summary="Messages of one conversation",
)
def conversation_messages(conversation_id: int, user: CurrentUser, session: SessionDep):
    return memory.list_messages(session, user.id, conversation_id)
