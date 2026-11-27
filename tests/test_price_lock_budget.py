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
