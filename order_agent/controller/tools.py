"""Framework-free tool dispatch. Thin handlers over the rules engine.

Each handler converts the LLM's arguments, then delegates to OrderSession. If an
argument is missing or cannot be converted, it returns a refusal without
touching the session. No Pipecat types here: a head adapts ToolOutcome itself.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from loguru import logger

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
    """An amount that may be left out (None or absent = not given). A present but unreadable value is refused."""
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


_BAD_READBACK = "restaurant_items must be a list of {name, quantity} with whole-number quantities of at least 1."


def _readback(arguments: dict, key: str) -> list[tuple[str, int]] | None:
    """The restaurant's read-back as (name, quantity) pairs; None when absent."""
    value = arguments.get(key)
    if value is None:
        return None
    if not isinstance(value, list):
        raise _BadArgument(_BAD_READBACK)
    pairs = []
    for entry in value:
        if not isinstance(entry, dict):
            raise _BadArgument(_BAD_READBACK)
        try:
            name, quantity = _text(entry, "name"), _whole(entry, "quantity")
        except _BadArgument:
            raise _BadArgument(_BAD_READBACK) from None
        if quantity < 1:
            raise _BadArgument(_BAD_READBACK)
        pairs.append((name, quantity))
    return pairs


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
                lambda a: (_optional_money(a, "delivery_fee_pkr"), _optional_money(a, "tax_pkr"), _flag(a, "corrected")),
                session.set_fees,
            ),
            "set_minimum_order": (lambda a: (_money(a, "minimum_pkr"),), session.set_minimum_order),
            "confirm_order": (
                lambda a: (_money(a, "quoted_total_pkr"), _whole(a, "delivery_minutes"), _readback(a, "restaurant_items")),
                session.confirm_order,
            ),
        }

    async def dispatch(self, tool: str, arguments: Mapping | None) -> ToolOutcome:
        """Never raises: every failure becomes exactly one ``ok=False`` outcome."""
        if tool == "end_call":
            return self._end_call(arguments)
        handler = self._handlers.get(tool)
        if handler is None:
            return ToolOutcome(ok=False, message=f"Refused: unknown tool {tool!r}.")
        convert, act = handler
        try:
            args = convert(arguments or {})
        except _BadArgument as exc:
            return _refusal(exc)
        except Exception as exc:  # noqa: BLE001 - e.g. arguments that are not a dict
            logger.exception("tool argument conversion failed")
            return ToolOutcome(ok=False, message=f"Refused: could not read the arguments ({exc}).")
        try:
            result = act(*args)
            return ToolOutcome(ok=result.ok, message=result.message)
        except Exception as exc:  # noqa: BLE001 - the LLM must always get an answer
            logger.exception("tool handler failed")
            return ToolOutcome(ok=False, message=f"Refused: internal error ({exc}). Try again or end the call.")

    def _end_call(self, arguments: Mapping | None) -> ToolOutcome:
        """Only converts and asks the session; end-of-call work belongs to CallController."""
        try:
            arguments = arguments or {}
            args = (_text(arguments, "outcome"), _text(arguments, "reason"))
        except _BadArgument as exc:
            return _refusal(exc)
        except Exception as exc:  # noqa: BLE001 - e.g. arguments that are not a dict
            logger.exception("end_call argument conversion failed")
            return ToolOutcome(ok=False, message=f"Refused: could not read the arguments ({exc}).")
        try:
            result = self.session.end(*args)
        except Exception as exc:  # noqa: BLE001
            logger.exception("end_call failed")
            return ToolOutcome(ok=False, message=f"Refused: internal error ({exc}).")
        # A successful end must not trigger another inference (a second goodbye racing the
        # pipeline end). A refusal still lets the LLM respond so it can adapt.
        if result.ok:
            return ToolOutcome(ok=True, message=result.message, run_llm=False, ended=True)
        return ToolOutcome(ok=False, message=result.message)
