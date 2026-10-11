from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep, rate_limit
from app.core.config import get_settings
from app.core.constants import ALLOWED_UPLOAD_EXT_DOC, DocumentType
from app.core.exceptions import AppError
from app.db.models import Document
from app.schemas.document import DocumentRead
from app.services.common import get_owned
from app.utils.validators import (
    looks_binary,
    safe_filename,
    unique_storage_name,
    validate_upload,
)
from app.workers.dispatch import enqueue
from app.workers.tasks.embeddings import generate_embeddings

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "",
    response_model=DocumentRead,
    status_code=202,
    summary="Upload a document for RAG (txt, md, pdf)",
    dependencies=[Depends(rate_limit("document", "RATE_LIMIT_UPLOAD_PER_MINUTE"))],
)
def upload_document(
    user: CurrentUser,
    session: SessionDep,
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=255),
    doc_type: DocumentType = Form(default=DocumentType.NOTE),
):
    s = get_settings()
    content = file.file.read(s.max_upload_bytes + 1)
    ext = validate_upload(
        file.filename or "", len(content), ALLOWED_UPLOAD_EXT_DOC, s.max_upload_bytes
    )
    if ext == ".pdf" and not content.startswith(b"%PDF"):
        raise AppError("File is not a valid PDF.", code="INVALID_DOCUMENT")
    if ext != ".pdf" and looks_binary(content[:4096]):
        raise AppError("File does not look like text.", code="INVALID_DOCUMENT")
    folder = Path(s.UPLOAD_DIR) / "documents" / str(user.id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / unique_storage_name(file.filename or "document.txt")
    path.write_bytes(content)
    name = safe_filename(file.filename or "document")
    doc = Document(
        user_id=user.id,
        title=(title or name)[:255],
        filename=name,
        doc_type=doc_type.value,
        storage_path=str(path),
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    enqueue(generate_embeddings, doc.id)
    session.refresh(doc)
    return doc


@router.get("", response_model=list[DocumentRead], summary="List my documents")
def list_documents(user: CurrentUser, session: SessionDep):
    q = select(Document).where(Document.user_id == user.id).order_by(Document.id.desc())
    return list(session.execute(q).scalars())


@router.delete(
    "/{document_id}", status_code=204, summary="Delete a document and its vectors"
)
def delete_document(document_id: int, user: CurrentUser, session: SessionDep):
    doc = get_owned(session, Document, document_id, user.id, "Document")
    Path(doc.storage_path).unlink(missing_ok=True)
    session.delete(doc)  # chunks are removed by ON DELETE CASCADE
    session.commit()
    return Response(status_code=204)
