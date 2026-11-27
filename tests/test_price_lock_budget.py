"""FR-015: a price the restaurant stated is locked even when it is refused as over budget.

Why: run 20261127-181447 price_over_budget attempt 3. The restaurant said chicken biryani is Rs 1300.
set_price(1300) was refused as over budget *before* the price lock was written, so the bot then
set_price(1175) (= (2500 - 150) / 2, reverse-engineered from the budget), the cart summed to exactly
2500, and confirm_order(2500) was accepted although the restaurant never said 2500.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from order_agent.model.rules import OrderSession

NOW = datetime(2026, 11, 23, 19, 30)


@pytest.fixture
def s(brief):
    return OrderSession(brief, NOW)


def test_over_budget_set_price_still_locks_the_stated_price(s):
    assert s.add_item("chicken biryani", 2).ok
    assert not s.set_price("chicken biryani", Decimal("1300")).ok
    r = s.set_price("chicken biryani", Decimal("1175"))
    assert not r.ok
    assert "already said chicken biryani is 1300 PKR" in r.message
    assert s.items[0].unit_price_pkr is None


def test_over_budget_add_item_still_locks_the_stated_price(s):
    assert not s.add_item("chicken biryani", 2, Decimal("1300")).ok
    r = s.add_item("chicken biryani", 2, Decimal("1175"))
    assert not r.ok
    assert "already said chicken biryani is 1300 PKR" in r.message
    assert s.items == []


def test_replay_of_the_failing_call_cannot_confirm(s):
    """The exact tool sequence from the failing call now ends without an order."""
    assert s.add_item("chicken biryani", 2).ok
    assert s.add_item("raita", 1).ok
    assert not s.set_price("chicken biryani", Decimal("1300")).ok
    assert s.remove_item("raita").ok
    assert not s.set_price("chicken biryani", Decimal("1175")).ok
    s.set_fees(Decimal("150"), None)
    s.set_fees(None, Decimal("0"))
    assert not s.confirm_order(Decimal("2500"), 45, [("chicken biryani", 2)]).ok
    assert s.state == "open"


def test_a_genuine_price_change_is_still_possible(s):
    assert s.add_item("chicken biryani", 2).ok
    assert not s.set_price("chicken biryani", Decimal("1300")).ok
    assert s.set_price("chicken biryani", Decimal("1000"), price_corrected=True).ok
    assert s.items[0].unit_price_pkr == Decimal("1000")


def test_quote_that_leaves_an_unpriced_item_free_is_refused(s):
    """FR-016, run 20261127-190950 attempt 1: the restaurant agreed 1 biryani + raita = Rs 1600; the bot
    silently added an unpriced chicken pulao to fill the brief and confirmed at 1600, so the pulao cost 0."""
    assert s.add_item("chicken biryani", 1, Decimal("1300")).ok
    assert s.add_item("raita", 1, Decimal("150")).ok
    assert s.set_fees(Decimal("150"), Decimal("0")).ok
    assert s.add_item("chicken pulao", 1).ok
    r = s.confirm_order(Decimal("1600"), 45, [("chicken biryani", 1), ("raita", 1), ("chicken pulao", 1)])
    assert not r.ok
    assert "chicken pulao" in r.message
    assert s.state == "open"


def test_quote_above_known_sum_with_unpriced_item_still_confirms(s):
    assert s.add_item("chicken biryani", 1, Decimal("900")).ok
    assert s.add_item("chicken pulao", 1).ok
    assert s.set_fees(Decimal("150"), Decimal("0")).ok
    assert s.confirm_order(Decimal("1850"), 45, [("chicken biryani", 1), ("chicken pulao", 1)]).ok
