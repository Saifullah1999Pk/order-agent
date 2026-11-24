"""Runtime settings loaded from .env and environment variables."""

import os
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class Settings(BaseModel):
    google_api_key: str | None = None
    groq_api_key: str | None = None
    model: str = "gemini-3.5-flash-lite"
    fallback_model: str = "gemini-2.5-flash"
    llm_provider: Literal["gemini", "groq"] = "gemini"
    groq_model: str = "qwen/qwen3.8-27b"
    reports_dir: Path = Path("reports")
    brief_path: Path = Path("briefs/example.yaml")
    call_time: datetime | None = None


def require_google_key(settings: Settings) -> str:
    """The Gemini key, or a clear error when a Gemini path needs it and it is not set."""
    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set (put it in order-agent/.env); the Gemini path needs it")
    return settings.google_api_key


def load_settings() -> Settings:
    load_dotenv()
    values = {
        "google_api_key": os.getenv("GOOGLE_API_KEY"),
        "groq_api_key": os.getenv("GROQ_API_KEY"),
        "model": os.getenv("ORDER_AGENT_MODEL"),
        "fallback_model": os.getenv("ORDER_AGENT_FALLBACK_MODEL"),
        "llm_provider": os.getenv("ORDER_AGENT_LLM_PROVIDER"),
        "groq_model": os.getenv("ORDER_AGENT_GROQ_MODEL"),
        "reports_dir": os.getenv("ORDER_REPORTS_DIR"),
        "brief_path": os.getenv("ORDER_BRIEF"),
        "call_time": os.getenv("ORDER_CALL_TIME"),
    }
    return Settings(**{k: v for k, v in values.items() if v})


async def pick_model(settings: Settings, probe: Callable[[str], Awaitable[bool]]) -> str:
    """Return the primary model if the probe succeeds, else the fallback."""
    if await probe(settings.model):
        return settings.model
    return settings.fallback_model
