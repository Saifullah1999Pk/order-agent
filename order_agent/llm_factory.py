"""Builds the bot's LLM service from settings (Gemini by default, Groq optional)."""

from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.llm_service import LLMService

from order_agent.call import llm_http_options
from order_agent.config import Settings


def groq_reasoning_effort(model: str) -> str:
    """Qwen models stream reasoning inline in <think> tags unless it is switched off, and that
    text would be spoken. gpt-oss models cannot switch it off, so keep it short."""
    return "none" if model.startswith("qwen/") else "low"


def build_bot_llm(settings: Settings, system_prompt: str, gemini_model: str | None = None) -> LLMService:
    """The bot's LLM. `gemini_model` is the model chosen by the Gemini probe (ignored for Groq)."""
    if settings.llm_provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError(
                "ORDER_AGENT_LLM_PROVIDER=groq needs GROQ_API_KEY (put it in order-agent/.env)"
            )
        llm = GroqLLMService(
            api_key=settings.groq_api_key,
            settings=GroqLLMService.Settings(
                model=settings.groq_model,
                system_instruction=system_prompt,
                reasoning_effort=groq_reasoning_effort(settings.groq_model),
            ),
        )
        # The opening and nudge messages use the "developer" role; send them as "user" messages.
        llm.supports_developer_role = False
        return llm
    return GoogleLLMService(
        api_key=settings.google_api_key,
        settings=GoogleLLMService.Settings(
            model=gemini_model or settings.model,
            system_instruction=system_prompt,
        ),
        http_options=llm_http_options(),
    )
