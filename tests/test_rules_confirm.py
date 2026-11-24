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


def test_lowered_minimum_does_not_excuse_overfill(brief):
    s = _two_biryani(brief)
    s.set_minimum_order(Decimal("3000"))
    assert s.add_item("raita", 3, Decimal("150")).ok
    s.set_minimum_order(Decimal("1000"))
    result = s.confirm_order(Decimal("2400"), 45)
    assert not result.ok
    assert "raita" in result.message and "remove_item" in result.message
    s.remove_item("raita")
    assert s.add_item("raita", 1, Decimal("150")).ok
    assert s.confirm_order(Decimal("2100"), 45).ok


def test_extra_quantity_capped_at_shortfall(brief):
    s = _two_biryani(brief)
    s.set_minimum_order(Decimal("2200"))
    result = s.add_item("raita", 5, Decimal("150"))
    assert not result.ok
    assert "at most 3 extra" in result.message
    assert s.add_item("raita", 3, Decimal("150")).ok


# -- minimum_reachable: the engine must tell the bot exactly what to add ----


def _minimum_reachable(brief) -> OrderSession:
    """Order of the failed Gemini runs: 2 biryani + 1 raita, fees, then Rs 2200 minimum."""
    s = _session(brief)
    assert s.add_item("chicken biryani", 2, Decimal("900")).ok
    assert s.add_item("raita", 1, Decimal("150")).ok
    assert s.set_fees(Decimal("150"), Decimal("0")).ok
    return s


def test_set_minimum_states_exact_shortfall_and_quantity(brief):
    s = _minimum_reachable(brief)
    result = s.set_minimum_order(Decimal("2200"))
    assert result.ok
    assert "food is 1950 PKR" in result.message
    assert "250 PKR short" in result.message
    assert "add 2 more raita (300 PKR)" in result.message
    assert "2400 PKR" in result.message and "within your 2500 PKR budget" in result.message


def test_add_item_while_still_short_repeats_remaining_quantity(brief):
    s = _minimum_reachable(brief)
    s.set_minimum_order(Decimal("2200"))
    result = s.add_item("raita", 1, Decimal("150"))  # the bot's mistake: only one
    assert result.ok
    assert "100 PKR short" in result.message
    assert "add 1 more raita (150 PKR)" in result.message


def test_engine_path_reaches_correct_cart(brief):
    s = _minimum_reachable(brief)
    s.set_minimum_order(Decimal("2200"))
    assert s.add_item("raita", 2, Decimal("150")).ok  # exactly what the message said
    assert s.cart_total() == Decimal("2400")
    assert s.confirm_order(Decimal("2400"), 45).ok


def test_met_minimum_message_has_no_shortfall_hint(brief):
    s = _two_biryani(brief)
    assert "short" not in s.set_minimum_order(Decimal("1800")).message


def test_minimum_refusal_names_quantity(brief):
    s = _minimum_reachable(brief)
    s.set_minimum_order(Decimal("2200"))
    s.add_item("raita", 1, Decimal("150"))
    result = s.confirm_order(Decimal("2250"), 45)
    assert not result.ok
    assert "add 1 more raita (150 PKR)" in result.message


def test_shortfall_hint_says_when_nothing_fits_budget(make_brief):
    s = _session(make_brief(budget_pkr=Decimal("2000")))
    s.add_item("chicken biryani", 2, Decimal("900"))
    s.set_fees(Decimal("150"), Decimal("0"))
    result = s.set_minimum_order(Decimal("2200"))
    assert "no addition fits" in result.message
    assert "not_ordered" in result.message
