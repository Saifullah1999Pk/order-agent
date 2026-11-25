import order_agent.controller.prompt as controller_prompt
import order_agent.prompt as legacy_prompt


def test_build_system_prompt_lives_in_controller_and_legacy_module_reexports_it():
    assert legacy_prompt.build_system_prompt is controller_prompt.build_system_prompt


def test_prompt_for_brief_fixture_is_unchanged(brief):
    assert controller_prompt.build_system_prompt(brief) == legacy_prompt.build_system_prompt(brief)
