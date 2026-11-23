from pipecat.services.openai.base_llm import BaseOpenAILLMService

from order_agent.eval_llm import gemini_llm


def test_gemini_llm_factory(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    llm = gemini_llm({"model": "gemini-2.5-flash"})
    assert isinstance(llm, BaseOpenAILLMService)
    assert llm._settings.model == "gemini-2.5-flash"
