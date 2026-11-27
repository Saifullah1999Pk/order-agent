from datetime import datetime
from decimal import Decimal

from order_agent.model.brief import WantedLine
from order_agent.model.rules import OrderSession

NOW = datetime(2026, 11, 23, 19, 30)


def _cart(make_brief) -> OrderSession:
    """2 chicken biryani at 900 and 3 raita at 100, delivery 100: total 2200."""
    brief = make_brief(wanted=[WantedLine(item="chicken biryani", quantity=2, substitutes=["chicken karahi"]), WantedLine(item="raita", quantity=3, optional=True)])
    s = OrderSession(brief, NOW)
    assert s.add_item("chicken biryani", 2, Decimal("900")).ok
    assert s.add_item("raita", 3, Decimal("100")).ok
    assert s.set_fees(Decimal("100"), Decimal("0")).ok
    return s


def _two_biryani(brief) -> OrderSession:
    s = OrderSession(brief, NOW)
    assert s.add_item("chicken biryani", 2, Decimal("900")).ok
    assert s.set_fees(Decimal("150"), Decimal("0")).ok
    return s


def test_quantity_mismatch_is_refused_and_named(make_brief):
    s = _cart(make_brief)
    r = s.confirm_order(Decimal("2200"), 45, restaurant_items=[("chicken biryani", 2), ("raita", 4)])
    assert not r.ok
    assert "raita: restaurant 4, order 3" in r.message
    assert "chicken biryani" not in r.message.split("(")[1].split(")")[0]
    assert "Do not change the order to match" in r.message
    assert s.state == "open"


def test_missing_item_is_refused(make_brief):
    s = _cart(make_brief)
    r = s.confirm_order(Decimal("2200"), 45, restaurant_items=[("chicken biryani", 2)])
    assert not r.ok and "raita: restaurant 0, order 3" in r.message


def test_extra_item_is_refused(make_brief):
    s = _cart(make_brief)
    r = s.confirm_order(Decimal("2200"), 45, restaurant_items=[("chicken biryani", 2), ("raita", 3), ("naan", 2)])
    assert not r.ok and "naan: restaurant 2, order 0" in r.message


def test_duplicates_are_summed(make_brief):
    s = _cart(make_brief)
    ok = s.confirm_order(Decimal("2200"), 45, restaurant_items=[("chicken biryani", 2), ("raita", 1), ("raita", 2)])
    assert ok.ok, ok.message


def test_matching_readback_with_matcher_variant_name_proceeds(make_brief):
    s = _cart(make_brief)
    r = s.confirm_order(Decimal("2200"), 45, restaurant_items=[("Biryani Chicken", 2), ("Raitas", 3)])
    assert r.ok, r.message


def test_readback_check_runs_before_quote_check(make_brief):
    s = _cart(make_brief)
    r = s.confirm_order(Decimal("999"), 45, restaurant_items=[("chicken biryani", 2), ("raita", 4)])
    assert "read-back does not match" in r.message


def test_matching_readback_still_hits_the_quote_check(make_brief):
    s = _cart(make_brief)
    r = s.confirm_order(Decimal("999"), 45, restaurant_items=[("chicken biryani", 2), ("raita", 3)])
    assert not r.ok and "does not match the prices and fees" in r.message


def test_omitted_readback_is_identical_to_today(brief):
    a, b = _two_biryani(brief), _two_biryani(brief)
    ra = a.confirm_order(Decimal("1950"), 45)
    rb = b.confirm_order(Decimal("1950"), 45, restaurant_items=None)
    assert (ra.ok, ra.message) == (rb.ok, rb.message)
    assert a.events[-1].args == b.events[-1].args == {"quoted_total_pkr": Decimal("1950"), "delivery_minutes": 45}
    assert "restaurant_items" not in a.events[-1].args


def test_given_readback_is_recorded_in_event_args(brief):
    s = _two_biryani(brief)
    s.confirm_order(Decimal("1950"), 45, restaurant_items=[("chicken biryani", 3)])
    assert s.events[-1].args["restaurant_items"] == [("chicken biryani", 3)]
    assert not s.events[-1].ok


def _two_lines(make_brief, with_mutton=True) -> OrderSession:
    wanted = [WantedLine(item="chicken biryani", quantity=2, substitutes=["mutton biryani"]), WantedLine(item="raita", quantity=3, optional=True)]
    s = OrderSession(make_brief(wanted=wanted), NOW)
    assert s.add_item("chicken biryani", 1, Decimal("900")).ok
    if with_mutton:
        assert s.add_item("mutton biryani", 1, Decimal("1000")).ok
    return s


def test_subset_name_matches_a_unique_cart_line(make_brief):
    s = _cart(make_brief)
    r = s.confirm_order(Decimal("2200"), 45, restaurant_items=[("biryani", 2), ("raita", 3)])
    assert r.ok, r.message


def test_wrong_quantity_via_subset_name_is_refused(make_brief):
    s = _cart(make_brief)
    r = s.confirm_order(Decimal("2200"), 45, restaurant_items=[("biryani", 3), ("raita", 3)])
    assert not r.ok and "chicken biryani: restaurant 3, order 2" in r.message


def test_reverse_subset_name_matches_a_unique_cart_line(make_brief):
    s = _cart(make_brief)
    r = s.confirm_order(Decimal("2200"), 45, restaurant_items=[("special chicken biryani", 2), ("raita", 3)])
    assert r.ok, r.message


def test_ambiguous_subset_name_is_refused_as_extra(make_brief):
    s = _two_lines(make_brief)
    r = s.confirm_order(Decimal("1900"), 45, restaurant_items=[("biryani", 2)])
    assert not r.ok and "biryani: restaurant 2, order 0" in r.message


def test_extra_naan_still_refused_with_subset_matching(make_brief):
    s = _cart(make_brief)
    r = s.confirm_order(Decimal("2200"), 45, restaurant_items=[("biryani", 2), ("raita", 3), ("naan", 1)])
    assert not r.ok and "naan: restaurant 1, order 0" in r.message


def test_subset_and_exact_names_for_one_line_are_summed(make_brief):
    s = _cart(make_brief)
    r = s.confirm_order(Decimal("2200"), 45, restaurant_items=[("biryani", 1), ("chicken biryani", 1), ("raita", 3)])
    assert r.ok, r.message


def test_readback_refusal_has_an_escape(make_brief):
    s = _cart(make_brief)
    r = s.confirm_order(Decimal("2200"), 45, restaurant_items=[("raita", 3)])
    assert "If they will not correct it, end the call as not_ordered." in r.message
