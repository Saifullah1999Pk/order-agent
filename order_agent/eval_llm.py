"""LLM factory for Pipecat's eval tools, pointing at Gemini's OpenAI-compatible API."""

from pipecat.services.openai.llm import OpenAILLMService

from order_agent.config import GEMINI_OPENAI_BASE_URL, load_settings


def gemini_llm(config: dict) -> OpenAILLMService:
    return OpenAILLMService(
        api_key=load_settings().google_api_key,
        base_url=GEMINI_OPENAI_BASE_URL,
        settings=OpenAILLMService.Settings(model=config.get("model", "gemini-3.5-flash-lite")),
    )
