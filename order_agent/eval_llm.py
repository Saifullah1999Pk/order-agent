"""LLM factory for Pipecat's eval tools, pointing at Gemini's OpenAI-compatible API."""

from pipecat.classifiers.llm.classifier import LLMClassifier
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.openai.llm import OpenAILLMService

from order_agent.config import GEMINI_OPENAI_BASE_URL, load_settings, require_google_key
from order_agent.throttle import Throttle

THROTTLE_KEYS = ("max_concurrency", "min_interval_s", "max_retries", "retry_base_s")
_throttles: dict[str, Throttle] = {}


class ThrottledOpenAILLMService(OpenAILLMService):
    """Paces ``run_inference``, the one call the eval judge and explainer make."""

    def __init__(self, *, throttle: Throttle, **kwargs):
        super().__init__(**kwargs)
        self._throttle = throttle
        # The SDK retries 429s itself (default 2); ours are paced, so they are the only ones.
        self._client = self._client.with_options(max_retries=0)

    async def run_inference(self, *args, **kwargs):
        parent = super().run_inference
        return await self._throttle.run(lambda: parent(*args, **kwargs))


def _shared_throttle(config: dict) -> Throttle:
    """One limiter per model and settings, so eval and explainer share the gap."""
    opts = {k: config[k] for k in THROTTLE_KEYS if k in config}
    key = f"{config.get('model')}|{sorted(opts.items())}"
    if key not in _throttles:
        _throttles[key] = Throttle(**opts)
    return _throttles[key]


def gemini_llm(config: dict) -> OpenAILLMService:
    kwargs = dict(
        api_key=require_google_key(load_settings()),
        base_url=GEMINI_OPENAI_BASE_URL,
        settings=OpenAILLMService.Settings(model=config.get("model", "gemini-3.5-flash-lite")),
    )
    if any(k in config for k in THROTTLE_KEYS):
        return ThrottledOpenAILLMService(throttle=_shared_throttle(config), **kwargs)
    return OpenAILLMService(**kwargs)


def gemini_classifier(config: dict) -> LLMClassifier:
    """Judge classifier whose timeout (``timeout_s``) allows for the throttle's queue."""
    return LLMClassifier(llm=gemini_llm(config), timeout=config.get("timeout_s", 120.0))


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
