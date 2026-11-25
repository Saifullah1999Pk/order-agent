# Contract: Controller API (`order_agent.controller`)

Channel-independent. No Pipecat, transport or web-framework imports. Signatures are the contract; bodies
belong to implementation.

```python
# order_agent/controller/toolspecs.py
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    properties: dict          # JSON-schema property map
    required: list[str]

TOOL_SPECS: tuple[ToolSpec, ...]   # add_item, set_price, remove_item, set_fees,
                                   # set_minimum_order, confirm_order, end_call

# order_agent/controller/session.py
@dataclass(frozen=True)
class ToolOutcome:
    ok: bool
    message: str
    run_llm: bool = True      # False only for a successful end_call
    ended: bool = False       # True once the call has ended
    def as_payload(self) -> dict: ...      # {"ok": ..., "message": ...}

@dataclass(frozen=True)
class NudgeDecision:
    nudge: bool
    text: str = NUDGE_TEXT
    delay_secs: float = NUDGE_DELAY_SECS

class CallHooks(Protocol):
    async def inject(self, text: str) -> None: ...   # add a developer message and run the LLM
    async def hangup(self) -> None: ...              # end the channel (after the report is written)

class CallController:
    def __init__(self, brief: OrderBrief, *, reports_dir: Path,
                 now: datetime | None = None, hooks: CallHooks | None = None,
                 opening_wait_secs: float = 3.0, nudge_delay_secs: float = 3.0,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None: ...

    # --- start
    @property
    def instructions(self) -> str: ...        # build_system_prompt(brief), in controller/prompt.py
    @property
    def opening_text(self) -> str: ...        # "Nobody has spoken yet. Open the call: ..."
    def tool_specs(self) -> tuple[ToolSpec, ...]: ...
    def channel_opened(self) -> None: ...     # start opening timer (no-op if hooks is None)

    # --- tool actions
    async def perform(self, tool: str, arguments: Mapping | None,
                      reply: Callable[[ToolOutcome], Awaitable[None]] | None = None) -> ToolOutcome: ...

    # --- transcript and conversation events
    def add_line(self, role: Literal["agent", "restaurant"], text: str) -> None: ...
    def restaurant_spoke(self, text: str | None = None) -> None: ...   # flag, cancel nudge/opening, line
    def llm_turn_started(self) -> None: ...                            # cancels pending nudge
    def function_calls_started(self) -> None: ...
    def llm_turn_ended(self, content: str, interrupted: bool = False) -> NudgeDecision: ...

    # --- finish
    async def finish(self, outcome: Literal["ordered", "not_ordered", "call_dropped"], reason: str) -> Path: ...
    async def drop(self) -> Path: ...         # call_dropped; "after the order was confirmed" when applicable

    # --- read
    session: OrderSession
    transcript: list[TranscriptLine]
    report: CallReport | None
    report_path: Path | None
    @property
    def finished(self) -> bool: ...
```

## Behaviour rules (all preserved from today)

1. `perform` never raises. Unknown tool name returns `ToolOutcome(False, "Refused: unknown tool 'x'.")`.
   Bad or missing arguments return the same `Refused: ...` strings as `tools.py` today (for example
   `Missing or invalid 'name': it must be non-empty text.`). Internal errors return
   `Refused: internal error (...)`. Exactly one outcome per call.
2. A successful `end_call` returns `run_llm=False, ended=True`. A refused `end_call` returns `run_llm=True`.
3. Order inside `perform("end_call")` on success: build outcome, `await reply(outcome)` (if given), then
   `finish(outcome, reason)` (a write failure is logged, not raised), cancel any pending nudge, then
   `hooks.hangup()` (always attempted, even if finish failed). A failure in `reply` does not skip the
   end-of-call work.
4. `finish` and `drop` write the report at most once, safe under concurrent calls, and return the same
   path afterwards. `drop` after a confirmed order uses the existing reason text.
5. `restaurant_spoke` sets the flag, resets the nudge counter, cancels any pending nudge and the opening
   timer, and (when `text` is given) appends a `restaurant` line.
6. `llm_turn_ended` appends an `agent` line only when `content` is non-blank, applies `NudgeTracker`
   (`should_nudge`, `MAX_NUDGES=2`, skipped when interrupted), and when a nudge is due and `hooks`
   is set, schedules `hooks.inject(NUDGE_TEXT)` after `nudge_delay_secs`.
7. The opening timer fires `hooks.inject(opening_text)` after `opening_wait_secs` unless the restaurant
   has spoken or the call has finished.
8. After the call has ended, nudges and openings never fire.

## Voice head mapping (Pipecat event to controller call)

| Pipecat event | Controller call |
|---|---|
| `transport on_client_connected` | `controller.channel_opened()` |
| `transport on_client_disconnected` | `await controller.drop()`, then `runner.cancel()` |
| `user_aggregator on_user_turn_started` | `controller.restaurant_spoke()` |
| `user_aggregator on_user_turn_message_added` | `controller.add_line("restaurant", text)` |
| `llm on_function_calls_started` | `controller.function_calls_started()` |
| `assistant_aggregator on_assistant_turn_started` | `controller.llm_turn_started()` |
| `assistant_aggregator on_assistant_turn_stopped` | `controller.llm_turn_ended(content, interrupted)` |
| function call (tool handler) | `await controller.perform(name, args, reply=send)`; `send` maps `run_llm=False` to `FunctionCallResultProperties(run_llm=False)` |
| after `runner.run()` returns | `await controller.drop()` (no-op if a report exists) |

Voice-head `CallHooks`: `inject(text)` does `context.add_message({"role": "developer", "content": text})`
then `worker.queue_frames([LLMRunFrame()])`; `hangup()` does `llm.push_frame(EndWorkerFrame())`.

Note: `restaurant_spoke()` and `add_line("restaurant", ...)` stay two separate calls in the voice head
because Pipecat fires `on_user_turn_started` and `on_user_turn_message_added` at different times; the
controller does not merge them.

## Pipecat schema building (voice head only)

`heads/voice/tools.py: build_tools(controller) -> ToolsSchema` builds one `FunctionSchema` per
`controller.tool_specs()` entry (same name, description, properties, required) and a handler
`async def handler(params): outcome = await controller.perform(spec.name, params.arguments, reply=send)`.
`send` calls `params.result_callback(outcome.as_payload(), properties=...)`.
