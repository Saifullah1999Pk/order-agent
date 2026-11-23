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


async def test_on_end_pushes_end_even_if_report_write_fails(brief, tmp_path, monkeypatch):
    from order_agent import call

    state = _state(brief, tmp_path)
    pushed = []

    async def push_end():
        pushed.append(True)

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(call, "write_report", boom)
    await call.make_on_end(state, push_end)("not_ordered", "x")
    assert pushed == [True]
    assert state.report_path is None  # retried later by on_disconnect


async def test_on_end_writes_report_then_pushes_end(brief, tmp_path):
    from order_agent import call

    state = _state(brief, tmp_path)
    pushed = []

    async def push_end():
        pushed.append(state.report_path)

    await call.make_on_end(state, push_end)("not_ordered", "x")
    assert pushed == [state.report_path] and state.report_path is not None


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
