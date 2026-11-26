import json
from datetime import datetime
from decimal import Decimal

from order_agent.model.report import CallReport, TranscriptLine, build_report, summarise, write_report
from order_agent.model.rules import OrderSession

NOW = datetime(2026, 11, 23, 19, 30)
END = datetime(2026, 11, 23, 19, 36)
TRANSCRIPT = [
    TranscriptLine(role="restaurant", text="Hello, how can I help?", at=NOW),
    TranscriptLine(role="agent", text="Two chicken biryani please.", at=NOW),
]


def _confirmed(brief) -> OrderSession:
    s = OrderSession(brief, NOW)
    assert s.add_item("chicken biryani", 2, Decimal("900")).ok
    assert s.set_fees(Decimal("150"), Decimal("0")).ok
    assert s.confirm_order(Decimal("1950"), 45).ok
    assert s.end("ordered", "all good").ok
    return s


def _report(brief):
    return build_report(_confirmed(brief), "ordered", "all good", TRANSCRIPT, NOW, END)


def test_build_report_ordered(brief):
    r = _report(brief)
    assert r.outcome == "ordered"
    assert r.cart_total_pkr == Decimal("1950")
    assert r.quoted_total_pkr == Decimal("1950")
    assert r.delivery_eta == datetime(2026, 11, 23, 20, 15)


def test_summary_mentions_outcome_items_total(brief):
    text = summarise(_report(brief))
    assert "ordered" in text
    assert "chicken biryani" in text
    assert "1950" in text


def test_summary_not_ordered_gives_reason(brief):
    reason = "biryani sold out, no allowed substitute"
    s = OrderSession(brief, NOW)
    s.end("not_ordered", reason)
    r = build_report(s, "not_ordered", reason, [], NOW, END)
    assert reason in summarise(r)


def test_write_report_roundtrip(brief, tmp_path):
    r = _report(brief)
    path = write_report(r, tmp_path)
    assert path.name == "20261123-193000.json"
    json.loads(path.read_text(encoding="utf-8"))
    assert CallReport.model_validate_json(path.read_text(encoding="utf-8")) == r
    assert path.with_suffix(".txt").exists()


def test_report_keeps_refused_tool_events(brief):
    s = OrderSession(brief, NOW)
    assert not s.add_item("beef nihari", 1, Decimal("700")).ok
    r = build_report(s, "not_ordered", "x", [], NOW, END)
    assert any(e["tool"] == "add_item" and e["ok"] is False for e in r.tool_events)
    CallReport.model_validate_json(r.model_dump_json())


def test_summary_call_dropped_before_any_order(brief):
    s = OrderSession(brief, NOW)
    r = build_report(s, "call_dropped", "line went dead", [], NOW, END)
    assert "no order was confirmed" in summarise(r)


def test_summary_call_dropped_after_order_confirmed(brief):
    s = _confirmed(brief)
    r = build_report(s, "call_dropped", "line went dead", TRANSCRIPT, NOW, END)
    text = summarise(r)
    assert "no order was confirmed" not in text
    assert "dropped after the order was confirmed at Rs 1950" in text
    assert "20:15" in text


def _terse_report(brief):
    s = OrderSession(brief, NOW)
    assert s.add_item("chicken biryani", 2, None).ok
    assert s.add_item("raita", 1, None).ok
    assert s.confirm_order(Decimal("2100"), 45).ok
    assert s.end("ordered", "ok").ok
    return build_report(s, "ordered", "ok", TRANSCRIPT, NOW, END)


def test_unpriced_report_has_none_prices_and_unknown_cart_total(brief):
    r = _terse_report(brief)
    assert all(i["unit_price_pkr"] is None for i in r.items)
    assert r.cart_total_pkr is None
    assert r.quoted_total_pkr == Decimal("2100")
    assert r.total_only is True


def test_unpriced_report_summary_says_prices_not_itemised(brief):
    text = summarise(_terse_report(brief))
    assert "prices not itemised by the restaurant; confirmed at their total Rs 2100" in text
    assert "None" not in text
    assert "chicken biryani" in text


def test_unpriced_report_roundtrip(brief, tmp_path):
    r = _terse_report(brief)
    path = write_report(r, tmp_path)
    assert CallReport.model_validate_json(path.read_text(encoding="utf-8")) == r
    assert "None" not in path.with_suffix(".txt").read_text(encoding="utf-8")


def test_fully_priced_report_is_unchanged(brief):
    r = _report(brief)
    assert r.total_only is False and r.fees_set is True
