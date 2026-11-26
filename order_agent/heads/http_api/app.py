"""The HTTP head: a thin FastAPI adapter over CallController (contracts/http-api.md)."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from order_agent.heads.http_api.store import (
    NotFound,
    ReportNotReady,
    SessionClosed,
    SessionStore,
    TooManySessions,
)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def create_app(
    reports_dir: Path,
    brief_dir: Path = Path("briefs"),
    clock: Callable[[], datetime] = datetime.now,
) -> FastAPI:
    app = FastAPI(title="Order agent HTTP head")
    app.state.store = SessionStore()
    app.state.reports_dir = reports_dir
    app.state.brief_dir = brief_dir
    app.state.clock = clock

    @app.exception_handler(NotFound)
    async def _not_found(request: Request, exc: NotFound):
        return _error(404, "session_not_found", str(exc))

    @app.exception_handler(SessionClosed)
    async def _closed(request: Request, exc: SessionClosed):
        return _error(409, "session_closed", str(exc))

    @app.exception_handler(ReportNotReady)
    async def _not_ready(request: Request, exc: ReportNotReady):
        return _error(409, "report_not_ready", str(exc))

    @app.exception_handler(TooManySessions)
    async def _too_many(request: Request, exc: TooManySessions):
        return _error(429, "too_many_sessions", str(exc))

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, exc: RequestValidationError):
        parts = []
        for e in exc.errors():
            where = ".".join(str(x) for x in e["loc"])
            parts.append(f"{where}: {e['msg']}")
        return _error(422, "validation_error", "; ".join(parts) or "invalid request")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app
