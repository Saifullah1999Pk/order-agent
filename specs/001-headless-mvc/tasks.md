---

description: "Task list for 001 Headless MVC Architecture"
---

# Tasks: Headless MVC Architecture

**Input**: Design documents from `specs/001-headless-mvc/` (plan.md, spec.md, research.md, data-model.md,
contracts/, quickstart.md) and `.specify/memory/constitution.md` v1.0.0.

**Tests**: REQUESTED. Constitution Principle III makes strict TDD mandatory: every task starts with a
failing test (RED), then the smallest change that passes (GREEN). A refactor keeps the existing suite
green and never weakens a test.

**Organization**: grouped by user story. The plan's 8 migration steps keep their order and are shown as
"Step N" markers inside the phases: Step 1 = Phase 2, Steps 2 to 5 = Phase 3 (US1), Step 6 = Phase 4
(US2), Step 7 = Phase 5 (US3), Step 8 = Phase 6 (Polish).

## Format: `- [ ] T### [P?] [Story?] Description with file path`

- **[P]**: independent of every other incomplete task (different files, no shared edits). No task is
  marked [P] in this list (see "Parallel opportunities"); all tasks run in order.
- **[US1] [US2] [US3]**: user story from spec.md. Setup, Foundational and Polish tasks have none.
- Sub-bullets: **RED** = the failing test to write first; **GREEN** = the smallest change; **Verify** =
  the command that must pass before the commit.

## Execution rules for every task (subagent-driven development)

1. One fresh implementer per task, then an independent review per task (spec compliance, then code
   quality) before the next task starts.
2. **Every commit is green**: `uv run pytest -q` passes (baseline 366, never fewer tests passing) before
   and after each task. One task = one commit, message `refactor|feat|test: T### <summary>`, ending with
   the attribution line the session requires.
3. No behaviour change: do not edit `order_agent/model/rules.py` logic, refusal strings, report fields or
   tool descriptions. Move code verbatim; improve nothing en route (log follow-ups instead).
4. Changing an existing test needs a stated reason in the commit message (research.md R9 lists the
   expected ones). Never delete or loosen an assertion.
5. No network or real API calls in tests. Do not run bots, evals or API calls except T033, which needs the
   user's explicit go-ahead.
6. Before every commit run `git diff --cached | grep -nE 'gsk_|AIza|org_[A-Za-z0-9]{16,}'` (expect none).
   Never push.
7. Constrained fields are implemented per [data-model.md](data-model.md); tasks cite `Entity.field` rather
   than restating the rule.

---

## Phase 1: Setup

- [x] T001 Record the baseline and confirm the branch (no file changes)
  - Verify: `git branch --show-current` prints `feat/headless-mvc`, `git status --short` is clean,
    `uv run pytest -q` prints `366 passed`. Stop and report if not.

---

## Phase 2: Foundational (Step 1 of the plan): boundary check and Model package

**Purpose**: the boundary test must exist before any code moves, so every later move is checked.
Blocking for all stories.

- [x] T002 Create the boundary checker and its tests in `tests/architecture.py` (helper) and
  `tests/test_architecture.py`
  - RED: `tests/test_architecture.py` imports `architecture` (the helper in `tests/`, missing; `tests/` has no
    `__init__.py` and pytest puts it on `sys.path`, so do NOT add `tests/__init__.py`, research R8) and asserts: (a) `violations(src, "model")`
    flags `import pipecat`, a lazy `def f(): import google.genai`, `from order_agent.controller import x`,
    `from . import x` resolving outside the layer, and returns nothing for a clean snippet (per
    [contracts/boundaries.md](contracts/boundaries.md) "Tests" item 2); (b) the real-tree check is
    parametrised per `.py` file under each layer directory that exists; (c) a classification test: every
    `.py` under `order_agent/` is in a layer dir, is `__init__.py` or `config.py`, or is named in a
    `LEGACY_FLAT` set listing today's flat modules (`brief matching rules report prompt call tools
    llm_factory eval_config eval_llm suite throttle preflight`).
  - GREEN: implement `imported_modules` (ast, any depth, relative imports resolved) and `violations`
    with the `model` rules from the boundaries table (only the `model` layer is required now; other layers
    are added by later tasks). Use `sys.stdlib_module_names` for stdlib detection. Keep the helper stdlib-only.
    The subprocess tests added later use `python -I`, which needs the project installed in the venv;
    `uv run` does this (editable install), so state this assumption in the test docstring.
  - Verify: `uv run pytest tests/test_architecture.py -q` then `uv run pytest -q`.

- [x] T003 Move `brief.py` to `order_agent/model/brief.py` and leave a shim
  - RED: `tests/test_model_package.py::test_brief_lives_in_model` asserts `order_agent.model.brief.OrderBrief`
    imports and `order_agent.brief.OrderBrief is order_agent.model.brief.OrderBrief`; and
    `tests/test_architecture.py` real-tree param for `model/brief.py` exists. Fails: package missing.
  - GREEN: `git mv order_agent/brief.py order_agent/model/brief.py`, add `order_agent/model/__init__.py`,
    new `order_agent/brief.py` re-exporting `OrderBrief, WantedLine, load_brief`. Field rules
    (`OrderBrief.budget_pkr` stays `Decimal`, `OrderBrief.deliver_by`, `OrderBrief.never`) are unchanged per
    [data-model.md](data-model.md).
  - Verify: `uv run pytest -q` (all green, unchanged count plus the new tests).

- [x] T004 Move `matching.py` to `order_agent/model/matching.py` and leave a shim
  - RED: `tests/test_model_package.py::test_matching_lives_in_model` (path import plus identity of
    `normalise` and `match_line` through the old path).
  - GREEN: `git mv`, update its import to `order_agent.model.brief`, shim at `order_agent/matching.py`.
  - Verify: `uv run pytest -q`.

- [x] T005 Move `rules.py` to `order_agent/model/rules.py` and leave a shim
  - RED: `tests/test_model_package.py::test_rules_live_in_model` (identity of `OrderSession`, `ToolResult`,
    `ToolEvent`, `CartItem` through the old path).
  - GREEN: `git mv`, update its imports to `order_agent.model.brief` and `order_agent.model.matching`,
    shim at `order_agent/rules.py` re-exporting the four public names. No logic edit.
  - Verify: `uv run pytest -q`.

- [x] T006 Move `report.py` to `order_agent/model/report.py` and leave a shim
  - RED: `tests/test_model_package.py::test_report_lives_in_model` (identity of `CallReport`,
    `TranscriptLine`, `build_report`, `summarise`, `write_report`). Report schema fields
    (`CallReport.*`) are unchanged per [data-model.md](data-model.md), so saved reports and `--rescore`
    stay valid.
  - GREEN: `git mv`, update import to `order_agent.model.rules`, shim at `order_agent/report.py`.
  - Verify: `uv run pytest -q`, plus `uv run pytest tests/test_architecture.py -q` shows all four model
    files checked with no violations.

**Checkpoint**: Model package exists (`brief matching rules report`), boundary check enforces it, all
old import paths still work.

---

## Phase 3: User Story 1 - Same agent, cleaner structure (Priority: P1) (Steps 2 to 5)

**Goal**: the Controller and voice head exist, the voice pipeline is thin, behaviour is identical.

**Independent Test**: full unit suite green with no test weakened, plus a live `happy_path` eval (T033)
and a browser call (T034).

### Step 2: controller tool layer (additive; old `tools.py` untouched)

- [x] T007 [US1] Add the controller layer to the boundary check and create `order_agent/controller/__init__.py`
  - RED: in `tests/test_architecture.py` snippets: `import pipecat`, `from fastapi import FastAPI`,
    `from order_agent.heads.voice import x`, `from order_agent.config import Settings` and
    `from order_agent.evaltools import x` each give a violation for layer `controller`; `loguru` and
    `from order_agent.model.brief import OrderBrief` give none.
  - GREEN: add the `controller` row (third-party allow `loguru`; forbidden per
    [contracts/boundaries.md](contracts/boundaries.md)) and the empty package.
  - Verify: `uv run pytest -q`.

- [x] T008 [US1] Create `order_agent/controller/toolspecs.py` with `ToolSpec` and `TOOL_SPECS`
  - RED: `tests/test_controller_toolspecs.py`: names are unique (`ToolSpec.name`, per
    [data-model.md](data-model.md)) and equal to `[add_item, set_price, remove_item, set_fees,
    set_minimum_order, confirm_order, end_call]`; for each spec, `description`, `properties` and `required`
    equal the matching `FunctionSchema` produced by the existing `order_agent.tools.build_tools` (byte
    identical LLM-visible text).
  - GREEN: frozen dataclass plus the seven specs copied verbatim from `tools.py`.
  - Verify: `uv run pytest tests/test_controller_toolspecs.py -q` then `uv run pytest -q`.

- [x] T009 [US1] Create `order_agent/controller/tools.py`: argument converters and `ToolDispatcher` for the six non-end tools
  - RED: `tests/test_controller_tools.py`: an async matrix mirroring the cases in `tests/test_tools.py`
    (valid call, missing or blank text, non-number money, bool as money, 2.5 as a whole number, bad flag,
    optional price omitted) for `add_item set_price remove_item set_fees set_minimum_order confirm_order`,
    asserting `ToolDispatcher(session).dispatch(tool, args)` returns a `ToolOutcome` whose `ok` and
    `message` equal the strings the legacy handlers send (`Refused: Missing or invalid 'name': ...`).
    Define `ToolOutcome` (`ToolOutcome.ok`, `.message`, `.run_llm`, `.ended`, `as_payload()`) in this file;
    it is re-exported from `controller/session.py` later.
  - GREEN: move `_BadArgument`, `_text`, `_money`, `_optional_money`, `_flag`, `_whole`, `_refusal`
    verbatim from `tools.py` (copy now, the old file is deleted in T031); handler table without any Pipecat
    type.
  - Verify: `uv run pytest tests/test_controller_tools.py -q` then `uv run pytest -q`.

- [x] T010 [US1] Extend `ToolDispatcher` in `order_agent/controller/tools.py` with `end_call` and the never-raise shield
  - RED: `tests/test_controller_tools.py`: successful `end_call` gives `ToolOutcome.run_llm is False` and
    `ToolOutcome.ended is True`; a refused `end_call` (for example outcome `ordered` before confirm) keeps
    `run_llm True`, `ended False`; non-dict arguments, `None` arguments, an unknown tool name, and a
    session method that raises each return exactly one `ok=False` outcome with text starting `Refused:` and
    never raise (matches the legacy `Refused: could not read the arguments (...)` and `Refused: internal
    error (...)`).
  - GREEN: add `end_call` conversion (`outcome`, `reason` as non-empty text) and the `try/except` shields
    as in `tools.py`. Dispatcher only returns the outcome; end-of-call work belongs to `CallController`.
  - Verify: `uv run pytest -q`.

### Step 3: nudge, prompt and `CallController`

- [x] T011 [US1] Move nudge logic to `order_agent/controller/nudge.py` (`should_nudge`, `NudgeTracker`, `NudgeScheduler`, `NUDGE_TEXT`, `MAX_NUDGES`, `NUDGE_DELAY_SECS`)
  - RED: `tests/test_controller_nudge.py`: names import from `order_agent.controller.nudge`;
    `order_agent.call.should_nudge is order_agent.controller.nudge.should_nudge` (and the same for the
    other five names). Fails: module missing.
  - GREEN: move the code verbatim out of `call.py`; `call.py` imports and re-exports them. `NudgeDecision`
    is added in T017, not here.
  - Verify: `uv run pytest -q` (existing `tests/test_call.py` unchanged and green).

- [x] T012 [US1] Move `prompt.py` to `order_agent/controller/prompt.py` (instructions for the LLM belong to the Controller) and leave a shim
  - RED: `tests/test_controller_prompt.py`: `build_system_prompt` imports from
    `order_agent.controller.prompt`, `order_agent.prompt.build_system_prompt` is the same object, and the
    prompt for the `brief` fixture equals the output of the legacy function (identity covers it).
    Architecture: a `controller/prompt.py` file is checked by the real-tree param with no violations.
  - GREEN: `git mv`, update import to `order_agent.model.brief`, shim at `order_agent/prompt.py`.
  - Verify: `uv run pytest -q` (existing `tests/test_prompt.py` unchanged and green).

- [x] T013 [US1] Create `order_agent/controller/session.py`: `CallController` core (constructor, `session`, `transcript`, `add_line`, `instructions`, `opening_text`, `tool_specs`) plus `CallHooks`, `NudgeDecision`, re-export of `ToolOutcome`
  - RED: `tests/test_controller_session.py`: `CallController(brief, reports_dir=tmp_path, now=NOW)` exposes
    `session` (an `OrderSession` built with `now`), empty `transcript`, `instructions == build_system_prompt(brief)`,
    `opening_text` equal to today's string ("Nobody has spoken yet. Open the call: greet, say you'd like to
    place a delivery order."), `tool_specs() == TOOL_SPECS`; `add_line("agent","hi")` appends a
    `TranscriptLine`; `NudgeDecision.delay_secs` defaults to `NUDGE_DELAY_SECS` and `.text` to `NUDGE_TEXT`
    (`NudgeDecision` fields per [data-model.md](data-model.md)); `ToolOutcome` is importable from
    `order_agent.controller.session`. No `Settings` parameter exists.
  - GREEN: implement per [contracts/controller-api.md](contracts/controller-api.md).
  - Verify: `uv run pytest -q`.

- [x] T014 [US1] `CallController.attach_hooks(hooks)`: late binding of channel hooks (resolves the voice head's construction cycle)
  - RED: `tests/test_controller_session.py`: (a) a controller built with `hooks=None` schedules no nudge and
    no opening and `perform("end_call")` does not fail; after `attach_hooks(fake)` the same events inject
    through `fake` and a successful `end_call` calls `fake.hangup()` (use fake sleep); (b) calling
    `attach_hooks` a second time raises `RuntimeError`; (c) `attach_hooks` after `finish` is accepted and
    changes nothing (nothing fires after the call ended). Contract: rule 0 in
    [contracts/controller-api.md](contracts/controller-api.md).
  - GREEN: store hooks on the controller; the nudge scheduler and opening timer read `self._hooks` at fire
    time (not at construction), so no event is lost or double-fired by late attachment.
  - Verify: `uv run pytest -q`.

- [x] T015 [US1] `CallController.finish` and `drop`: one report, idempotent, concurrency safe, `report` and `report_path` attributes
  - RED: in `tests/test_controller_session.py`, port the cases of `tests/test_call.py` (write once, same
    path on second call, safe under `asyncio.gather` of `finish`, `drop`, `finish`, drop writes
    `call_dropped` with reason `call ended without end_call`, drop after a confirmed order uses
    `... after the order was confirmed (total Rs N)`). Add: `CallController.report` is the `CallReport`
    object after `finish` and `None` before; `finished` flips to True (`CallController.report`, per
    [data-model.md](data-model.md): set once). Keep the originals in `tests/test_call.py` untouched.
  - GREEN: lift `CallState.finish` and `on_disconnect` logic with an `asyncio.Lock`; `drop` replaces
    `on_disconnect`.
  - Verify: `uv run pytest -q`.

- [x] T016 [US1] `CallController.perform`: dispatch, reply-before-end ordering, end-of-call sequence
  - RED: `tests/test_controller_session.py` with a fake `CallHooks` that records calls in a shared list:
    (a) `perform("add_item", ...)` returns the dispatcher outcome and never calls hooks;
    (b) successful `perform("end_call", ..., reply=fake_reply)` records, in this order, `reply`,
    `finish` (report file exists), `hangup`; (c) if `reply` raises, `finish` and `hangup` still happen;
    (d) if `finish` raises (reports_dir unwritable), `hangup` still happens and the exception does not
    escape; (e) a refused `end_call` does not finish or hang up; (f) `perform` with `hooks=None` on a
    successful end writes the report and does not fail.
  - GREEN: implement rule 3 of [contracts/controller-api.md](contracts/controller-api.md); also cancel any
    pending nudge before `hangup`. `ToolOutcome.run_llm` and `.ended` per [data-model.md](data-model.md).
  - Verify: `uv run pytest -q`.

- [x] T017 [US1] `CallController` conversation events and nudge scheduling: `restaurant_spoke`, `llm_turn_started`, `function_calls_started`, `llm_turn_ended`
  - RED: `tests/test_controller_session.py` with a fake `sleep` and fake hooks:
    (a) empty non-interrupted turn with nothing else returns `NudgeDecision(nudge=True)` and, after the fake
    sleep, `hooks.inject(NUDGE_TEXT)` runs once; (b) a turn with a function call, a non-blank turn, an
    interrupted turn, or a restaurant turn since the run starts returns `nudge=False` and injects nothing;
    (c) `restaurant_spoke()` cancels a pending nudge and resets the in-a-row counter; (d)
    `llm_turn_started()` cancels a pending nudge; (e) at most `MAX_NUDGES` (2) nudges in a row; (f) a
    non-blank `content` appends an `agent` line, blank content appends none; `restaurant_spoke("hi")`
    appends a `restaurant` line, `restaurant_spoke()` appends none; (g) after `finish`, no nudge fires; (h)
    `hooks=None` never schedules anything. Mirror the `NudgeTracker` cases in `tests/test_call.py`.
  - GREEN: compose `NudgeTracker` and `NudgeScheduler` inside the controller as in the old `bot.py`
    handlers. `NudgeDecision.delay_secs` per [data-model.md](data-model.md).
  - Verify: `uv run pytest -q`.

- [x] T018 [US1] `CallController.channel_opened` (opening timer)
  - RED: `tests/test_controller_session.py` with fake sleep and hooks: (a) after `opening_wait_secs`
    `hooks.inject(opening_text)` runs once; (b) if `restaurant_spoke()` is called first, nothing is
    injected; (c) if the call finished first, nothing is injected; (d) `hooks=None` is a no-op; (e) calling
    `channel_opened` twice does not inject twice.
  - GREEN: asyncio task with generation check, like `NudgeScheduler`.
  - Verify: `uv run pytest -q`.

- [x] T019 [US1] Turn `order_agent/call.py` into a compatibility shim: `CallState` subclasses `CallController`
  - RED: `tests/test_controller_session.py::test_callstate_shim`: `CallState(brief, Settings(reports_dir=tmp_path), NOW)`
    is a `CallController`, exposes `.settings` and the same `finish`, `on_disconnect`, `add_line`,
    `transcript`, `report_path`; `make_on_end` still importable. The existing `tests/test_call.py` must pass
    unmodified.
  - GREEN: `class CallState(CallController)` with `__init__(brief, settings, now)` calling
    `super().__init__(brief, reports_dir=settings.reports_dir, now=now)`, plus `on_disconnect = drop`.
    Keep `llm_http_options` and `make_on_end` in `call.py` for now (removed in T031 and T024).
  - Verify: `uv run pytest -q` (`tests/test_call.py` unchanged).

### Step 4: voice tools (Pipecat schema adapter) with parity proof

- [x] T020 [US1] Add the voice-head layer to the boundary check; create `order_agent/heads/__init__.py` and `order_agent/heads/voice/__init__.py`
  - RED: snippets for layer `heads/voice`: `from fastapi import FastAPI`,
    `from order_agent.heads.http_api import x`, `from order_agent.evaltools import x`, and (task-specific
    narrowing for SC-005) `from order_agent.model.rules import OrderSession` and
    `from order_agent.model.matching import match_line` each give a violation; `import pipecat`,
    `from order_agent.controller import CallController` and `from order_agent.config import Settings` give
    none.
  - GREEN: add the `heads/voice` row to the checker. The SC-005 narrowing (heads may not import the rules
    engine or matching) is applied to all heads; it adds to
    [contracts/boundaries.md](contracts/boundaries.md), which has no such row yet.
  - Verify: `uv run pytest -q`.

- [x] T021 [US1] Create `order_agent/heads/voice/tools.py`: `build_tools(controller) -> ToolsSchema` (schemas only)
  - RED: `tests/test_voice_tools.py`: for a `CallController`, `build_tools(controller).standard_tools` has
    seven `FunctionSchema`s whose `name`, `description`, `properties`, `required` equal both
    `TOOL_SPECS` and the legacy `order_agent.tools.build_tools` output; every schema has a callable handler.
  - GREEN: loop over `controller.tool_specs()`, build `FunctionSchema` with a handler stub that calls
    `controller.perform`.
  - Verify: `uv run pytest -q`.

- [x] T022 [US1] Voice tool handlers: call `controller.perform` with a `reply` that maps `run_llm=False` to `FunctionCallResultProperties`
  - RED: `tests/test_voice_tools.py` using the `Harness` pattern from `tests/test_tools.py` (SimpleNamespace
    `params` with `arguments` and `result_callback`): exactly one `result_callback` call per tool call
    (including bad args), payload equals `{"ok":..., "message":...}`, successful `end_call` passes
    `properties.run_llm is False`, refused `end_call` and all other tools pass `properties=None`, and the
    result callback runs before the report file exists (record order with a fake hooks object).
  - GREEN: handler per [contracts/controller-api.md](contracts/controller-api.md) "Pipecat schema building".
  - Verify: `uv run pytest -q`.

- [x] T023 [US1] Parity test between the legacy `order_agent/tools.py` and the new voice tools
  - RED: `tests/test_tools_parity.py`: build both for identical briefs, run one shared argument matrix
    (every tool, valid and invalid arguments, a refusal such as a forbidden item, an over-budget add, a
    full happy-path sequence ending in `end_call`) through both and assert identical result payloads,
    identical `properties.run_llm`, and identical `session.events` (tool, args, ok, message). If this passes
    immediately because T021 and T022 are correct, add one case that exposes a mismatch first (for example
    non-dict arguments) to prove the test can fail, then fix.
  - GREEN: fix any discovered mismatch in the new code only.
  - Verify: `uv run pytest -q`. This file is deleted together with `tools.py` in T031.

### Step 5: voice pipeline

- [x] T024 [US1] Move `llm_factory.py` to `order_agent/heads/voice/llm_factory.py` and `llm_http_options` with it; leave shims
  - RED: `tests/test_voice_llm_factory_home.py`: `build_bot_llm`, `groq_reasoning_effort`, `llm_http_options`
    import from `order_agent.heads.voice.llm_factory`, and the old names (`order_agent.llm_factory.build_bot_llm`,
    `order_agent.call.llm_http_options`) are the same objects.
  - GREEN: `git mv` the factory, move `llm_http_options` from `call.py`, `call.py` and
    `order_agent/llm_factory.py` re-export. `tests/test_llm_factory.py` unchanged here.
  - Verify: `uv run pytest -q`.

- [x] T025 [US1] Move `make_probe` and `PROBE_TIMEOUT_SECS` from `bot.py` to `order_agent/heads/voice/probe.py`
  - RED: `tests/test_voice_probe.py`: `make_probe` imports from the new module, `PROBE_TIMEOUT_SECS == 10.0`,
    and `make_probe(Settings(google_api_key=None))` raises `RuntimeError` mentioning `GOOGLE_API_KEY`
    (existing `require_google_key` behaviour; no network, the genai import is lazy).
  - GREEN: move verbatim; `bot.py` imports it from the new location.
  - Verify: `uv run pytest -q`.

- [x] T026 [US1] Create `order_agent/heads/voice/hooks.py`: `PipecatHooks(context, worker, llm)` implementing `CallHooks`
  - RED: `tests/test_voice_hooks.py` with fakes: `await hooks.inject("x")` calls
    `context.add_message({"role": "developer", "content": "x"})` then `worker.queue_frames([...])` with one
    `LLMRunFrame`; `await hooks.hangup()` calls `llm.push_frame` with an `EndWorkerFrame`.
  - GREEN: implement per [contracts/controller-api.md](contracts/controller-api.md) "Voice-head `CallHooks`".
  - Verify: `uv run pytest -q`.

- [x] T027 [US1] Create `order_agent/heads/voice/bridge.py`: `register_events(transport, user_aggregator, assistant_aggregator, llm, controller, runner, ...)` mapping each Pipecat event to one controller call
  - RED: `tests/test_voice_bridge.py` with fake objects whose `event_handler(name)` returns a decorator that
    stores the function, and a fake controller recording calls. Assert the exact mapping of
    [contracts/controller-api.md](contracts/controller-api.md) "Voice head mapping": `on_client_connected`
    -> `channel_opened()`; `on_client_disconnected` -> `drop()` then `runner.cancel()`;
    `on_user_turn_started` -> `restaurant_spoke()`; `on_user_turn_message_added` -> `add_line("restaurant", text)`;
    `on_function_calls_started` -> `function_calls_started()`; `on_assistant_turn_started` ->
    `llm_turn_started()`; `on_assistant_turn_stopped` -> `llm_turn_ended(content, interrupted)`. Also: the
    bridge holds no state of its own (no flags or counters on the bridge object) and contains no
    `if` on message content.
  - GREEN: register the handlers; keep the `logger.info("Transcript ...")` lines as today.
  - Verify: `uv run pytest -q`.

- [x] T028 [US1] Create `order_agent/heads/voice/pipeline.py` (`run_bot`, `bot`, `transport_params`) built on the controller; reduce root `bot.py` to an entry shim
  - RED: `tests/test_bot_entry.py`: `import bot` exposes `bot` (coroutine function), `run_bot`,
    `transport_params` with keys `webrtc` and `eval`, `OPENING_WAIT_SECS` no longer defined in `bot.py`
    (controller owns it); `bot.run_bot is order_agent.heads.voice.pipeline.run_bot`; and the pipeline module
    source contains no use of `NudgeTracker`, `NudgeScheduler`, `CallState` or `add_message` outside
    `hooks.py` (read with `ast`); and an env-var test (FR-012, no network): with
    `monkeypatch.setenv` for `ORDER_BRIEF` (a brief under `tmp_path`), `ORDER_CALL_TIME` and
    `ORDER_REPORTS_DIR`, the extracted brief-and-settings setup used by `run_bot` (put it in a small function
    in `pipeline.py`, for example `load_call_inputs()`) returns that brief with the call time applied and
    that reports dir; `ORDER_AGENT_LLM_PROVIDER=groq` is read through `config.load_settings`.
  - GREEN: move `run_bot` body: settings and brief loading (with the `ORDER_CALL_TIME` override), model
    choice and probe, STT/LLM/TTS construction, `controller = CallController(brief, reports_dir=settings.reports_dir)` (no hooks yet),
    `LLMContext(tools=build_tools(controller))`, pipeline and worker, then
    `controller.attach_hooks(PipecatHooks(context, worker, llm))` (T014), `register_events(...)`, and after
    `runner.run()` `await controller.drop()`. Attach before the transport can connect (contract rule 0;
    document the choice in the commit). Root `bot.py` keeps `if __name__ == "__main__": from pipecat.runner.run import main; main()`.
  - Verify: `uv run pytest -q`, then `uv run python bot.py --help` exits 0 (loads the entry point, no API
    call, no model download).

- [x] T029 [US1] Migrate `tests/test_tools.py`, `tests/test_tool_registration.py`, `tests/test_llm_factory.py` to the new APIs (stated reason: `build_tools(session, on_end)` is replaced by `build_tools(controller)`; assertions unchanged)
  - RED: edit the three files first so they import `order_agent.heads.voice.tools.build_tools` and construct
    a `CallController` in the `Harness` (replace the `on_end` recording with a fake `CallHooks` whose
    `hangup` records into `self.ended`-equivalent). Same assertions, same cases. Run them: they pass
    against the new code; confirm each still contains every original assertion (`git diff` shows only
    construction and import lines changed). Explicit RED (mutation check, not committed): temporarily make the
    `run_llm=False` mapping in `heads/voice/tools.py` wrong, confirm the migrated `test_tools.py` fails on the
    `end_call` assertion, then revert. Record in the commit message that this is a refactor of tests
    (Constitution III, second bullet).
  - GREEN: none beyond the test edits.
  - Verify: `uv run pytest -q` (count at least the pre-task count).

- [x] T030 [US1] Port the two `make_on_end` tests in `tests/test_call.py` to `CallController.perform("end_call")` (stated reason: `make_on_end` is replaced by the controller's end-of-call sequence; research.md R9)
  - RED: write the ported tests first in `tests/test_controller_session.py` (they may already be partly
    covered by T016; add what is missing): (a) a successful end writes the report and `hooks.hangup()`
    runs; (b) when the report write fails (reports_dir is an existing file), `hangup()` still runs and
    nothing escapes. Then delete the two `make_on_end` tests from `tests/test_call.py` in the same commit,
    keeping their assertions' intent in the new tests (the diff must show equivalent assertions, none
    dropped).
  - GREEN: none expected; fix `perform` if a case is not yet met.
  - Verify: `uv run pytest -q`; `grep -n make_on_end tests` returns nothing.

- [x] T031 [US1] Delete legacy voice code: `order_agent/tools.py`, `tests/test_tools_parity.py`, `make_on_end` in `call.py`, and unused imports
  - RED: `tests/test_architecture.py::test_legacy_tools_module_gone` asserts `order_agent/tools.py` does not
    exist and `order_agent.call` has no `make_on_end`; fails until the deletion.
  - GREEN: delete them; `grep -rn "order_agent.tools\|make_on_end" .` must return nothing outside specs and docs.
  - Verify: `uv run pytest -q`.

- [x] T032 [US1] Review checkpoint (SC-005, no code): voice head contains zero business rules
  - Verify: `grep -rnE "Decimal|OrderSession|match_line|should_nudge|NudgeTracker" order_agent/heads/voice bot.py`
    returns no logic hits (type-only mentions in comments are acceptable and must be listed in the review
    note); the boundary test passes; the reviewer ticks each row of the mapping table in
    [contracts/controller-api.md](contracts/controller-api.md) against `bridge.py`. Findings go to the PR
    description, not to a new file.

- [x] T033 [US1] LIVE VERIFICATION, REQUIRES THE USER'S EXPLICIT GO-AHEAD (uses API quota; do not run without it): `happy_path` eval with the default setup (SC-004)
  - Prerequisite: T001 to T032 merged on the branch with a green suite. Ask the user and wait for a yes.
  - Run: `PYTHONIOENCODING=utf-8 uv run python run_suite.py --only happy_path` (see
    [quickstart.md](quickstart.md) section 5).
  - Baseline: the committed `evals/confirmation/unpriced-items-2026-11-25/` run 3, where `happy_path` passed.
    Expect: no worse than that baseline on the deterministic checks (outcome, budget, prices, forbidden
    items, required items; SC-004). Judge-only soft-quality differences, quota failures and simulator
    failures are not bot failures (Constitution IV); ambiguous cases count against the bot. Retry within the
    usual 3 attempts. If a deterministic check fails for a real reason, stop, do not start Step 6, and report
    with the attempt logs.
  - Evidence: scrub keys, account ids and local paths, then commit only after the user agrees, under the
    existing `evals/results/` convention.

- [ ] T034 [US1] MANUAL, user-run browser call (quickstart section 4): `PYTHONIOENCODING=utf-8 uv run python bot.py`, open `http://localhost:7860/client/`, play the restaurant
  - Expect: bot opens after about 3 s of silence, orders, confirms, ends, and a report appears in `reports/`.
    The user reports the result; no commit unless notes are wanted.

**Checkpoint**: User Story 1 delivered and verified live. Step 6 may not start until T033 has passed.

---

## Phase 4: User Story 2 - Use the order core without the voice stack (Priority: P2) (Step 6)

**Goal**: a second head (local HTTP API) drives the same controller with no Pipecat imports.

**Independent Test**: scripted `happy_path`-equivalent through the HTTP head with the import-budget test
proving no speech stack loaded (SC-003).

- [x] T035 [US2] Declare `fastapi` and `uvicorn` in `pyproject.toml` at the versions already in `uv.lock` (research R5)
  - RED: `tests/test_http_deps.py`: `fastapi.testclient.TestClient` and `uvicorn` import; and
    `pyproject.toml` text lists `fastapi` and `uvicorn` under `dependencies` (parse with `tomllib`).
  - GREEN: add `"fastapi==0.165.0"` and `"uvicorn"` (match the locked uvicorn version) to `dependencies`;
    run `uv lock`.
  - Verify: `git diff uv.lock` shows only project-metadata dependency lines (no new or upgraded packages),
    `uv run pytest -q`.

- [x] T036 [US2] Create `order_agent/heads/http_api/store.py` and `schemas.py` (`SessionStore`, request and response models)
  - RED: `tests/test_http_store.py`: `create` returns a 32-char hex id and a `CallController`; `get` of an
    unknown id raises the store's `NotFound`; `delete` removes; two creates yield different controllers with
    different `OrderSession` objects; creating beyond `max_sessions` raises `TooManySessions`; pydantic
    models reject a blank transcript text and a role other than `agent` or `restaurant`, and require
    exactly one of `brief` or `brief_name` ([contracts/http-api.md](contracts/http-api.md)).
  - GREEN: implement `SessionStore(max_sessions=100)` and the models in `schemas.py`.
  - Verify: `uv run pytest -q`.

- [x] T037 [US2] Create `order_agent/heads/http_api/app.py` skeleton: `create_app`, `GET /health`, uniform error body; add the `heads/http_api` rules to the boundary check
  - RED: `tests/test_http_head.py`: `GET /health` returns 200 `{"status":"ok"}`; an invalid body to any
    route returns 422 with `{"error":{"code":"validation_error","message":...}}`; architecture snippets for
    layer `heads/http_api`: `import pipecat`, `import torch`, `from order_agent.heads.voice import x`,
    `from order_agent.model.rules import OrderSession` each violate; `from fastapi import FastAPI` and
    `from order_agent.controller import CallController` do not.
  - GREEN: app factory `create_app(reports_dir, brief_dir=Path("briefs"), clock=datetime.now)`, exception
    handlers for `NotFound` (404 `session_not_found`), closed session (409 `session_closed`), report not
    ready (409 `report_not_ready`), too many (429 `too_many_sessions`), request validation (422).
  - Verify: `uv run pytest -q`.

- [x] T038 [US2] `POST /sessions` in `order_agent/heads/http_api/app.py`
  - RED: `tests/test_http_head.py`: inline `brief` returns 201 with `session_id`, `instructions` equal to
    `build_system_prompt(brief)`, `opening_text`, and 7 `tools`; `brief_name: "example"` loads
    `briefs/example.yaml`; `call_time` overrides; 422 for both or neither brief field, for an unknown or
    path-like `brief_name` (`../x`), and for an invalid brief; 429 beyond the cap.
  - GREEN: implement with `load_brief` from the model layer and the controller built with `hooks=None`.
  - Verify: `uv run pytest -q`.

- [x] T039 [US2] `GET /sessions/{id}`
  - RED: `tests/test_http_head.py`: returns `state` `live`, `order_state` `open`, `transcript_lines` 0,
    `report_ready` false for a new session; `confirmed` after a confirm action; 404 with the error body for
    an unknown id.
  - GREEN: implement from controller attributes only.
  - Verify: `uv run pytest -q`.

- [x] T040 [US2] `POST /sessions/{id}/actions`
  - RED: `tests/test_http_head.py`: a valid `add_item` returns 200 `{"ok":true,...,"ended":false}`; a
    forbidden item and an over-budget add return 200 with `ok:false` and the same message text the
    dispatcher gives; bad arguments return 200 `ok:false` `Refused: ...`; unknown `tool` returns 422; unknown
    session 404; after a successful `end_call` (`ended:true`) any further action returns 409
    `session_closed`.
  - GREEN: delegate to `controller.perform(tool, arguments)`; validate the tool name against `tool_specs()`.
  - Verify: `uv run pytest -q`.

- [x] T041 [US2] `POST /sessions/{id}/transcript`
  - RED: `tests/test_http_head.py`: 204 and `transcript_lines` increments; blank text or bad role 422;
    unknown 404; closed 409.
  - GREEN: delegate to `controller.add_line`.
  - Verify: `uv run pytest -q`.

- [x] T042 [US2] `POST /sessions/{id}/end`, `GET /sessions/{id}/report`, `DELETE /sessions/{id}`
  - RED: `tests/test_http_head.py`: `end` on a live session writes a `call_dropped` report and returns the
    report body (same shape as `GET .../report`: `report`, `summary`, `report_path`, where `report_path` is
    relative to the reports dir and never absolute, `ReportResponse.report_path` in
    [data-model.md](data-model.md)); second `end` returns
    the same report and only one JSON file exists in `reports_dir`; `GET report` on a live session returns
    409 `report_not_ready`; after `end_call` the report returns `outcome: "ordered"`; `DELETE` of a live
    session writes a `call_dropped` report first, then 204, then 404 on the next GET; 404 cases.
  - GREEN: delegate to `controller.drop()`, `controller.report`, `summarise`.
  - Verify: `uv run pytest -q`.

- [x] T043 [US2] Isolation test for concurrent sessions (FR-007)
  - RED: `tests/test_http_head.py::test_two_sessions_do_not_leak`: create two sessions from different
    briefs, interleave actions (add items to A, lock a price in B, set fees in A), run both to a report with
    `asyncio.gather`/`httpx.AsyncClient`, assert carts, price locks, transcripts and report files are
    independent. Include "actions on session A after A ends do not affect B".
  - Explicit RED (mutation check, not committed): temporarily make `SessionStore.create` reuse one shared
    `CallController`, confirm this test fails, then revert.
  - GREEN: should pass if the earlier tasks are correct; if not, fix the store or controller (no shared state).
  - Verify: `uv run pytest -q`.

- [x] T044 [US2] Scripted `happy_path`-equivalent order through the HTTP head (SC-003)
  - RED: `tests/test_http_happy_path.py`: read the `happy_path` brief and expected order from
    `evals/expected.yaml` and `evals/scenarios/happy_path.yaml`, start a session, send the actions an LLM
    would (add items with stated prices, `set_fees`, `confirm_order` with the quoted total and minutes,
    `end_call` outcome `ordered`), fetch the report, assert `outcome == "ordered"`, the totals equal the
    expected, and that the set of report keys equals `set(build_report(...).model_dump().keys())` and
    `CallReport.model_validate` accepts the body.
  - Explicit RED (mutation check, not committed): temporarily make the `end_call` action skip report writing,
    confirm this test fails, then revert.
  - GREEN: fix any gap found.
  - Verify: `uv run pytest -q`.

- [x] T045 [US2] Import-budget test: the HTTP head loads no speech or Pipecat modules (FR-007)
  - RED: `tests/test_http_import_budget.py` runs `python -I -c "import order_agent.heads.http_api.app, sys; ..."`
    in a subprocess (`sys.executable`) and asserts none of `pipecat`, `torch`, `faster_whisper`, `kokoro`,
    `google.genai`, `openai` is in `sys.modules`. If it passes at once, first run it against a throwaway
    import of `pipecat` to see it fail, then remove that line (do not commit the throwaway).
  - GREEN: remove any accidental import found (for example a heavy import at the top of `schemas.py` or
    `store.py`).
  - Verify: `uv run pytest -q`.

- [x] T046 [US2] `order_agent/heads/http_api/__main__.py`: run with uvicorn on `127.0.0.1`, `--port` option
  - RED: `tests/test_http_main.py`: `build_parser().parse_args([])` gives `host == "127.0.0.1"` and port 8000;
    `main(["--port","9001"], serve=fake)` calls `fake(app, host="127.0.0.1", port=9001)`; there is no
    `--host` option (local-only, spec assumption). Reports dir comes from `load_settings().reports_dir`
    (`ORDER_REPORTS_DIR`).
  - GREEN: implement; `uvicorn` imported inside `main` only.
  - Verify: `uv run pytest -q`.

- [ ] T047 [US2] MANUAL, user-run (no API quota): `uv run python -m order_agent.heads.http_api`, then the curl script in [quickstart.md](quickstart.md) section 3
  - Expect: allowed and refused answers as in the tests, report fields match a voice-call report, startup
    about a second. The user reports the result.

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Layer boundaries that can't silently erode (Priority: P3) (Step 7)

**Goal**: eval tooling is separate, all shims are gone, and the boundary check covers every module.

**Independent Test**: add a forbidden import on a scratch edit and watch the check fail (T055); remove it
and watch it pass.

- [x] T048 [US3] Move `eval_config.py` and `preflight.py` to `order_agent/evaltools/`; update importers
  - RED: add the `evaltools` layer to the boundary check (snippets: `from order_agent.controller import x`,
    `from order_agent.heads.voice import x` violate; `import pipecat`, `import yaml`,
    `from order_agent.model.report import CallReport` do not), and `tests/test_evaltools_home.py` asserting
    `order_agent.evaltools.eval_config.apply_eval_configs` and `order_agent.evaltools.preflight.preflight_message`
    import. Fails: package missing.
  - GREEN: `git mv`, add `evaltools/__init__.py`, update `run_suite.py`, `tests/test_eval_config.py` and
    `tests/test_preflight.py` imports (stated reason: module moved; no assertion changed). No shim.
  - Verify: `uv run pytest -q` and `uv run python run_suite.py --help` exits 0.

- [x] T049 [US3] Move `throttle.py` and `eval_llm.py` to `order_agent/evaltools/`; update importers
  - RED: `tests/test_evaltools_home.py` extended: `Throttle`, `is_rate_limit_error`, `gemini_llm` import from
    the new paths; and a compat test (FR-010): for every `factory:` value in `evals/judge*.yaml` and
    `evals/simulator*.yaml` (parse with `yaml`), `importlib` resolves it (module `order_agent.eval_llm`,
    attribute) to a callable that is the same object as the one in `order_agent.evaltools.eval_llm`.
    Fails after the move until the compat module exists.
  - GREEN: `git mv` `eval_llm.py` and `throttle.py` into `evaltools/`; keep `order_agent/eval_llm.py` as a
    compat module containing only re-exports of `gemini_llm gemini_classifier gemini_native_llm groq_llm
    groq_classifier ollama_classifier ThrottledOpenAILLMService ThrottledGroqLLMService` (and an
    `__all__`). The `evals/*.yaml` files and docs are NOT edited. Update other importers (`run_suite.py` if
    any, `tests/test_eval_llm.py`, `tests/test_throttle.py`) to the new paths (stated reason: module moved).
  - Verify: `uv run pytest -q`.

- [x] T050 [US3] Move `suite.py` to `order_agent/evaltools/suite.py`; update importers
  - RED: `tests/test_evaltools_home.py` extended for `load_expected`, `rescore_run`, `render_summary` etc.
  - GREEN: `git mv`, update `run_suite.py`, `tests/test_suite.py`, `tests/test_persona_totals.py` imports
    (stated reason: module moved), and its imports of `brief`, `matching`, `report` to `order_agent.model.*`.
  - Verify: `uv run pytest -q`.

- [x] T051 [US3] Point every remaining consumer at the new module paths (no shim users left)
  - RED: `tests/test_architecture.py::test_no_imports_of_legacy_shims` fails while any file under `tests/`,
    `run_suite.py`, `bot.py` or `order_agent/` imports `order_agent.{brief,matching,rules,report,prompt,call,llm_factory}`
    (ast scan of the repo, excluding the shim files themselves).
  - GREEN: update imports to `order_agent.model.*`, `order_agent.controller.*`, `order_agent.heads.voice.*`
    in `tests/test_brief.py`, `test_matching.py`, `test_rules_*.py`, `test_report.py`, `test_prompt.py`,
    `test_call.py`, `test_persona_totals.py`, `test_scenarios.py` (if needed), `conftest.py`, `run_suite.py`,
    `order_agent/**`. Stated reason in the commit: modules moved; no assertion edited.
  - Verify: `uv run pytest -q`.

- [x] T052 [US3] Delete the shims and make classification strict
  - RED: set `LEGACY_FLAT = set()` in `tests/architecture.py`, allow only `order_agent/eval_llm.py` as a
    compat module and add a test that it contains only re-export `ImportFrom` statements and `__all__`
    (ast); `test_every_module_is_classified` now fails because the shim files
    `order_agent/{brief,matching,rules,report,prompt,call,llm_factory}.py` exist.
  - GREEN: delete the shims. If `tests/test_call.py` still tests `CallState`, port its cases to
    `CallController` first (they are already duplicated in `tests/test_controller_session.py` by T015;
    delete `CallState` and keep `test_call.py` only for cases not duplicated, with the reason stated).
  - Verify: `uv run pytest -q`; `ls order_agent` shows only `__init__.py`, `config.py`, `eval_llm.py` (compat),
    `model/`, `controller/`, `heads/`, `evaltools/`.

- [x] T053 [US3] Runtime import-graph test for Model and Controller
  - RED: `tests/test_architecture.py::test_runtime_import_graph`: a `python -I` subprocess imports
    `order_agent.model` modules and `order_agent.controller` and asserts none of `pipecat`, `fastapi`,
    `starlette`, `uvicorn`, `google`, `openai`, `torch` is in `sys.modules`
    ([contracts/boundaries.md](contracts/boundaries.md) item 4).
  - GREEN: fix any transitive leak found (should be none).
  - Verify: `uv run pytest -q`.

- [x] T054 [US3] Rescore verification on a copy of committed evidence (no API calls, FR-010)
  - Run: copy the most recent directory in `evals/results/` that has attempt report JSON to the scratchpad,
    run `uv run python run_suite.py --rescore <copy>`, diff the regenerated `summary.md` against the
    original (it rewrites in place, hence the copy). Expect identical classifications; only the title line
    mentioning "rescored" may differ. Report any other difference and stop. No commit unless a code fix is
    needed.

- [x] T055 [US3] Demonstrate the boundary check failing (acceptance scenario for US3), uncommitted
  - Steps: add `import pipecat` to `order_agent/model/rules.py`, run `uv run pytest tests/test_architecture.py -q`,
    expect a failure naming `order_agent/model/rules.py` and `pipecat`; repeat with `import fastapi` in
    `order_agent/controller/session.py`; revert both with `git checkout -- <file>`; rerun and expect pass.
  - Verify: `git status --short` is clean afterwards. Record the failing output in the PR description.

**Checkpoint**: all three user stories complete.

---

## Phase 6: Polish and cross-cutting (Step 8)

- [x] T056 Add the architecture section to `README.md` (FR-011, SC-006)
  - RED: `tests/test_readme_architecture.py`: README contains the headings "Architecture", "Add a new head",
    mentions each of `order_agent/model`, `order_agent/controller`, `order_agent/heads/voice`,
    `order_agent/heads/http_api`, `order_agent/evaltools`, and names every `.py` file under those
    directories (walk the tree) in the module map, so a new module without a README entry fails.
  - GREEN: layers diagram (ASCII), table module to layer, the dependency rule, the boundary test, the HTTP
    head run command, and "how to add a head" (steps from [contracts/boundaries.md](contracts/boundaries.md)).
  - Verify: `uv run pytest -q`.

- [x] T057 Update README "Project layout", "Unit tests" and command lines to match the new tree; update only numbers that changed
  - RED: extend `tests/test_readme_architecture.py`: the old layout block lines (`rules.py  the rules engine`
    at the flat path, `call.py`) are gone, and the README's "Unit tests" row (currently `285 passing`, stale
    against the 366 baseline) equals the count from `uv run pytest --collect-only -q` after all tasks
    (Constitution IV: numbers trace to evidence). State the 285 to final-count correction in the commit
    message.
  - GREEN: edit `README.md` only; leave results tables and other evidence numbers untouched.
  - Verify: `uv run pytest -q`.

- [x] T058 Final verification and requirement checklist (no new code)
  - Verify: `uv run pytest -q` all green and count at least 366 plus the new tests; `uv run python bot.py --help`
    and `uv run python run_suite.py --help` exit 0; `git diff main...HEAD | grep -nE 'gsk_|AIza|org_[A-Za-z0-9]{16,}'`
    empty; `git log --oneline` shows only green, single-purpose commits; list the changed existing tests with
    their reasons (research.md R9) in the PR description; tick FR-001 to FR-012 and SC-001 to SC-006 against
    evidence (T033 for SC-004, T044 for SC-003, T045 for FR-007, T055 for SC-002, T032 for SC-005, T056 for SC-006).
  - Independent final review (spec compliance then code quality) before any merge. Do not push or merge
    without the user's explicit OK.

---

## Dependencies and execution order

- Phase 1 then Phase 2 (blocking) then Phase 3 (US1) then Phase 4 (US2) then Phase 5 (US3) then Phase 6.
  This is also the plan's step order 1 to 8; do not reorder.
- Within Phase 3: T007 to T010 (Step 2) before T011 to T019 (Step 3) before T020 to T023 (Step 4) before
  T024 to T034 (Step 5; T030 must precede T031). T033 (live eval, user go-ahead) gates Phase 4.
- T009 depends on T008 only for the shared names check; T010 on T009; T013 on T008 to T010; T014 to T018
  on T013 (T014 attach_hooks before T016 to T018); T019 on T015; T021 to T023 on T019; T028 on T014, T016, T017, T018, T026, T027; T030 on T016; T031 on T029 and T030.
- Phase 4: T035 first; T036 to T042 are sequential (one file, `app.py`); T043 to T046 after T042.
- Phase 5: T048 to T050 sequential (they all edit `run_suite.py`); T051 after them; T052 after T051.

### Parallel opportunities

None are marked. Candidates were checked and rejected: T011 and T012 both touch `call.py` or the shims and
share `tests/test_architecture.py` checks; T024, T025 and T026 touch `call.py`, `bot.py` and the voice head
package that T028 consumes; the HTTP tasks share `app.py`; the evaltools moves share `run_suite.py`. Running
them in order costs little and removes merge conflicts between fresh implementers. A task may be marked
[P] later only if the file sets are verified disjoint.

## Implementation strategy

- **MVP = User Story 1 (Phases 1 to 3)**: restructure with identical behaviour, proven by the suite, the
  parity test (T023) and the live eval (T033). Stop and review there.
- Then US2 (Phase 4) as an additive increment, then US3 (Phase 5) to remove shims and lock the boundary,
  then docs.
- Keep each commit green, small and independently reviewable; the riskiest task group is Step 5
  (T026 to T028), so T027's fake-hooks tests and T033 are the safety net before anything builds on it.

## Notes

- Task count: 58 (Setup 1, Foundational 5, US1 28, US2 13, US3 8, Polish 3). T014 (`attach_hooks`) and
  T030 (port the `make_on_end` tests) were added after the analysis (F2, F4); IDs T014 and later were
  renumbered accordingly, so the task IDs quoted in `analysis.md` refer to the earlier numbering.
- Manual or user-gated tasks: T033 (API quota, needs go-ahead), T034, T047 (user-run), T054 and T055 (no
  API, no commit).
