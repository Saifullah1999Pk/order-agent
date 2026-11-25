"""T028: root bot.py is an entry shim over order_agent.heads.voice.pipeline."""

import ast
import inspect
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_bot_exposes_the_pipecat_entry_points():
    import bot
    from order_agent.heads.voice import pipeline

    assert inspect.iscoroutinefunction(bot.bot)
    assert bot.run_bot is pipeline.run_bot
    assert set(bot.transport_params) == {"webrtc", "eval"}
    assert not hasattr(bot, "OPENING_WAIT_SECS")  # the controller owns the opening wait


def test_pipeline_does_not_touch_nudge_or_call_state_internals():
    import order_agent.heads.voice.pipeline as pipeline

    tree = ast.parse(Path(pipeline.__file__).read_text(encoding="utf-8"))
    banned = {"NudgeTracker", "NudgeScheduler", "CallState", "add_message"}
    seen = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            seen.add(node.id)
        elif isinstance(node, ast.Attribute):
            seen.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            seen.update(a.name.split(".")[-1] for a in node.names)
    assert seen & banned == set()


def test_load_call_inputs_reads_the_environment(monkeypatch, tmp_path):
    from order_agent.heads.voice.pipeline import load_call_inputs

    brief_file = tmp_path / "brief.yaml"
    shutil.copy(ROOT / "briefs" / "example.yaml", brief_file)
    monkeypatch.setattr("order_agent.config.load_dotenv", lambda *a, **k: None)  # ignore the real .env
    monkeypatch.setenv("ORDER_BRIEF", str(brief_file))
    monkeypatch.setenv("ORDER_CALL_TIME", "2026-12-01T12:15:00")
    monkeypatch.setenv("ORDER_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("ORDER_AGENT_LLM_PROVIDER", "groq")
    settings, brief = load_call_inputs()
    assert settings.llm_provider == "groq"
    assert settings.reports_dir == tmp_path / "reports"
    assert brief.customer_name == "Ali Raza"
    assert brief.call_time.isoformat() == "2026-12-01T12:15:00"


def test_load_call_inputs_keeps_the_brief_call_time_when_no_override(monkeypatch, tmp_path):
    from order_agent.heads.voice.pipeline import load_call_inputs

    monkeypatch.setattr("order_agent.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("ORDER_BRIEF", str(ROOT / "briefs" / "example.yaml"))
    monkeypatch.delenv("ORDER_CALL_TIME", raising=False)
    _, brief = load_call_inputs()
    assert brief.call_time.isoformat() == "2026-11-23T19:30:00"
