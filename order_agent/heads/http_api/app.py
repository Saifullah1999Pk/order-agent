"""The HTTP head: a thin FastAPI adapter over CallController (contracts/http-api.md)."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from order_agent.heads.http_api.schemas import SessionCreated, SessionInfo, StartSession, ToolInfo
from order_agent.heads.http_api.store import (
    NotFound,
    ReportNotReady,
    SessionClosed,
    SessionStore,
    TooManySessions,
)
from order_agent.model.brief import OrderBrief, load_brief


class InvalidBrief(Exception):
    pass


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

    @app.exception_handler(InvalidBrief)
    async def _bad_brief(request: Request, exc: InvalidBrief):
        return _error(422, "validation_error", str(exc))

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

    def _load_named_brief(name: str) -> OrderBrief:
        path = brief_dir / f"{name}.yaml"
        if not path.is_file():
            raise InvalidBrief(f"Unknown brief_name {name!r}.")
        try:
            return load_brief(path)
        except Exception as exc:  # noqa: BLE001 - bad YAML or a brief that fails validation
            raise InvalidBrief(f"Brief {name!r} is not a valid brief: {exc}") from None

    @app.post("/sessions", status_code=201)
    async def start_session(body: StartSession) -> SessionCreated:
        brief = body.brief if body.brief is not None else _load_named_brief(body.brief_name)
        if body.call_time is not None:
            brief = brief.model_copy(update={"call_time": body.call_time})
        store: SessionStore = app.state.store
        # One reports folder per session: report files are named by start second, so two
        # sessions begun in the same second would otherwise overwrite each other.
        session_id, controller = store.create(
            brief, reports_dir=reports_dir, now=clock(), per_session_dir=True
        )
        return SessionCreated(
            session_id=session_id,
            instructions=controller.instructions,
            opening_text=controller.opening_text,
            tools=[
                ToolInfo(name=t.name, description=t.description, properties=t.properties, required=t.required)
                for t in controller.tool_specs()
            ],
        )

    @app.get("/sessions/{session_id}")
    async def get_session(session_id: str) -> SessionInfo:
        controller = app.state.store.get(session_id)
        return SessionInfo(
            session_id=session_id,
            state="ended" if controller.finished else "live",
            order_state=controller.session.state,
            transcript_lines=len(controller.transcript),
            report_ready=controller.report is not None,
        )

    return app
