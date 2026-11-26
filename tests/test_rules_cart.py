from datetime import datetime
from decimal import Decimal

from order_agent.model.rules import OrderSession
from order_agent.model.brief import WantedLine

NOW = datetime(2026, 11, 23, 19, 30)


def session(brief) -> OrderSession:
    return OrderSession(brief, NOW)


def test_add_wanted_item(brief):
    s = session(brief)
    r = s.add_item("chicken biryani", 2, Decimal("900"))
    assert r.ok
    assert s.cart_total() == Decimal("1800")


def test_add_item_not_in_brief_refused(brief):
    r = session(brief).add_item("fish special", 1, Decimal("500"))
    assert not r.ok
    assert "not in your brief" in r.message


def test_add_item_hits_never_keyword(make_brief):
    brief = make_brief(
        wanted=[
            WantedLine(
                item="chicken biryani", quantity=2, substitutes=["fish biryani"]
            )
        ]
    )
    r = session(brief).add_item("fish biryani", 1, Decimal("500"))
    assert not r.ok
    assert "seafood" in r.message


def test_add_item_over_budget_refused(brief):
    s = session(brief)
    r = s.add_item("chicken biryani", 2, Decimal("1300"))
    assert not r.ok
    assert "budget" in r.message and "2500" in r.message
    assert s.items == []


def test_add_item_over_budget_suggests_dropping_optional(brief):
    s = session(brief)
    assert s.add_item("raita", 1, Decimal("150")).ok
    r = s.add_item("chicken biryani", 2, Decimal("1200"))  # 2550 with raita
    assert not r.ok
    assert "raita" in r.message
    assert len(s.items) == 1


def test_add_item_rejects_nonpositive_price(brief):
    s = session(brief)
    assert not s.add_item("chicken biryani", 1, Decimal("0")).ok
    assert not s.add_item("chicken biryani", 1, Decimal("-5")).ok
    assert not s.add_item("chicken biryani", 0, Decimal("900")).ok
    assert s.items == []


def test_add_beyond_line_quantity_refused_without_minimum(brief):
    s = session(brief)
    assert s.add_item("chicken biryani", 2, Decimal("900")).ok
    r = s.add_item("chicken biryani", 1, Decimal("900"))
    assert not r.ok
    assert "already" in r.message


def test_substitute_counts_toward_line_quantity(brief):
    s = session(brief)
    assert s.add_item("chicken biryani", 1, Decimal("900")).ok
    assert s.add_item("chicken karahi", 1, Decimal("1000")).ok
    assert not s.add_item("chicken pulao", 1, Decimal("800")).ok


def test_remove_item(brief):
    s = session(brief)
    s.add_item("chicken biryani", 1, Decimal("900"))
    assert s.remove_item("Chicken Biryani").ok
    assert s.items == []
    assert not s.remove_item("chicken biryani").ok


def test_fees_count_toward_budget(brief):
    s = session(brief)
    s.add_item("chicken biryani", 2, Decimal("900"))
    s.add_item("raita", 1, Decimal("150"))
    r = s.set_fees(Decimal("600"), Decimal("0"))
    assert not r.ok
    assert s.delivery_fee_pkr == Decimal("0")
    assert s.set_fees(Decimal("500"), Decimal("0")).ok
    assert s.cart_total() == Decimal("2450")


def test_fees_reject_negative(brief):
    assert not session(brief).set_fees(Decimal("-1"), Decimal("0")).ok


def test_add_item_over_budget_counts_fees(brief):
    s = session(brief)
    s.set_fees(Decimal("300"), Decimal("100"))
    assert not s.add_item("chicken biryani", 2, Decimal("1100")).ok


def test_events_record_refusals(brief):
    s = session(brief)
    s.add_item("chicken biryani", 1, Decimal("900"))
    s.add_item("fish special", 1, Decimal("500"))
    assert len(s.events) == 2
    assert s.events[0].ok and s.events[1].ok is False
    assert s.events[1].tool == "add_item"


def test_over_budget_names_listed_substitutes_not_a_smaller_quantity(brief):
    s = session(brief)
    r = s.add_item("chicken biryani", 2, Decimal("1300"))
    assert not r.ok
    assert "chicken karahi" in r.message and "chicken pulao" in r.message
    assert "smaller quantity" not in r.message


def test_over_budget_skips_substitutes_already_in_cart_and_the_item_itself(make_brief):
    brief = make_brief(budget_pkr=Decimal("2000"))
    s = session(brief)
    assert s.add_item("chicken karahi", 1, Decimal("800")).ok
    r = s.add_item("chicken biryani", 1, Decimal("1300"))  # 2100 > 2000
    assert not r.ok
    assert "chicken pulao" in r.message
    assert "chicken karahi" not in r.message
