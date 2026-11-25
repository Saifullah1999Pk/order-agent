"""Parity: legacy order_agent.tools vs the voice head over the Controller.

Deleted together with the legacy tools.py (T031).
"""
from types import SimpleNamespace

import pytest

from order_agent.controller import CallController
from order_agent.heads.voice.tools import build_tools as new_build_tools
from order_agent.rules import OrderSession
from order_agent.tools import build_tools as legacy_build_tools


class Side:
    def __init__(self, tools, events):
        self.tools = tools
        self._events = events
        self.log: list[tuple[dict, object]] = []  # (payload, run_llm) per call

    async def call(self, tool, arguments):
        schema = next(t for t in self.tools.standard_tools if t.name == tool)
        got = []

        async def result_callback(result, properties=None):
            got.append((result, True if properties is None else properties.run_llm))

        await schema.handler(SimpleNamespace(arguments=arguments, result_callback=result_callback))
        assert len(got) == 1
        self.log.append(got[0])
        return got[0]

    @property
    def events(self):
        return [(e.tool, e.args, e.ok, e.message) for e in self._events()]


@pytest.fixture
def pair(make_brief, tmp_path):
    brief = make_brief()
    legacy_session = OrderSession(brief, brief.call_time)

    async def on_end(outcome, reason):
        pass

    legacy = Side(legacy_build_tools(legacy_session, on_end), lambda: legacy_session.events)
    controller = CallController(make_brief(), reports_dir=tmp_path, now=brief.call_time)
    new = Side(new_build_tools(controller), lambda: controller.session.events)
    return legacy, new


async def run_both(pair, steps):
    legacy, new = pair
    for tool, arguments in steps:
        assert await new.call(tool, arguments) == await legacy.call(tool, arguments), (tool, arguments)
    assert new.events == legacy.events
    assert new.log == legacy.log


BAD_ARGUMENTS = ["not a dict", None, 5, ["a"], {}]
NAMES = ["add_item", "set_price", "remove_item", "set_fees", "set_minimum_order", "confirm_order", "end_call"]


@pytest.mark.parametrize("bad", BAD_ARGUMENTS)
@pytest.mark.parametrize("tool", NAMES)
async def test_non_dict_and_empty_arguments(pair, tool, bad):
    await run_both(pair, [(tool, bad)])


@pytest.mark.parametrize(
    "steps",
    [
        [("add_item", {"name": "chicken biryani", "quantity": 2, "unit_price_pkr": 900})],
        [("add_item", {"name": "chicken biryani", "quantity": 1.5, "unit_price_pkr": 900})],
        [("add_item", {"name": "chicken biryani", "quantity": 1, "unit_price_pkr": "twelve"})],
        [("add_item", {"name": "chicken biryani", "quantity": 1, "price_corrected": "maybe"})],
        [("add_item", {"name": "prawn karahi", "quantity": 1, "unit_price_pkr": 900})],  # forbidden item
        [("add_item", {"name": "chicken biryani", "quantity": 5, "unit_price_pkr": 900})],  # over budget
        [("add_item", {"name": "chicken biryani", "quantity": 1}), ("set_price", {"name": "chicken biryani", "unit_price_pkr": "900"})],
        [("set_price", {"name": "nothing", "unit_price_pkr": 10})],
        [("remove_item", {"name": "nothing"})],
        [("set_fees", {"delivery_fee_pkr": 100, "tax_pkr": "50.5"}), ("set_fees", {"delivery_fee_pkr": 0, "tax_pkr": 0})],
        [("set_minimum_order", {"minimum_pkr": 1000}), ("set_minimum_order", {"minimum_pkr": "lots"})],
        [("confirm_order", {"quoted_total_pkr": 100, "delivery_minutes": 30})],
        [("end_call", {"outcome": "ordered", "reason": "done"})],  # refused: nothing confirmed
        [("end_call", {"outcome": "not_ordered", "reason": "sold out"}), ("add_item", {"name": "raita", "quantity": 1})],
    ],
)
async def test_argument_matrix(pair, steps):
    await run_both(pair, steps)


async def test_happy_path_ending_in_end_call(pair):
    await run_both(
        pair,
        [
            ("add_item", {"name": "chicken biryani", "quantity": 2, "unit_price_pkr": 900}),
            ("add_item", {"name": "raita", "quantity": 1, "unit_price_pkr": 100}),
            ("set_fees", {"delivery_fee_pkr": 150, "tax_pkr": 0}),
            ("set_minimum_order", {"minimum_pkr": 1000}),
            ("confirm_order", {"quoted_total_pkr": 2050, "delivery_minutes": 40}),
            ("end_call", {"outcome": "ordered", "reason": "confirmed"}),
        ],
    )
    legacy, new = pair
    assert new.log[-1] == ({"ok": True, "message": new.log[-1][0]["message"]}, False)


@pytest.mark.parametrize(
    "steps",
    [
        [("add_item", {"name": "chicken biryani", "quantity": True, "unit_price_pkr": 900})],
        [("add_item", {"name": "chicken biryani", "quantity": 1, "unit_price_pkr": float("nan")})],
        [("add_item", {"name": "chicken biryani", "quantity": 1, "unit_price_pkr": "1,200"})],
        [("add_item", {"name": "  ", "quantity": 1})],
        [("add_item", {"name": "chicken biryani", "quantity": 1, "unit_price_pkr": 900, "price_corrected": "TRUE", "extra": 1})],
        [("end_call", {"outcome": "not_ordered", "reason": 7})],
        [("end_call", {"outcome": "bogus", "reason": "x"})],
        [("end_call", {"outcome": "not_ordered", "reason": "  "})],
        [("confirm_order", {"quoted_total_pkr": "x", "delivery_minutes": 30})],
        [("set_fees", {"delivery_fee_pkr": 1, "tax_pkr": 1, "corrected": "maybe"})],
    ],
)
async def test_edge_argument_matrix(pair, steps):
    await run_both(pair, steps)
