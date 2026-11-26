from datetime import datetime
from decimal import Decimal

from order_agent.model.rules import OrderSession

NOW = datetime(2026, 11, 23, 19, 30)


def _s(brief) -> OrderSession:
    return OrderSession(brief, NOW)


def _terse(brief) -> OrderSession:
    s = _s(brief)
    assert s.add_item("chicken biryani", 2, None).ok
    assert s.add_item("raita", 1, None).ok
    return s


def test_unpriced_add_is_allowed_and_recorded(brief):
    s = _s(brief)
    r = s.add_item("chicken biryani", 2, None)
    assert r.ok, r.message
    assert s.items[0].unit_price_pkr is None
    assert "price" in r.message.lower()


def test_unpriced_add_still_refuses_off_brief_and_forbidden(brief):
    s = _s(brief)
    assert not s.add_item("mutton karahi", 1, None).ok
    assert not s.add_item("fish biryani", 1, None).ok
    assert s.items == []


def test_unpriced_add_still_refuses_overfill(brief):
    s = _s(brief)
    assert not s.add_item("chicken biryani", 3, None).ok


def test_bad_price_still_refused(brief):
    assert not _s(brief).add_item("chicken biryani", 2, Decimal("0")).ok


def test_set_price_fills_missing_price(brief):
    s = _s(brief)
    s.add_item("chicken biryani", 2, None)
    r = s.set_price("chicken biryani", Decimal("900"))
    assert r.ok, r.message
    assert s.items[0].unit_price_pkr == Decimal("900")


def test_set_price_refused_for_item_not_in_cart(brief):
    r = _s(brief).set_price("raita", Decimal("150"))
    assert not r.ok and "not in the cart" in r.message


def test_set_price_respects_price_lock(brief):
    s = _s(brief)
    s.add_item("chicken biryani", 2, Decimal("900"))
    r = s.set_price("chicken biryani", Decimal("975"))
    assert not r.ok and "900" in r.message
    assert s.items[0].unit_price_pkr == Decimal("900")
    assert s.set_price("chicken biryani", Decimal("975"), price_corrected=True).ok
    assert s.items[0].unit_price_pkr == Decimal("975")


def test_set_price_same_price_is_fine_and_bad_price_refused(brief):
    s = _s(brief)
    s.add_item("chicken biryani", 2, Decimal("900"))
    assert s.set_price("chicken biryani", Decimal("900")).ok
    assert not s.set_price("chicken biryani", Decimal("-1")).ok


def test_set_price_over_budget_refused(brief):
    s = _s(brief)
    s.add_item("chicken biryani", 2, None)
    assert not s.set_price("chicken biryani", Decimal("1500")).ok
    assert s.items[0].unit_price_pkr is None


def test_priced_add_over_budget_still_refused_with_other_items_unpriced(brief):
    s = _s(brief)
    s.add_item("chicken biryani", 2, None)
    assert not s.add_item("raita", 1, Decimal("3000")).ok


def test_confirm_unpriced_within_budget(brief):
    s = _terse(brief)
    r = s.confirm_order(Decimal("2100"), 45)
    assert r.ok, r.message
    assert s.state == "confirmed"
    assert s.quoted_total_pkr == Decimal("2100")
    assert s.confirmed_at_total_only is True
    assert s.cart_total_known() is False


def test_confirm_unpriced_over_budget_refused(brief):
    s = _terse(brief)
    r = s.confirm_order(Decimal("2600"), 45)
    assert not r.ok and "2500" in r.message
    assert s.state == "open"


def test_confirm_unpriced_late_refused(brief):
    r = _terse(brief).confirm_order(Decimal("2100"), 120)
    assert not r.ok and "21:00" in r.message


def test_confirm_unpriced_incomplete_refused(brief):
    s = _s(brief)
    s.add_item("chicken biryani", 1, None)
    r = s.confirm_order(Decimal("1000"), 45)
    assert not r.ok and "need 2, have 1" in r.message


def test_confirm_unpriced_with_minimum_asks_for_prices(brief):
    s = _terse(brief)
    assert s.set_minimum_order(Decimal("1500")).ok
    r = s.confirm_order(Decimal("2100"), 45)
    assert not r.ok
    assert "ask the restaurant for each item's price to check the minimum order" in r.message.lower()
    assert s.state == "open"


def test_minimum_then_prices_then_confirm(brief):
    s = _terse(brief)
    s.set_minimum_order(Decimal("1500"))
    s.set_price("chicken biryani", Decimal("900"))
    s.set_price("raita", Decimal("150"))
    assert s.confirm_order(Decimal("2100"), 45).ok  # fees never set: unknown, quote within budget


def test_fees_never_set_with_priced_cart_uses_quote_path(brief):
    s = _s(brief)
    s.add_item("chicken biryani", 2, Decimal("900"))
    assert s.cart_total_known() is False
    assert s.confirm_order(Decimal("1950"), 45).ok
    assert s.confirmed_at_total_only is True


def test_priced_cart_with_fees_unchanged(brief):
    s = _s(brief)
    s.add_item("chicken biryani", 2, Decimal("900"))
    s.set_fees(Decimal("150"), Decimal("0"))
    assert s.cart_total_known() is True
    r = s.confirm_order(Decimal("2100"), 45)
    assert not r.ok and "1950" not in r.message and "does not match" in r.message
    assert s.confirm_order(Decimal("1950"), 45).ok
    assert s.confirmed_at_total_only is False


def test_unpriced_cart_with_fees_set_is_still_unknown(brief):
    s = _terse(brief)
    s.set_fees(Decimal("0"), Decimal("0"))
    assert s.cart_total_known() is False
    assert s.confirm_order(Decimal("2100"), 45).ok


def test_add_price_to_existing_unpriced_item_via_add_item(brief):
    s = _s(brief)
    s.add_item("chicken biryani", 1, None)
    assert s.add_item("chicken biryani", 1, Decimal("900")).ok
    assert s.items[0].unit_price_pkr == Decimal("900") and s.items[0].quantity == 2


def test_adding_unpriced_to_priced_item_keeps_price(brief):
    s = _s(brief)
    s.add_item("chicken biryani", 1, Decimal("900"))
    assert s.add_item("chicken biryani", 1, None).ok
    assert s.items[0].unit_price_pkr == Decimal("900") and s.items[0].quantity == 2


def test_total_only_quote_below_known_partial_sum_refused(brief):
    s = _s(brief)
    s.add_item("chicken biryani", 2, Decimal("1000"))
    s.add_item("raita", 1, None)
    r = s.confirm_order(Decimal("1000"), 45)
    assert not r.ok
    assert "less than the prices already recorded." in r.message and "2000" not in r.message
    assert "Rs 1000" in r.message
    assert s.state == "open"


def test_total_only_quote_at_or_above_partial_sum_ok(brief):
    s = _s(brief)
    s.add_item("chicken biryani", 2, Decimal("1000"))
    s.add_item("raita", 1, None)
    assert s.confirm_order(Decimal("2150"), 45).ok


def test_total_only_quote_below_partial_sum_includes_set_fees(brief):
    s = _s(brief)
    s.add_item("chicken biryani", 2, Decimal("900"))
    s.add_item("raita", 1, None)
    s.set_fees(Decimal("150"), Decimal("0"))
    assert not s.confirm_order(Decimal("1900"), 45).ok
    assert s.confirm_order(Decimal("1950"), 45).ok


def test_session_exposes_fees_set(brief):
    s = _s(brief)
    assert s.fees_set is False
    s.set_fees(Decimal("0"), Decimal("0"))
    assert s.fees_set is True
