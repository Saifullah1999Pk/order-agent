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
