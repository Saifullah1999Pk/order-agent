"""Compat shim: the LLM factory now lives in order_agent.heads.voice.llm_factory."""
from order_agent.heads.voice.llm_factory import build_bot_llm, groq_reasoning_effort

__all__ = ["build_bot_llm", "groq_reasoning_effort"]
