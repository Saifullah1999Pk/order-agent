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
