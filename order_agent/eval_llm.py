"""LLM factory for Pipecat's eval tools, pointing at Gemini's OpenAI-compatible API."""

from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.openai.llm import OpenAILLMService

from order_agent.config import GEMINI_OPENAI_BASE_URL, load_settings, require_google_key


def gemini_llm(config: dict) -> OpenAILLMService:
    return OpenAILLMService(
        api_key=require_google_key(load_settings()),
        base_url=GEMINI_OPENAI_BASE_URL,
        settings=OpenAILLMService.Settings(model=config.get("model", "gemini-3.5-flash-lite")),
    )


def gemini_native_llm(config: dict) -> GoogleLLMService:
    """Native Google service for the simulator persona.

    The OpenAI-compatible route breaks the persona's end_call tool round trip
    (missing thought_signature / empty function_response name).
    """
    return GoogleLLMService(
        api_key=require_google_key(load_settings()),
        settings=GoogleLLMService.Settings(model=config.get("model", "gemini-3.5-flash-lite")),
    )


def groq_llm(config: dict) -> GroqLLMService:
    """Groq (free tier) service for the simulated restaurant and the judge."""
    key = load_settings().groq_api_key
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set (put it in order-agent/.env)")
    settings = GroqLLMService.Settings(model=config.get("model", "openai/gpt-oss-120b"))
    if "reasoning_effort" in config:
        settings.reasoning_effort = config["reasoning_effort"]
    return GroqLLMService(api_key=key, settings=settings)
