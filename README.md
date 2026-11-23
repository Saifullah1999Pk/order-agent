# order-agent

A Pipecat voice agent that phones a restaurant as the customer and places an order.

## Setup

    uv sync
    # put GOOGLE_API_KEY=... in .env

Run anything that imports Pipecat with `PYTHONIOENCODING=utf-8`.

## Gemini via the OpenAI-compatible endpoint

`order_agent.eval_llm.gemini_llm` builds an `OpenAILLMService` pointed at
`https://generativelanguage.googleapis.com/v1beta/openai/`.
Live check: model id `gemini-3.5-flash-lite` works WITHOUT the `models/` prefix.

## Running the bot (phase 1: you play the restaurant)

    PYTHONIOENCODING=utf-8 uv run python bot.py

Wait for "Bot ready!", open http://localhost:7860/client/ and click Connect. The agent waits
3 seconds for you to greet it, then speaks first. Each call writes a report (JSON and a short
text summary) to `reports/`. Use `--port 7861` if 7860 is busy.

### Menu card (use this when playing the restaurant)

| Item | Price (PKR) |
|---|---|
| Chicken biryani | 900 |
| Chicken karahi | 1400 |
| Raita | 150 |
| Delivery fee | 150 |

Three test calls (record results in `docs/phase1-results.md`):

- (a) Happy path: 2 chicken biryani, delivery 150 -> expect `ordered`, total 1950.
- (b) Say "Biryani is finished, we only have fish biryani" -> expect `not_ordered` (or karahi if you offer it).
- (c) Say "one minute please", stay silent for about 10 s, then continue -> the agent should wait without talking over you.
