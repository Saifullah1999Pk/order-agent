"""Pipecat function-calling tools. Thin handlers over the rules engine.

Each handler converts the LLM's arguments, then delegates to OrderSession. If an
argument is missing or cannot be converted, it returns a refusal without
touching the session.
"""

from collections.abc import Awaitable, Callable
from decimal import Decimal, InvalidOperation

from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema

from order_agent.rules import OrderSession


class _BadArgument(Exception):
    pass


def _text(arguments: dict, key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _BadArgument(f"Missing or invalid '{key}': it must be non-empty text.")
    return value


def _money(arguments: dict, key: str) -> Decimal:
    value = arguments.get(key)
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise _BadArgument(f"Missing or invalid '{key}': it must be a number. Ask the restaurant to repeat it.")
    try:
        number = Decimal(str(value).strip().replace(",", ""))
    except InvalidOperation:
        raise _BadArgument(f"'{key}' must be a plain number such as 1200, not {value!r}.") from None
    if not number.is_finite():
        raise _BadArgument(f"'{key}' must be a finite number.")
    return number


def _whole(arguments: dict, key: str) -> int:
    """A whole number. An integral float such as 2.0 is accepted; 2.5 is not."""
    value = arguments.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _BadArgument(f"Missing or invalid '{key}': it must be a whole number.")
    if isinstance(value, float) and not value.is_integer():  # also rejects nan and inf
        raise _BadArgument(f"'{key}' must be a whole number, not {value}.")
    return int(value)


def _refusal(exc: _BadArgument) -> dict:
    return {"ok": False, "message": f"Refused: {exc}"}


def build_tools(
    session: OrderSession, on_end: Callable[[str, str], Awaitable[None]]
) -> ToolsSchema:
    def handler(convert: Callable[[dict], tuple], act: Callable):
        async def run(params):
            try:
                args = convert(params.arguments or {})
            except _BadArgument as exc:
                await params.result_callback(_refusal(exc))
                return
            result = act(*args)
            await params.result_callback({"ok": result.ok, "message": result.message})

        return run

    async def end_call(params):
        arguments = params.arguments or {}
        try:
            args = (_text(arguments, "outcome"), _text(arguments, "reason"))
        except _BadArgument as exc:
            await params.result_callback(_refusal(exc))
            return
        result = session.end(*args)
        await params.result_callback({"ok": result.ok, "message": result.message})
        if result.ok:
            await on_end(*args)

    add_item = handler(
        lambda a: (_text(a, "name"), _whole(a, "quantity"), _money(a, "unit_price_pkr")),
        session.add_item,
    )
    remove_item = handler(lambda a: (_text(a, "name"),), session.remove_item)
    set_fees = handler(
        lambda a: (_money(a, "delivery_fee_pkr"), _money(a, "tax_pkr")), session.set_fees
    )
    set_minimum = handler(lambda a: (_money(a, "minimum_pkr"),), session.set_minimum_order)
    confirm = handler(
        lambda a: (_money(a, "quoted_total_pkr"), _whole(a, "delivery_minutes")),
        session.confirm_order,
    )

    return ToolsSchema(
        standard_tools=[
            FunctionSchema(
                name="add_item",
                description="Add an item the restaurant has offered to the order, at the price they stated.",
                properties={
                    "name": {"type": "string", "description": "Item name as the restaurant said it."},
                    "quantity": {"type": "integer", "description": "How many to add."},
                    "unit_price_pkr": {"type": "number", "description": "Price of one unit in PKR, as a number."},
                },
                required=["name", "quantity", "unit_price_pkr"],
                handler=add_item,
            ),
            FunctionSchema(
                name="remove_item",
                description="Remove an item from the order.",
                properties={"name": {"type": "string", "description": "Name of the item to remove."}},
                required=["name"],
                handler=remove_item,
            ),
            FunctionSchema(
                name="set_fees",
                description="Record the delivery fee and tax the restaurant stated (use 0 if none).",
                properties={
                    "delivery_fee_pkr": {"type": "number", "description": "Delivery fee in PKR."},
                    "tax_pkr": {"type": "number", "description": "Tax in PKR."},
                },
                required=["delivery_fee_pkr", "tax_pkr"],
                handler=set_fees,
            ),
            FunctionSchema(
                name="set_minimum_order",
                description="Record the restaurant's minimum order for food, if they state one.",
                properties={"minimum_pkr": {"type": "number", "description": "Minimum order in PKR."}},
                required=["minimum_pkr"],
                handler=set_minimum,
            ),
            FunctionSchema(
                name="confirm_order",
                description="Confirm the order with the total and delivery time the restaurant quoted.",
                properties={
                    "quoted_total_pkr": {"type": "number", "description": "The all-in total the restaurant quoted, in PKR."},
                    "delivery_minutes": {"type": "integer", "description": "Delivery time in minutes (longest end of a range)."},
                },
                required=["quoted_total_pkr", "delivery_minutes"],
                handler=confirm,
            ),
            FunctionSchema(
                name="end_call",
                description="End the call once the order is confirmed, or when it cannot be made.",
                properties={
                    "outcome": {"type": "string", "enum": ["ordered", "not_ordered"], "description": "ordered only after confirm_order succeeded."},
                    "reason": {"type": "string", "description": "Short reason for the outcome."},
                },
                required=["outcome", "reason"],
                handler=end_call,
            ),
        ]
    )
