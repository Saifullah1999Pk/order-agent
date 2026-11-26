from datetime import datetime
from decimal import Decimal

from order_agent.model.rules import OrderSession

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
    assert "does not match" in result.message
    assert s.state == "open"
    assert s.delivery_eta is None and s.quoted_total_pkr is None


def test_mismatch_refusal_reveals_no_computed_figures(brief):
    s = _two_biryani(brief)  # items 1800, delivery 150, tax 0, cart total 1950
    result = s.confirm_order(Decimal("1800"), 45)
    assert not result.ok
    for figure in ("1950", "1800", "150", "items "):
        assert figure not in result.message
    assert "Do not tell the restaurant a total of your own" in result.message
    assert "itemise" in result.message
    assert "Do not edit the cart or the fees" in result.message
    assert "not_ordered" in result.message


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
    assert "2400 PKR" not in result.message and "within your" not in result.message  # FR-008: no projected total


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
    from order_agent.model.brief import WantedLine

    wanted = [WantedLine(item="chicken biryani", quantity=2, substitutes=[])]
    s = _session(make_brief(budget_pkr=Decimal("2000"), wanted=wanted))
    s.add_item("chicken biryani", 2, Decimal("900"))
    s.set_fees(Decimal("150"), Decimal("0"))
    result = s.set_minimum_order(Decimal("2200"))
    assert "no addition fits" in result.message
    assert "not_ordered" in result.message


def test_hint_does_not_say_give_up_when_optional_item_not_yet_in_cart(brief):
    """Live run 151509 attempt 2: raita not added yet, the hint wrongly said to end as not_ordered."""
    s = _session(brief)
    s.add_item("chicken biryani", 2, Decimal("900"))
    result = s.set_minimum_order(Decimal("2200"))
    assert "end the call as not_ordered" in result.message.split("If its price doesn't fit")[-1]  # only as a conditional fallback
    assert "raita" in result.message
    assert "400 PKR short" in result.message
    assert "ask" in result.message.lower()
    # and the cart can still reach the minimum
    s.add_item("raita", 3, Decimal("150"))
    assert s.set_fees(Decimal("150"), Decimal("0")).ok
    assert s.confirm_order(Decimal("2400"), 45).ok


# -- review fixes: hint only when required lines are filled ------------------


def test_hint_mid_order_does_not_push_required_line(brief):
    s = _session(brief)
    s.set_minimum_order(Decimal("2200"))
    result = s.add_item("chicken biryani", 1, Decimal("900"))
    assert result.ok
    assert "2200 PKR minimum still applies" in result.message
    assert "more chicken biryani" not in result.message
    assert "not_ordered" not in result.message


def test_hint_after_remove_swap_does_not_say_not_ordered(brief):
    s = _session(brief)
    s.set_fees(Decimal("150"), Decimal("0"))
    s.set_minimum_order(Decimal("2200"))
    s.add_item("chicken biryani", 2, Decimal("900"))
    result = s.remove_item("chicken biryani")
    assert result.ok
    assert "not_ordered" not in result.message
    assert "still applies" in result.message


def test_hint_prefers_optional_over_cheaper_required(make_brief):
    from order_agent.model.brief import WantedLine

    wanted = [
        WantedLine(item="chicken biryani", quantity=1, substitutes=[]),
        WantedLine(item="soda", quantity=1, optional=True),
    ]
    s = _session(make_brief(wanted=wanted, budget_pkr=Decimal("5000")))
    s.set_fees(Decimal("0"), Decimal("0"))
    s.add_item("chicken biryani", 1, Decimal("100"))
    s.add_item("soda", 1, Decimal("200"))
    result = s.set_minimum_order(Decimal("350"))  # short 50: biryani x1 costs 100, soda x1 costs 200
    assert "add 1 more soda (200 PKR)" in result.message


def test_hint_before_fees_set_does_not_claim_within_budget(brief):
    s = _session(brief)
    s.add_item("chicken biryani", 2, Decimal("900"))
    s.add_item("raita", 1, Decimal("150"))
    result = s.set_minimum_order(Decimal("2200"))
    assert "add 2 more raita (300 PKR)" in result.message
    assert "Delivery fee and tax are not recorded yet, so ask about them" in result.message
    assert "within your" not in result.message


def test_hint_asks_restaurant_first_and_states_no_projected_total(brief):
    s = _session(brief)
    s.add_item("chicken biryani", 2, Decimal("900"))
    s.add_item("raita", 1, Decimal("150"))
    s.set_fees(Decimal("150"), Decimal("0"))
    result = s.set_minimum_order(Decimal("2200"))  # food 1950, short 250: 2 more raita
    assert "ask the restaurant to add 2 more raita (300 PKR)" in result.message
    assert "only after they agree" in result.message
    assert "total would" not in result.message.lower()
    assert "within your" not in result.message
    assert "2400" not in result.message and "2250" not in result.message


def test_set_fees_result_repeats_hint_with_budget_claim(brief):
    s = _session(brief)
    s.add_item("chicken biryani", 2, Decimal("900"))
    s.add_item("raita", 1, Decimal("150"))
    s.set_minimum_order(Decimal("2200"))
    result = s.set_fees(Decimal("150"), Decimal("0"))
    assert "add 2 more raita (300 PKR)" in result.message
    assert "within your" not in result.message and "2400" not in result.message  # FR-008: no projected total


def test_remove_item_result_has_hint_when_lines_filled(brief):
    s = _minimum_reachable(brief)
    s.set_minimum_order(Decimal("2200"))
    s.add_item("raita", 2, Decimal("150"))
    result = s.remove_item("raita")
    assert result.ok
    assert "400 PKR short" in result.message  # food back to 1800
    assert "raita" in result.message and "ask its price" in result.message


def test_pending_optional_without_room_says_not_ordered_fallback(make_brief):
    s = _session(make_brief(budget_pkr=Decimal("2000")))
    s.add_item("chicken biryani", 2, Decimal("900"))
    s.set_fees(Decimal("150"), Decimal("0"))
    result = s.set_minimum_order(Decimal("2200"))
    assert "50 PKR more" in result.message
    assert "doesn't fit" in result.message and "not_ordered" in result.message
