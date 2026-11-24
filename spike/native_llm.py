"""Spike-only factory: Gemini through Pipecat's NATIVE Google service.

The OpenAI-compat route breaks on the persona's end_call tool round-trip
(see FINDINGS.md); the native service handles thought signatures and
function_response names correctly.
"""
from pipecat.services.google.llm import GoogleLLMService

from order_agent.config import load_settings


def gemini_native_llm(config: dict) -> GoogleLLMService:
    return GoogleLLMService(
        api_key=load_settings().google_api_key,
        settings=GoogleLLMService.Settings(model=config.get("model", "gemini-3.5-flash-lite")),
    )
