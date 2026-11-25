from decimal import Decimal
from types import SimpleNamespace

import pytest

from order_agent.rules import OrderSession
from order_agent.tools import build_tools

NAMES = ["add_item", "remove_item", "set_fees", "set_minimum_order", "confirm_order", "end_call"]


class Harness:
    def __init__(self, brief):
        self.session = OrderSession(brief, brief.call_time)
        self.ended: list[tuple[str, str]] = []
        self.properties: list = []
        self.tools = build_tools(self.session, self._on_end)

    async def _on_end(self, outcome, reason):
        self.ended.append((outcome, reason))

    async def call(self, tool, **arguments):
        schema = next(t for t in self.tools.standard_tools if t.name == tool)
        results = []

        async def result_callback(result, properties=None):
            results.append(result)
            self.properties.append(properties)

        params = SimpleNamespace(arguments=arguments, result_callback=result_callback)
        await schema.handler(params)
        assert len(results) == 1
        return results[0]


@pytest.fixture
def h(brief):
    return Harness(brief)


def test_tools_schema_names(h):
    assert [t.name for t in h.tools.standard_tools] == NAMES


async def test_handler_add_item_calls_session(h):
    result = await h.call("add_item", name="chicken biryani", quantity=2, unit_price_pkr=900)
    assert result["ok"] is True
    assert h.session.cart_total() == Decimal("1800")


@pytest.mark.parametrize("price", ["twelve hundred", True, float("nan"), None, [900]])
async def test_handler_rejects_unparseable_price(h, price):
    result = await h.call("add_item", name="chicken biryani", quantity=2, unit_price_pkr=price)
    assert result["ok"] is False
    assert h.session.events == []


async def test_handler_rejects_missing_argument(h):
    result = await h.call("add_item", name="chicken biryani", quantity=2)
    assert result["ok"] is False
    assert h.session.events == []


async def test_handler_quantity_integral_float_ok_fraction_rejected(h):
    assert (await h.call("add_item", name="chicken biryani", quantity=1.0, unit_price_pkr=900))["ok"] is True
    result = await h.call("add_item", name="chicken biryani", quantity=1.5, unit_price_pkr=900)
    assert result["ok"] is False
    assert len(h.session.events) == 1


async def test_other_handlers_delegate(h):
    await h.call("add_item", name="chicken biryani", quantity=2, unit_price_pkr=900)
    assert (await h.call("set_minimum_order", minimum_pkr=1000))["ok"] is True
    assert (await h.call("set_fees", delivery_fee_pkr=100, tax_pkr="50.5"))["ok"] is True
    assert h.session.tax_pkr == Decimal("50.5")
    assert (await h.call("remove_item", name="chicken biryani"))["ok"] is True
    bad = await h.call("confirm_order", quoted_total_pkr="lots", delivery_minutes=30)
    assert bad["ok"] is False


async def test_end_call_invokes_on_end_only_when_allowed(h):
    refused = await h.call("end_call", outcome="ordered", reason="done")
    assert refused["ok"] is False
    assert h.ended == []
    ok = await h.call("end_call", outcome="not_ordered", reason="sold out")
    assert ok["ok"] is True
    assert h.ended == [("not_ordered", "sold out")]


async def test_successful_end_call_does_not_rerun_llm_but_refusal_does(h):
    await h.call("end_call", outcome="ordered", reason="done")  # refused: nothing confirmed
    refused_props = h.properties[-1]
    assert refused_props is None or refused_props.run_llm is not False
    await h.call("end_call", outcome="not_ordered", reason="sold out")
    assert h.properties[-1].run_llm is False


async def test_handler_survives_session_exception(h, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(h.session, "add_item", boom)
    h.tools = build_tools(h.session, h._on_end)
    result = await h.call("add_item", name="chicken biryani", quantity=1, unit_price_pkr=900)
    assert result["ok"] is False and "kaboom" in result["message"]


async def test_end_call_survives_exception_in_on_end(h):
    async def bad_on_end(outcome, reason):
        raise RuntimeError("shutdown failed")

    h.tools = build_tools(h.session, bad_on_end)
    result = await h.call("end_call", outcome="not_ordered", reason="nothing")
    assert result["ok"] is True


@pytest.mark.parametrize("bad", ["not a dict", None, 5, ["a"]])
@pytest.mark.parametrize("tool", NAMES)
async def test_non_dict_arguments_get_exactly_one_refusal(h, tool, bad):
    schema = next(t for t in h.tools.standard_tools if t.name == tool)
    results = []

    async def result_callback(result, properties=None):
        results.append(result)

    await schema.handler(SimpleNamespace(arguments=bad, result_callback=result_callback))
    assert len(results) == 1
    assert results[0]["ok"] is False
    assert h.session.items == []
    assert h.ended == []


async def test_add_item_price_corrected_flag_reaches_session(h):
    await h.call("add_item", name="chicken biryani", quantity=1, unit_price_pkr=900)
    refused = await h.call("add_item", name="chicken biryani", quantity=1, unit_price_pkr=950)
    assert refused["ok"] is False and "price_corrected=true" in refused["message"]
    ok = await h.call("add_item", name="chicken biryani", quantity=1, unit_price_pkr=950, price_corrected=True)
    assert ok["ok"] is True
    assert h.session.events[-1].args["price_corrected"] is True


async def test_set_fees_corrected_flag_reaches_session(h):
    await h.call("set_fees", delivery_fee_pkr=150, tax_pkr=0)
    assert (await h.call("set_fees", delivery_fee_pkr=0, tax_pkr=0))["ok"] is False
    assert (await h.call("set_fees", delivery_fee_pkr=200, tax_pkr=0, corrected=True))["ok"] is True


async def test_correction_flag_must_be_boolean(h):
    result = await h.call("add_item", name="chicken biryani", quantity=1, unit_price_pkr=900, price_corrected="maybe")
    assert result["ok"] is False
    assert h.session.events == []


def test_correction_flags_are_in_the_schemas(h):
    props = {t.name: t.properties for t in h.tools.standard_tools}
    assert props["add_item"]["price_corrected"]["type"] == "boolean"
    assert props["set_fees"]["corrected"]["type"] == "boolean"
    required = {t.name: t.required for t in h.tools.standard_tools}
    assert "price_corrected" not in required["add_item"] and "corrected" not in required["set_fees"]
