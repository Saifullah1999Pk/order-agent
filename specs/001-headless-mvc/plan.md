# Implementation Plan: Headless MVC Architecture

**Branch**: `feat/headless-mvc` (Spec Kit feature dir `001-headless-mvc`) | **Date**: 2026-11-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-headless-mvc/spec.md`

## Summary

Restructure `order_agent` into Model, Controller and Heads. The Model (brief, matching, rules, report)
is already pure and only moves. Prompt building moves to the Controller (how the LLM is spoken to). The real work is extracting the *controller logic* that today
lives inside `bot.py` (call lifecycle, opening, nudge decisions, transcript capture) and `tools.py`
(tool-argument conversion, refusals, end-of-call sequencing, tool definitions) into a new
channel-independent `CallController`. The Pipecat pipeline becomes the thin voice head. A second head,
a local FastAPI app, drives the same controller with no Pipecat or speech imports. An ast-based unit
test enforces the layer boundaries. Migration is 8 small steps; every intermediate commit keeps the
366-test baseline green, using compatibility shims at the old import paths until step 7.

## Technical Context

**Language/Version**: Python 3.12 (`requires-python >=3.12,<3.13`), managed with `uv`.

**Primary Dependencies**: existing: `pipecat-ai[...]==1.17.0`, pydantic, pyyaml, python-dotenv, loguru.
For the HTTP head: `fastapi` (locked at 0.165.0) and `uvicorn` are already in `uv.lock` as transitive
deps of `pipecat-ai[runner]`. We declare `fastapi` and `uvicorn` explicitly in `pyproject.toml` at the
versions already locked (no new package, no paid service). The TestClient needs `httpx`, also already
locked. No NEEDS CLARIFICATION remains.

**Storage**: process memory only for HTTP sessions; call reports still go to `reports_dir` as today.

**Testing**: pytest + pytest-asyncio (`asyncio_mode=auto`). Baseline recorded: **366 passed** (3.2 s).
No network in unit tests (Constitution III).

**Target Platform**: Windows 11 (Git Bash) first-class; the HTTP head binds `127.0.0.1` only.

**Project Type**: single Python project with two entry-point heads.

**Performance Goals**: none new. Voice-path behaviour and latency unchanged (controller calls are
in-process function calls).

**Constraints**: no behaviour change (FR-008); entry points `bot.py`, `run_suite.py` and env vars
unchanged (FR-012); eval suite and `--rescore` unchanged (FR-010); free services only.

**Scale/Scope**: about 2.5k lines moved or re-homed, about 400 new lines (controller, HTTP head,
boundary test), no new domain behaviour.

## Constitution Check

*GATE: passed before Phase 0; re-checked after Phase 1 (below).*

| Principle | Pre-research | Post-design | Notes |
|---|---|---|---|
| I Headless MVC | PASS | PASS | This feature implements it and adds the enforcing test (FR-009). |
| II LLM talks, code decides | PASS | PASS | All validation stays in `model/rules.py`. The controller only converts arguments (same refusal text) and forwards. The HTTP head sends explicit actions and cannot bypass the rules engine. Money stays `Decimal`. |
| III Test-first | PASS | PASS | Each migration step starts RED (new test) then GREEN. Existing tests are not weakened. The only test edits are import-path or constructor changes in steps 5 and 7, listed with reasons (research.md R9). A parity test runs the old and new tool handlers on one argument matrix before the old one is deleted. |
| IV Evidence | PASS | PASS | SC-004 needs a live `happy_path` run after step 5, compared with the committed baseline `evals/confirmation/unpriced-items-2026-11-25/` run 3 (pass), on the deterministic checks only. README numbers are untouched apart from the layout section. `--rescore` is re-run on committed evidence in step 7 to show classification is unchanged. |
| V Free, safe, honest | PASS | PASS | FastAPI/uvicorn are already installed. The HTTP head is local-only (127.0.0.1), synthetic briefs, no auth claimed. The evidence scrub rule applies to anything committed. |

Result: **no violations**. Complexity Tracking is empty.

Note for honesty: `setup-plan.sh` reported branch `001-headless-mvc` (taken from the spec dir); the
checked-out git branch is `feat/headless-mvc`. Work and commits stay on `feat/headless-mvc`.

## Current code to layer map (from reading the actual code)

| Current module | Layer | Destination | Notes |
|---|---|---|---|
| `brief.py` | Model | `model/brief.py` | pure (pydantic, yaml) |
| `matching.py` | Model | `model/matching.py` | pure |
| `rules.py` | Model | `model/rules.py` | pure, 421 lines, untouched |
| `report.py` | Model | `model/report.py` | `build_report`, `summarise`, `write_report` (stdlib file write, accepted as model persistence) |
| `prompt.py` | Controller | `controller/prompt.py` | instructions for the LLM built from the brief; a conversation concern, not a domain rule |
| `call.py`: `should_nudge`, `NudgeTracker`, `NUDGE_TEXT`, `MAX_NUDGES` | Controller | `controller/nudge.py` | pure |
| `call.py`: `NudgeScheduler` | Controller | `controller/nudge.py` | stdlib asyncio only |
| `call.py`: `CallState`, `make_on_end` | Controller | `controller/session.py` as `CallController` | takes `reports_dir`, not `Settings` |
| `call.py`: `llm_http_options` | Head (voice) | `heads/voice/llm_factory.py` | google-genai retry option; vendor detail wrongly in call.py today |
| `tools.py`: arg converters, refusal text, exception shielding, handler table | Controller | `controller/tools.py` | `ToolDispatcher` |
| `tools.py`: schema text, `ToolsSchema` | Controller (neutral `ToolSpec` data) plus Head (Pipecat schema) | `controller/toolspecs.py`, `heads/voice/tools.py` | descriptions are domain text; `FunctionSchema` is Pipecat |
| `llm_factory.py` | Head (voice) | `heads/voice/llm_factory.py` | Pipecat services |
| `bot.py` | Head (voice) | `heads/voice/pipeline.py`; root `bot.py` stays as a thin entry shim | |
| `config.py` | App config | stays `order_agent/config.py` | `Settings`, `load_settings`, `pick_model`; imported by heads, eval tooling and entry points only, never by Model or Controller |
| `eval_config.py`, `eval_llm.py`, `suite.py`, `throttle.py`, `preflight.py` | Eval tooling | `evaltools/` (`order_agent/eval_llm.py` stays as a re-export compat module, see below) | may import Model; never Controller or Heads. `suite.py` already imports only brief, matching, report |
| `run_suite.py`, root `bot.py` | Entry points | unchanged location | imports updated |

### Exactly what must move out of `bot.py` and `tools.py`

Controller logic (moves):

- *bot.py*: the `restaurant_spoke` flag; the opening behaviour (3 s wait, the "Nobody has spoken yet..."
  text, skipped if the restaurant already spoke); routing of "user turn started / LLM run started /
  function calls started / assistant turn stopped" into `NudgeTracker`; the nudge cancel rules (cancel
  on restaurant speech, on a new LLM run, on end_call, on disconnect); the `fire_nudge` text and delay;
  transcript capture rules (restaurant line on user turn, agent line only if non-blank);
  `on_disconnect` and the post-run "idle timeout still writes a report"; `push_end` ordering (cancel
  nudge, then end the channel).
- *tools.py*: argument conversion and the exact refusal strings; the never-raise shield (exactly one
  result per action); `end_call` rules (only a successful end suppresses another LLM run; the report is
  written after the result is delivered; an `on_end` failure must not stall); tool names, descriptions
  and JSON schemas.

Pure channel wiring (stays in the voice head): STT/TTS/LLM construction, `transport_params`,
`SileroVADAnalyzer`, aggregators, `Pipeline`/`PipelineWorker`/`WorkerRunner`, Pipecat event-handler
registration (each handler becomes one forwarding call), `EndWorkerFrame`, `LLMRunFrame`,
`LLMContext.add_message`, `FunctionSchema`/`ToolsSchema`/`FunctionCallResultProperties`, the Gemini
model probe and model choice, and the `ORDER_CALL_TIME` override of the brief.

## Target package layout

```text
order_agent/
  __init__.py
  config.py                     # app settings (heads, eval tooling, entry points only)
  model/                        # Layer 1: pure domain + rules. stdlib + pydantic + yaml only
    brief.py  matching.py  rules.py  report.py
  controller/                   # Layer 2: conversation logic. stdlib + loguru + model
    prompt.py    (build_system_prompt, moved from order_agent/prompt.py)
    session.py   (CallController, CallHooks, NudgeDecision; re-exports ToolOutcome)
    nudge.py     (should_nudge, NudgeTracker, NudgeScheduler, NUDGE_TEXT, MAX_NUDGES)
    tools.py     (ToolDispatcher: arguments -> OrderSession call -> result; defines ToolOutcome)
    toolspecs.py (ToolSpec data for the 7 tools; no Pipecat)
  heads/                        # Layer 3: channel adapters, thin
    voice/      pipeline.py  tools.py  llm_factory.py  probe.py  hooks.py  bridge.py
    http_api/   app.py  schemas.py  store.py  __main__.py
  eval_llm.py                   # compat module: re-exports the factories (YAML configs name this path)
  evaltools/                    # test tooling, not a product layer
    eval_config.py  eval_llm.py  suite.py  throttle.py  preflight.py
bot.py                          # entry shim: `bot`, `main` from heads.voice.pipeline
run_suite.py                    # unchanged behaviour; imports from evaltools
tests/
  architecture.py               # boundary-check helper (imported as `architecture`, see research R8)
  test_architecture.py          # boundary check
  test_controller_*.py, test_http_head.py (new)
```

The HTTP head package is named `http_api`, not `http`, to avoid confusion with the stdlib module.
Dependencies point inward only: `heads -> controller -> model`. `evaltools -> model, config`.

## Controller API (summary; full signatures in [contracts/controller-api.md](contracts/controller-api.md))

`CallController(brief, *, reports_dir, now=None, hooks=None)`; `instructions`; `opening_text`;
`tool_specs()`; `attach_hooks(hooks)` (late binding for heads whose channel objects need the controller
first, such as the voice head); `await perform(tool, arguments, reply=None) -> ToolOutcome`; `add_line(role, text)`;
event methods `restaurant_spoke(text)`, `llm_turn_started()`, `function_calls_started()`,
`llm_turn_ended(content, interrupted) -> NudgeDecision`; `channel_opened()` (starts the opening
timer); `await finish(outcome, reason)`; `await drop()`; `report`, `report_path`, `state`,
`finished`. Channel effects (inject a developer message and run the LLM, end the pipeline) go out
through a `CallHooks` protocol the head supplies. With `hooks=None` (HTTP head) nudges and opening are
disabled, because the client is the "LLM".

## HTTP head design (summary; full contract in [contracts/http-api.md](contracts/http-api.md))

FastAPI app from `create_app(reports_dir, brief_dir, clock)`. In-memory `SessionStore`
(`dict[str, CallController]`, uuid4 ids): each session has its own `OrderSession`, transcript and
lock. Endpoints: `POST /sessions`, `GET /sessions/{id}`, `POST /sessions/{id}/actions`,
`POST /sessions/{id}/transcript`, `POST /sessions/{id}/end`, `GET /sessions/{id}/report`,
`DELETE /sessions/{id}`, `GET /health`. A refused action is a normal `200 {"ok": false, ...}` (the
same result the voice head hands the LLM); transport-level problems use 404/409/422 with a uniform
error body. It imports only `fastapi`, `pydantic`, `uvicorn` (only in `__main__`), controller and
model. A test imports the app in a fresh interpreter and asserts no `pipecat`, `torch`,
`faster_whisper` or `kokoro` module was loaded.

## Boundary check design (summary; rules in [contracts/boundaries.md](contracts/boundaries.md))

`tests/test_architecture.py` walks every `*.py` under each layer directory, parses it with `ast`
(all `Import`/`ImportFrom` nodes at any depth, so lazy imports inside functions are caught; relative
imports are resolved to absolute names) and compares against a per-layer forbidden-prefix table. The
check is a pure function `violations(source, layer)`, tested with bad snippets, so the suite
demonstrably fails on a forbidden import (SC-002) without needing a scratch branch. Extra checks:
every module under `order_agent/` maps to exactly one layer, the two heads do not import each other,
and a subprocess test confirms that importing `order_agent.model` and `order_agent.controller` loads
no `pipecat`, web or LLM module at runtime.

## Eval suite and `--rescore`

`run_suite.py` spawns `python bot.py --port N` and passes `ORDER_BRIEF`, `ORDER_CALL_TIME`,
`ORDER_REPORTS_DIR`. The root `bot.py` keeps exposing `bot()` (Pipecat runner discovery) and `main()`,
so spawning is unchanged. Reports keep the same `CallReport` schema, so `--rescore` (which reads
committed report JSON through `CallReport` and `suite.py`) is unaffected. Scenario YAML, judge and
simulator configs are untouched. The seven `evals/judge*.yaml` / `simulator-*.yaml` files name factories as
`order_agent.eval_llm.<factory>`, so `order_agent/eval_llm.py` stays as a compatibility module that
re-exports every factory from `order_agent/evaltools/eval_llm.py`; a test loads each factory path named in
those YAMLs. The boundary check allows exactly this one compat module (re-exports only). Only Python import
paths inside `run_suite.py` and tests change, in step 7.

## Migration path (8 steps, each commit green)

| # | Step | RED test first | Shims left |
|---|---|---|---|
| 1 | Boundary test (model rules) and move `brief matching rules report` to `model/` | `test_architecture` (packages exist, rule checker) | old paths re-export from `model.*` |
| 2 | Add `controller/toolspecs.py` and `controller/tools.py` (`ToolDispatcher`), additive | dispatcher tests mirroring `test_tools.py` cases | none (old `tools.py` untouched) |
| 3 | Add `controller/nudge.py`, move `prompt.py` to `controller/prompt.py`, add `CallController` (with `attach_hooks`); `call.py` becomes a shim (`CallState` subclass, same constructor) and `prompt.py` re-exports | controller lifecycle, nudge, drop, opening tests; boundary rule covers `controller/prompt.py` | `call.py`, `prompt.py` |
| 4 | Add `heads/voice/tools.py` (`build_tools(controller)`) plus a parity test running old `tools.build_tools` and the new one on one argument matrix | parity test | old `tools.py` still used by `bot.py` |
| 5 | Move the `bot.py` body to `heads/voice/pipeline.py` using the controller; root `bot.py` becomes an entry shim; move `llm_factory.py` and `llm_http_options`; migrate `test_tools`, `test_tool_registration`, `test_llm_factory` to the new API; delete old `tools.py` | fake-hooks event-forwarding tests (restaurant spoke, empty-turn nudge, end_call ordering) | root `bot.py` entry shim only |
| 6 | HTTP head, additive | scripted `happy_path`, isolation, error codes, import-graph tests | none |
| 7 | Move eval tooling to `evaltools/`; update `run_suite.py` and test imports; delete remaining shims except the `eval_llm.py` compat module; tighten the boundary test to the full layer map | tightened `test_architecture` | `eval_llm.py` compat module only |
| 8 | README architecture section, diagram, layout, "how to add a head" | n/a (docs) | none |

**Riskiest step: 5** (voice pipeline). It is the only step where real-time ordering matters and unit
tests cannot fully cover it: the `end_call` result must be sent before the report is written and the
pipeline ended; nudge timers must cancel on the same events as today; the opening must not fire if the
restaurant already spoke. Mitigations: keep the exact event-to-call mapping (one controller call per
Pipecat handler), fake-hooks tests for each ordering rule, a side-by-side review of the handler bodies
against the old `bot.py`, and a live `happy_path` eval (SC-004) before starting step 6. Step 1 is the
second risk (many import paths) but is mechanical and shimmed.

## Project Structure

### Documentation (this feature)

```text
specs/001-headless-mvc/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── controller-api.md
│   ├── http-api.md
│   └── boundaries.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks (not created here)
```

### Source Code (repository root)

See "Target package layout" above.

**Structure Decision**: single project, one `order_agent` package with three layer sub-packages
(`model`, `controller`, `heads`) plus `evaltools`. Tests stay in the existing top-level `tests/`, with
new architecture, controller and HTTP tests added.

## Complexity Tracking

No Constitution violations. Nothing to justify.
