"""LLM factory for Pipecat's eval tools, pointing at Gemini's OpenAI-compatible API."""

from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.openai.llm import OpenAILLMService

from order_agent.config import GEMINI_OPENAI_BASE_URL, load_settings


def gemini_llm(config: dict) -> OpenAILLMService:
    return OpenAILLMService(
        api_key=load_settings().google_api_key,
        base_url=GEMINI_OPENAI_BASE_URL,
        settings=OpenAILLMService.Settings(model=config.get("model", "gemini-3.5-flash-lite")),
    )


def gemini_native_llm(config: dict) -> GoogleLLMService:
    """Native Google service for the simulator persona.

    The OpenAI-compatible route breaks the persona's end_call tool round trip
    (missing thought_signature / empty function_response name).
    """
    return GoogleLLMService(
        api_key=load_settings().google_api_key,
        settings=GoogleLLMService.Settings(model=config.get("model", "gemini-3.5-flash-lite")),
    )
