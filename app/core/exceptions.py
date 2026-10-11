import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.metrics import DB_ERRORS

log = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str = "Bad request.", code: str | None = None,
                 status_code: int | None = None, details: object | None = None,
                 headers: dict[str, str] | None = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details
        self.headers = headers


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class AuthenticationError(AppError):
    status_code = 401
    code = "UNAUTHENTICATED"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"


class AIProviderError(AppError):
    status_code = 502
    code = "AI_PROVIDER_ERROR"


class ToolArgumentError(AppError):
    status_code = 422
    code = "INVALID_TOOL_ARGUMENTS"


def not_found(entity: str) -> NotFoundError:
    return NotFoundError(f"{entity} not found.", code=f"{entity.upper().replace(' ', '_')}_NOT_FOUND")


def _body(code: str, message: str, details: object | None = None) -> dict:
    err: dict = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return {"error": err}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(_body(exc.code, exc.message, exc.details), status_code=exc.status_code,
                            headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [{"loc": [str(p) for p in e["loc"]], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(_body("VALIDATION_ERROR", "Request validation failed.", details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(
            exc.status_code, "HTTP_ERROR")
        return JSONResponse(_body(code, str(exc.detail)), status_code=exc.status_code,
                            headers=getattr(exc, "headers", None))

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError):
        DB_ERRORS.inc()
        log.warning("integrity error", extra={"error": type(exc.orig).__name__})
        return JSONResponse(_body("DUPLICATE_RESOURCE", "Resource already exists or violates a constraint."),
                            status_code=409)

    @app.exception_handler(SQLAlchemyError)
    async def _db(_: Request, exc: SQLAlchemyError):
        DB_ERRORS.inc()
        log.exception("database error")
        return JSONResponse(_body("DATABASE_ERROR", "A database error occurred."), status_code=500)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled error")
        msg = f"{type(exc).__name__}: {exc}" if get_settings().DEBUG else "Internal server error."
        return JSONResponse(_body("INTERNAL_ERROR", msg), status_code=500)
