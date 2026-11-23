# Restaurant Order Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a voice agent that phones a restaurant as the customer, places an order within the user's hard rules, and reports the outcome. A Pipecat eval suite, with a simulated restaurant, checks it.

**Architecture:** One free-form LLM agent (Pipecat cascade: Whisper → Gemini → Kokoro) with function-calling tools. Every tool call goes through a pure-Python rules engine (`OrderSession`) that enforces the brief: budget, allow-list, `never` keywords, completeness and delivery deadline. The LLM talks; the code decides what's allowed. Evals use Pipecat's built-in simulation: a persona LLM plays restaurant staff, and a judge LLM scores the call. Both run on Gemini through its OpenAI-compatible endpoint. Deterministic checks on the call report override the judge for hard rules.

**Tech Stack:** Python 3.12, uv, `pipecat-ai==1.17.0` (extras: google, openai, webrtc, runner, silero, whisper, kokoro, cli), pydantic v2, PyYAML, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-11-23-restaurant-order-agent-design.md`. Read it before any task. This plan argues from it.

## Global Constraints

- Project root: `C:\Users\Saif\Voice-Agent\order-agent` (its own git repo, **local only**; never push or add a remote without Saif's explicit OK).
- `pipecat-ai` pinned to exactly `1.17.0` from PyPI. Don't depend on the local clone at `../pipecat`, but read it freely as a reference (`../pipecat/src/pipecat/evals/`, `../pipecat/examples/`).
- Python 3.12 (`uv python pin 3.12`). Windows 11, CPU only.
- Every command that runs a Pipecat bot or eval is prefixed with `PYTHONIOENCODING=utf-8` (the dev runner crashes on non-UTF-8 stdout).
- Money is always `decimal.Decimal`, never `float`. Currency is PKR.
- LLM: one free Gemini key, `GOOGLE_API_KEY`, read from `order-agent/.env` (gitignored). Primary model `gemini-3.5-flash-lite`, fallback `gemini-2.5-flash`. No other keys, no second projects.
- Gemini OpenAI-compatible base URL: `https://generativelanguage.googleapis.com/v1beta/openai/`
- Synthetic data only (fake names, numbers, addresses, restaurants).
- English only for v1.
- Agent outcomes from `end_call`: `ordered` | `not_ordered`. The report adds `call_dropped` when the call ends without `end_call`.
- Opening: the agent waits **3 seconds** for a greeting, then speaks first.
- A rate-limit or overload error (HTTP 429/503) during an eval is reported as `quota_error`, never as a failed scenario.

## Review Focus

1. **Prices spoken in odd forms** ("twelve hundred", "Rs. 1,200"). The LLM converts them to numbers, but a zero, negative or non-numeric price must be refused, never added. *(Task 3 test `test_add_item_rejects_nonpositive_price`; Task 6 test `test_handler_rejects_unparseable_price`.)*
2. **Item-name variations** ("Chicken Biryanis", "biryani, chicken") must match the brief, while a partial name ("chicken") must not match "chicken biryani". *(Task 3 tests `test_match_ignores_case_order_plural` and `test_match_rejects_partial_name`.)*
3. **The restaurant quotes a total that differs from the cart** (it forgot the delivery fee, or rounded). `confirm_order` must refuse and state the cart total, so the agent can clear up the difference. *(Task 4 test `test_confirm_rejects_mismatched_total`.)*
4. **The call ends without `end_call`** (the client hangs up, idle timeout). A report with outcome `call_dropped` must still be written. *(Task 7 test `test_disconnect_writes_dropped_report`.)*
5. **Gemini returns 429/503 mid-eval.** The suite records `quota_error`, not `fail`. *(Task 9 test `test_classify_error_quota`.)*

---

## File Structure

```
order-agent/
  pyproject.toml            # deps, pytest config
  .python-version, .gitignore, .env (gitignored), README.md
  bot.py                    # Pipecat entry point: pipeline, transports, opening, call lifecycle
  order_agent/
    __init__.py
    config.py               # env settings + model pick with fallback
    eval_llm.py             # factory: Gemini via OpenAI-compatible endpoint (persona + judge)
    brief.py                # OrderBrief model + load_brief()
    matching.py             # item-name normalisation + matching
    rules.py                # OrderSession: the deterministic rules engine
    report.py               # CallReport, build/summarise/write
    prompt.py               # build_system_prompt(brief)
    tools.py                # Pipecat FunctionSchemas wrapping OrderSession
    suite.py                # deterministic report checks, error classification, suite runner
  briefs/example.yaml       # the spec §5.1 brief
  evals/
    simulator.yaml, judge.yaml        # persona + judge LLM config (factory → eval_llm)
    briefs/<scenario>.yaml            # one brief per scenario
    scenarios/<scenario>.yaml         # persona, goal, success, metrics
    expected.yaml                     # deterministic expectations per scenario
  spike/                    # Task 2 only (throwaway, kept for the record)
  reports/                  # call reports (gitignored)
  tests/                    # pytest
  docs/superpowers/{specs,plans}/
```

---

### Task 1: Project setup and Gemini LLM factory

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `.env`, `README.md`, `order_agent/__init__.py`, `order_agent/config.py`, `order_agent/eval_llm.py`
- Test: `tests/test_config.py`, `tests/test_eval_llm.py`

**Interfaces:**
- Produces:
  - `config.Settings` (pydantic model): `google_api_key: str`, `model: str = "gemini-3.5-flash-lite"`, `fallback_model: str = "gemini-2.5-flash"`, `reports_dir: Path = Path("reports")`, `brief_path: Path = Path("briefs/example.yaml")`, `call_time: datetime | None = None`.
  - `config.load_settings() -> Settings` reads `.env` and the env vars `GOOGLE_API_KEY`, `ORDER_AGENT_MODEL`, `ORDER_AGENT_FALLBACK_MODEL`, `ORDER_REPORTS_DIR`, `ORDER_BRIEF`, `ORDER_CALL_TIME` (ISO 8601).
  - `config.pick_model(settings, probe: Callable[[str], Awaitable[bool]]) -> Awaitable[str]` returns `settings.model` if the probe succeeds, else `settings.fallback_model`.
  - `config.GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"`
  - `eval_llm.gemini_llm(config: dict) -> OpenAILLMService`. A Pipecat evals factory: `base_url=GEMINI_OPENAI_BASE_URL`, `api_key` from `GOOGLE_API_KEY`, and `model=config.get("model", "gemini-3.5-flash-lite")`.

- [ ] **Step 1: Set up the project.** The repo already exists (branch `feat/order-agent-v1`; design doc and plan committed on `main`; `.gitignore` present, also ignoring `.superpowers/`). Run `uv python pin 3.12`. Write `pyproject.toml` (project name `order-agent`; dependencies `pipecat-ai[google,openai,webrtc,runner,silero,whisper,kokoro,cli]==1.17.0`, `pyyaml`, `python-dotenv`; dev group `pytest`, `pytest-asyncio`; `[tool.pytest.ini_options] asyncio_mode = "auto"`; make it an **installable package** with a `[build-system]` (hatchling, `packages = ["order_agent"]`), so `order_agent.eval_llm.gemini_llm` imports from Pipecat's eval CLI regardless of the working directory). `.gitignore` covers `.env`, `.venv/`, `reports/`, `evals/results/`, `__pycache__/`. `.env` holds `GOOGLE_API_KEY=`; copy the value from `../pipecat/.env`. Run `uv sync`. Expected: it resolves and installs with no errors.
- [ ] **Step 2: Write failing tests.**
  - `test_load_settings_defaults`: with only `GOOGLE_API_KEY` set (monkeypatch), `model == "gemini-3.5-flash-lite"` and `fallback_model == "gemini-2.5-flash"`.
  - `test_load_settings_call_time`: `ORDER_CALL_TIME=2026-11-23T19:30:00` → `call_time == datetime(2026, 11, 23, 19, 30)`.
  - `test_pick_model_uses_fallback_when_probe_fails`: a probe returning `False` for the primary model → `"gemini-2.5-flash"`.
  - `test_pick_model_primary_ok`: probe `True` → `"gemini-3.5-flash-lite"`.
  - `test_gemini_llm_factory`: `gemini_llm({"model": "gemini-2.5-flash"})` returns an instance of `pipecat.services.openai.base_llm.BaseOpenAILLMService`, and its model setting is `"gemini-2.5-flash"`.
- [ ] **Step 3: Run.** `uv run pytest tests/test_config.py tests/test_eval_llm.py -v`. Expected: FAIL (module not found).
- [ ] **Step 4: Implement `config.py` and `eval_llm.py`** to the Interfaces above.
- [ ] **Step 5: Run.** Same command. Expected: 5 passed.
- [ ] **Step 6: Live check (one real request).** Run `uv run python -c "..."`, which builds `gemini_llm({})` and calls `run_inference` on a one-message `LLMContext` ("Reply with just: ok"). Expected: prints text containing `ok`. If it fails with 404, try `model` without the `models/` prefix or with it, and record which one works in the README.
- [ ] **Step 7: Commit** everything above. Message: `chore: scaffold order-agent and Gemini eval LLM factory`.

---

### Task 2: SPIKE — Gemini-driven restaurant persona against a minimal caller bot (go/no-go gate)

Throwaway code in `spike/`. **No TDD.** This decides whether phases 2–3 use Pipecat evals.

**Files:**
- Create: `spike/caller_bot.py`, `spike/simulator.yaml`, `spike/judge.yaml`, `spike/restaurant.yaml`, `spike/FINDINGS.md`

**Interfaces:**
- Consumes: `eval_llm.gemini_llm` (Task 1).

- [ ] **Step 1: Write `spike/caller_bot.py`.** Copy `../bots/free_voice_bot.py` and change three things:
  - Add an `"eval"` entry to `transport_params`, using `EvalTransportParams(audio_in_enabled=True, audio_out_enabled=True)` exactly as in `../pipecat/examples/getting-started/06-voice-agent.py`.
  - Replace the system prompt with: you are a customer phoning Karachi Kitchen to order 2 chicken biryani for delivery; keep turns short.
  - In `on_client_connected`, wait 3 s, then queue `LLMRunFrame` with the developer message "Nobody has spoken yet. Open the call."
- [ ] **Step 2: Write the eval config.**
  - `spike/simulator.yaml`: `factory: order_agent.eval_llm.gemini_llm`, `model: gemini-3.5-flash-lite`.
  - `spike/judge.yaml`: `eval: {factory: order_agent.eval_llm.gemini_llm, model: gemini-3.5-flash-lite}` and the same under `explainer:`.
  - `spike/restaurant.yaml`: one simulation, `max_turns: 10`, `max_duration_s: 180`.
    - **persona:** "You are Bilal, the staff member who answered the phone at Karachi Kitchen, a restaurant. The voice on the line is a customer, not an assistant. Menu: chicken biryani Rs 900, chicken karahi Rs 1400, raita Rs 150; delivery fee Rs 150. Take the order, quote the total, say delivery takes 45 minutes."
    - **goal:** "Take the customer's order, quote the total and delivery time, then end the call."
    - **success:** "the customer ordered 2 chicken biryani and the total of Rs 1950 including delivery was agreed".
- [ ] **Step 3: Run three times.** Start `PYTHONIOENCODING=utf-8 uv run python spike/caller_bot.py --port 7860` in the background. Then run `PYTHONIOENCODING=utf-8 uv run pipecat eval run spike/restaurant.yaml --bot-url ws://localhost:7860/ws -v` three times.
- [ ] **Step 4: Assess and record in `spike/FINDINGS.md`:**
  - (a) Did the run complete using only Gemini (no Ollama)?
  - (b) Reading each `*.conversation.json`: did the persona behave as **restaurant staff** in each run? Quote one exchange.
  - (c) Did the bot open the call after about 3 s?
  - (d) How many LLM requests per run, counting the bot's usage-metric log lines plus the persona's turns?
  - (e) Did any 429/503 errors occur?
- [ ] **Step 5: GATE.**
  - **Go:** (a) holds and (b) holds in at least 2 of 3 runs.
  - **No-go:** stop and report the findings to Saif before any further task. The spec's fallback, a text-only two-LLM simulator of our own, then needs a plan revision.
- [ ] **Step 6: Commit.** Message: `spike: gemini restaurant persona vs caller bot (findings)`.

---

### Task 3: Order brief, name matching, and cart basics in the rules engine

**Files:**
- Create: `order_agent/brief.py`, `order_agent/matching.py`, `order_agent/rules.py`, `briefs/example.yaml`
- Test: `tests/conftest.py`, `tests/test_brief.py`, `tests/test_matching.py`, `tests/test_rules_cart.py`

**Interfaces:**
- Produces:
  - `brief.WantedLine`: `item: str`, `quantity: int` (≥1), `substitutes: list[str] = []`, `optional: bool = False`.
  - `brief.OrderBrief`:
    - fields: `customer_name`, `callback_number`, `delivery_address: str`; `wanted: list[WantedLine]` (min 1); `budget_pkr: Decimal` (>0); `never: dict[str, list[str]]`; `deliver_by: time`; `call_time: datetime | None = None`; `notes: str = ""`.
    - YAML `never` may be a list (`["seafood"]` → `{"seafood": ["seafood"]}`) or a mapping (`{seafood: [fish, prawn]}`). A rule's own name is always one of its keywords.
  - `brief.load_brief(path: Path) -> OrderBrief`.
  - `matching.normalise(name: str) -> frozenset[str]`: lowercase; replace non-letters with spaces; split into words; strip a trailing `es` from a word longer than 4 letters, else a trailing `s` from a word longer than 3; return the set of words.
  - `matching.match_line(brief, name) -> tuple[WantedLine, bool] | None`: the line whose `item` (→ `False`) or one of whose `substitutes` (→ `True`) has a word set **equal** to `normalise(name)`.
  - `rules.ToolResult` (frozen dataclass): `ok: bool`, `message: str`.
  - `rules.ToolEvent` (dataclass): `tool: str`, `args: dict`, `ok: bool`, `message: str`, `at: datetime`.
  - `rules.CartItem` (dataclass): `name: str` (as the restaurant said it), `line_item: str` (the brief line it fills), `quantity: int`, `unit_price_pkr: Decimal`.
  - `rules.OrderSession(brief: OrderBrief, now: datetime)`:
    - attributes: `items: list[CartItem]`, `delivery_fee_pkr: Decimal = 0`, `tax_pkr: Decimal = 0`, `minimum_order_pkr: Decimal | None = None`, `state: Literal["open", "confirmed", "ended"]`, `events: list[ToolEvent]`.
    - methods: `add_item(name, quantity: int, unit_price_pkr: Decimal) -> ToolResult`, `remove_item(name) -> ToolResult`, `set_fees(delivery_fee_pkr: Decimal, tax_pkr: Decimal) -> ToolResult`, `cart_total() -> Decimal` (items + fees + tax).
    - Every public mutating method appends a `ToolEvent`, including refusals.

Test fixture `brief` in `conftest.py` is the spec §5.1 brief exactly, with `never: {seafood: [seafood, fish, prawn, jhinga], beef: [beef]}` and `call_time 2026-11-23T19:30`. `briefs/example.yaml` holds the same data.

- [ ] **Step 1: Write failing tests.**
  - `test_load_example_brief`: `load_brief(Path("briefs/example.yaml")).budget_pkr == Decimal("2500")`, and `wanted[0].substitutes == ["chicken karahi", "chicken pulao"]`.
  - `test_never_list_form_normalised`: `never: ["beef"]` → `{"beef": ["beef"]}`.
  - `test_brief_rejects_zero_budget`: `budget_pkr: 0` → `ValidationError`.
  - `test_match_ignores_case_order_plural`: `"Chicken Biryanis"` and `"biryani, chicken"` both → (the biryani line, `False`); `"chicken karahi"` → (the biryani line, `True`).
  - `test_match_rejects_partial_name`: `"chicken"` → `None`; `"fish special"` → `None`.
  - `test_add_wanted_item`: `add_item("chicken biryani", 2, Decimal("900"))` → `ok`; `cart_total() == Decimal("1800")`.
  - `test_add_item_not_in_brief_refused`: `"fish special"` → not ok; the message contains `"not in your brief"`.
  - `test_add_item_hits_never_keyword`: a brief whose biryani substitutes include `"fish biryani"` → `add_item("fish biryani", …)` is not ok; the message contains `"seafood"`.
  - `test_add_item_over_budget_refused`: `add_item("chicken biryani", 2, Decimal("1300"))` → not ok; the message contains `"budget"` and `"2500"`; the cart is unchanged.
  - `test_add_item_over_budget_suggests_dropping_optional`: the cart has raita; an add that would exceed budget only because of the raita → the message contains `"raita"`.
  - `test_add_item_rejects_nonpositive_price`: price `0` or `-5`, or quantity `0` → not ok.
  - `test_add_beyond_line_quantity_refused_without_minimum`: after 2 biryani, `add_item("chicken biryani", 1, …)` → not ok; the message contains `"already"`.
  - `test_remove_item`: add, then `remove_item("Chicken Biryani")` → ok; the cart is empty.
  - `test_fees_count_toward_budget`: 2 biryani at 900 plus raita at 150, then `set_fees(Decimal("600"), Decimal("0"))` → not ok (2550 > 2500).
  - `test_events_record_refusals`: after one ok and one refused call, `len(session.events) == 2` and `events[1].ok is False`.
- [ ] **Step 2: Run.** `uv run pytest tests/test_brief.py tests/test_matching.py tests/test_rules_cart.py -v`. Expected: FAIL (imports).
- [ ] **Step 3: Implement** `brief.py`, `matching.py`, and the `OrderSession` constructor plus `add_item`, `remove_item`, `set_fees` and `cart_total`, to the Interfaces above. Refusal messages must say **why** and **what the agent could do instead**.
- [ ] **Step 4: Run.** Same command. Expected: all pass.
- [ ] **Step 5: Commit.** Message: `feat: order brief, name matching, cart rules`.

---

### Task 4: Rules engine — minimum order, completeness, confirmation, delivery time, ending

**Files:**
- Modify: `order_agent/rules.py`
- Test: `tests/test_rules_confirm.py`

**Interfaces:**
- Consumes: Task 3's `OrderSession`.
- Produces, on `OrderSession`:
  - `set_minimum_order(minimum_pkr: Decimal) -> ToolResult`.
  - `missing_lines() -> list[str]`: human-readable shortfalls, one per non-optional line, e.g. `"chicken biryani: need 2, have 1"`.
  - `confirm_order(quoted_total_pkr: Decimal, delivery_minutes: int) -> ToolResult`.
  - `end(outcome: Literal["ordered", "not_ordered"], reason: str) -> ToolResult`.
  - attributes `delivery_eta: datetime | None` and `quoted_total_pkr: Decimal | None`. Both are set only by a successful `confirm_order`.
  - Note: `set_minimum_order` isn't in the spec's §5.2 tool list. The plan adds it because the spec's minimum-order rule needs the code to know the minimum.
- Rules (spec §5.1, "When an order is complete"):
  - A line's filled quantity is the sum over cart items mapped to it, whether original or substitute.
  - The minimum order is compared against the **food subtotal** (items only, excluding the delivery fee and tax), as real restaurants do.
  - With `minimum_order_pkr` set and the food subtotal below it, `add_item` may exceed a line's quantity, or add an optional line, as long as the total stays within budget.
  - The ETA is `(brief.call_time or now) + delivery_minutes`.

- [ ] **Step 1: Write failing tests** (with `brief` from the fixture).
  - `test_mixed_substitute_completes_line`: 1 biryani at 900, plus 1 karahi at 1400 → `missing_lines() == []`.
  - `test_missing_required_line_blocks_confirm`: 1 biryani only → `confirm_order` is not ok; the message contains `"need 2, have 1"`.
  - `test_optional_line_may_be_missing`: 2 biryani at 900 plus `set_fees(150, 0)` → `confirm_order(Decimal("1950"), 45)` is ok; `state == "confirmed"`; `delivery_eta == datetime(2026, 11, 23, 20, 15)`.
  - `test_confirm_rejects_mismatched_total`: cart 1950, quoted `1800` → not ok; the message contains `"1950"`.
  - `test_confirm_rejects_late_delivery`: as the happy path but `delivery_minutes=120` → not ok; the message contains `"21:00"`.
  - `test_minimum_order_blocks_confirm`: `set_minimum_order(Decimal("2200"))`, food subtotal 1800 (cart total 1950) → confirm is not ok; the message contains `"2200"` and `"raita"`.
  - `test_minimum_allows_extra_quantity`: with minimum 2200 and a food subtotal of 1800, `add_item("raita", 3, Decimal("150"))` is ok (subtotal 2250, total 2400). Then confirming with 2400 is ok.
  - `test_minimum_unreachable_within_budget`: minimum 3000 → no allowed add reaches it. `add_item("chicken biryani", 1, Decimal("900"))` is refused for budget, and the message suggests ending without ordering.
  - `test_no_changes_after_confirm`: after a confirm, `add_item` is not ok; the message contains `"already confirmed"`.
  - `test_end_ordered_requires_confirm`: `end("ordered", "x")` on an open session is not ok. `end("not_ordered", "sold out")` is ok, and `state == "ended"`.
  - `test_end_twice_refused`: a second `end(...)` is not ok.
- [ ] **Step 2: Run.** `uv run pytest tests/test_rules_confirm.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the methods and rules above in `rules.py`.
- [ ] **Step 4: Run** `uv run pytest -v`. Expected: all tests so far pass.
- [ ] **Step 5: Commit.** Message: `feat: completeness, minimum order, confirmation and ending rules`.

---

### Task 5: Call report

**Files:**
- Create: `order_agent/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `OrderSession`, `CartItem`, `ToolEvent` (Tasks 3–4).
- Produces:
  - `report.TranscriptLine` (pydantic): `role: Literal["agent", "restaurant"]`, `text: str`, `at: datetime`.
  - `report.CallReport` (pydantic):
    - outcome: `outcome: Literal["ordered", "not_ordered", "call_dropped"]`, `reason: str`;
    - order: `items: list[dict]` (name, line_item, quantity, unit_price_pkr), `delivery_fee_pkr: Decimal`, `tax_pkr: Decimal`, `cart_total_pkr: Decimal`, `quoted_total_pkr: Decimal | None`, `delivery_eta: datetime | None`;
    - history: `tool_events: list[dict]`, `transcript: list[TranscriptLine]`;
    - timing: `started_at: datetime`, `ended_at: datetime`.
  - `report.build_report(session, outcome, reason, transcript, started_at, ended_at) -> CallReport`.
  - `report.summarise(report) -> str`: one plain-English paragraph.
  - `report.write_report(report, out_dir: Path) -> Path` writes `<started_at:%Y%m%d-%H%M%S>.json` (Decimals as strings) and a `.txt` file with the summary. Returns the JSON path.

- [ ] **Step 1: Write failing tests.**
  - `test_build_report_ordered`: from the confirmed happy-path session → `outcome == "ordered"`, `cart_total_pkr == Decimal("1950")`, and `delivery_eta` set.
  - `test_summary_mentions_outcome_items_total`: the summary contains `"ordered"`, `"chicken biryani"` and `"1950"`.
  - `test_summary_not_ordered_gives_reason`: `not_ordered` with reason "biryani sold out, no allowed substitute" → the summary contains that reason.
  - `test_write_report_roundtrip`: `write_report(r, tmp_path)` → JSON loads; `CallReport.model_validate_json` equals `r`; the `.txt` file exists.
  - `test_report_keeps_refused_tool_events`: a session with one refused `add_item` → `tool_events` contains an entry with `ok: false`.
- [ ] **Step 2: Run.** `uv run pytest tests/test_report.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `report.py`.**
- [ ] **Step 4: Run.** Expected: pass.
- [ ] **Step 5: Commit.** Message: `feat: call report`.

---

### Task 6: System prompt and Pipecat tools

**Files:**
- Create: `order_agent/prompt.py`, `order_agent/tools.py`
- Test: `tests/test_prompt.py`, `tests/test_tools.py`

**Interfaces:**
- Consumes: `OrderBrief`, `OrderSession`, `ToolResult`.
- Produces:
  - `prompt.build_system_prompt(brief: OrderBrief) -> str`.
  - `tools.build_tools(session: OrderSession, on_end: Callable[[str, str], Awaitable[None]]) -> ToolsSchema`, with `FunctionSchema`s named exactly:
    - `add_item(name: str, quantity: int, unit_price_pkr: number)`
    - `remove_item(name: str)`
    - `set_fees(delivery_fee_pkr: number, tax_pkr: number)`
    - `set_minimum_order(minimum_pkr: number)`
    - `confirm_order(quoted_total_pkr: number, delivery_minutes: integer)`
    - `end_call(outcome: "ordered" | "not_ordered", reason: str)`
  - Each handler converts numbers via `Decimal(str(x))`. A conversion error or a missing argument returns `{"ok": False, "message": ...}` without touching the session. Otherwise it calls the session method and does `await params.result_callback({"ok": r.ok, "message": r.message})`. `end_call` calls `on_end(outcome, reason)` only when `session.end` returns ok.
  - Pattern reference: the `FunctionSchema(..., handler=...)` and `ToolsSchema(standard_tools=[...])` usage in `../pipecat/examples/realtime/realtime-gemini-live.py`.

- [ ] **Step 1: Write failing tests.**
  - `test_prompt_contains_rules`: the prompt contains `"2500"`, `"chicken biryani"`, `"chicken karahi"`, `"seafood"`, `"21:00"`, `"House 12, Street 4, F-7/2, Islamabad"` and the customer's name.
  - `test_prompt_forbids_inventing`: the prompt contains `"Never state a price or item the restaurant did not say"` and `"use the tools"`.
  - `test_prompt_mentions_spoken_style`: contains `"short"` and `"no lists or markdown"`.
  - `test_tools_schema_names`: the names of `build_tools(...).standard_tools` equal the six names above.
  - `test_handler_add_item_calls_session`: invoke the `add_item` handler with a fake params object (`arguments={"name": "chicken biryani", "quantity": 2, "unit_price_pkr": 900}` and a recording `result_callback`) → the callback gets `{"ok": True, ...}`; `session.cart_total() == Decimal("1800")`.
  - `test_handler_rejects_unparseable_price`: `unit_price_pkr="twelve hundred"` → the callback gets `ok: False`; the session's events are unchanged.
  - `test_end_call_invokes_on_end_only_when_allowed`: `end_call("ordered", ...)` on an open session → `on_end` is not awaited. `end_call("not_ordered", "sold out")` → `on_end` is awaited with `("not_ordered", "sold out")`.
- [ ] **Step 2: Run.** `uv run pytest tests/test_prompt.py tests/test_tools.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `prompt.py` (spec §5.2 content: the role, the brief in plain words, the hard rules, spoken style, the never-invent rule, using the tools for every change, calling `end_call` at the end) and `tools.py`.
- [ ] **Step 4: Run.** Expected: pass.
- [ ] **Step 5: Commit.** Message: `feat: system prompt and order tools`.

---

### Task 7: The agent bot (phase 1: Saif plays the restaurant)

**Files:**
- Create: `bot.py`, `order_agent/call.py`
- Test: `tests/test_call.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `call.CallState(brief, settings, now: datetime)` holds an `OrderSession`, `transcript: list[TranscriptLine]`, `started_at`, and `report_path: Path | None`.
    - `add_line(role, text)`.
    - `async finish(outcome, reason) -> Path`: builds and writes the report once; a second call returns the existing path.
    - `async on_disconnect() -> Path`: calls `finish("call_dropped", "call ended without end_call")` if no report exists yet.
  - `bot.py` follows the shape of `../bots/free_voice_bot.py`, with these changes:
    - `transport_params` has `"webrtc"` and `"eval"` (`EvalTransportParams`).
    - Settings come from `load_settings()`; the brief from `settings.brief_path`. If `settings.call_time` is set, it overrides the brief's (`brief.model_copy(update={"call_time": ...})`).
    - The model comes from `pick_model`, with the probe being a single 1-token Gemini request with a 10 s timeout.
    - The `GoogleLLMService` model is the picked model, the system prompt is `build_system_prompt(brief)`, and the `LLMContext` gets `tools=build_tools(...)`.
    - `on_end` = `call_state.finish(...)` and then pushing `EndTaskFrame()` upstream, so the pipeline ends after the agent's last words.
    - Transcripts are captured with `on_user_turn_message_added` (role `restaurant`) and `on_assistant_turn_stopped` (role `agent`).
    - **Opening:** on `on_client_connected`, start a task that waits 3.0 s. If no `on_user_turn_started` has fired by then, add the developer message "Nobody has spoken yet. Open the call: greet, say you'd like to place a delivery order." and queue `LLMRunFrame`. If the restaurant spoke first, the normal turn flow answers it and no extra run is queued.
    - `on_client_disconnected` → `await call_state.on_disconnect()`, then `runner.cancel()`.

- [ ] **Step 1: Write failing tests.**
  - `test_finish_writes_once`: two `finish` calls → the same path, and exactly one JSON file in `tmp_path`.
  - `test_disconnect_writes_dropped_report`: `on_disconnect()` with no prior finish → the report's `outcome == "call_dropped"`.
  - `test_disconnect_after_finish_keeps_outcome`: `finish("not_ordered", "x")`, then `on_disconnect()` → the outcome is still `not_ordered`.
- [ ] **Step 2: Run.** `uv run pytest tests/test_call.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `call.py` and `bot.py`.**
- [ ] **Step 4: Run** `uv run pytest -v`. Expected: all pass.
- [ ] **Step 5: Smoke start.** `PYTHONIOENCODING=utf-8 uv run python bot.py`. Expected: "Bot ready!" and HTTP 200 from `http://localhost:7860/client/`. Stop it.
- [ ] **Step 6: Phase 1 with Saif (human; the executor pauses here and asks Saif).** Saif runs the bot, opens the client and plays the restaurant using a menu card in `README.md`: chicken biryani 900, chicken karahi 1400, raita 150, delivery 150. He does three calls:
  - (a) A happy path: expect `ordered`, total 1950.
  - (b) "Biryani is finished, we only have fish biryani": expect `not_ordered`, or karahi if he offers it.
  - (c) He says "one minute please", stays silent for about 10 s, then continues: expect the agent waits without talking over him.

  Record each report's outcome and Saif's notes in `docs/phase1-results.md`.
- [ ] **Step 7: Commit.** Message: `feat: order agent bot with opening, report and drop handling`.

---

### Task 8: Eval scenarios (simulated restaurant)

Only after a **Go** at the Task 2 gate.

**Files:**
- Create: `evals/simulator.yaml`, `evals/judge.yaml` (as in the spike, moved here), `evals/briefs/*.yaml`, `evals/scenarios/*.yaml`, `evals/expected.yaml`

**Interfaces:**
- Produces: `evals/expected.yaml`, mapping a scenario name to `{brief: <path>, call_time: <ISO>, outcome: ordered | not_ordered, max_total_pkr: <n>, must_include: [<line items>], must_exclude: [<words>]}`. Task 9 reads this file.
- Scenario names, one file per scenario. Each has a restaurant persona with a menu and that scenario's twist. Each uses `success:` wording that matches the expected outcome, and the metrics `politeness` and `no_invention` ("the reply never states a price or item the restaurant did not say").

| name | twist in the persona | expected outcome |
|---|---|---|
| `happy_path` | everything available, biryani 900, raita 150, delivery 150, 45 min | ordered, ≤ 2500 |
| `sold_out_substitute` | biryani sold out, karahi 1100 available | ordered with karahi |
| `sold_out_no_substitute` | biryani, karahi and pulao all sold out; offers prawn biryani | not_ordered |
| `price_drop_optional` | biryani 1150, raita 250, delivery 150 (2700 with raita, 2450 without) | ordered without raita |
| `price_over_budget` | biryani 1300, delivery 150 | not_ordered |
| `late_delivery` | everything available, but 2 hours | not_ordered |
| `minimum_reachable` | minimum order Rs 2200 on food; biryani 900, raita 150, delivery 150 | ordered, food subtotal ≥ 2200, total ≤ 2500 |
| `minimum_unreachable` | minimum order Rs 3000 | not_ordered |
| `staff_asks_details` | asks for name, number and address before confirming | ordered; details match the brief |
| `pushes_forbidden` | keeps recommending "our fish special" | ordered, with no fish item |
| `terse_staff` | one-word answers, a noisy line ("what?"), still serves | ordered, no repeat loop (judged metric: "the reply does not ask the same question more than twice") |

- [ ] **Step 1: Write the briefs and scenario files.** Every brief has `call_time: 2026-11-23T19:30:00`. Use the spike's persona wording, which passed the gate, as the template.
- [ ] **Step 2: Validate the parse.** `uv run python -c "from pipecat.evals.scenario import EvalScenarioFile; ..."` loads every file in `evals/scenarios/`. Expected: 11 scenarios, no errors.
- [ ] **Step 3: Commit.** Message: `test: restaurant eval scenarios`.

---

### Task 9: Suite runner with deterministic checks and quota handling

**Files:**
- Create: `order_agent/suite.py`, `run_suite.py`
- Test: `tests/test_suite.py`

**Interfaces:**
- Consumes: `CallReport`, `evals/expected.yaml`, `EvalScenarioFile` and `EvalSession` (see `../pipecat/AGENTS.md`, "Behavioral evals").
- Produces:
  - `suite.Expected` (pydantic) mirrors one `expected.yaml` entry.
  - `suite.check_report(report: CallReport, expected: Expected) -> list[str]`: violations, empty when fine. It checks:
    - the outcome;
    - `cart_total_pkr ≤ max_total_pkr` and `≤ brief budget`;
    - every `must_include` line item is present;
    - no item name contains a `must_exclude` word;
    - no item hits a `never` keyword.
  - `suite.classify_error(exc: BaseException) -> Literal["quota_error", "error"]`: `quota_error` if the exception text, or any chained cause, contains `429`, `503`, `RESOURCE_EXHAUSTED` or `UNAVAILABLE`.
  - `suite.ScenarioResult`: `name`, `status: Literal["pass", "fail", "quota_error", "error"]`, `judge_passed: bool | None`, `violations: list[str]`, `report_path`, `llm_requests: int | None`.
  - `suite.count_requests(bot_log: str, conversation: dict) -> int`: the agent's requests are the number of lines in the bot log containing `"prompt tokens:"` (Pipecat's usage metric, one per LLM call). The persona's requests are the number of restaurant turns in the saved conversation. The judge's requests aren't counted (note this in the summary). Test: `test_count_requests` with a 3-line log fixture and a 2-turn conversation → `5`.
  - `run_suite.py` captures the bot subprocess's stdout and stderr to `bot.log` in the scenario's results folder.
  - Final status: `pass` only if the judge passed **and** there are no violations. Violations alone mean `fail`, even if the judge passed.
  - `run_suite.py [--only NAME] [--audio]` loops over the scenarios. For each one:
    1. Start `bot.py` as a subprocess, with `ORDER_BRIEF`, `ORDER_CALL_TIME`, a fresh `ORDER_REPORTS_DIR=evals/results/<run-id>/<name>` and `PYTHONIOENCODING=utf-8`.
    2. Wait for HTTP 200 on `/client/`.
    3. Run `EvalSession.from_scenario(scenario, "ws://localhost:7860/ws", ...)`. Text-only by default; `--audio` turns on audio mode.
    4. Stop the bot.
    5. Load the report and apply `check_report`.
    6. Sleep 5 s between scenarios, to be gentle on quota.

    It writes `evals/results/<run-id>/summary.md` (a table: name, status, judge, violations, requests).

- [ ] **Step 1: Write failing tests.**
  - `test_check_report_pass`: an `ordered` report, total 1950, biryani → `[]` against the `happy_path` expectations.
  - `test_check_report_over_budget`: total 2600 → a violation mentioning `"2600"`.
  - `test_check_report_wrong_outcome`: `ordered` when `not_ordered` was expected → a violation mentioning `"outcome"`.
  - `test_check_report_forbidden_word`: an item "fish special" with `must_exclude: [fish]` → a violation.
  - `test_classify_error_quota`: `Exception("503 UNAVAILABLE ...")` and a chained `429` → `"quota_error"`; `ValueError("boom")` → `"error"`.
  - `test_final_status_violation_overrides_judge`: judge passed plus one violation → `"fail"`.
- [ ] **Step 2: Run.** `uv run pytest tests/test_suite.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `suite.py` and `run_suite.py`.**
- [ ] **Step 4: Run** `uv run pytest -v`. Expected: all pass.
- [ ] **Step 5: First live scenario.** `PYTHONIOENCODING=utf-8 uv run python run_suite.py --only happy_path`. Expected: `summary.md` shows `pass` or a clear reason. Fix the bot or prompt, **not** the checks, until it passes.
- [ ] **Step 6: Commit.** Message: `feat: eval suite runner with deterministic checks`.

---

### Task 10: Full run and results write-up (spec §7, definition of done)

**Files:**
- Create: `docs/results-v1.md`; modify `README.md`.

- [ ] **Step 1: Full text-only run.** `PYTHONIOENCODING=utf-8 uv run python run_suite.py`. For each `fail`, read the conversation and the report, then fix the prompt or bot (never weaken a check or a scenario's expected outcome without Saif's OK). Re-run only the failed ones with `--only`. Re-run `quota_error` scenarios later; they don't count as failures.
- [ ] **Step 2: Audio runs.** `--audio --only happy_path`, then two more scenarios, chosen as `sold_out_substitute` and `pushes_forbidden`.
- [ ] **Step 3: Verify done.** Every scenario `pass` in text mode (one run), and the three audio scenarios `pass`. `uv run pytest` is fully green.
- [ ] **Step 4: Write `docs/results-v1.md`** for the mentor:
  - a pass/fail table;
  - latency (from bot metrics) and LLM requests per scenario;
  - quota incidents;
  - known limitations: ingredient claims can't be verified; hold and silence are tested by hand only; English only; no real phone line.

  Then update `README.md` with how to run everything.
- [ ] **Step 5: Commit.** Message: `docs: v1 results`. Ask Saif before any push.
