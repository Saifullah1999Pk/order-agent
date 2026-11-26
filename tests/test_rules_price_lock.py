from datetime import datetime
from decimal import Decimal

from order_agent.model.rules import OrderSession

NOW = datetime(2026, 11, 23, 19, 30)
D = Decimal


def sess(brief) -> OrderSession:
    return OrderSession(brief, NOW)


def test_price_lock_refuses_different_price_after_remove_and_readd(brief):
    s = sess(brief)
    assert s.add_item("chicken biryani", 2, D("900")).ok
    assert s.remove_item("chicken biryani").ok
    r = s.add_item("chicken biryani", 1, D("1350"))
    assert not r.ok
    assert "The restaurant already said chicken biryani is 900 PKR" in r.message
    assert "Do not change prices to make a total match" in r.message
    assert "price_corrected=true" in r.message
    assert s.items == []


def test_price_lock_refuses_different_price_while_in_cart(brief):
    s = sess(brief)
    s.add_item("chicken biryani", 1, D("900"))
    r = s.add_item("chicken biryani", 1, D("950"))
    assert not r.ok and "already said" in r.message


def test_price_lock_matches_by_normalised_name(brief):
    s = sess(brief)
    s.add_item("Chicken Biryani", 1, D("900"))
    s.remove_item("chicken biryani")
    assert not s.add_item("biryani chicken", 1, D("1000")).ok


def test_same_price_after_remove_is_fine(brief):
    s = sess(brief)
    s.add_item("chicken biryani", 2, D("900"))
    s.remove_item("chicken biryani")
    assert s.add_item("chicken biryani", 2, D("900")).ok


def test_refused_add_does_not_set_the_lock(brief):
    s = sess(brief)
    assert not s.add_item("chicken biryani", 5, D("900")).ok  # over the brief quantity
    assert s.add_item("chicken biryani", 1, D("950")).ok  # first accepted price wins


def test_price_correction_allowed_with_flag_and_recorded(brief):
    s = sess(brief)
    s.add_item("chicken biryani", 1, D("900"))
    s.remove_item("chicken biryani")
    r = s.add_item("chicken biryani", 1, D("950"), price_corrected=True)
    assert r.ok
    assert s.cart_total() == D("950")
    assert s.events[-1].args["price_corrected"] is True
    # The corrected price is now the one that is locked.
    s.remove_item("chicken biryani")
    assert not s.add_item("chicken biryani", 1, D("900")).ok
    assert s.add_item("chicken biryani", 1, D("950")).ok


def test_price_correction_reprices_item_already_in_cart(brief):
    s = sess(brief)
    s.add_item("chicken biryani", 1, D("900"))
    assert s.add_item("chicken biryani", 1, D("950"), price_corrected=True).ok
    assert s.cart_total() == D("1900")
    assert len(s.items) == 1


def test_corrected_add_still_respects_budget(brief):
    s = sess(brief)
    s.add_item("chicken biryani", 2, D("900"))
    r = s.add_item("chicken biryani", 1, D("1500"), price_corrected=True)
    assert not r.ok


def test_normal_add_event_records_flag_false(brief):
    s = sess(brief)
    s.add_item("chicken biryani", 1, D("900"))
    assert s.events[-1].args["price_corrected"] is False


def test_fee_lock_refuses_change(brief):
    s = sess(brief)
    assert s.set_fees(D("150"), D("0")).ok
    r = s.set_fees(D("0"), D("0"))
    assert not r.ok
    assert "already said" in r.message and "delivery fee" in r.message and "150" in r.message
    assert "Do not change" in r.message and "corrected=true" in r.message
    assert s.delivery_fee_pkr == D("150")


def test_fee_lock_covers_tax(brief):
    s = sess(brief)
    s.set_fees(D("150"), D("50"))
    r = s.set_fees(D("150"), D("500"))
    assert not r.ok and "tax" in r.message


def test_same_fees_again_allowed(brief):
    s = sess(brief)
    s.set_fees(D("150"), D("0"))
    assert s.set_fees(D("150"), D("0")).ok


def test_zero_fee_is_not_locked(brief):
    s = sess(brief)
    s.set_fees(D("0"), D("0"))
    assert s.set_fees(D("150"), D("0")).ok


def test_fee_correction_allowed_with_flag_and_recorded(brief):
    s = sess(brief)
    s.set_fees(D("150"), D("0"))
    assert s.set_fees(D("200"), D("0"), corrected=True).ok
    assert s.delivery_fee_pkr == D("200")
    assert s.events[-1].args["corrected"] is True


def test_terse_staff_sequence_is_refused_at_first_bending_step(brief):
    s = sess(brief)
    assert s.add_item("chicken biryani", 2, D("900")).ok
    assert s.set_fees(D("150"), D("0")).ok
    r = s.confirm_order(D("1350"), 45)
    assert not r.ok
    assert "itemise" in r.message
    # The bot then tries to bend the cart to 1350: every step is refused.
    assert not s.set_fees(D("0"), D("0")).ok
    assert s.remove_item("chicken biryani").ok  # removing is not bending ...
    assert not s.add_item("chicken biryani", 1, D("1350")).ok  # ... re-adding at a new price is
    assert s.quoted_total_pkr is None


def test_confirm_mismatch_tells_bot_to_ask_for_itemised_total(brief):
    s = sess(brief)
    s.add_item("chicken biryani", 2, D("900"))
    s.set_fees(D("150"), D("0"))
    r = s.confirm_order(D("1350"), 45)
    assert not r.ok
    for phrase in ("1350", "1950", "itemise", "each item", "Do not edit"):
        assert phrase in r.message
