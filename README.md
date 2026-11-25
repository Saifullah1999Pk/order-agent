# order-agent

A Pipecat voice agent that phones a restaurant as the customer and places an order inside hard
rules (budget, allowed items, forbidden keywords, delivery deadline). The LLM does the talking;
`order_agent/rules.py` decides what is allowed. A suite of 11 simulated-restaurant scenarios
checks it. Results: [docs/results-v1.md](docs/results-v1.md).

## Setup

    uv sync

Create `.env` (gitignored) with two free-tier keys:

    GOOGLE_API_KEY=...   # bot LLM (gemini-3.5-flash-lite, fallback gemini-2.5-flash)
    GROQ_API_KEY=...     # judge (gpt-oss-20b), suite only. The simulated restaurant defaults to a local Ollama model (see below)

The bot's LLM is Gemini by default. To run it on Groq's free tier instead (for example when Gemini's daily
cap is used up), set in `.env` or the environment:

    ORDER_AGENT_LLM_PROVIDER=groq              # "gemini" (default), "groq" or "ollama"
    ORDER_AGENT_GROQ_MODEL=qwen/qwen3.8-27b    # default; needs GROQ_API_KEY. in 2 audio attempts gpt-oss-20b called a tool that does not exist

The suite passes these to the bot it starts. Keep results from different bot models apart
(see docs/results-v1.md section 9).

### Default test setup: hybrid (Gemini bot, local Ollama restaurant, Groq judge)

The suite's simulated restaurant (`evals/simulator.yaml`) is local Ollama `qwen3:8b`, so running the suite needs Ollama
running with the model pulled (`ollama pull qwen3:8b`). On Windows (PowerShell), start the server in its own window:

    $env:OLLAMA_NUM_PARALLEL=1; $env:OLLAMA_CONTEXT_LENGTH=8192; $env:OLLAMA_KV_CACHE_TYPE="q8_0"; $env:OLLAMA_FLASH_ATTENTION=1; $env:OLLAMA_KEEP_ALIVE="2h"; ollama serve

Check `ollama ps` says `100% GPU`. This halves Gemini use per test call, because the persona no longer calls Gemini. To use a
cloud persona instead, pass `--simulator` with a config that has the Gemini or Groq block (both are kept as comments in
`evals/simulator.yaml`; copy that file and uncomment one).

### All-local (Ollama): bot, simulated restaurant and judge, no cloud keys

Needs [Ollama](https://ollama.com) and `ollama pull qwen3:8b` (5.2 GB, fits an 8 GB GPU). Start the server with one
cache slot per role (bot, persona, judge) and a 4k context per slot. A q8 KV cache is what keeps all three slots on an
8 GB GPU (check `ollama ps`: it should say `100% GPU`):

    OLLAMA_NUM_PARALLEL=3 OLLAMA_CONTEXT_LENGTH=4096 OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KEEP_ALIVE=2h ollama serve

Then run the suite with the bot, persona and judge on Ollama:

    ORDER_AGENT_LLM_PROVIDER=ollama PYTHONIOENCODING=utf-8 uv run python run_suite.py --only happy_path --simulator evals/simulator-ollama.yaml --judge evals/judge-ollama.yaml

`ORDER_AGENT_OLLAMA_MODEL` (default `qwen3:8b`) and `ORDER_AGENT_OLLAMA_URL` (default `http://localhost:11434/v1`) change
the bot's model and server. qwen3's hidden thinking is switched off with `reasoning_effort: none` in the request (Ollama's
OpenAI-compatible endpoint ignores `think: false`); the bot, persona and judge all send it. `--simulator` / `--judge`
replace the persona and judge configs for that run only; the committed defaults (Ollama persona, Groq judge) are unchanged.
Results and an honest quality comparison: `evals/confirmation/all-ollama/README.md`.

Anything that imports Pipecat must be run with `PYTHONIOENCODING=utf-8` on Windows (the dev
runner crashes on non-UTF-8 stdout). Prefix every command below with it.

## Run the bot (you play the restaurant)

    PYTHONIOENCODING=utf-8 uv run python bot.py

Wait for "Bot ready!", open http://localhost:7860/client/ and click Connect. The agent waits
3 seconds for you to greet it, then speaks first. Use `--port 7861` if 7860 is busy.
`ORDER_BRIEF=path.yaml` picks the brief (default `briefs/example.yaml`).
Each call writes a report (JSON and a short text summary) to `reports/` (gitignored).

Menu card for manual calls: chicken biryani 900, chicken karahi 1400, raita 150, delivery fee 150 (PKR).

## Run the eval suite

Text mode (the simulated restaurant types, no audio models):

    PYTHONIOENCODING=utf-8 uv run python run_suite.py                       # all 11 scenarios
    PYTHONIOENCODING=utf-8 uv run python run_suite.py --only happy_path,pushes_forbidden

Audio mode (the simulated restaurant speaks with Kokoro, Whisper transcribes the bot):

    PYTHONIOENCODING=utf-8 uv run python run_suite.py --audio --only happy_path

Options: `--attempts N` (default 3, pass@3: stops at the first pass), `--sleep S` (seconds between
attempts, default 20; raise it if you see 429s). A harness error that is a 429/503 is recorded as `quota_error`. So is a cut-off call whose `bot.log` shows the bot's own LLM failing with 429/503, unless a budget, forbidden-item or never-keyword violation is also present (a confirmed order with a violation stays `fail`).
`--rescore evals/results/<run-id>` re-classifies saved attempts and rewrites that run's `summary.md` without any new run.
Deterministic report checks (outcome, budget, forbidden items) override the judge.

Where things go (all under `evals/results/<timestamp>/`, gitignored): `summary.md`, and per scenario
and attempt `bot.log`, `conversation.json`, `eval.log`, `judge.txt` and the call report (`.json`/`.txt`).
Expected outcomes live in `evals/expected.yaml`, scenarios in `evals/scenarios/`, briefs in `evals/briefs/`.
Run summaries kept as evidence are committed under `evals/confirmation/`.

## Tests

    uv run pytest

## Notes

`order_agent.eval_llm` builds OpenAI-compatible LLM services for Gemini
(`https://generativelanguage.googleapis.com/v1beta/openai/`, model id without the `models/` prefix)
and Groq. Free-tier limits that matter: Gemini about 15 requests/min per model and a daily cap;
Groq 8000 tokens/min per model.
