from sqlalchemy import Column, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from sqlmodel import Field, SQLModel

from app.core.config import get_settings


class DocumentChunk(SQLModel, table=True):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index(
            "ix_document_chunks_embedding_hnsw", "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(
        sa_column=Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True))
    # Denormalised owner id: every vector query filters on it (tenant isolation).
    user_id: int = Field(foreign_key="users.id", index=True)
    chunk_index: int
    content: str
    embedding: list[float] = Field(sa_column=Column(Vector(get_settings().EMBEDDING_DIM), nullable=False))
    meta: dict = Field(default_factory=dict, sa_column=Column("metadata", JSONB, nullable=False, server_default="{}"))
