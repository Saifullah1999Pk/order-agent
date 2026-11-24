"""Proves LLMContext(tools=...) with handler-carrying FunctionSchemas registers the handlers
on GoogleLLMService (Pipecat 1.17.0), with no network calls."""

from datetime import datetime
from types import SimpleNamespace

from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.google.llm import GoogleLLMService

from order_agent.rules import OrderSession
from order_agent.tools import build_tools

NAMES = {"add_item", "remove_item", "set_fees", "set_minimum_order", "confirm_order", "end_call"}


async def test_handlers_register_and_run(brief):
    session = OrderSession(brief, datetime(2026, 11, 23, 19, 30))
    ended = []

    async def on_end(outcome, reason):
        ended.append((outcome, reason))

    context = LLMContext(tools=build_tools(session, on_end))
    llm = GoogleLLMService(api_key="test-key", settings=GoogleLLMService.Settings(model="gemini-2.5-flash"))
    # The same call the service makes when an LLMContextFrame reaches it.
    llm._sync_registered_tool_handlers(context.tools)
    assert NAMES <= set(llm._functions)

    results = []

    async def result_callback(result, properties=None):
        results.append(result)

    params = SimpleNamespace(
        arguments={"name": "chicken biryani", "quantity": 2, "unit_price_pkr": 900},
        result_callback=result_callback,
    )
    await llm._functions["add_item"].handler(params)
    assert results[-1]["ok"] is True
    assert session.items[0].quantity == 2
