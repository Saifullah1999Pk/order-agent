import pytest

import order_agent.controller.nudge as nudge

NAMES = ["should_nudge", "NudgeTracker", "NudgeScheduler", "NUDGE_TEXT", "MAX_NUDGES", "NUDGE_DELAY_SECS"]


@pytest.mark.parametrize("name", NAMES)
def test_name_lives_in_controller(name):
    assert hasattr(nudge, name)
