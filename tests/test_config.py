from datetime import datetime

from order_agent.config import load_settings, pick_model


def _clean(monkeypatch):
    for name in ("ORDER_AGENT_MODEL", "ORDER_AGENT_FALLBACK_MODEL", "ORDER_REPORTS_DIR",
                 "ORDER_BRIEF", "ORDER_CALL_TIME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")


def test_load_settings_defaults(monkeypatch):
    _clean(monkeypatch)
    s = load_settings()
    assert s.model == "gemini-3.5-flash-lite"
    assert s.fallback_model == "gemini-2.5-flash"


def test_load_settings_call_time(monkeypatch):
    _clean(monkeypatch)
    monkeypatch.setenv("ORDER_CALL_TIME", "2026-11-23T19:30:00")
    assert load_settings().call_time == datetime(2026, 11, 23, 19, 30)


async def test_pick_model_uses_fallback_when_probe_fails(monkeypatch):
    _clean(monkeypatch)

    async def probe(model):
        return False

    assert await pick_model(load_settings(), probe) == "gemini-2.5-flash"


async def test_pick_model_primary_ok(monkeypatch):
    _clean(monkeypatch)

    async def probe(model):
        return True

    assert await pick_model(load_settings(), probe) == "gemini-3.5-flash-lite"
