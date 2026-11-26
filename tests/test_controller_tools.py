from decimal import Decimal

import pytest

from order_agent.controller.tools import ToolDispatcher, ToolOutcome
from order_agent.model.rules import OrderSession


@pytest.fixture
def session(brief):
    return OrderSession(brief, brief.call_time)


@pytest.fixture
def dispatcher(session):
    return ToolDispatcher(session)


def test_tool_outcome_defaults_and_payload():
    outcome = ToolOutcome(ok=True, message="done")
    assert outcome.run_llm is True and outcome.ended is False
    assert outcome.as_payload() == {"ok": True, "message": "done"}


async def test_add_item_valid(dispatcher, session):
    outcome = await dispatcher.dispatch("add_item", {"name": "chicken biryani", "quantity": 2, "unit_price_pkr": 900})
    assert isinstance(outcome, ToolOutcome)
    assert outcome.ok is True
    assert outcome.run_llm is True and outcome.ended is False
    assert session.cart_total() == Decimal("1800")


async def test_add_item_price_optional(dispatcher, session):
    outcome = await dispatcher.dispatch("add_item", {"name": "chicken biryani", "quantity": 2})
    assert outcome.ok is True
    assert len(session.events) == 1


@pytest.mark.parametrize("name", [None, "", "   ", 5])
async def test_missing_or_blank_text(dispatcher, session, name):
    args = {"quantity": 1} if name is None else {"name": name, "quantity": 1}
    outcome = await dispatcher.dispatch("add_item", args)
    assert outcome.ok is False
    assert outcome.message == "Refused: Missing or invalid 'name': it must be non-empty text."
    assert session.events == []


@pytest.mark.parametrize("tool,args", [("remove_item", {}), ("set_price", {"unit_price_pkr": 900})])
async def test_missing_name_refused_for_other_tools(dispatcher, session, tool, args):
    outcome = await dispatcher.dispatch(tool, args)
    assert outcome.ok is False
    assert outcome.message == "Refused: Missing or invalid 'name': it must be non-empty text."


async def test_non_number_money(dispatcher, session):
    outcome = await dispatcher.dispatch(
        "add_item", {"name": "chicken biryani", "quantity": 2, "unit_price_pkr": "twelve hundred"}
    )
    assert outcome.ok is False
    assert outcome.message == "Refused: 'unit_price_pkr' must be a plain number such as 1200, not 'twelve hundred'."
    assert session.events == []


@pytest.mark.parametrize("value", [True, [900], float("nan")])
async def test_bad_money_values(dispatcher, session, value):
    outcome = await dispatcher.dispatch("set_price", {"name": "x", "unit_price_pkr": value})
    assert outcome.ok is False and outcome.message.startswith("Refused: ")
    assert session.events == []


async def test_bool_money_message(dispatcher):
    outcome = await dispatcher.dispatch("set_minimum_order", {"minimum_pkr": True})
    assert outcome.message == "Refused: Missing or invalid 'minimum_pkr': it must be a number. Ask the restaurant to repeat it."


async def test_missing_money(dispatcher):
    outcome = await dispatcher.dispatch("set_fees", {"delivery_fee_pkr": 100})
    assert outcome.ok is False
    assert "Missing or invalid 'tax_pkr'" in outcome.message


async def test_whole_number_float_ok_fraction_refused(dispatcher, session):
    ok = await dispatcher.dispatch("add_item", {"name": "chicken biryani", "quantity": 1.0, "unit_price_pkr": 900})
    assert ok.ok is True
    bad = await dispatcher.dispatch("add_item", {"name": "chicken biryani", "quantity": 2.5, "unit_price_pkr": 900})
    assert bad.ok is False
    assert bad.message == "Refused: 'quantity' must be a whole number, not 2.5."
    assert len(session.events) == 1


async def test_quantity_missing_or_bool(dispatcher):
    for args in ({"name": "x"}, {"name": "x", "quantity": True}):
        outcome = await dispatcher.dispatch("add_item", args)
        assert outcome.message == "Refused: Missing or invalid 'quantity': it must be a whole number."


async def test_bad_flag(dispatcher, session):
    outcome = await dispatcher.dispatch(
        "add_item", {"name": "chicken biryani", "quantity": 1, "unit_price_pkr": 900, "price_corrected": "maybe"}
    )
    assert outcome.ok is False
    assert outcome.message == "Refused: 'price_corrected' must be true or false."
    assert session.events == []


async def test_flag_reaches_session(dispatcher, session):
    await dispatcher.dispatch("add_item", {"name": "chicken biryani", "quantity": 1, "unit_price_pkr": 900})
    refused = await dispatcher.dispatch("add_item", {"name": "chicken biryani", "quantity": 1, "unit_price_pkr": 950})
    assert refused.ok is False and "price_corrected=true" in refused.message
    ok = await dispatcher.dispatch(
        "add_item", {"name": "chicken biryani", "quantity": 1, "unit_price_pkr": 950, "price_corrected": "true"}
    )
    assert ok.ok is True
    assert session.events[-1].args["price_corrected"] is True


async def test_other_tools_delegate(dispatcher, session):
    await dispatcher.dispatch("add_item", {"name": "chicken biryani", "quantity": 2, "unit_price_pkr": 900})
    assert (await dispatcher.dispatch("set_minimum_order", {"minimum_pkr": 1000})).ok is True
    assert (await dispatcher.dispatch("set_fees", {"delivery_fee_pkr": 100, "tax_pkr": "50.5"})).ok is True
    assert session.tax_pkr == Decimal("50.5")
    assert (await dispatcher.dispatch("set_price", {"name": "chicken biryani", "unit_price_pkr": 900})).ok is True
    assert (await dispatcher.dispatch("remove_item", {"name": "chicken biryani"})).ok is True
    bad = await dispatcher.dispatch("confirm_order", {"quoted_total_pkr": "lots", "delivery_minutes": 30})
    assert bad.ok is False
    assert bad.message == "Refused: 'quoted_total_pkr' must be a plain number such as 1200, not 'lots'."


async def test_confirm_order_valid_matches_session(dispatcher, brief):
    twin = OrderSession(brief, brief.call_time)
    for target in (dispatcher.session, twin):
        target.add_item("chicken biryani", 2, Decimal("900"))
    outcome = await dispatcher.dispatch("confirm_order", {"quoted_total_pkr": 1800, "delivery_minutes": 30})
    expected = twin.confirm_order(Decimal("1800"), 30)
    assert (outcome.ok, outcome.message) == (expected.ok, expected.message)


async def test_end_call_success_stops_llm_and_marks_ended(dispatcher):
    outcome = await dispatcher.dispatch("end_call", {"outcome": "not_ordered", "reason": "sold out"})
    assert outcome.ok is True
    assert outcome.run_llm is False and outcome.ended is True


async def test_end_call_refused_keeps_llm_running(dispatcher):
    outcome = await dispatcher.dispatch("end_call", {"outcome": "ordered", "reason": "done"})
    assert outcome.ok is False
    assert outcome.run_llm is True and outcome.ended is False


async def test_end_call_blank_reason_refused(dispatcher):
    outcome = await dispatcher.dispatch("end_call", {"outcome": "not_ordered", "reason": " "})
    assert outcome.message == "Refused: Missing or invalid 'reason': it must be non-empty text."
    assert outcome.run_llm is True and outcome.ended is False


@pytest.mark.parametrize("bad", ["not a dict", 5, ["a"]])
@pytest.mark.parametrize(
    "tool",
    ["add_item", "set_price", "remove_item", "set_fees", "set_minimum_order", "confirm_order", "end_call"],
)
async def test_non_dict_arguments_get_one_refusal(dispatcher, session, tool, bad):
    outcome = await dispatcher.dispatch(tool, bad)
    assert outcome.ok is False
    assert outcome.message.startswith("Refused: could not read the arguments (")
    assert session.items == []


async def test_none_arguments_refused_without_raising(dispatcher):
    for tool in ("add_item", "end_call"):
        outcome = await dispatcher.dispatch(tool, None)
        assert outcome.ok is False and outcome.message.startswith("Refused:")


async def test_unknown_tool_refused(dispatcher):
    outcome = await dispatcher.dispatch("launch_missiles", {})
    assert outcome.ok is False and outcome.message.startswith("Refused:")
    assert "launch_missiles" in outcome.message


async def test_session_exception_becomes_refusal(dispatcher, session, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(session, "add_item", boom)
    outcome = await ToolDispatcher(session).dispatch("add_item", {"name": "x", "quantity": 1})
    assert outcome.ok is False
    assert outcome.message == "Refused: internal error (kaboom). Try again or end the call."


async def test_end_call_session_exception_becomes_refusal(session, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(session, "end", boom)
    outcome = await ToolDispatcher(session).dispatch("end_call", {"outcome": "not_ordered", "reason": "x"})
    assert outcome.ok is False and outcome.run_llm is True and outcome.ended is False
    assert outcome.message == "Refused: internal error (kaboom)."
