# Research: Headless MVC Architecture

All decisions below were checked against the actual code (bot.py, tools.py, call.py, rules.py, report.py,
suite.py, run_suite.py, tests/) and `uv.lock`. No NEEDS CLARIFICATION remains.

## R1. Package layout

- **Decision**: `order_agent/{model,controller,heads/{voice,http_api},evaltools}` plus app-level
  `config.py`. Root `bot.py` and `run_suite.py` stay as entry points.
- **Rationale**: one directory per layer makes the boundary check a simple per-directory rule and makes the
  README map trivial (SC-006). Eval tooling is separated because it is test infrastructure, not a product
  layer. `config.py` holds API keys and provider choice, so it must not be reachable from Model or
  Controller (Constitution: LLM choice never in Model or Controller). The Controller therefore takes
  `reports_dir: Path`, not `Settings`.
- **Alternatives**: (a) keep flat modules and enforce by naming: rejected, nothing to check against.
  (b) separate top-level packages (`core/`, `heads/`): rejected, breaks `packages = ["order_agent"]` in the
  wheel config and every import. (c) put `Settings` in the Controller: rejected, it carries Gemini/Groq keys.
  (d) name the HTTP package `http`: rejected, shadows the stdlib name in readers' minds; use `http_api`.

## R2. Where the controller logic is today

- `bot.py` holds, inside `run_bot`, closures that are really controller decisions: `restaurant_spoke`,
  `open_call_if_silent`, `fire_nudge`, the routing of Pipecat events into `NudgeTracker`, nudge cancel
  rules, transcript capture and the disconnect/idle report write.
- `tools.py` mixes three things: argument conversion (pure), the never-raise result shield (pure), and
  Pipecat `FunctionSchema` objects plus `FunctionCallResultProperties(run_llm=False)` (Pipecat). The
  `end_call` sequencing (send the result, then write the report, then end the pipeline) is conversation
  logic.
- `call.py` is already the start of a controller (`CallState`, `NudgeTracker`, `NudgeScheduler`,
  `make_on_end`) with no Pipecat imports, but it takes `Settings` and contains `llm_http_options`
  (google-genai specific).
- **Decision**: grow `call.py` into `controller/` (see plan.md map). Keep the exact algorithms; only change
  where they live and what they depend on.

## R3. Controller API shape

- **Decision**: one class `CallController` plus a `CallHooks` protocol (channel callbacks) plus plain
  dataclasses `ToolOutcome` and `NudgeDecision`. Details in `contracts/controller-api.md`.
- **Rationale**:
  - Event methods (`restaurant_spoke`, `llm_turn_started`, `function_calls_started`, `llm_turn_ended`)
    mirror the four Pipecat events that `bot.py` already forwards to `NudgeTracker`, so the voice head
    stays a one-line-per-handler forwarder and the HTTP head can ignore them.
  - Channel effects go through `CallHooks` (`inject(text)`, `hangup()`), not by importing the channel. The
    controller owns *when* to nudge or open and what text to use; the head owns *how* to deliver it. With
    `hooks=None` no nudge or opening runs, which is correct for the HTTP head where the client is the LLM.
  - `perform(tool, arguments, reply=None)`: the optional `reply` callback is awaited with the
    `ToolOutcome` *before* the end-of-call work (report, hangup). That preserves today's order (result
    delivered, then `on_end`) in one call, with the ordering owned by the controller, not re-implemented
    per head. The HTTP head passes no `reply` and reads the return value.
  - `perform` never raises: bad arguments, unknown arguments and internal errors become
    `ok=False` outcomes with the same refusal text as today (Spec edge case, FR-008).
  - Time is injectable (`now`, `clock`) so tests need no sleeps; `NudgeScheduler` already accepts an
    injectable `sleep`.
- **Alternatives**: (a) free functions plus a state dict: loses the single owner of state. (b) the
  controller drives the LLM itself: out of scope (spec assumption). (c) the head owns nudge timers:
  rejected, FR-005 says the head makes no conversation-state decisions.

## R4. Tool definitions: neutral data plus a Pipecat adapter

- **Decision**: `controller/toolspecs.py` holds `ToolSpec(name, description, properties, required)` for the
  seven tools, as plain JSON-schema dicts (copied verbatim from `tools.py`).
  `heads/voice/tools.py` builds `FunctionSchema`/`ToolsSchema` from them and registers a handler that calls
  `controller.perform`. `GET /sessions/{id}` and the session-start response expose the same specs over HTTP.
- **Rationale**: the descriptions are domain wording (they shape LLM behaviour and the evals depend on
  them). Keeping one copy means every head offers the LLM the same tools. Moving them verbatim keeps the
  LLM-visible text byte-identical, which matters for eval parity.
- **Alternatives**: duplicate the schema in each head (drift risk); build `FunctionSchema` in the
  controller (violates FR-004).

## R5. HTTP head framework

- **Verified**: `uv.lock` has `fastapi 0.165.0`, `starlette`, `uvicorn[standard]` and `httpx` (the
  TestClient dependency), all pulled in by `pipecat-ai[runner]`.
- **Decision**: FastAPI, app factory `create_app(...)` (no import-time global app, so tests and
  concurrent sessions are isolated), pydantic request/response models, run with
  `uvicorn.run(create_app(...), host="127.0.0.1", port=8000)` from `python -m order_agent.heads.http_api`.
  Declare `fastapi` and `uvicorn` in `pyproject.toml` at the already-locked versions so the dependency is
  explicit rather than accidental.
- **Import graph**: `fastapi`, `starlette` and `uvicorn` do not import `pipecat` (pipecat imports them,
  not the reverse). The HTTP head imports only the controller and model, which import no Pipecat. A
  fresh-interpreter test asserts `sys.modules` has no `pipecat`, `torch`, `faster_whisper`, `kokoro`
  after importing `order_agent.heads.http_api.app` (`uvicorn` import happens only in `__main__`).
- **Alternatives**: stdlib `http.server` (no validation, poor tests); Flask (new dependency); a raw
  Pipecat `FastAPIWebsocketTransport` (drags the speech stack in, defeats the point).

## R6. Session store and isolation

- **Decision**: `SessionStore` with `dict[str, CallController]`, ids from `uuid.uuid4().hex`, no shared
  mutable state between sessions. Each controller owns its `OrderSession` and an `asyncio.Lock` that
  serialises `perform` and `finish` for that session. A global cap (default 100 live sessions, 429 when
  exceeded) keeps a local dev server from growing without bound. `DELETE` frees a session. No persistence.
- **Rationale**: spec edge case "two sessions must not leak". Because `OrderSession` has no module-level
  state (verified: all state is on `self`), instance separation is sufficient; a test runs two sessions
  interleaved and compares carts and reports.
- **Alternatives**: a database (out of scope); a single global session (violates FR-007).

## R7. Error codes

- Refused rule/argument problems stay `200` with `{"ok": false, "message": ...}`. That is the same payload
  the LLM gets today, and a refusal is a normal, expected outcome, not an HTTP error.
- `404 session_not_found`; `409 session_closed` (action or transcript after end/finish);
  `409 report_not_ready` (report requested before finish); `422` (FastAPI validation: bad body, unknown
  tool name, bad brief); `429 too_many_sessions`. Error body shape `{"error": {"code", "message"}}`.
  Full table in `contracts/http-api.md`.

## R8. Boundary check mechanics

- **Decision**: `ast`-based, no new dependency (not `import-linter`: that adds a dependency and a config
  format for a seven-rule policy). Details in `contracts/boundaries.md`.
- **Why ast not grep**: grep misses `from x import y` aliases and lazy imports inside functions (the
  codebase uses a lazy `from google import genai` in `bot.py` today). `ast.walk` finds imports at any depth.
  Relative imports are resolved using the file's package path, so `from . import x` cannot dodge the rule.
- **Self-test**: `violations(source: str, layer: str) -> list[str]` is a pure function; tests feed it a
  bad snippet per layer and assert it reports it (proves SC-002), then run it over the real tree.
- **Runtime check**: one subprocess test imports `order_agent.model` then `order_agent.controller` and
  asserts no forbidden top-level module appears in `sys.modules`, catching transitive leaks the static
  check cannot see (for example via a third-party package).

## R9. Existing tests that must change, and why (Constitution III)

No assertion is weakened or removed. Expected edits, each with its reason, to be listed in the commit
messages and in `tasks.md`:

| Test file | Change | Reason |
|---|---|---|
| `test_tools.py`, `test_tool_registration.py`, `test_llm_factory.py` | build tools through `heads.voice.tools.build_tools(controller)`; the `Harness` constructs a `CallController` | `build_tools(session, on_end)` is replaced by a controller-based API. Same calls, same expected results |
| `test_prompt.py` | none in step 3 (shim); import from `order_agent.controller.prompt` in step 7 | module moved to the Controller (instructions are about how the LLM is spoken to, not domain rules) |
| `test_call.py` | none in step 3 (shim keeps `CallState(brief, settings, now)`); in step 7 import from `order_agent.controller` | module moved |
| `test_brief/matching/rules_*/report.py` | none in step 1 (shims); import path updated in step 7 | module moved |
| `test_suite.py`, `test_eval_config.py`, `test_eval_llm.py`, `test_preflight.py`, `test_throttle.py`, `test_persona_totals.py` | import path updated in step 7 | eval tooling moved to `evaltools/` |

## R10. Eval suite and rescore compatibility

- `run_suite.py` only needs `bot.py --port` to start a Pipecat runner serving `/api/offer` on the eval
  transport. The root `bot.py` keeps `bot` and `main` exported, so Pipecat runner discovery and the
  subprocess spawn work unchanged.
- `--rescore` reads saved report JSON via `CallReport` (Model, schema unchanged) and `suite.py` checks
  (eval tooling). Neither imports the controller or heads. Verification in step 7: run
  `run_suite.py --rescore` on committed evidence (no API call) and diff the classification output.

## R11. Items deliberately not done

- No LLM inside the HTTP head, no auth, no persistence, no new domain behaviour (spec assumptions).
- No change to `rules.py` behaviour. Any domain issue noticed during the move is logged as a follow-up.
- `write_report` stays in `model/report.py` (a stdlib file write used by both heads). If persistence ever
  needs a database, the controller can take a `ReportSink`; not needed now (YAGNI).
