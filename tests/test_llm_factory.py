"""The bot's LLM is chosen by settings; no network calls."""

from types import SimpleNamespace

import pytest
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.groq.llm import GroqLLMService

from order_agent.config import Settings, load_settings
from order_agent.llm_factory import build_bot_llm
from order_agent.controller import CallController
from order_agent.heads.voice.tools import build_tools

NAMES = {"add_item", "remove_item", "set_fees", "set_minimum_order", "confirm_order", "end_call"}


def test_settings_defaults():
    s = Settings(google_api_key="g")
    assert s.llm_provider == "gemini"
    assert s.groq_model == "qwen/qwen3.8-27b"


def test_load_settings_reads_provider_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    monkeypatch.setenv("ORDER_AGENT_LLM_PROVIDER", "groq")
    monkeypatch.setenv("ORDER_AGENT_GROQ_MODEL", "openai/gpt-oss-20b")
    s = load_settings()
    assert (s.llm_provider, s.groq_model) == ("groq", "openai/gpt-oss-20b")


def test_default_builds_gemini_service():
    llm = build_bot_llm(Settings(google_api_key="g"), "be polite", gemini_model="gemini-2.5-flash")
    assert isinstance(llm, GoogleLLMService)
    assert llm._settings.model == "gemini-2.5-flash"
    assert llm._settings.system_instruction == "be polite"


def test_groq_builds_groq_service_with_model_and_prompt():
    s = Settings(google_api_key="g", groq_api_key="k", llm_provider="groq", groq_model="openai/gpt-oss-20b")
    llm = build_bot_llm(s, "be polite")
    assert isinstance(llm, GroqLLMService)
    assert llm._settings.model == "openai/gpt-oss-20b"
    assert llm._settings.system_instruction == "be polite"


def test_groq_without_key_raises_clear_error():
    s = Settings(google_api_key="g", llm_provider="groq")
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        build_bot_llm(s, "x")


def test_groq_sends_developer_messages_as_user():
    s = Settings(google_api_key="g", groq_api_key="k", llm_provider="groq")
    assert build_bot_llm(s, "x").supports_developer_role is False


async def test_tool_registration_with_groq_service(brief, tmp_path):
    controller = CallController(brief, reports_dir=tmp_path, now=brief.call_time)
    session = controller.session

    context = LLMContext(tools=build_tools(controller))
    s = Settings(google_api_key="g", groq_api_key="k", llm_provider="groq")
    llm = build_bot_llm(s, "x")
    llm._sync_registered_tool_handlers(context.tools)
    assert NAMES <= set(llm._functions)

    results = []

    async def result_callback(result, properties=None):
        results.append(result)

    params = SimpleNamespace(
        arguments={"name": "chicken biryani", "quantity": 2, "unit_price_pkr": 900},
        result_callback=result_callback,
    )
    await llm._functions["add_item"].handler(params)
    assert results[-1]["ok"] is True
    assert session.items[0].quantity == 2


def _no_google(monkeypatch, tmp_path):
    monkeypatch.setattr("order_agent.config.load_dotenv", lambda *a, **k: None)  # ignore the real .env
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("ORDER_AGENT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ORDER_AGENT_GROQ_MODEL", raising=False)


def test_groq_works_without_google_key(monkeypatch, tmp_path):
    _no_google(monkeypatch, tmp_path)
    monkeypatch.setenv("ORDER_AGENT_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    s = load_settings()
    assert s.google_api_key is None
    assert isinstance(build_bot_llm(s, "x"), GroqLLMService)


def test_gemini_without_google_key_raises_clear_error(monkeypatch, tmp_path):
    _no_google(monkeypatch, tmp_path)
    s = load_settings()
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        build_bot_llm(s, "x")


def test_gemini_eval_factories_need_google_key(monkeypatch, tmp_path):
    from order_agent.evaltools.eval_llm import gemini_llm, gemini_native_llm

    _no_google(monkeypatch, tmp_path)
    for factory in (gemini_llm, gemini_native_llm):
        with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
            factory({})


# --- all-local Ollama bot ---

def test_ollama_settings_defaults():
    s = Settings()
    assert s.ollama_model == "qwen3:8b"
    assert s.ollama_base_url == "http://localhost:11434/v1"


def test_load_settings_reads_ollama_env(monkeypatch):
    monkeypatch.setattr("order_agent.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("ORDER_AGENT_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("ORDER_AGENT_OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("ORDER_AGENT_OLLAMA_URL", "http://example:1234/v1")
    s = load_settings()
    assert (s.llm_provider, s.ollama_model, s.ollama_base_url) == ("ollama", "qwen3:4b", "http://example:1234/v1")


def test_ollama_builds_ollama_service_with_model_prompt_and_thinking_off():
    from pipecat.services.ollama.llm import OLLamaLLMService

    s = Settings(llm_provider="ollama", ollama_model="qwen3:8b", ollama_base_url="http://example:1234/v1")
    llm = build_bot_llm(s, "be polite")  # no API key of any kind
    assert isinstance(llm, OLLamaLLMService)
    assert llm._settings.model == "qwen3:8b"
    assert llm._settings.system_instruction == "be polite"
    assert llm._settings.extra == {"reasoning_effort": "none"}
    assert str(llm._client.base_url).startswith("http://example:1234/v1")


def test_ollama_works_without_any_keys(monkeypatch):
    _no_google(monkeypatch, None)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("ORDER_AGENT_LLM_PROVIDER", "ollama")
    s = load_settings()
    assert s.google_api_key is None and s.groq_api_key is None
    build_bot_llm(s, "x")


async def test_tool_registration_with_ollama_service(brief, tmp_path):
    controller = CallController(brief, reports_dir=tmp_path, now=brief.call_time)
    session = controller.session

    context = LLMContext(tools=build_tools(controller))
    llm = build_bot_llm(Settings(llm_provider="ollama"), "x")
    llm._sync_registered_tool_handlers(context.tools)
    assert NAMES <= set(llm._functions)

    results = []

    async def result_callback(result, properties=None):
        results.append(result)

    params = SimpleNamespace(
        arguments={"name": "chicken biryani", "quantity": 2, "unit_price_pkr": 900},
        result_callback=result_callback,
    )
    await llm._functions["add_item"].handler(params)
    assert results[-1]["ok"] is True
    assert session.items[0].quantity == 2


def test_ollama_builds_local_service_with_thinking_off():
    from pipecat.services.ollama.llm import OLLamaLLMService

    s = Settings(llm_provider="ollama", ollama_model="qwen3:8b", ollama_base_url="http://box:1234/v1")
    llm = build_bot_llm(s, "be polite")  # what bot.py calls for the ollama provider; no key, no network
    assert isinstance(llm, OLLamaLLMService)
    assert llm._settings.model == "qwen3:8b"
    assert llm._settings.system_instruction == "be polite"
    assert llm._settings.extra == {"reasoning_effort": "none"}


def test_load_settings_reads_ollama_env(monkeypatch):
    monkeypatch.setenv("ORDER_AGENT_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("ORDER_AGENT_OLLAMA_URL", "http://box:1234/v1")
    s = load_settings()
    assert (s.llm_provider, s.ollama_base_url) == ("ollama", "http://box:1234/v1")
