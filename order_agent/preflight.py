"""Checks run_suite makes before starting any bot: is Ollama reachable when something needs it."""

import urllib.request
from collections.abc import Callable, Mapping

DEFAULT_OLLAMA_URL = "http://localhost:11434/v1"
FALLBACK_HINT = "start it (see README) or pass --simulator evals/simulator-gemini.yaml"


def _base(url: str) -> str:
    url = url.rstrip("/")
    return url[: -len("/v1")] if url.endswith("/v1") else url


def _is_ollama(cfg: Mapping) -> bool:
    return cfg.get("service") == "ollama" or "ollama" in str(cfg.get("factory", ""))


def ollama_bases(simulator: Mapping, judge: Mapping, provider: str | None, bot_url: str | None) -> list[str]:
    """Distinct Ollama server addresses (no /v1) the run will use, in a stable order."""
    bases: list[str] = []

    def add(url: str | None) -> None:
        b = _base(url or DEFAULT_OLLAMA_URL)
        if b not in bases:
            bases.append(b)

    if provider == "ollama":
        add(bot_url)
    if _is_ollama(simulator):
        add(simulator.get("base_url") or bot_url)
    if _is_ollama(judge):
        add(judge.get("endpoint"))
    return bases


def ollama_up(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def check_ollama(bases: list[str], get: Callable[[str], bool]) -> str | None:
    for base in bases:
        if not get(f"{base}/api/tags"):
            return f"Ollama is not running at {base}: {FALLBACK_HINT}"
    return None


def preflight_message(simulator: Mapping, judge: Mapping, env: Mapping[str, str], get: Callable[[str], bool]) -> str | None:
    bases = ollama_bases(simulator, judge, env.get("ORDER_AGENT_LLM_PROVIDER"), env.get("ORDER_AGENT_OLLAMA_URL"))
    return check_ollama(bases, get)
