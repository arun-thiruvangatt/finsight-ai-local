"""Conversation history. Kept separate from financial calculations: history is only used for
conversational context, every number shown is recomputed by tools."""
from sqlalchemy import select
from sqlmodel import Session

from app.core.exceptions import not_found
from app.db.models import Conversation, ConversationMessage
from app.services.common import get_owned


def get_or_create(session: Session, user_id: int, conversation_id: int | None, title: str) -> Conversation:
    if conversation_id is not None:
        return get_owned(session, Conversation, conversation_id, user_id, "Conversation")
    conv = Conversation(user_id=user_id, title=title[:80] or "New conversation")
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return conv


def add_message(session: Session, conversation_id: int, role: str, content: str, meta: dict | None = None) -> None:
    session.add(ConversationMessage(conversation_id=conversation_id, role=role, content=content, meta=meta or {}))
    session.commit()


def history(session: Session, conversation_id: int, limit: int = 8) -> list[dict]:
    rows = session.execute(select(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id)
                           .order_by(ConversationMessage.id.desc()).limit(limit)).scalars().all()
    return [{"role": r.role, "content": r.content} for r in reversed(rows)]


def list_conversations(session: Session, user_id: int) -> list[Conversation]:
    return list(session.execute(select(Conversation).where(Conversation.user_id == user_id)
                                .order_by(Conversation.id.desc()).limit(50)).scalars())


def list_messages(session: Session, user_id: int, conversation_id: int) -> list[ConversationMessage]:
    conv = get_owned(session, Conversation, conversation_id, user_id, "Conversation")
    if conv is None:
        raise not_found("Conversation")
    return list(session.execute(select(ConversationMessage).where(ConversationMessage.conversation_id == conv.id)
                                .order_by(ConversationMessage.id)).scalars())
