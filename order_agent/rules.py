"""Deterministic rules engine. Every LLM tool call goes through OrderSession.

No Pipecat imports here: this must stay pure Python so it can be tested alone.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from order_agent.brief import OrderBrief
from order_agent.matching import match_line, normalise


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    message: str


@dataclass
class ToolEvent:
    tool: str
    args: dict
    ok: bool
    message: str
    at: datetime


@dataclass
class CartItem:
    name: str  # as the restaurant said it
    line_item: str  # the brief line it fills
    quantity: int
    unit_price_pkr: Decimal


def _fmt(amount: Decimal) -> str:
    return f"{amount:f}"


def _closed(state: str, what: str) -> ToolResult:
    return ToolResult(False, f"Refused: the order is already {state}; {what} can no longer change.")


class OrderSession:
    def __init__(self, brief: OrderBrief, now: datetime):
        self.brief = brief
        self.now = now
        self.items: list[CartItem] = []
        self.delivery_fee_pkr: Decimal = Decimal(0)
        self.tax_pkr: Decimal = Decimal(0)
        self.minimum_order_pkr: Decimal | None = None
        self.state: Literal["open", "confirmed", "ended"] = "open"
        self.events: list[ToolEvent] = []

    # -- helpers -----------------------------------------------------------

    def _record(self, tool: str, args: dict, result: ToolResult) -> ToolResult:
        self.events.append(ToolEvent(tool, args, result.ok, result.message, self.now))
        return result

    def _items_total(self) -> Decimal:
        return sum((i.quantity * i.unit_price_pkr for i in self.items), Decimal(0))

    def cart_total(self) -> Decimal:
        return self._items_total() + self.delivery_fee_pkr + self.tax_pkr

    def _filled(self, line_item: str) -> int:
        return sum(i.quantity for i in self.items if i.line_item == line_item)

    def _never_hit(self, name: str) -> str | None:
        words = normalise(name)
        for rule, keywords in self.brief.never.items():
            for keyword in keywords:
                kw_words = normalise(keyword)
                if kw_words and kw_words <= words:
                    return rule
        return None

    def _optional_to_drop(self, overshoot: Decimal) -> str | None:
        """An optional cart item whose removal would cover the overshoot."""
        optional = {line.item for line in self.brief.wanted if line.optional}
        for item in self.items:
            if item.line_item in optional and item.quantity * item.unit_price_pkr >= overshoot:
                return item.name
        return None

    def _over_budget(self, what: str, new_total: Decimal) -> ToolResult:
        budget = self.brief.budget_pkr
        msg = (
            f"Refused: {what} would bring the all-in total (items, delivery fee "
            f"and tax) to {_fmt(new_total)} PKR, over the budget of {_fmt(budget)} PKR."
        )
        drop = self._optional_to_drop(new_total - budget)
        if drop:
            msg += (
                f" Dropping the optional item '{drop}' (remove_item) would make room; "
                "otherwise ask for a cheaper option or end the call as not_ordered."
            )
        else:
            msg += " Ask for a cheaper option or a smaller quantity, or end the call as not_ordered."
        return ToolResult(False, msg)

    # -- tools -------------------------------------------------------------

    def add_item(self, name: str, quantity: int, unit_price_pkr: Decimal) -> ToolResult:
        args = {"name": name, "quantity": quantity, "unit_price_pkr": unit_price_pkr}
        return self._record("add_item", args, self._add_item(name, quantity, unit_price_pkr))

    def _add_item(self, name: str, quantity: int, price: Decimal) -> ToolResult:
        if self.state != "open":
            return _closed(self.state, "the cart")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
            return ToolResult(False, "Refused: quantity must be a whole number of at least 1. Ask the restaurant how many they mean.")
        if not isinstance(price, Decimal) or not price.is_finite() or price <= 0:
            return ToolResult(False, "Refused: the unit price must be a number greater than zero. Ask the restaurant to repeat the price per unit.")

        matched = match_line(self.brief, name)
        if matched is None:
            wanted = ", ".join(line.item for line in self.brief.wanted)
            return ToolResult(False, f"Refused: '{name}' is not in your brief, so you may not order it. You may only order: {wanted} (or their listed substitutes). Ask for one of those instead.")
        line, _is_substitute = matched

        rule = self._never_hit(name)
        if rule:
            return ToolResult(False, f"Refused: '{name}' breaks your '{rule}' rule. Do not order it; ask for another allowed item or substitute.")

        existing = next((i for i in self.items if normalise(i.name) == normalise(name)), None)
        if existing and existing.unit_price_pkr != price:
            return ToolResult(False, f"Refused: '{existing.name}' is already in the cart at {_fmt(existing.unit_price_pkr)} PKR each, not {_fmt(price)}. Clarify the price with the restaurant, or remove_item it first and add it again.")

        filled = self._filled(line.item)
        if filled + quantity > line.quantity:
            return ToolResult(False, f"Refused: your brief wants {line.quantity} x {line.item} and {filled} are already in the cart, so adding {quantity} more goes over. Add at most {line.quantity - filled}.")

        new_total = self.cart_total() + quantity * price
        if new_total > self.brief.budget_pkr:
            return self._over_budget(f"adding {quantity} x {name}", new_total)

        if existing:
            existing.quantity += quantity
        else:
            self.items.append(CartItem(name, line.item, quantity, price))
        return ToolResult(True, f"Added {quantity} x {name} at {_fmt(price)} PKR each. Cart total is now {_fmt(self.cart_total())} PKR.")

    def remove_item(self, name: str) -> ToolResult:
        return self._record("remove_item", {"name": name}, self._remove_item(name))

    def _remove_item(self, name: str) -> ToolResult:
        if self.state != "open":
            return _closed(self.state, "the cart")
        target = normalise(name)
        for item in self.items:
            if normalise(item.name) == target:
                self.items.remove(item)
                return ToolResult(True, f"Removed {item.name}. Cart total is now {_fmt(self.cart_total())} PKR.")
        in_cart = ", ".join(i.name for i in self.items) or "nothing yet"
        return ToolResult(False, f"Refused: '{name}' is not in the cart. The cart holds: {in_cart}.")

    def set_fees(self, delivery_fee_pkr: Decimal, tax_pkr: Decimal) -> ToolResult:
        args = {"delivery_fee_pkr": delivery_fee_pkr, "tax_pkr": tax_pkr}
        return self._record("set_fees", args, self._set_fees(delivery_fee_pkr, tax_pkr))

    def _set_fees(self, fee: Decimal, tax: Decimal) -> ToolResult:
        if self.state != "open":
            return _closed(self.state, "fees")
        for value in (fee, tax):
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                return ToolResult(False, "Refused: fees must be numbers of zero or more. Ask the restaurant to repeat the delivery fee and tax (use 0 if there is none).")
        new_total = self._items_total() + fee + tax
        if new_total > self.brief.budget_pkr:
            return self._over_budget(f"a delivery fee of {_fmt(fee)} and tax of {_fmt(tax)}", new_total)
        self.delivery_fee_pkr, self.tax_pkr = fee, tax
        return ToolResult(True, f"Fees recorded: delivery {_fmt(fee)} PKR, tax {_fmt(tax)} PKR. Cart total is now {_fmt(self.cart_total())} PKR.")
