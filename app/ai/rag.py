"""RAG: extract -> clean -> chunk -> embed -> pgvector; retrieval is ALWAYS filtered by user_id."""
import asyncio
import logging
import re
from pathlib import Path

from sqlalchemy import delete, select
from sqlmodel import Session

from app.ai.embeddings import get_embedder
from app.core.constants import DocumentStatus
from app.db.models import Document, DocumentChunk

log = logging.getLogger(__name__)
CHUNK_SIZE, CHUNK_OVERLAP = 900, 150


def extract_text(path: str | Path) -> str:
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        pages = PdfReader(str(p)).pages
        page_texts = [(page.extract_text() or "") for page in pages]
        pages_to_ocr = [i for i, text in enumerate(page_texts, start=1) if not text.strip()]
        if pages_to_ocr:
            try:
                import pytesseract
                from pdf2image import convert_from_path
            except ImportError as exc:
                raise RuntimeError(
                    "Scanned PDF OCR requires pdf2image, pytesseract, Poppler, and Tesseract."
                ) from exc

            for page_number in pages_to_ocr:
                images = convert_from_path(
                    str(p), dpi=200, first_page=page_number, last_page=page_number, timeout=60
                )
                if images:
                    try:
                        page_texts[page_number - 1] = pytesseract.image_to_string(
                            images[0], lang="eng", timeout=60
                        )
                    except pytesseract.TesseractNotFoundError as exc:
                        raise RuntimeError(
                            "Tesseract is required to OCR scanned PDFs. Install Tesseract and its English language data."
                        ) from exc
        return "\n\n".join(page_texts)
    return p.read_text(encoding="utf-8", errors="replace")


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)            # collapse spaces/tabs
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)  # control chars
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Paragraph-aware chunking; oversize paragraphs are split on words with overlap."""
    chunks: list[str] = []
    current = ""
    for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
        if len(para) > size:
            if current:
                chunks.append(current)
                current = ""
            words, buf = para.split(), ""
            for w in words:
                if len(buf) + len(w) + 1 > size:
                    chunks.append(buf)
                    buf = buf[-overlap:].split(" ", 1)[-1] + " " + w if overlap else w
                else:
                    buf = f"{buf} {w}".strip()
            if buf:
                current = buf
        elif len(current) + len(para) + 2 <= size:
            current = f"{current}\n\n{para}".strip()
        else:
            chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()]


def ingest_document(session: Session, document_id: int) -> int:
    """Run in a worker. Returns number of chunks stored."""
    doc = session.get(Document, document_id)
    if doc is None:
        return 0
    doc.status, doc.error_message = DocumentStatus.PROCESSING.value, None
    session.add(doc)
    session.commit()
    try:
        chunks = chunk_text(clean_text(extract_text(doc.storage_path)))
        if not chunks:
            raise ValueError("No extractable text found in document.")
        vectors = asyncio.run(get_embedder().embed(chunks))
        session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
        session.add_all([
            DocumentChunk(document_id=doc.id, user_id=doc.user_id, chunk_index=i, content=c, embedding=v,
                          meta={"title": doc.title, "doc_type": doc.doc_type})
            for i, (c, v) in enumerate(zip(chunks, vectors, strict=True))])
        doc.status, doc.chunk_count = DocumentStatus.READY.value, len(chunks)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        doc = session.get(Document, document_id)
        doc.status, doc.error_message = DocumentStatus.FAILED.value, str(exc)[:500]
        log.warning("document ingestion failed", extra={"error": type(exc).__name__})
    session.add(doc)
    session.commit()
    return doc.chunk_count


def search_chunks(session: Session, user_id: int, query_vector: list[float], k: int = 5) -> list[dict]:
    dist = DocumentChunk.embedding.cosine_distance(query_vector)
    q = (select(DocumentChunk.document_id, Document.title, DocumentChunk.chunk_index, DocumentChunk.content,
                dist.label("dist"))
         .join(Document, Document.id == DocumentChunk.document_id)
         .where(DocumentChunk.user_id == user_id, Document.user_id == user_id,  # tenant isolation
                Document.status == DocumentStatus.READY.value)
         .order_by(dist).limit(k))
    return [{"document_id": r.document_id, "document_title": r.title, "chunk_index": r.chunk_index,
             "content": r.content, "score": round(1 - float(r.dist), 4)} for r in session.execute(q).all()]


def search_sync(session: Session, user_id: int, query: str, k: int = 5) -> list[dict]:
    vec = asyncio.run(get_embedder().embed([query]))[0]
    return search_chunks(session, user_id, vec, k)


async def search(session: Session, user_id: int, query: str, k: int = 5) -> list[dict]:
    from starlette.concurrency import run_in_threadpool
    vec = (await get_embedder().embed([query]))[0]
    return await run_in_threadpool(search_chunks, session, user_id, vec, k)
