from pipecat.services.openai.base_llm import BaseOpenAILLMService

from order_agent.eval_llm import gemini_llm


def test_gemini_llm_factory(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    llm = gemini_llm({"model": "gemini-2.5-flash"})
    assert isinstance(llm, BaseOpenAILLMService)
    assert llm._settings.model == "gemini-2.5-flash"


def test_gemini_llm_reads_key_from_dotenv_file(monkeypatch, tmp_path):
    from functools import partial

    from dotenv import load_dotenv

    import order_agent.config as config

    env_file = tmp_path / ".env"
    env_file.write_text("GOOGLE_API_KEY=key-from-file\n")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(config, "load_dotenv", partial(load_dotenv, dotenv_path=env_file))
    llm = gemini_llm({})
    assert llm._client.api_key == "key-from-file"


def test_gemini_native_llm_factory(monkeypatch):
    from pipecat.services.google.llm import GoogleLLMService

    from order_agent.eval_llm import gemini_native_llm

    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    llm = gemini_native_llm({"model": "gemini-2.5-flash"})
    assert isinstance(llm, GoogleLLMService)
    assert llm._settings.model == "gemini-2.5-flash"
    assert gemini_native_llm({})._settings.model == "gemini-3.5-flash-lite"


def test_groq_llm_factory(monkeypatch):
    from order_agent.eval_llm import groq_llm

    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")
    llm = groq_llm({"model": "openai/gpt-oss-120b"})
    assert isinstance(llm, BaseOpenAILLMService)
    assert llm._settings.model == "openai/gpt-oss-120b"
    assert "api.groq.com" in str(llm._client.base_url)


def test_groq_llm_requires_key(monkeypatch):
    import pytest

    import order_agent.config as config
    from order_agent.eval_llm import groq_llm

    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        groq_llm({"model": "openai/gpt-oss-120b"})


def test_groq_llm_passes_reasoning_effort(monkeypatch):
    from order_agent.eval_llm import groq_llm

    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")
    llm = groq_llm({"model": "qwen/qwen3.8-27b", "reasoning_effort": "none"})
    assert llm._settings.reasoning_effort == "none"


def test_gemini_llm_plain_without_throttle_keys(monkeypatch):
    from order_agent.eval_llm import ThrottledOpenAILLMService

    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    assert not isinstance(gemini_llm({"model": "m"}), ThrottledOpenAILLMService)


def test_gemini_llm_throttled_when_configured_and_limiter_shared(monkeypatch):
    from order_agent.eval_llm import ThrottledOpenAILLMService

    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    cfg = {"model": "m", "max_concurrency": 1, "min_interval_s": 4.5, "max_retries": 3}
    a, b = gemini_llm(cfg), gemini_llm(cfg)
    assert isinstance(a, ThrottledOpenAILLMService)
    assert a._throttle is b._throttle


async def test_throttled_service_wraps_run_inference(monkeypatch):
    from pipecat.services.openai.llm import OpenAILLMService

    from order_agent.eval_llm import ThrottledOpenAILLMService
    from order_agent.throttle import Throttle

    calls = []

    async def fake(self, context, **kw):
        calls.append(kw)
        return "x"

    monkeypatch.setattr(OpenAILLMService, "run_inference", fake)
    svc = ThrottledOpenAILLMService(
        throttle=Throttle(min_interval_s=0), api_key="k", base_url="http://x",
        settings=OpenAILLMService.Settings(model="m"),
    )
    assert await svc.run_inference(None, max_tokens=5) == "x"
    assert calls == [{"max_tokens": 5}]


def test_gemini_classifier_factory_sets_timeout(monkeypatch):
    from order_agent.eval_llm import gemini_classifier

    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    c = gemini_classifier({"model": "m", "min_interval_s": 4.5, "timeout_s": 90})
    assert c._timeout == 90


def test_throttled_service_disables_sdk_internal_retries(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    llm = gemini_llm({"model": "m", "min_interval_s": 4.5})
    assert llm._client.max_retries == 0


# --- Groq judge throttle ---

def _groq_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")


def test_groq_llm_plain_without_throttle_keys(monkeypatch):
    from order_agent.eval_llm import ThrottledOpenAILLMService, groq_llm

    _groq_env(monkeypatch)
    assert not isinstance(groq_llm({"model": "openai/gpt-oss-20b"}), ThrottledOpenAILLMService)


def test_groq_llm_throttled_keeps_groq_settings(monkeypatch):
    from pipecat.services.groq.llm import GroqLLMService

    from order_agent.eval_llm import ThrottledOpenAILLMService, groq_llm

    _groq_env(monkeypatch)
    llm = groq_llm({"model": "openai/gpt-oss-20b", "reasoning_effort": "low", "min_interval_s": 20})
    assert isinstance(llm, ThrottledOpenAILLMService)
    assert isinstance(llm, GroqLLMService)
    assert llm._settings.model == "openai/gpt-oss-20b"
    assert llm._settings.reasoning_effort == "low"
    assert "api.groq.com" in str(llm._client.base_url)


def test_groq_throttled_disables_sdk_retries(monkeypatch):
    from order_agent.eval_llm import groq_llm

    _groq_env(monkeypatch)
    assert groq_llm({"model": "m", "min_interval_s": 20})._client.max_retries == 0


def test_groq_classifier_sets_timeout_and_default(monkeypatch):
    from order_agent.eval_llm import ThrottledOpenAILLMService, groq_classifier

    _groq_env(monkeypatch)
    c = groq_classifier({"model": "m", "min_interval_s": 20, "timeout_s": 300})
    assert c._timeout == 300
    assert isinstance(c._llm, ThrottledOpenAILLMService)
    assert groq_classifier({"model": "m"})._timeout == 180.0


def test_groq_eval_and_explainer_share_limiter(monkeypatch):
    from order_agent.eval_llm import groq_classifier, groq_llm

    _groq_env(monkeypatch)
    cfg = {"model": "openai/gpt-oss-20b", "reasoning_effort": "low", "max_concurrency": 1,
           "min_interval_s": 20, "max_retries": 3, "retry_base_s": 15}
    assert groq_classifier({**cfg, "timeout_s": 300})._llm._throttle is groq_llm(cfg)._throttle


async def test_groq_rate_limit_text_is_retried(monkeypatch):
    from pipecat.services.openai.llm import OpenAILLMService

    from order_agent.eval_llm import groq_llm
    from order_agent.throttle import Throttle, is_rate_limit_error

    _groq_env(monkeypatch)
    msg = ("Error code: 400 - {'error': {'message': 'Rate limit reached for model "
           "`openai/gpt-oss-20b` ...', 'code': 'rate_limit_exceeded'}}")
    assert is_rate_limit_error(RuntimeError(msg))
    assert is_rate_limit_error(RuntimeError("Rate limit reached for model"))
    assert is_rate_limit_error(RuntimeError("Error code: 429"))

    calls = []

    async def flaky(self, context, **kw):
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError(msg)
        return "ok"

    async def nosleep(_):
        pass

    monkeypatch.setattr(OpenAILLMService, "run_inference", flaky)
    llm = groq_llm({"model": "m", "max_retries": 2})
    llm._throttle = Throttle(max_retries=2, sleep=nosleep)
    assert await llm.run_inference(None) == "ok"
    assert len(calls) == 2
