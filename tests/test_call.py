import asyncio
import json
from datetime import datetime
from decimal import Decimal

from order_agent.call import CallState
from order_agent.config import Settings

NOW = datetime(2026, 11, 23, 19, 30)


def _state(brief, tmp_path) -> CallState:
    settings = Settings(google_api_key="test-key", reports_dir=tmp_path)
    return CallState(brief, settings, NOW)


def _json_files(tmp_path):
    return list(tmp_path.glob("*.json"))


async def test_finish_writes_once(brief, tmp_path):
    state = _state(brief, tmp_path)
    first = await state.finish("not_ordered", "x")
    second = await state.finish("not_ordered", "y")
    assert first == second == state.report_path
    assert len(_json_files(tmp_path)) == 1


async def test_finish_is_safe_when_called_concurrently(brief, tmp_path):
    state = _state(brief, tmp_path)
    paths = await asyncio.gather(
        state.finish("not_ordered", "a"), state.on_disconnect(), state.finish("not_ordered", "b")
    )
    assert len(set(paths)) == 1
    assert len(_json_files(tmp_path)) == 1


async def test_disconnect_writes_dropped_report(brief, tmp_path):
    state = _state(brief, tmp_path)
    path = await state.on_disconnect()
    assert json.loads(path.read_text(encoding="utf-8"))["outcome"] == "call_dropped"


async def test_disconnect_after_finish_keeps_outcome(brief, tmp_path):
    state = _state(brief, tmp_path)
    await state.finish("not_ordered", "x")
    path = await state.on_disconnect()
    assert json.loads(path.read_text(encoding="utf-8"))["outcome"] == "not_ordered"
    assert len(_json_files(tmp_path)) == 1


async def test_drop_after_confirm_mentions_confirmed_order_and_total(brief, tmp_path):
    state = _state(brief, tmp_path)
    assert state.session.add_item("chicken biryani", 2, Decimal("900")).ok
    assert state.session.set_fees(Decimal("150"), Decimal("0")).ok
    assert state.session.confirm_order(Decimal("1950"), 45).ok
    path = await state.on_disconnect()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["outcome"] == "call_dropped"
    assert data["reason"] == "call ended without end_call after the order was confirmed (total Rs 1950)"


async def test_drop_before_confirm_uses_plain_reason(brief, tmp_path):
    state = _state(brief, tmp_path)
    path = await state.on_disconnect()
    assert json.loads(path.read_text(encoding="utf-8"))["reason"] == "call ended without end_call"


async def test_add_line_lands_in_report(brief, tmp_path):
    state = _state(brief, tmp_path)
    state.add_line("restaurant", "Hello")
    state.add_line("agent", "Hi, I'd like to order.")
    data = json.loads((await state.finish("not_ordered", "x")).read_text(encoding="utf-8"))
    assert [t["role"] for t in data["transcript"]] == ["restaurant", "agent"]


from order_agent.call import MAX_NUDGES, should_nudge


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


from order_agent.call import NudgeTracker


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
    from order_agent.call import llm_http_options

    opts = llm_http_options()
    retry = opts["retry_options"]
    assert retry["attempts"] == 3
    assert retry["initial_delay"] == 2.0
    assert 429 in retry["http_status_codes"] and 503 in retry["http_status_codes"]


import asyncio

from order_agent.call import NudgeScheduler


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
