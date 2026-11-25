"""T024: the LLM factory and llm_http_options live in the voice head; the old names are the same objects."""


def test_factory_lives_in_the_voice_head_and_old_names_are_the_same_objects():
    import order_agent.call as call
    import order_agent.heads.voice.llm_factory as new
    import order_agent.llm_factory as old

    assert old.build_bot_llm is new.build_bot_llm
    assert old.groq_reasoning_effort is new.groq_reasoning_effort
    assert call.llm_http_options is new.llm_http_options
    assert new.llm_http_options()["retry_options"]["attempts"] == 3
