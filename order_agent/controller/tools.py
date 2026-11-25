"""Framework-free tool dispatch. Thin handlers over the rules engine.

Each handler converts the LLM's arguments, then delegates to OrderSession. If an
argument is missing or cannot be converted, it returns a refusal without
touching the session. No Pipecat types here: a head adapts ToolOutcome itself.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from order_agent.model.rules import OrderSession


@dataclass(frozen=True)
class ToolOutcome:
    ok: bool
    message: str
    run_llm: bool = True  # False only for a successful end_call
    ended: bool = False  # True once the call has ended

    def as_payload(self) -> dict:
        return {"ok": self.ok, "message": self.message}


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


def _optional_money(arguments: dict, key: str) -> Decimal | None:
    """A price that may be left out (None or absent = not given). A present but unreadable value is refused."""
    if arguments.get(key) is None:
        return None
    return _money(arguments, key)


def _flag(arguments: dict, key: str) -> bool:
    """An optional true/false argument; absent means false."""
    value = arguments.get(key)
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    raise _BadArgument(f"'{key}' must be true or false.")


def _whole(arguments: dict, key: str) -> int:
    """A whole number. An integral float such as 2.0 is accepted; 2.5 is not."""
    value = arguments.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _BadArgument(f"Missing or invalid '{key}': it must be a whole number.")
    if isinstance(value, float) and not value.is_integer():  # also rejects nan and inf
        raise _BadArgument(f"'{key}' must be a whole number, not {value}.")
    return int(value)


def _refusal(exc: _BadArgument) -> ToolOutcome:
    return ToolOutcome(ok=False, message=f"Refused: {exc}")


class ToolDispatcher:
    """Turns (tool name, raw arguments) into a ToolOutcome by calling the OrderSession."""

    def __init__(self, session: OrderSession) -> None:
        self.session = session
        # tool name -> (argument converter, session method)
        self._handlers: dict[str, tuple[Callable[[dict], tuple], Callable]] = {
            "add_item": (
                lambda a: (_text(a, "name"), _whole(a, "quantity"), _optional_money(a, "unit_price_pkr"), _flag(a, "price_corrected")),
                session.add_item,
            ),
            "set_price": (
                lambda a: (_text(a, "name"), _money(a, "unit_price_pkr"), _flag(a, "price_corrected")),
                session.set_price,
            ),
            "remove_item": (lambda a: (_text(a, "name"),), session.remove_item),
            "set_fees": (
                lambda a: (_money(a, "delivery_fee_pkr"), _money(a, "tax_pkr"), _flag(a, "corrected")),
                session.set_fees,
            ),
            "set_minimum_order": (lambda a: (_money(a, "minimum_pkr"),), session.set_minimum_order),
            "confirm_order": (
                lambda a: (_money(a, "quoted_total_pkr"), _whole(a, "delivery_minutes")),
                session.confirm_order,
            ),
        }

    async def dispatch(self, tool: str, arguments: Mapping | None) -> ToolOutcome:
        convert, act = self._handlers[tool]
        try:
            args = convert(arguments or {})
        except _BadArgument as exc:
            return _refusal(exc)
        result = act(*args)
        return ToolOutcome(ok=result.ok, message=result.message)
