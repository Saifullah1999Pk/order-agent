"""The Gemini availability probe used to choose a model before the call starts."""

import asyncio

from loguru import logger

from order_agent.config import Settings, require_google_key

PROBE_TIMEOUT_SECS = 10.0


def make_probe(settings: Settings):
    """A single 1-token Gemini request with a 10 s timeout. Any failure counts as 'not usable'."""
    from google import genai  # Gemini only: imported here so the Groq path never touches it
    from google.genai import types as genai_types

    client = genai.Client(api_key=require_google_key(settings))

    async def probe(model: str) -> bool:
        try:
            await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model,
                    contents="hi",
                    config=genai_types.GenerateContentConfig(max_output_tokens=1),
                ),
                timeout=PROBE_TIMEOUT_SECS,
            )
            return True
        except Exception as exc:  # includes timeout, 429, 503, bad key
            logger.warning(f"Model probe failed for {model}: {exc!r}")
            return False

    return probe
