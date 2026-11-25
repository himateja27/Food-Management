from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.orders import BusinessRuleError
from app.services.auth import RegistrationConflict


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID", str(uuid4()))[:100]
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response


def _error(request: Request, code: str, message: str, status_code: int, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "request_id": getattr(request.state, "request_id", "unknown")},
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(BusinessRuleError)
    async def business_error_handler(request: Request, exc: BusinessRuleError) -> JSONResponse:
        return _error(request, exc.code, exc.message, exc.status_code)

    @app.exception_handler(RegistrationConflict)
    async def registration_conflict_handler(request: Request, exc: RegistrationConflict) -> JSONResponse:
        return _error(request, "EMAIL_ALREADY_REGISTERED", str(exc), 409)

    @app.exception_handler(LookupError)
    async def not_found_handler(request: Request, _: LookupError) -> JSONResponse:
        return _error(request, "NOT_FOUND", "The requested resource was not found", 404)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, _: RequestValidationError) -> JSONResponse:
        return _error(request, "VALIDATION_ERROR", "Request validation failed", 422)

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "Request could not be completed"
        code = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT", 429: "RATE_LIMITED"}.get(exc.status_code, "HTTP_ERROR")
        return _error(request, code, detail, exc.status_code, exc.headers)

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, _: IntegrityError) -> JSONResponse:
        return _error(request, "CONFLICT", "The request conflicts with current data", 409)

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, _: Exception) -> JSONResponse:
        return _error(request, "INTERNAL_ERROR", "An unexpected error occurred", 500)
