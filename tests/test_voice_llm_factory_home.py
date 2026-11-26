"""T024: the LLM factory and llm_http_options live in the voice head."""


def test_factory_lives_in_the_voice_head():
    import order_agent.heads.voice.llm_factory as new

    assert callable(new.build_bot_llm) and callable(new.groq_reasoning_effort)
    assert new.llm_http_options()["retry_options"]["attempts"] == 3
