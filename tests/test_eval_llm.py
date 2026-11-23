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
