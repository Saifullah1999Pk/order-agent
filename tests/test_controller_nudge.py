import pytest

import order_agent.call as call
import order_agent.controller.nudge as nudge

NAMES = ["should_nudge", "NudgeTracker", "NudgeScheduler", "NUDGE_TEXT", "MAX_NUDGES", "NUDGE_DELAY_SECS"]


@pytest.mark.parametrize("name", NAMES)
def test_name_lives_in_controller_and_call_reexports_it(name):
    assert getattr(call, name) is getattr(nudge, name)
