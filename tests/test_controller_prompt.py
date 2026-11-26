import order_agent.controller.prompt as controller_prompt


def test_build_system_prompt_lives_in_controller():
    assert callable(controller_prompt.build_system_prompt)


def test_prompt_for_brief_fixture_is_unchanged(brief):
    first = controller_prompt.build_system_prompt(brief)
    assert first and first == controller_prompt.build_system_prompt(brief)
