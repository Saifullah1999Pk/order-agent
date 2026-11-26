# order-agent

**A voice agent that phones a restaurant as the customer and places a food order, without breaking the rules it was given.**

You give the agent an order brief: what to order, a budget, acceptable substitutes, foods to avoid, and a delivery deadline. It calls the restaurant, talks to the staff, adapts when items are sold out or prices change, and confirms the order or politely declines. It then writes a report of the call.

Built with [Pipecat](https://github.com/pipecat-ai/pipecat) as an internship project at Arbisoft, to learn real-time voice agents and how to test them properly. It uses **free services only**: local speech models, free-tier cloud LLMs, and an optional local LLM through Ollama.

---

## How it works

```
 you / restaurant ──voice──▶ Whisper (local) ──text──▶ LLM ──tool calls──▶ rules engine
                                                        │                   (plain Python)
                                                        ▼                         │
 you / restaurant ◀──voice── Kokoro (local) ◀──reply── LLM ◀──allowed / refused──┘
```

**The LLM talks; plain code decides what is allowed.** The agent can only change the order through tools: `add_item`, `set_price`, `remove_item`, `set_fees`, `set_minimum_order`, `confirm_order` and `end_call`. Every tool call goes through `order_agent/model/rules.py`, which enforces the brief:

- **Budget:** the total, including fees, never goes over.
- **Allow-list:** only the wanted items or their listed substitutes can be ordered.
- **Forbidden foods:** items matching a rule such as `seafood: [fish, prawn]` are refused.
- **Completeness:** quantities never go down. A minimum order can only be met with items from the brief.
- **Delivery deadline** and **quote fidelity**: the confirmed total must match the cart.

A refused tool call tells the agent why, and what it could try instead.

**Example from a test run:** the restaurant offered prawn biryani, and the LLM tried to add it. The engine refused ("'prawn biryani' is not in your brief"), and the order stayed clean.

## How it is tested

Unit tests cover the rules engine, the reports, the tools and the call handling. On top of those, an **automated eval suite** runs 11 scenarios, each a simulated restaurant with a twist:

- a dish is sold out;
- prices rise;
- the delivery would be too late;
- there is a minimum order;
- the staff push a forbidden dish;
- the staff are terse;
- …and so on.

Each test call involves three roles:

| Role | Model (default) | Runs where |
|---|---|---|
| The agent (bot) | Gemini `gemini-3.5-flash-lite` | Cloud, free tier |
| Simulated restaurant staff | `qwen3:8b` via Ollama | Your machine (GPU) |
| Judge (scores the call) | Groq `openai/gpt-oss-20b`, throttled (one call at a time, 20 s apart) | Cloud, free tier |

**Code checks override the judge.** After every call, deterministic checks on the agent's report decide the hard rules: outcome, budget, forbidden items, required items and minimum order. Of the four judge setups we tested, none agreed with these checks more than about 56% of the time. The judge is trusted only for soft qualities such as politeness. Each scenario gets up to 3 attempts (pass@3), and every attempt is recorded.

## Results at a glance

| | |
|---|---|
| v1 suite (2026-11-23) | 8 of 11 scenarios passed within 3 attempts. **0 failures came from the agent breaking a rule.** Later, a price check showed bots sometimes invented prices. Of those 8 passes, 4 were re-checked and still pass. 4 have no saved report and cannot be re-checked: happy_path and price_drop_optional (orders placed), and late_delivery and minimum_unreachable (no order placed). See [section 16](docs/results-v1.md). |
| Since then | Fixed the simulated restaurant hanging up early and the agent's minimum-order handling. In the 2026-11-25 hybrid run ([evidence](evals/confirmation/hybrid-2026-11-25/README.md)), `minimum_reachable` and `staff_asks_details` passed on their first attempt, judged by the throttled Gemini judge (`evals/judge-gemini-throttled.yaml`) because the default Groq judge timed out on Groq's per-minute token cap. In the same run `happy_path` failed on the judge's conduct score (correct order, no rule violations) and `terse_staff` did not pass (a bot bug: it rewrote its order to match a wrong total the restaurant insisted on). |
| Latency (end of speech to bot speaking) | Median 2.73 s, P90 3.64 s (n=28, bot on Groq, audio runs) |
| Local LLM (Ollama, `qwen3:8b`) | Good as the simulated restaurant (2 wrong-total slips in 7 calls, never hung up early). Not reliable as the bot (it invented prices) or the judge. |
| Unit tests | 672 passing |

Full write-up, with every number linked to its evidence: [docs/results-v1.md](docs/results-v1.md).

## Quick start

Requirements: Python 3.12 and [uv](https://docs.astral.sh/uv/). For the default eval setup you also need [Ollama](https://ollama.com). No Ollama? Run the suite with a cloud restaurant instead (see below).

```bash
uv sync
```

Create `.env` (gitignored) with free-tier keys:

```
GOOGLE_API_KEY=...   # the agent's LLM (Gemini)
GROQ_API_KEY=...     # the judge (Groq), eval suite only
```

> **Windows:** prefix every command that runs Pipecat with `PYTHONIOENCODING=utf-8`. Pipecat's dev runner crashes on non-UTF-8 output.

### Talk to the agent (you play the restaurant)

```bash
PYTHONIOENCODING=utf-8 uv run python bot.py
```

Open http://localhost:7860/client/, click **Connect** and answer like a restaurant. The agent waits 3 seconds for a greeting, then speaks first.

- Menu for manual calls: chicken biryani 900, chicken karahi 1400, raita 150, delivery 150 (PKR).
- `ORDER_BRIEF=path.yaml` picks the order brief. The default is `briefs/example.yaml`.
- Each call writes a report to `reports/`.

### Run the eval suite

Start Ollama for the simulated restaurant, once per session. On Windows, in PowerShell:

```powershell
ollama pull qwen3:8b
$env:OLLAMA_NUM_PARALLEL=1; $env:OLLAMA_CONTEXT_LENGTH=8192; $env:OLLAMA_KV_CACHE_TYPE="q8_0"; $env:OLLAMA_FLASH_ATTENTION=1; $env:OLLAMA_KEEP_ALIVE="2h"; ollama serve
```

On macOS or Linux (bash), the equivalent is:

```bash
OLLAMA_NUM_PARALLEL=1 OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KEEP_ALIVE=2h ollama serve
```

`ollama ps` should show `100% GPU`. On an AMD RX 6600 this works through Vulkan. `run_suite.py` checks that Ollama is running before it starts and stops with a clear message if it is not.

**No Ollama?** Use a cloud simulated restaurant instead (it spends free-tier quota):

```bash
PYTHONIOENCODING=utf-8 uv run python run_suite.py --only happy_path --simulator evals/simulator-gemini.yaml
```

`evals/simulator-groq.yaml` is the Groq alternative, but that persona hung up early more often in our tests.

```bash
PYTHONIOENCODING=utf-8 uv run python run_suite.py                         # all 11 scenarios
PYTHONIOENCODING=utf-8 uv run python run_suite.py --only happy_path       # one scenario
PYTHONIOENCODING=utf-8 uv run python run_suite.py --audio --only happy_path   # spoken (Kokoro + Whisper)
```

Useful options:

| Option | What it does |
|---|---|
| `--attempts N` | Attempts per scenario. Default 3. |
| `--sleep S` | Pause between attempts. Raise it if you see 429s. |
| `--rescore evals/results/<run>` | Re-classifies a saved run. Makes no new calls. |
| `--simulator FILE` / `--judge FILE` | Swaps the restaurant or judge model for one run. Files are checked before any bot starts. |

The default judge (`evals/judge.yaml`) is throttled for Groq's free 8000 tokens/minute cap: the judge asks ~7 questions per call, each carrying the whole transcript, so they are sent one at a time, 30 s apart, with 429 retries. A full judgement therefore takes ~2-5 minutes per call. An explanation can occasionally come back empty (Pipecat's 60 s explainer timeout includes queue wait); the verdict still stands. `evals/judge-gemini-throttled.yaml` is a rate-limited Gemini alternative.

Fully local run (bot, restaurant and judge all on Ollama):

```bash
ORDER_AGENT_LLM_PROVIDER=ollama PYTHONIOENCODING=utf-8 uv run python run_suite.py --only happy_path --judge evals/judge-ollama.yaml
```

Each attempt gets one status:

| Status | Meaning |
|---|---|
| `pass` | Judge passed and every deterministic check passed. |
| `fail` | A check or the judge failed (budget, forbidden item, wrong prices, bent cart, wrong outcome, ...). |
| `quota_error` | A rate limit or overload stopped the run; not a bot failure. |
| `restaurant_error` | The simulated restaurant quoted a total that matches no valid order, and the bot refused it. Applies only when ALL hold: the bot's cart matches the menu exactly (every unit price, delivery fee and tax, with no zero-fee exemption, and no `price_corrected`/`corrected` flag); every refused quote differs from the menu-correct total of that cart; no quote is any figure on the persona's Totals line (a quote matching a valid order is ambiguous); the judge's `conduct` metric passed; no order was confirmed and the only violations are consequences of that. Ambiguous cases count as bot failures. Retried within `--attempts`; a scenario with only `restaurant_error`/`quota_error` attempts is reported as such, never as pass or fail. The note reads "restaurant quoted Rs X, which matches no valid order (correct for this cart: Rs Y); bot declined". |
| `error` | Harness problem (bot not ready, crash, ...). |

Each persona also carries a precomputed "Totals" line (checked against `evals/expected.yaml` by `tests/test_persona_totals.py`) so the restaurant model quotes the right totals instead of adding them up.

Results go to `evals/results/<timestamp>/`, which is gitignored. `summary.md` holds the per-attempt status. Run summaries kept as evidence are committed under `evals/confirmation/`.

### Swap the agent's LLM

| Setting | Effect |
|---|---|
| `ORDER_AGENT_LLM_PROVIDER=gemini` | The default |
| `ORDER_AGENT_LLM_PROVIDER=groq` | Uses `ORDER_AGENT_GROQ_MODEL`, default `qwen/qwen3.8-27b`. Needs `GROQ_API_KEY`. |
| `ORDER_AGENT_LLM_PROVIDER=ollama` | Uses `ORDER_AGENT_OLLAMA_MODEL`, default `qwen3:8b`. Fully local, no keys. |
| `ORDER_AGENT_OLLAMA_URL` | Ollama's OpenAI-compatible address, default `http://localhost:11434/v1`. |

A fully local setup, with the bot, restaurant and judge all on Ollama, is described with its honest quality results in [evals/confirmation/all-ollama/README.md](evals/confirmation/all-ollama/README.md).

### Unit tests

```bash
uv run pytest
```

## Architecture

The code is split into layers so the rules and the conversation logic can be used, and tested, without any voice framework. One call can be driven by a phone-style voice pipeline or, just as well, by plain HTTP requests.

```
   heads (talk to the outside world)
   +-----------------------------+   +-----------------------------+
   | voice head (Pipecat)        |   | HTTP head (FastAPI, local)  |
   | order_agent/heads/voice     |   | order_agent/heads/http_api  |
   +--------------+--------------+   +--------------+--------------+
                  \                               /
                   v                             v
              +--------------------------------------+
              | Controller: order_agent/controller   |   one call, no framework
              | CallController, tool dispatch, prompt|
              +------------------+-------------------+
                                 v
              +--------------------------------------+
              | Model: order_agent/model             |   pure rules and data
              | brief, rules engine, matching, report|
              +--------------------------------------+

   order_agent/evaltools: eval suite tooling, used by run_suite.py (sits beside the layers)
```

- **Model** decides what is allowed (budget, allow-list, forbidden foods, deadline). It knows nothing about voice, web or LLMs.
- **Controller** runs one call: it holds the order state, turns a tool call into a model decision, writes the report, and builds the agent's instructions. It has no web or voice framework either.
- **Heads** connect a channel to the Controller. The voice head listens and speaks through Pipecat. The HTTP head lets a script play the agent by sending requests.

### Module map

| Module | Layer | What it does |
|---|---|---|
| `order_agent/model/brief.py` | Model | The order brief: what to order and the hard rules |
| `order_agent/model/matching.py` | Model | Item-name matching (case, word order, plurals) |
| `order_agent/model/rules.py` | Model | The rules engine; every tool call is checked here |
| `order_agent/model/report.py` | Model | The per-call report (JSON and plain-English summary) |
| `order_agent/controller/session.py` | Controller | `CallController`: one conversation, independent of the channel |
| `order_agent/controller/tools.py` | Controller | Framework-free tool dispatch over the rules engine |
| `order_agent/controller/toolspecs.py` | Controller | The tool definitions the LLM sees |
| `order_agent/controller/prompt.py` | Controller | The agent's instructions, built from the brief |
| `order_agent/controller/nudge.py` | Controller | When to nudge the agent after an empty reply |
| `order_agent/heads/voice/pipeline.py` | Voice head | Pipecat pipeline: speech to text, LLM, text to speech |
| `order_agent/heads/voice/bridge.py` | Voice head | Maps each Pipecat event to one Controller call |
| `order_agent/heads/voice/hooks.py` | Voice head | The two things only the pipeline can do (speak, nudge) |
| `order_agent/heads/voice/tools.py` | Voice head | Pipecat tool schemas built from the Controller's specs |
| `order_agent/heads/voice/llm_factory.py` | Voice head | Builds the agent's LLM (Gemini, Groq or Ollama) |
| `order_agent/heads/voice/probe.py` | Voice head | Gemini availability probe run before the call |
| `order_agent/heads/http_api/app.py` | HTTP head | The FastAPI app: sessions, actions, transcript, report |
| `order_agent/heads/http_api/schemas.py` | HTTP head | Request and response models |
| `order_agent/heads/http_api/store.py` | HTTP head | In-memory sessions, one Controller each |
| `order_agent/heads/http_api/__main__.py` | HTTP head | Starts the server locally |
| `order_agent/evaltools/suite.py` | Eval tools | Deterministic report checks, error classification, summary |
| `order_agent/evaltools/throttle.py` | Eval tools | Judge rate limiting and 429 retries |
| `order_agent/evaltools/eval_llm.py` | Eval tools | LLM factories for the simulated restaurant and judge |
| `order_agent/evaltools/eval_config.py` | Eval tools | Swap a scenario's restaurant or judge config |
| `order_agent/evaltools/preflight.py` | Eval tools | Checks before a run (is Ollama up) |

Outside the layers: `order_agent/config.py` (settings and API keys, used by the heads and eval tools, never by the Model or Controller) and `order_agent/eval_llm.py` (a re-export shim so the `evals/*.yaml` files keep working). `bot.py` and `run_suite.py` are entry points that only wire things together.

### The dependency rule

Dependencies point inward only: `heads -> controller -> model`. An inner layer never imports an outer one. The two heads never import each other, and no head imports the rules engine directly; it reaches it through the Controller.

### The boundary test

`tests/test_architecture.py` reads every file's imports (with Python's `ast` module) and fails if a layer imports something it should not, for example `pipecat` inside the Model. It also fails if a new module is not placed in a layer. It runs with the normal unit tests. The full rules are in [specs/001-headless-mvc/contracts/boundaries.md](specs/001-headless-mvc/contracts/boundaries.md).

### Run the HTTP head

No voice, no API keys, no LLM: you play the agent by sending requests. It listens on `127.0.0.1:8000` only.

```bash
uv run python -m order_agent.heads.http_api
```

The endpoints are described in [specs/001-headless-mvc/contracts/http-api.md](specs/001-headless-mvc/contracts/http-api.md).

### Add a new head

1. Create `order_agent/heads/<name>/`.
2. Build a `CallController(brief, reports_dir=..., hooks=<your CallHooks or None>)`.
3. Translate your channel's events into the Controller calls listed in [specs/001-headless-mvc/contracts/controller-api.md](specs/001-headless-mvc/contracts/controller-api.md).
4. Add the head to `LAYERS` in `tests/architecture.py`, with the third-party packages it may use. `tests/test_architecture.py` then checks it.
5. Add its modules to the module map above (a test fails if one is missing).

## Project layout

```
bot.py                 entry point: starts the voice agent (wiring only)
run_suite.py           entry point: eval runner (pass@3, report checks, quota handling, --rescore)
order_agent/
  model/               pure rules and data: brief, matching, rules engine, report
  controller/          one call, no framework: CallController, tool dispatch, prompt, nudges
  heads/voice/         Pipecat voice head: pipeline, event bridge, LLM factory
  heads/http_api/      FastAPI head for local use: app, schemas, in-memory sessions
  evaltools/           eval suite tooling: checks, throttle, preflight, eval LLM factories
  config.py            settings and API keys
  eval_llm.py          re-export shim so evals/*.yaml factory paths keep working
  (every module is listed in the Architecture section above)
briefs/                order briefs
evals/                 scenarios, expected outcomes, model configs, committed evidence
docs/                  design spec, implementation plan, results write-up
spike/                 early go/no-go experiment (kept as evidence)
tests/                 unit tests
```

## Status and known limits

- **English only, and no real phone line yet.** Calls run in the browser over WebRTC.
- **Free-tier quotas shape everything.**
  - Gemini allows about 500 requests a day and 15 a minute. Groq caps tokens per minute and per day.
  - Running the simulated restaurant locally cut Gemini use by about 31% per test call (13.4 vs 19.6 requests).
- **LLM judges are unreliable,** which is why the code checks decide pass or fail.
- **Prices are now checked in two places.** The eval compares every price and fee in the report with the restaurant's menu in `evals/expected.yaml` (invented or off-menu items fail). At runtime the engine locks the first price it accepts for each item and the first non-zero fees, refuses later changes unless the bot flags a real correction (`price_corrected` / `corrected`), and tells the bot to ask the restaurant to itemise a total that does not match. The engine still cannot know a price is true. It trusts the first price the bot records, and the correction flags are the bot's own claim. The eval's menu check on final prices is the backstop. A correction reprices the whole line, and a tax of 0 is not locked.
- **Unpriced items (restaurants that only give a total).** `add_item`'s price is optional; `set_price` fills one in later. With an unpriced item, or if `set_fees` was never called, the cart total is treated as unknown: `confirm_order` then checks the restaurant's quoted total against the budget, the delivery deadline, completeness and the forbidden items, and skips the cart-sum check (the report says the order was confirmed at the restaurant's total). If a minimum order applies, `confirm_order` refuses until every item has a price. Limits: in this mode the engine cannot detect a restaurant that quotes a wrong or inflated total within budget, and a delivery fee or tax the restaurant never mentions stays unknown. Also, if the bot leaves items unpriced or never records fees even though the restaurant stated them, the quote-fidelity, price-lock and eval menu checks are skipped and the eval cannot detect it (an accepted trade-off of total-only mode).
- **Not tested yet:** holding ("one minute please"), silence, real accents and noise. Ingredient claims ("the biryani has beef") can't be verified by code.

## Next steps

1. ~~Rate-limit the Groq judge~~ Done: the default judge is throttled (see Running the eval).
2. Urdu and Urdu–English (code-switched) conversation.
3. Use the same pattern (LLM talks, code decides) in other domains.

## License

To be decided.

## Acknowledgements

Built on [Pipecat](https://github.com/pipecat-ai/pipecat), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) and [Ollama](https://ollama.com). Developed with [Claude Code](https://claude.ai/code), using spec-driven design, test-driven development and independent reviews for every task.
