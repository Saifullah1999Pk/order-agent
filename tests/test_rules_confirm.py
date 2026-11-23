from datetime import datetime
from decimal import Decimal

from order_agent.rules import OrderSession

NOW = datetime(2026, 11, 23, 19, 30)


def _session(brief) -> OrderSession:
    return OrderSession(brief, NOW)


def _two_biryani(brief) -> OrderSession:
    s = _session(brief)
    assert s.add_item("chicken biryani", 2, Decimal("900")).ok
    assert s.set_fees(Decimal("150"), Decimal("0")).ok
    return s


def test_mixed_substitute_completes_line(brief):
    s = _session(brief)
    assert s.add_item("chicken biryani", 1, Decimal("900")).ok
    assert s.add_item("chicken karahi", 1, Decimal("1400")).ok
    assert s.missing_lines() == []


def test_missing_required_line_blocks_confirm(brief):
    s = _session(brief)
    s.add_item("chicken biryani", 1, Decimal("900"))
    assert s.missing_lines() == ["chicken biryani: need 2, have 1"]
    result = s.confirm_order(Decimal("900"), 45)
    assert not result.ok
    assert "need 2, have 1" in result.message
    assert s.state == "open"


def test_optional_line_may_be_missing(brief):
    s = _two_biryani(brief)
    result = s.confirm_order(Decimal("1950"), 45)
    assert result.ok, result.message
    assert s.state == "confirmed"
    assert s.delivery_eta == datetime(2026, 11, 23, 20, 15)
    assert s.quoted_total_pkr == Decimal("1950")


def test_confirm_rejects_mismatched_total(brief):
    s = _two_biryani(brief)
    result = s.confirm_order(Decimal("1800"), 45)
    assert not result.ok
    assert "1950" in result.message
    assert s.state == "open"
    assert s.delivery_eta is None and s.quoted_total_pkr is None


def test_confirm_rejects_late_delivery(brief):
    s = _two_biryani(brief)
    result = s.confirm_order(Decimal("1950"), 120)
    assert not result.ok
    assert "21:00" in result.message
    assert s.state == "open"


def test_confirm_uses_now_when_no_call_time(make_brief):
    s = OrderSession(make_brief(call_time=None), NOW)
    s.add_item("chicken biryani", 2, Decimal("900"))
    assert s.confirm_order(Decimal("1800"), 30).ok
    assert s.delivery_eta == datetime(2026, 11, 23, 20, 0)


def test_minimum_order_blocks_confirm(brief):
    s = _two_biryani(brief)
    assert s.set_minimum_order(Decimal("2200")).ok
    result = s.confirm_order(Decimal("1950"), 45)
    assert not result.ok
    assert "2200" in result.message
    assert "raita" in result.message


def test_minimum_allows_extra_quantity(brief):
    s = _two_biryani(brief)
    s.set_minimum_order(Decimal("2200"))
    assert s.add_item("raita", 3, Decimal("150")).ok
    assert s.cart_total() == Decimal("2400")
    assert s.confirm_order(Decimal("2400"), 45).ok


def test_minimum_unreachable_within_budget(brief):
    s = _two_biryani(brief)
    s.set_minimum_order(Decimal("3000"))
    result = s.add_item("chicken biryani", 1, Decimal("900"))
    assert not result.ok
    assert "budget" in result.message
    assert "not_ordered" in result.message


def test_extra_quantity_refused_once_minimum_met(brief):
    s = _two_biryani(brief)
    s.set_minimum_order(Decimal("1800"))
    result = s.add_item("raita", 2, Decimal("150"))
    assert not result.ok


def test_set_minimum_rejects_nonpositive(brief):
    s = _session(brief)
    assert not s.set_minimum_order(Decimal("0")).ok
    assert s.minimum_order_pkr is None


def test_no_changes_after_confirm(brief):
    s = _two_biryani(brief)
    assert s.confirm_order(Decimal("1950"), 45).ok
    result = s.add_item("raita", 1, Decimal("150"))
    assert not result.ok
    assert "already confirmed" in result.message


def test_end_ordered_requires_confirm(brief):
    s = _session(brief)
    assert not s.end("ordered", "x").ok
    assert s.state == "open"
    assert s.end("not_ordered", "sold out").ok
    assert s.state == "ended"


def test_end_ordered_after_confirm(brief):
    s = _two_biryani(brief)
    s.confirm_order(Decimal("1950"), 45)
    assert s.end("ordered", "done").ok
    assert s.state == "ended"


def test_end_twice_refused(brief):
    s = _session(brief)
    assert s.end("not_ordered", "sold out").ok
    assert not s.end("not_ordered", "again").ok
