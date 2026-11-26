"""The HTTP head: a thin FastAPI adapter over CallController (contracts/http-api.md)."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from order_agent.heads.http_api.schemas import (
    ActionRequest,
    ActionResult,
    EndRequest,
    ReportResponse,
    SessionCreated,
    SessionInfo,
    TranscriptRequest,
    StartSession,
    ToolInfo,
)
from order_agent.heads.http_api.store import (
    NotFound,
    ReportNotReady,
    SessionClosed,
    SessionStore,
    TooManySessions,
)
from order_agent.model.brief import OrderBrief, load_brief
from order_agent.model.report import summarise


class InvalidRequest(Exception):
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

    @app.exception_handler(InvalidRequest)
    async def _bad_brief(request: Request, exc: InvalidRequest):
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
            raise InvalidRequest(f"Unknown brief_name {name!r}.")
        try:
            return load_brief(path)
        except Exception as exc:  # noqa: BLE001 - bad YAML or a brief that fails validation
            raise InvalidRequest(f"Brief {name!r} is not a valid brief: {exc}") from None

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

    def _live(session_id: str):
        controller = app.state.store.get(session_id)
        if controller.finished or controller.session.state == "ended":
            raise SessionClosed(f"Session {session_id} has already ended.")
        return controller

    @app.post("/sessions/{session_id}/actions")
    async def act(session_id: str, body: ActionRequest) -> ActionResult:
        store: SessionStore = app.state.store
        controller = _live(session_id)
        if body.tool not in {spec.name for spec in controller.tool_specs()}:
            raise InvalidRequest(f"Unknown tool {body.tool!r}.")
        async with store.lock(session_id):
            if controller.finished:  # another request ended the call while this one waited
                raise SessionClosed(f"Session {session_id} has already ended.")
            outcome = await controller.perform(body.tool, body.arguments)
        return ActionResult(ok=outcome.ok, message=outcome.message, ended=outcome.ended)

    @app.post("/sessions/{session_id}/transcript", status_code=204)
    async def add_transcript(session_id: str, body: TranscriptRequest) -> Response:
        _live(session_id).add_line(body.role, body.text)
        return Response(status_code=204)

    def _report_response(controller) -> ReportResponse:
        if controller.report is None or controller.report_path is None:
            raise ReportNotReady("The call is still live; there is no report yet.")
        return ReportResponse(
            report=controller.report,
            summary=summarise(controller.report),
            report_path=controller.report_path.relative_to(reports_dir).as_posix(),
        )

    @app.post("/sessions/{session_id}/end")
    async def end_session(session_id: str, body: EndRequest | None = None) -> ReportResponse:
        store: SessionStore = app.state.store
        controller = store.get(session_id)
        async with store.lock(session_id):
            await controller.drop()  # returns the existing report if the call already ended
        return _report_response(controller)

    @app.get("/sessions/{session_id}/report")
    async def get_report(session_id: str) -> ReportResponse:
        return _report_response(app.state.store.get(session_id))

    @app.delete("/sessions/{session_id}", status_code=204)
    async def delete_session(session_id: str) -> Response:
        store: SessionStore = app.state.store
        controller = store.get(session_id)
        async with store.lock(session_id):
            await controller.drop()  # a live call is finished as call_dropped, so no report is lost
        store.delete(session_id)
        return Response(status_code=204)

    return app
