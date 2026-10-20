import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep, rate_limit
from app.core.config import get_settings
from app.core.constants import ALLOWED_UPLOAD_EXT_CSV
from app.core.exceptions import AppError, not_found
from app.db.models import Account, ImportJob
from app.schemas.import_job import ImportJobRead
from app.services import import_service
from app.services.common import get_owned
from app.utils.csv_parser import CANONICAL
from app.utils.validators import looks_binary, unique_storage_name, validate_upload
from app.workers.dispatch import enqueue
from app.workers.tasks.imports import process_csv_import

router = APIRouter(prefix="/imports", tags=["Imports"])


@router.post(
    "/csv",
    response_model=ImportJobRead,
    status_code=202,
    summary="Upload a CSV; processed in the background",
    dependencies=[Depends(rate_limit("import", "RATE_LIMIT_UPLOAD_PER_MINUTE"))],
)
def upload_csv(
    user: CurrentUser,
    session: SessionDep,
    file: UploadFile = File(...),
    account_id: int = Form(...),
    column_mapping: str | None = Form(
        default=None, description='JSON, e.g. {"date":"Txn Date","amount":"Amt"}'
    ),
):
    s = get_settings()
    get_owned(session, Account, account_id, user.id, "Account")
    mapping: dict[str, str] = {}
    if column_mapping:
        try:
            mapping = json.loads(column_mapping)
            assert isinstance(mapping, dict) and set(mapping) <= set(CANONICAL)
        except (ValueError, AssertionError) as exc:
            raise AppError(
                f"column_mapping must be a JSON object with keys from {list(CANONICAL)}.",
                code="INVALID_MAPPING",
            ) from exc
    content = file.file.read(
        s.max_upload_bytes + 1
    )  # bounded read: never buffer more than limit+1 bytes
    validate_upload(
        file.filename or "", len(content), ALLOWED_UPLOAD_EXT_CSV, s.max_upload_bytes
    )
    if looks_binary(content[:4096]):
        raise AppError("File does not look like a text CSV.", code="INVALID_CSV")
    folder = Path(s.UPLOAD_DIR) / "imports" / str(user.id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / unique_storage_name(file.filename or "upload.csv")
    path.write_bytes(content)
    job = import_service.create_job(
        session, user.id, account_id, file.filename or path.name, str(path), mapping
    )
    enqueue(process_csv_import, job.id)
    session.refresh(job)
    return job


@router.get("", response_model=list[ImportJobRead], summary="List my import jobs")
def list_jobs(user: CurrentUser, session: SessionDep):
    q = (
        select(ImportJob)
        .where(ImportJob.user_id == user.id)
        .order_by(ImportJob.id.desc())
        .limit(50)
    )
    return list(session.execute(q).scalars())


@router.get(
    "/{job_id}", response_model=ImportJobRead, summary="Import job status / progress"
)
def get_job(job_id: int, user: CurrentUser, session: SessionDep):
    job = session.get(ImportJob, job_id)
    if job is None or job.user_id != user.id:
        raise not_found("Import job")
    return job
