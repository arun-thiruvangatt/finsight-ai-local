from pydantic import Field
from sqlmodel import Session

from app.ai import rag
from app.ai.tools.base import ToolArgs, register


class SearchDocsArgs(ToolArgs):
    query: str = Field(min_length=2, max_length=500)
    k: int = Field(default=4, ge=1, le=10)


@register("search_documents", "Semantic search over the user's own uploaded documents and notes (insurance, loans, "
                              "financial plans). Use for questions about document content, not for numbers in transactions.",
          SearchDocsArgs)
def search_documents(session: Session, user_id: int, a: SearchDocsArgs):
    return {"matches": rag.search_sync(session, user_id, a.query, a.k)}
