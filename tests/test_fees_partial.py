"""FR-014: set_fees records only the fees the restaurant stated; neither is forced.

Why: set_fees used to require both values ("use 0 if none"), so when the restaurant stated only
the tax, the bot had to invent a delivery fee and sent 0 (pushes_forbidden, runs 20261127-130223
and 20261127-151755).
"""

from datetime import datetime
from decimal import Decimal

import pytest

from order_agent.controller.tools import ToolDispatcher
from order_agent.controller.toolspecs import TOOL_SPECS
from order_agent.model.rules import OrderSession

NOW = datetime(2026, 11, 23, 19, 30)


@pytest.fixture
def s(brief):
    return OrderSession(brief, NOW)


def _priced_cart(s):
    assert s.add_item("chicken biryani", 2, Decimal("900")).ok
    assert s.add_item("raita", 1, Decimal("150")).ok


def test_tax_alone_is_recorded_and_fee_stays_unknown(s):
    _priced_cart(s)
    r = s.set_fees(None, Decimal("0"))
    assert r.ok
    assert "tax 0 PKR" in r.message
    assert "delivery fee is not recorded yet" in r.message
    assert s.tax_pkr == 0 and s.delivery_fee_pkr == 0
    assert not s.fees_set
    assert not s.cart_total_known()


def test_fee_given_later_completes_the_fees(s):
    _priced_cart(s)
    assert s.set_fees(None, Decimal("0")).ok
    r = s.set_fees(Decimal("150"), None)
    assert r.ok
    assert s.delivery_fee_pkr == 150 and s.tax_pkr == 0
    assert s.fees_set and s.cart_total_known()
    assert s.cart_total() == Decimal("2100")


def test_fee_alone_leaves_tax_unknown(s):
    _priced_cart(s)
    r = s.set_fees(Decimal("150"), None)
    assert r.ok
    assert "tax is not recorded yet" in r.message
    assert not s.fees_set


def test_neither_fee_is_refused(s):
    r = s.set_fees(None, None)
    assert not r.ok
    assert "Give the delivery fee, the tax, or both" in r.message
    assert not s.fees_set


def test_omitted_fee_does_not_trigger_the_change_guard(s):
    assert s.set_fees(Decimal("150"), Decimal("0")).ok
    assert s.set_fees(None, Decimal("0")).ok
    assert s.delivery_fee_pkr == 150


def test_changing_a_stated_fee_is_still_refused(s):
    assert s.set_fees(Decimal("150"), None).ok
    assert not s.set_fees(Decimal("100"), None).ok
    assert s.delivery_fee_pkr == 150


def test_partial_event_args_record_none_for_the_omitted_fee(s):
    s.set_fees(None, Decimal("0"))
    event = s.events[-1]
    assert event.args == {"delivery_fee_pkr": None, "tax_pkr": Decimal("0"), "corrected": False}


def test_schema_requires_neither_fee_and_drops_use_zero_if_none():
    spec = next(t for t in TOOL_SPECS if t.name == "set_fees")
    assert spec.required == []
    assert "use 0 if none" not in spec.description
    assert "only the ones they said" in spec.description
    assert "'including delivery' is not a fee" in spec.description


async def test_dispatch_tax_only(brief):
    s = OrderSession(brief, NOW)
    outcome = await ToolDispatcher(s).dispatch("set_fees", {"tax_pkr": 0})
    assert outcome.ok
    assert not s.fees_set


async def test_dispatch_neither_fee_is_one_refusal(brief):
    s = OrderSession(brief, NOW)
    outcome = await ToolDispatcher(s).dispatch("set_fees", {})
    assert outcome.ok is False
    assert "Give the delivery fee, the tax, or both" in outcome.message


async def test_dispatch_bad_fee_still_refused(brief):
    s = OrderSession(brief, NOW)
    outcome = await ToolDispatcher(s).dispatch("set_fees", {"delivery_fee_pkr": "abc"})
    assert outcome.ok is False
