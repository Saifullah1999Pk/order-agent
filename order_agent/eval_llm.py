"""Compatibility module: evals/*.yaml name factories as ``order_agent.eval_llm.*``.

The implementation lives in order_agent.evaltools.eval_llm. This is the one allowed shim (FR-010):
it contains only re-exports so the YAML files and docs need no edit.
"""
from order_agent.evaltools.eval_llm import (
    ThrottledGroqLLMService,
    ThrottledOpenAILLMService,
    gemini_classifier,
    gemini_llm,
    gemini_native_llm,
    groq_classifier,
    groq_llm,
    ollama_classifier,
)

__all__ = [
    "gemini_llm",
    "gemini_classifier",
    "gemini_native_llm",
    "groq_llm",
    "groq_classifier",
    "ollama_classifier",
    "ThrottledOpenAILLMService",
    "ThrottledGroqLLMService",
]
