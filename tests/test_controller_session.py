import asyncio
import inspect
import json
from datetime import datetime
from decimal import Decimal

import pytest

from order_agent.controller.nudge import MAX_NUDGES, NUDGE_DELAY_SECS, NUDGE_TEXT
from order_agent.controller.prompt import build_system_prompt
from order_agent.controller.session import CallController, NudgeDecision, ToolOutcome
from order_agent.controller.toolspecs import TOOL_SPECS
from order_agent.controller.tools import ToolOutcome as ToolsToolOutcome
from order_agent.model.report import TranscriptLine
from order_agent.model.rules import OrderSession

NOW = datetime(2026, 11, 23, 19, 30)
OPENING = "Nobody has spoken yet. Open the call: greet, say you'd like to place a delivery order."


def _controller(brief, tmp_path, **kwargs) -> CallController:
    return CallController(brief, reports_dir=tmp_path, now=NOW, **kwargs)


def test_core_attributes(brief, tmp_path):
    c = _controller(brief, tmp_path)
    assert isinstance(c.session, OrderSession)
    assert c.transcript == []
    assert c.instructions == build_system_prompt(brief)
    assert c.opening_text == OPENING
    assert c.tool_specs() == TOOL_SPECS
    assert c.report is None and c.report_path is None


def test_no_settings_parameter():
    assert "settings" not in inspect.signature(CallController.__init__).parameters


def test_session_is_built_with_now(brief, tmp_path):
    c = _controller(brief, tmp_path)
    assert c.started_at == NOW
    assert c.session.state == OrderSession(brief, NOW).state


def test_add_line_appends_transcript_line(brief, tmp_path):
    c = _controller(brief, tmp_path)
    c.add_line("agent", "hi")
    assert len(c.transcript) == 1
    line = c.transcript[0]
    assert isinstance(line, TranscriptLine) and (line.role, line.text) == ("agent", "hi")


def test_nudge_decision_defaults():
    d = NudgeDecision(nudge=True)
    assert d.delay_secs == NUDGE_DELAY_SECS and d.text == NUDGE_TEXT


def test_tool_outcome_is_reexported():
    assert ToolOutcome is ToolsToolOutcome


class FakeHooks:
    def __init__(self, log=None):
        self.log = log if log is not None else []

    async def inject(self, text):
        self.log.append(("inject", text))

    async def hangup(self):
        self.log.append(("hangup",))


async def _no_sleep(_secs):
    return None


def _end_args(outcome="not_ordered", reason="done"):
    return {"outcome": outcome, "reason": reason}


async def test_attach_hooks_twice_raises(brief, tmp_path):
    c = _controller(brief, tmp_path)
    c.attach_hooks(FakeHooks())
    with pytest.raises(RuntimeError):
        c.attach_hooks(FakeHooks())


def test_attach_hooks_stores_hooks(brief, tmp_path):
    c = _controller(brief, tmp_path)
    fake = FakeHooks()
    c.attach_hooks(fake)
    assert c._hooks is fake


def test_attach_hooks_when_constructed_with_hooks_raises(brief, tmp_path):
    c = _controller(brief, tmp_path, hooks=FakeHooks())
    with pytest.raises(RuntimeError):
        c.attach_hooks(FakeHooks())


def _json_files(tmp_path):
    return list(tmp_path.glob("*.json"))


async def test_finish_writes_once(brief, tmp_path):
    c = _controller(brief, tmp_path)
    assert c.report is None and not c.finished
    first = await c.finish("not_ordered", "x")
    second = await c.finish("not_ordered", "y")
    assert first == second == c.report_path
    assert len(_json_files(tmp_path)) == 1
    assert c.report is not None and c.report.reason == "x" and c.finished


async def test_finish_is_safe_when_called_concurrently(brief, tmp_path):
    c = _controller(brief, tmp_path)
    paths = await asyncio.gather(c.finish("not_ordered", "a"), c.drop(), c.finish("not_ordered", "b"))
    assert len(set(paths)) == 1
    assert len(_json_files(tmp_path)) == 1


async def test_drop_writes_dropped_report(brief, tmp_path):
    c = _controller(brief, tmp_path)
    data = json.loads((await c.drop()).read_text(encoding="utf-8"))
    assert data["outcome"] == "call_dropped"
    assert data["reason"] == "call ended without end_call"


async def test_drop_after_finish_keeps_outcome(brief, tmp_path):
    c = _controller(brief, tmp_path)
    await c.finish("not_ordered", "x")
    data = json.loads((await c.drop()).read_text(encoding="utf-8"))
    assert data["outcome"] == "not_ordered"
    assert len(_json_files(tmp_path)) == 1


async def test_drop_after_confirm_mentions_confirmed_order_and_total(brief, tmp_path):
    c = _controller(brief, tmp_path)
    assert c.session.add_item("chicken biryani", 2, Decimal("900")).ok
    assert c.session.set_fees(Decimal("150"), Decimal("0")).ok
    assert c.session.confirm_order(Decimal("1950"), 45).ok
    data = json.loads((await c.drop()).read_text(encoding="utf-8"))
    assert data["reason"] == "call ended without end_call after the order was confirmed (total Rs 1950)"


async def test_add_line_lands_in_report(brief, tmp_path):
    c = _controller(brief, tmp_path)
    c.add_line("restaurant", "Hello")
    c.add_line("agent", "Hi, I'd like to order.")
    data = json.loads((await c.finish("not_ordered", "x")).read_text(encoding="utf-8"))
    assert [t["role"] for t in data["transcript"]] == ["restaurant", "agent"]


async def test_failed_write_leaves_no_report_so_a_later_call_retries(brief, tmp_path, monkeypatch):
    from order_agent.controller import session as session_module

    c = _controller(brief, tmp_path)
    real = session_module.write_report
    monkeypatch.setattr(session_module, "write_report", lambda *a, **k: (_ for _ in ()).throw(OSError("full")))
    with pytest.raises(OSError):
        await c.finish("not_ordered", "x")
    assert c.report is None and c.report_path is None and not c.finished
    monkeypatch.setattr(session_module, "write_report", real)
    assert (await c.drop()).exists()


def _spy(c, log):
    real = c.finish

    async def finish(outcome, reason):
        log.append("finish")
        return await real(outcome, reason)

    c.finish = finish


class OrderedHooks(FakeHooks):
    """Records hangup together with whether the report file existed at that moment."""

    def __init__(self, log, reports_dir):
        super().__init__(log)
        self._dir = reports_dir

    async def hangup(self):
        self.log.append("hangup")
        self.log.append(("report_exists_at_hangup", bool(list(self._dir.glob("*.json")))))


async def test_perform_dispatches_without_touching_hooks(brief, tmp_path):
    log = []
    c = _controller(brief, tmp_path, hooks=FakeHooks(log))
    out = await c.perform("add_item", {"name": "chicken biryani", "quantity": 2, "unit_price_pkr": 900})
    assert out.ok and out.run_llm and not out.ended
    assert log == []
    assert "Refused" in (await c.perform("nope", {})).message


async def test_successful_end_call_replies_then_finishes_then_hangs_up(brief, tmp_path):
    log = []
    c = _controller(brief, tmp_path, hooks=OrderedHooks(log, tmp_path))
    _spy(c, log)

    async def reply(outcome):
        log.append("reply")
        assert outcome.ok and not outcome.run_llm and outcome.ended

    out = await c.perform("end_call", _end_args(), reply=reply)
    assert out.ok and out.ended and not out.run_llm
    assert log == ["reply", "finish", "hangup", ("report_exists_at_hangup", True)]
    assert c.report is not None


async def test_reply_failure_does_not_skip_end_of_call_work(brief, tmp_path):
    log = []
    c = _controller(brief, tmp_path, hooks=OrderedHooks(log, tmp_path))
    _spy(c, log)

    async def reply(outcome):
        raise RuntimeError("socket closed")

    out = await c.perform("end_call", _end_args(), reply=reply)
    assert out.ok
    assert log[:2] == ["finish", "hangup"]


async def test_finish_failure_still_hangs_up_and_does_not_escape(brief, tmp_path):
    log = []
    blocked = tmp_path / "not_a_dir"
    blocked.write_text("x")
    c = CallController(brief, reports_dir=blocked, now=NOW, hooks=FakeHooks(log))
    out = await c.perform("end_call", _end_args())
    assert out.ok and out.ended
    assert log == [("hangup",)]
    assert c.report_path is None


async def test_refused_end_call_does_not_finish_or_hang_up(brief, tmp_path):
    log = []
    c = _controller(brief, tmp_path, hooks=FakeHooks(log))
    # confirmed-order rule: ending as "ordered" before confirming is refused
    out = await c.perform("end_call", _end_args("ordered", "bought"))
    assert not out.ok and out.run_llm and not out.ended
    assert log == [] and not c.finished


async def test_end_call_with_hooks_none_writes_report(brief, tmp_path):
    c = _controller(brief, tmp_path)
    out = await c.perform("end_call", _end_args())
    assert out.ok and out.ended
    assert c.finished and len(_json_files(tmp_path)) == 1


async def test_end_call_after_late_attach_hangs_up_through_new_hooks(brief, tmp_path):
    c = _controller(brief, tmp_path)
    log = []
    c.attach_hooks(FakeHooks(log))
    await c.perform("end_call", _end_args())
    assert log == [("hangup",)]
