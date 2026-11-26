# Data Model: Headless MVC Architecture

No order-domain data changes. This lists the entities the feature touches or adds, with the layer that
owns each.

## Existing (Model layer, moved unchanged)

| Entity | Module | Key fields | Notes |
|---|---|---|---|
| `OrderBrief`, `WantedLine` | `model/brief.py` | customer_name, wanted[item, quantity, substitutes, optional], budget_pkr (Decimal), never{rule: keywords}, deliver_by, call_time, notes | validated by pydantic; money is `Decimal` |
| `OrderSession` | `model/rules.py` | brief, items[CartItem], delivery_fee_pkr, tax_pkr, minimum_order_pkr, state, events[ToolEvent], delivery_eta, quoted_total_pkr | state: `open -> confirmed -> ended` |
| `ToolResult` | `model/rules.py` | ok, message | the allowed/refused answer, with reason |
| `ToolEvent` | `model/rules.py` | tool, args, ok, message, at | audit trail copied into the report |
| `CallReport`, `TranscriptLine` | `model/report.py` | outcome, reason, items, fees, totals, tool_events, transcript, started_at, ended_at | schema unchanged, so `--rescore` and evidence stay valid |

## New or re-homed (Controller layer)

### Instructions (`controller/prompt.py`)
`build_system_prompt(brief: OrderBrief) -> str`, moved unchanged from `order_agent/prompt.py`. It is
the text that tells the LLM who it is and how to run the call, so it belongs to the Controller, not the
Model (the Model holds the domain and its rules only). It reads `OrderBrief` and nothing else.

### `ToolSpec` (`controller/toolspecs.py`)
Frozen dataclass: `name: str`, `description: str`, `properties: dict` (JSON-schema property map),
`required: list[str]`. Seven instances, copied verbatim from today's `FunctionSchema`s. Validation: names
are unique and match the dispatcher's handler table (a test asserts both sets are equal).

### `ToolOutcome` (defined in `controller/tools.py`, re-exported from `controller/session.py`)
Frozen dataclass: `ok: bool`, `message: str`, `run_llm: bool = True`, `ended: bool = False`.
`as_payload()` returns `{"ok": ok, "message": message}`, the exact dict the LLM receives today.
`run_llm` is False only for a successful `end_call`. `ended` is True when the call has ended.

### `NudgeDecision` (`controller/session.py`)
Frozen dataclass: `nudge: bool`, `text: str = NUDGE_TEXT`, `delay_secs: float = NUDGE_DELAY_SECS`.
Returned by `llm_turn_ended`. When `hooks` is set, the controller schedules the delayed nudge itself;
the decision is also returned so a head or test can observe it.

### `CallHooks` (Protocol, `controller/session.py`)
`async inject(text: str) -> None` (add a developer message and run the LLM) and
`async hangup() -> None` (end the channel). Supplied by a head; absent for the HTTP head.

### `CallController` (`controller/session.py`)
Replaces `CallState`. One instance per conversation.

| Field | Type | Meaning |
|---|---|---|
| `session` | `OrderSession` | the Model state (cart, locks, events) |
| `transcript` | `list[TranscriptLine]` | lines in order |
| `started_at` | `datetime` | call start |
| `report` | `CallReport or None` | set once by `finish` |
| `report_path` | `Path or None` | where it was written |
| `_lock` | `asyncio.Lock` | serialises `perform`/`finish` |
| `_nudges`, `_scheduler`, `_opening` | internal | nudge flags/timer, opening timer |

**State machine** (controller level, derived from existing fields):

```text
live --perform(end_call ok)--> ended(report written, hangup) 
live --finish(outcome)-------> ended
live --drop()----------------> ended (outcome call_dropped)
ended --any later perform/transcript--> refused by the rules engine ("the order is already ended"); the HTTP head answers 409 first
ended --finish/drop again----> returns the same report (idempotent; one report ever)
```

Within `live`, `OrderSession.state` runs `open -> confirmed`; `end_call` moves it to `ended`.
A drop after `confirmed` keeps today's reason text ("... after the order was confirmed (total Rs N)").

Validation rules (all unchanged, still in `model/rules.py`): budget, allow-list, forbidden foods,
quantities, minimum order, delivery deadline, price/fee locks, quote fidelity. The controller adds only
argument-shape validation that exists today in `tools.py` (text non-empty, money is a finite number,
whole numbers, optional flags).

## New (HTTP head, `heads/http_api`)

Pydantic request/response models (full shapes in `contracts/http-api.md`):

| Model.field | Constraint |
|---|---|
| `StartSession.brief` / `StartSession.brief_name` | exactly one of the two is present; `brief` validates as `OrderBrief` |
| `StartSession.brief_name` | matches `^[A-Za-z0-9_-]+$` (no path separators) |
| `StartSession.call_time` | optional datetime |
| `ActionRequest.tool` | one of the seven `ToolSpec.name` values |
| `ActionRequest.arguments` | JSON object |
| `TranscriptRequest.role` | `agent` or `restaurant` |
| `TranscriptRequest.text` | non-blank |
| `ReportResponse.report_path` | path relative to the server's reports dir (never absolute) |

Other models: `SessionInfo`, `ActionResult`, `EndRequest`.
`SessionStore`: `dict[str, CallController]` with `create`, `get`, `delete`, `count`; `SessionStore.max_sessions` defaults to 100. Session id is a
random uuid4 hex string and carries no meaning.

## Relationships

```text
Head --(calls)--> CallController --(owns)--> OrderSession --(reads)--> OrderBrief
                       |--(builds)--> CallReport (from OrderSession + transcript)
Head --(implements)--> CallHooks <--(calls out)-- CallController
```
