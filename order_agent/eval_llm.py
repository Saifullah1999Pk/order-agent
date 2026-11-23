"""LLM factory for Pipecat's eval tools, pointing at Gemini's OpenAI-compatible API."""

import os

from pipecat.services.openai.llm import OpenAILLMService

from order_agent.config import GEMINI_OPENAI_BASE_URL


def gemini_llm(config: dict) -> OpenAILLMService:
    return OpenAILLMService(
        api_key=os.environ["GOOGLE_API_KEY"],
        base_url=GEMINI_OPENAI_BASE_URL,
        settings=OpenAILLMService.Settings(model=config.get("model", "gemini-3.5-flash-lite")),
    )
