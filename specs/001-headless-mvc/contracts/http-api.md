# Contract: HTTP head (`order_agent.heads.http_api`)

Local development and demo API. Binds `127.0.0.1:8000`. No authentication, no persistence (process
memory), no LLM. JSON in and out. It is a thin adapter over `CallController` created with `hooks=None`
(no nudges or opening: the client plays the LLM).

Run: `uv run python -m order_agent.heads.http_api` (env `ORDER_REPORTS_DIR` as today; optional
`--port`). App factory: `create_app(reports_dir: Path, brief_dir: Path = Path("briefs"), clock=datetime.now)`.

## Endpoints

### `GET /health`
`200 {"status": "ok"}`.

### `POST /sessions`
Start a call from a brief. Body (exactly one of the two brief fields):
```json
{ "brief": { ...OrderBrief fields... }, "brief_name": "example", "call_time": "2026-11-23T19:30:00" }
```
`brief_name` loads `briefs/<name>.yaml` (name must match `^[A-Za-z0-9_-]+$`; no path separators).
`call_time` optional (same override as `ORDER_CALL_TIME`).
`201`:
```json
{ "session_id": "3f9c...", "instructions": "You are Ali Raza, ...", "opening_text": "Nobody has spoken yet. ...",
  "tools": [ {"name": "add_item", "description": "...", "properties": {...}, "required": ["name","quantity"]} ] }
```
Errors: `422` invalid brief or both/neither brief field or unknown `brief_name`; `429` too many live sessions.

### `GET /sessions/{id}`
`200 {"session_id", "state": "live|ended", "order_state": "open|confirmed|ended", "transcript_lines": N,
"report_ready": bool}`. `404` unknown.

### `POST /sessions/{id}/actions`
Body `{"tool": "add_item", "arguments": {"name": "chicken biryani", "quantity": 2, "unit_price_pkr": 900}}`.
`200 {"ok": true|false, "message": "...", "ended": false}`. The `ok`/`message` pair is exactly what the
voice agent's LLM would receive, including refusals (forbidden item, over budget, price lock, unreadable
argument). A refusal is `200` with `ok: false`, not an HTTP error. A successful `end_call` returns
`ended: true` and writes the report.
Errors: `404` unknown session; `409 session_closed` if the call already ended; `422` unknown `tool` name
or body not an object.

### `POST /sessions/{id}/transcript`
Body `{"role": "agent|restaurant", "text": "..."}`. `204`. Errors: `404`, `409 session_closed`,
`422` (blank text, bad role).

### `POST /sessions/{id}/end`
Hang up without `end_call` (a client-side drop). Body optional `{}`. Writes a `call_dropped` report with
the same reason text as a voice drop, then `200` with the report body (same as `GET .../report`).
Idempotent: if the call already ended, returns the existing report. `404` unknown.

### `GET /sessions/{id}/report`
`200`:
```json
{ "report": { ...CallReport JSON, same fields as a voice-call report... },
  "summary": "The call ended with the order placed (ordered): ...", "report_path": "reports/20261123-193000.json" }
```
`report_path` is relative to the server's reports dir. `409 report_not_ready` while the call is live;
`404` unknown.

### `DELETE /sessions/{id}`
`204`; drops the session from memory. If the call is still live it is finished as `call_dropped` first, so
a report is never lost. `404` unknown.

## Error body (all non-2xx)
```json
{ "error": { "code": "session_not_found", "message": "No session with id 3f9c..." } }
```
Codes: `session_not_found` (404), `session_closed` (409), `report_not_ready` (409), `too_many_sessions`
(429), `validation_error` (422; FastAPI's default 422 body is mapped to this shape).

## Isolation and concurrency
- One `CallController` (own `OrderSession`, transcript, lock) per session id; no module-level state.
- Actions on one session are serialised by that session's lock; different sessions do not block each other.
- Concurrent `end`/`DELETE`/`end_call` on one session write exactly one report.

## Import budget (tested)
Importing `order_agent.heads.http_api.app` in a fresh interpreter must not load `pipecat`, `torch`,
`faster_whisper`, `kokoro`, `google.genai` or `openai`. Only `fastapi`, `pydantic`, `starlette` (via
fastapi), controller and model modules. `uvicorn` is imported in `__main__` only.

## Equivalent scripted `happy_path`
Acceptance test (SC-003) replays the `happy_path` order through `POST /sessions`, five to seven
`POST .../actions` calls, `POST .../end` or a final `end_call` action, then `GET .../report`, and asserts
`outcome == "ordered"` and that the report's field set equals a `build_report` result's field set.
