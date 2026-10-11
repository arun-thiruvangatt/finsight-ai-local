from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    conversation_id: int | None = None

    model_config = {"json_schema_extra": {"example": {"question": "How much did I spend on food last month?"}}}


class AskResponse(BaseModel):
    answer: str
    tools_used: list[str]
    data: dict
    conversation_id: int
    source: str = Field(description="'llm' when a language model composed the answer, 'rules' when deterministic.")
    disclaimer: str
    unverified_numbers: list[str] = []


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    k: int = Field(default=5, ge=1, le=20)


class SearchHit(BaseModel):
    document_id: int
    document_title: str
    chunk_index: int
    content: str
    score: float


class ConversationRead(ORMModel):
    id: int
    title: str
    created_at: datetime


class MessageRead(ORMModel):
    id: int
    role: str
    content: str
    meta: dict
    created_at: datetime
