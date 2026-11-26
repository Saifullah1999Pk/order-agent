from order_agent.controller.nudge import MAX_NUDGES, should_nudge


def test_nudge_after_empty_silent_turn():
    assert should_nudge("", had_function_call=False, restaurant_spoke_since=False, nudges_in_a_row=0)


def test_no_nudge_when_agent_said_something():
    assert not should_nudge("Okay.", had_function_call=False, restaurant_spoke_since=False, nudges_in_a_row=0)


def test_no_nudge_for_whitespace_only_is_still_empty():
    assert should_nudge("  \n", had_function_call=False, restaurant_spoke_since=False, nudges_in_a_row=0)


def test_no_nudge_after_function_call_turn():
    assert not should_nudge("", had_function_call=True, restaurant_spoke_since=False, nudges_in_a_row=0)


def test_no_nudge_when_restaurant_spoke_since():
    assert not should_nudge("", had_function_call=False, restaurant_spoke_since=True, nudges_in_a_row=0)


def test_at_most_two_nudges_in_a_row():
    assert MAX_NUDGES == 2
    assert should_nudge("", had_function_call=False, restaurant_spoke_since=False, nudges_in_a_row=1)
    assert not should_nudge("", had_function_call=False, restaurant_spoke_since=False, nudges_in_a_row=2)


from order_agent.controller.nudge import NudgeTracker


def test_tracker_nudges_empty_turn_answering_the_restaurant():
    t = NudgeTracker()
    t.on_user_turn_started()  # the restaurant asks something
    t.on_llm_run_started()  # the LLM run that answers them
    assert t.on_assistant_turn("") is True  # that run returned nothing (e.g. 429)


def test_tracker_no_nudge_when_restaurant_spoke_after_the_empty_run_started():
    t = NudgeTracker()
    t.on_llm_run_started()
    t.on_user_turn_started()  # they spoke while/after the run: their turn gets its own reply
    assert t.on_assistant_turn("") is False


def test_tracker_tool_turn_is_not_nudged_but_the_empty_follow_up_is():
    t = NudgeTracker()
    t.on_user_turn_started()
    t.on_llm_run_started()
    t.on_function_call()
    assert t.on_assistant_turn("") is False
    t.on_llm_run_started()
    assert t.on_assistant_turn("") is True


def test_tracker_bounded_at_two_nudges():
    t = NudgeTracker()
    results = []
    for _ in range(3):
        t.on_llm_run_started()
        results.append(t.on_assistant_turn(""))
    assert results == [True, True, False]


def test_tracker_count_resets_on_restaurant_speech_and_on_tool_run():
    t = NudgeTracker()
    for _ in range(2):
        t.on_llm_run_started()
        assert t.on_assistant_turn("")
    t.on_user_turn_started()
    t.on_llm_run_started()
    assert t.on_assistant_turn("") is True  # budget restored by the restaurant speaking
    t.on_llm_run_started()
    assert t.on_assistant_turn("") is True
    t.on_llm_run_started()
    t.on_function_call()
    assert t.on_assistant_turn("") is False
    t.on_llm_run_started()
    assert t.on_assistant_turn("") is True  # and by a tool run


def test_tracker_count_resets_on_spoken_reply_and_interrupted_is_not_nudged():
    t = NudgeTracker()
    t.on_llm_run_started()
    assert t.on_assistant_turn("")
    t.on_llm_run_started()
    assert t.on_assistant_turn("Hello") is False
    t.on_llm_run_started()
    assert t.on_assistant_turn("", interrupted=True) is False


def test_llm_retry_options_configured():
    from order_agent.heads.voice.llm_factory import llm_http_options

    opts = llm_http_options()
    retry = opts["retry_options"]
    assert retry["attempts"] == 3
    assert retry["initial_delay"] == 2.0
    assert 429 in retry["http_status_codes"] and 503 in retry["http_status_codes"]


import asyncio

from order_agent.controller.nudge import NudgeScheduler


class _Gate:
    """An injected sleep the test releases by hand."""

    def __init__(self):
        self.event = asyncio.Event()
        self.sleeps = 0

    async def sleep(self, secs):
        self.sleeps += 1
        await self.event.wait()


async def _settle():
    for _ in range(5):
        await asyncio.sleep(0)


def _scheduler(gate):
    fired = []

    async def fire():
        fired.append(1)

    return NudgeScheduler(fire, delay=3.0, sleep=gate.sleep), fired


async def test_scheduler_fires_once_after_the_delay():
    gate = _Gate()
    sched, fired = _scheduler(gate)
    sched.schedule()
    await _settle()
    assert fired == []
    gate.event.set()
    await _settle()
    assert fired == [1]


async def test_scheduler_cancel_on_restaurant_speech_or_llm_run_start():
    gate = _Gate()
    sched, fired = _scheduler(gate)
    sched.schedule()
    await _settle()
    sched.cancel()  # what bot.py does on user turn started and on llm run started
    gate.event.set()
    await _settle()
    assert fired == []


async def test_scheduler_second_schedule_replaces_the_first():
    gate = _Gate()
    sched, fired = _scheduler(gate)
    sched.schedule()
    await _settle()
    sched.schedule()
    await _settle()
    gate.event.set()
    await _settle()
    assert fired == [1]


async def test_scheduler_cancel_at_end_of_call_prevents_fire():
    gate = _Gate()
    sched, fired = _scheduler(gate)
    sched.schedule()
    await _settle()
    sched.cancel()  # end_call / end of run
    gate.event.set()
    await _settle()
    assert fired == []


async def test_scheduler_generation_guard_even_if_sleep_ignores_cancellation():
    async def stubborn_sleep(secs):
        try:
            await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            pass  # swallows the cancel, as a buggy sleep could

    fired = []

    async def fire():
        fired.append(1)

    sched = NudgeScheduler(fire, delay=3.0, sleep=stubborn_sleep)
    sched.schedule()
    await _settle()
    sched.cancel()
    await asyncio.sleep(0.4)
    assert fired == []


async def test_scheduler_firing_clears_pending_and_can_reschedule():
    gate = _Gate()
    sched, fired = _scheduler(gate)
    sched.schedule()
    gate.event.set()
    await _settle()
    assert fired == [1]
    assert not sched.pending
