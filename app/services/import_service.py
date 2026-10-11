import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import Session

from app.core.constants import ImportStatus
from app.core.exceptions import AppError
from app.db.models import Account, ImportJob, Transaction
from app.services import categorization_service
from app.services.transaction_service import balance_delta, make_fingerprint
from app.utils import csv_parser
from app.utils.money import ZERO

log = logging.getLogger(__name__)
MAX_ERRORS_KEPT = 20


def create_job(session: Session, user_id: int, account_id: int, filename: str, storage_path: str,
               mapping: dict[str, str]) -> ImportJob:
    job = ImportJob(user_id=user_id, account_id=account_id, filename=filename, storage_path=storage_path,
                    column_mapping=mapping, status=ImportStatus.PENDING.value)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _fail(session: Session, job: ImportJob, message: str) -> ImportJob:
    job.status = ImportStatus.FAILED.value
    job.error_message = message[:2000]
    job.completed_at = datetime.now(UTC)
    session.add(job)
    session.commit()
    return job


def run_import(session: Session, job_id: int, chunk_size: int = 500) -> ImportJob:
    """Pipeline: parse -> normalise -> validate -> de-duplicate (DB constraint) -> store -> categorise."""
    job = session.get(ImportJob, job_id)
    if job is None:
        raise AppError("Import job not found.", code="IMPORT_JOB_NOT_FOUND", status_code=404)
    job.status = ImportStatus.PROCESSING.value
    session.add(job)
    session.commit()

    account = session.get(Account, job.account_id)
    path = Path(job.storage_path)
    try:
        headers = csv_parser.read_headers(path)
        mapping = csv_parser.resolve_mapping(headers, job.column_mapping or None)
        job.total_rows = csv_parser.count_rows(path)
        session.add(job)
        session.commit()
    except (AppError, OSError, ValueError) as exc:
        return _fail(session, job, getattr(exc, "message", str(exc)))

    errors: list[str] = []
    seen: dict[str, int] = {}
    inserted_total = 0
    try:
        for chunk in csv_parser.iter_csv_chunks(path, chunk_size):
            rows, now = [], datetime.now(UTC)
            for row_no, raw in chunk:
                try:
                    p = csv_parser.parse_row(raw, mapping)
                except (ValueError, KeyError) as exc:
                    job.failed_rows += 1
                    if len(errors) < MAX_ERRORS_KEPT:
                        errors.append(f"row {row_no}: {exc}")
                    continue
                base_text = p.description or p.merchant or ""
                base = make_fingerprint(job.user_id, job.account_id, p.date, p.amount, base_text, p.reference, 0)
                n = seen.get(base, 0)
                seen[base] = n + 1
                fp = base if n == 0 else make_fingerprint(job.user_id, job.account_id, p.date, p.amount,
                                                          base_text, p.reference, n)
                rows.append({
                    "user_id": job.user_id, "account_id": job.account_id, "category_id": None,
                    "amount": p.amount, "transaction_type": p.transaction_type, "merchant": p.merchant,
                    "description": p.description, "transaction_date": p.date, "reference": p.reference,
                    "currency": account.currency if account else "INR", "is_recurring": False,
                    "is_anomaly": False, "fingerprint": fp, "import_job_id": job.id,
                    "created_at": now, "updated_at": now,
                })
            inserted = []
            if rows:
                stmt = (pg_insert(Transaction).values(rows)
                        .on_conflict_do_nothing(constraint="uq_transactions_user_fingerprint")
                        .returning(Transaction.amount, Transaction.transaction_type))
                inserted = session.execute(stmt).all()
                delta = sum((balance_delta(r.transaction_type, r.amount) for r in inserted), ZERO)
                if delta and account:
                    session.execute(update(Account).where(Account.id == account.id)
                                    .values(current_balance=Account.current_balance + delta))
            job.successful_rows += len(inserted)
            job.duplicate_rows += len(rows) - len(inserted)
            job.processed_rows += len(chunk)
            inserted_total += len(inserted)
            session.add(job)
            session.commit()  # progress is visible to polling clients after each chunk
    except Exception as exc:  # noqa: BLE001 - job must end in a terminal state
        session.rollback()
        job = session.get(ImportJob, job_id)
        log.exception("import failed")
        return _fail(session, job, f"Import aborted: {exc}")

    if inserted_total:
        categorization_service.categorize_by_rules(session, job.user_id, import_job_id=job.id)
    job.error_message = "\n".join(errors) or None
    if job.failed_rows and job.successful_rows == 0 and job.duplicate_rows == 0:
        job.status = ImportStatus.FAILED.value
    elif job.failed_rows:
        job.status = ImportStatus.PARTIAL.value
    else:
        job.status = ImportStatus.COMPLETED.value
    job.completed_at = datetime.now(UTC)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job
