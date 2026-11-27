"""Deterministic rules engine. Every LLM tool call goes through OrderSession.

No Pipecat imports here: this must stay pure Python so it can be tested alone.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from decimal import Decimal
from typing import Literal

from order_agent.model.brief import OrderBrief
from order_agent.model.matching import match_line, normalise


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
    unit_price_pkr: Decimal | None  # None: the restaurant has not given this item's price


def _fmt(amount: Decimal) -> str:
    return f"{amount:f}"


TOTAL_MISMATCH = (
    "Refused: the restaurant's total does not match the prices and fees you recorded. "
    "Do not tell the restaurant a total of your own. Ask them to itemise the total: each item with its price, then the delivery fee and tax. "
    "Do not edit the cart or the fees to make the totals match. Only if they clearly state a changed price or fee, correct it "
    "(add_item with price_corrected=true, or set_fees with corrected=true); if they cannot explain it, end the call as not_ordered."
)


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
        self._fees_set = False
        self._fee_known = False  # set_fees may record the fee and the tax separately (FR-014)
        self._tax_known = False
        # What the restaurant first said, kept for the whole call (even after remove_item).
        self._price_lock: dict[frozenset[str], tuple[str, Decimal]] = {}
        self.state: Literal["open", "confirmed", "ended"] = "open"
        self.events: list[ToolEvent] = []
        self.delivery_eta: datetime | None = None
        self.quoted_total_pkr: Decimal | None = None
        # True when the order was confirmed against the restaurant's total alone (prices or fees unknown).
        self.confirmed_at_total_only = False

    # -- helpers -----------------------------------------------------------

    def _record(self, tool: str, args: dict, result: ToolResult) -> ToolResult:
        self.events.append(ToolEvent(tool, args, result.ok, result.message, self.now))
        return result

    def record_refusal(self, tool: str, args: dict, message: str) -> ToolResult:
        """Record a refusal made outside the rules engine (the Controller's same-turn guard), like any other event."""
        return self._record(tool, args, ToolResult(False, message))

    def _items_total(self) -> Decimal:
        """Food subtotal of the priced items (unpriced items add nothing: see _has_unpriced)."""
        return sum((i.quantity * i.unit_price_pkr for i in self.items if i.unit_price_pkr is not None), Decimal(0))

    @property
    def fees_set(self) -> bool:
        """Whether set_fees has ever succeeded (otherwise the fee and tax are unknown, not 0)."""
        return self._fees_set

    def _has_unpriced(self) -> bool:
        return any(i.unit_price_pkr is None for i in self.items)

    def cart_total_known(self) -> bool:
        """The cart total is only honest to sum when every item has a price and the fees were set."""
        return self._fees_set and not self._has_unpriced()

    def cart_total(self) -> Decimal:
        """Sum of what is known. Only the true cart total when cart_total_known()."""
        return self._items_total() + self.delivery_fee_pkr + self.tax_pkr

    def _total_text(self) -> str:
        if self.cart_total_known():
            return f"Cart total is now {_fmt(self.cart_total())} PKR."
        return f"Known so far: {_fmt(self.cart_total())} PKR; the full cart total is not known yet (an item has no price or the fees are not recorded)."

    def _filled(self, line_item: str) -> int:
        return sum(i.quantity for i in self.items if i.line_item == line_item)

    def _below_minimum(self) -> bool:
        # False while anything is unpriced: the shortfall cannot be judged then, and confirm_order
        # enforces the minimum itself (it refuses until every item has a price).
        return self.minimum_order_pkr is not None and not self._has_unpriced() and self._items_total() < self.minimum_order_pkr

    def _minimum_hint(self) -> str:
        """Tell the bot exactly what to add to reach the minimum ('' if there is no shortfall)."""
        if not self._below_minimum():
            return ""
        food = self._items_total()
        shortfall = self.minimum_order_pkr - food
        head = f"The food is {_fmt(food)} PKR, {_fmt(shortfall)} PKR short of the {_fmt(self.minimum_order_pkr)} PKR minimum"
        if self.missing_lines():
            return f" The {_fmt(self.minimum_order_pkr)} PKR minimum still applies (food is {_fmt(food)} PKR): fill the required items from your brief first, then check it again."
        optional = {line.item for line in self.brief.wanted if line.optional}
        best = None
        for item in self.items:
            n = ceil(shortfall / item.unit_price_pkr)
            cost = n * item.unit_price_pkr
            if self.cart_total() + cost > self.brief.budget_pkr:
                continue
            key = (item.line_item not in optional, cost)
            if best is None or key < best[0]:
                best = (key, item, n, cost)
        budget = self.brief.budget_pkr
        if best is None:
            in_cart = {i.line_item for i in self.items}
            pending = [l.item for l in self.brief.wanted if l.optional and l.item not in in_cart]
            if pending:
                room = budget - self.cart_total()
                return (
                    f" {head}. Nothing in the cart covers it within budget, but {' or '.join(pending)} (optional) is not in the cart yet: "
                    f"ask its price and add enough of it, up to {_fmt(room)} PKR more within your {_fmt(budget)} PKR budget. "
                    "If its price doesn't fit in that room, end the call as not_ordered."
                )
            return f" {head}, and no addition fits within your {_fmt(budget)} PKR budget: end the call as not_ordered."
        _, item, n, cost = best
        tail = "" if self._fees_set else " Delivery fee and tax are not recorded yet, so ask about them."
        return f" {head}: ask the restaurant to add {n} more {item.name} ({_fmt(cost)} PKR) to reach it, and record it with add_item only after they agree.{tail}"

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
            if item.line_item in optional and item.unit_price_pkr is not None and item.quantity * item.unit_price_pkr >= overshoot:
                return item.name
        return None

    def _unused_substitutes(self, line, exclude: str = "") -> list[str]:
        in_cart = {normalise(i.name) for i in self.items} | {normalise(exclude)}
        return [s for s in line.substitutes if normalise(s) not in in_cart]

    def _over_budget(self, what: str, new_total: Decimal, line=None, exclude: str = "") -> ToolResult:
        budget = self.brief.budget_pkr
        msg = (
            f"Refused: {what} would bring the all-in total (items, delivery fee "
            f"and tax) to {_fmt(new_total)} PKR, over the budget of {_fmt(budget)} PKR."
        )
        drop = self._optional_to_drop(new_total - budget)
        if drop:
            msg += f" Dropping the optional item '{drop}' (remove_item) would make room."
        # Quantities never go down: after optional items, the only way out is a listed substitute.
        lines = [line] if line is not None else [
            ln for ln in self.brief.wanted if any(i.line_item == ln.item for i in self.items)
        ]
        subs = [s for ln in lines for s in self._unused_substitutes(ln, exclude)]
        if subs:
            msg += f" Otherwise you may ask for {' or '.join(subs)} instead, or end the call as not_ordered."
        else:
            msg += " Otherwise ask the restaurant for a cheaper price or end the call as not_ordered."
        return ToolResult(False, msg)

    # -- tools -------------------------------------------------------------

    def add_item(self, name: str, quantity: int, unit_price_pkr: Decimal | None = None, price_corrected: bool = False) -> ToolResult:
        args = {"name": name, "quantity": quantity, "unit_price_pkr": unit_price_pkr, "price_corrected": price_corrected}
        return self._record("add_item", args, self._add_item(name, quantity, unit_price_pkr, price_corrected))

    def _add_item(self, name: str, quantity: int, price: Decimal | None, corrected: bool = False) -> ToolResult:
        if self.state != "open":
            return _closed(self.state, "the cart")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
            return ToolResult(False, "Refused: quantity must be a whole number of at least 1. Ask the restaurant how many they mean.")
        if price is not None and (not isinstance(price, Decimal) or not price.is_finite() or price <= 0):
            return ToolResult(False, "Refused: the unit price must be a number greater than zero. Ask the restaurant to repeat the price per unit, or add the item without a price if they only give a total.")

        matched = match_line(self.brief, name)
        if matched is None:
            wanted = ", ".join(line.item for line in self.brief.wanted)
            return ToolResult(False, f"Refused: '{name}' is not in your brief, so you may not order it. You may only order: {wanted} (or their listed substitutes). Ask for one of those instead.")
        line, _is_substitute = matched

        rule = self._never_hit(name)
        if rule:
            return ToolResult(False, f"Refused: '{name}' breaks your '{rule}' rule. Do not order it; ask for another allowed item or substitute.")

        key = normalise(name)
        locked = self._price_lock.get(key)
        if price is not None and locked and locked[1] != price and not corrected:
            return ToolResult(False, f"Refused: The restaurant already said {locked[0]} is {_fmt(locked[1])} PKR. Do not change prices to make a total match. Ask the restaurant to read out each item's price; if they clearly say the price changed, call add_item with price_corrected=true.")
        existing = next((i for i in self.items if normalise(i.name) == key), None)
        # The price used for this add: the one given, else the one already recorded for this item (may be None).
        eff = price if price is not None else (existing.unit_price_pkr if existing else None)
        reprice = Decimal(0)
        if existing and price is not None:
            reprice = existing.quantity * (price - (existing.unit_price_pkr or Decimal(0)))

        filled = self._filled(line.item)
        if filled + quantity > line.quantity:
            if self.minimum_order_pkr is not None and (eff is None or self._has_unpriced()):
                return ToolResult(False, f"Refused: your brief wants {line.quantity} x {line.item} and {filled} are already in the cart, and a {_fmt(self.minimum_order_pkr)} PKR minimum order applies, but an item has no price yet so the food subtotal is unknown. Ask the restaurant for each item's price to check the minimum order (set_price), then add at most what the minimum needs.")
            if not self._below_minimum():
                return ToolResult(False, f"Refused: your brief wants {line.quantity} x {line.item} and {filled} are already in the cart, so adding {quantity} more goes over. Add at most {line.quantity - filled}.")
            room = max(0, line.quantity - filled)
            extra = quantity - room
            shortfall = self.minimum_order_pkr - self._items_total()
            cap = ceil(shortfall / eff)
            if extra > cap:
                return ToolResult(False, f"Refused: the food subtotal is only {_fmt(shortfall)} PKR short of the {_fmt(self.minimum_order_pkr)} PKR minimum, so at most {cap} extra x {name} (beyond your brief's {line.quantity} x {line.item}) are needed. Add at most {room + cap} now.")

        # Budget: only what is known. An unpriced add costs nothing we can count yet.
        new_total = self.cart_total() + reprice + (quantity * eff if eff is not None else Decimal(0))
        if new_total > self.brief.budget_pkr:
            return self._over_budget(f"adding {quantity} x {name}", new_total, line, name)

        if price is not None and (locked is None or locked[1] != price):
            self._price_lock[key] = (name, price)
        if existing:
            existing.unit_price_pkr = eff
            existing.quantity += quantity
        else:
            self.items.append(CartItem(name, line.item, quantity, eff))
        if eff is None:
            return ToolResult(True, f"Added {quantity} x {name} with no price recorded (the restaurant has not given one). Do not guess a price: if they only give a total, confirm with their total." + self._minimum_hint())
        return ToolResult(True, f"Added {quantity} x {name} at {_fmt(eff)} PKR each. " + self._total_text() + self._minimum_hint())

    def set_price(self, name: str, unit_price_pkr: Decimal, price_corrected: bool = False) -> ToolResult:
        args = {"name": name, "unit_price_pkr": unit_price_pkr, "price_corrected": price_corrected}
        return self._record("set_price", args, self._set_price(name, unit_price_pkr, price_corrected))

    def _set_price(self, name: str, price: Decimal, corrected: bool = False) -> ToolResult:
        if self.state != "open":
            return _closed(self.state, "prices")
        if not isinstance(price, Decimal) or not price.is_finite() or price <= 0:
            return ToolResult(False, "Refused: the unit price must be a number greater than zero. Ask the restaurant to repeat the price per unit.")
        key = normalise(name)
        item = next((i for i in self.items if normalise(i.name) == key), None)
        if item is None:
            in_cart = ", ".join(i.name for i in self.items) or "nothing yet"
            return ToolResult(False, f"Refused: '{name}' is not in the cart. The cart holds: {in_cart}. Add the item first (add_item).")
        locked = self._price_lock.get(key)
        if locked and locked[1] != price and not corrected:
            return ToolResult(False, f"Refused: The restaurant already said {locked[0]} is {_fmt(locked[1])} PKR. Do not change prices to make a total match. Ask the restaurant to read out each item's price; if they clearly say the price changed, call set_price with price_corrected=true.")
        old = item.unit_price_pkr
        new_total = self.cart_total() + item.quantity * (price - (old or Decimal(0)))
        if new_total > self.brief.budget_pkr:
            return self._over_budget(f"pricing {item.name} at {_fmt(price)} PKR each", new_total, None, item.name)
        item.unit_price_pkr = price
        self._price_lock[key] = (item.name, price)
        return ToolResult(True, f"Price recorded: {item.name} at {_fmt(price)} PKR each. " + self._total_text() + self._minimum_hint())

    def remove_item(self, name: str) -> ToolResult:
        return self._record("remove_item", {"name": name}, self._remove_item(name))

    def _remove_item(self, name: str) -> ToolResult:
        if self.state != "open":
            return _closed(self.state, "the cart")
        target = normalise(name)
        for item in self.items:
            if normalise(item.name) == target:
                self.items.remove(item)
                return ToolResult(True, f"Removed {item.name}. " + self._total_text() + self._minimum_hint())
        in_cart = ", ".join(i.name for i in self.items) or "nothing yet"
        return ToolResult(False, f"Refused: '{name}' is not in the cart. The cart holds: {in_cart}.")

    def set_fees(self, delivery_fee_pkr: Decimal | None, tax_pkr: Decimal | None, corrected: bool = False) -> ToolResult:
        args = {"delivery_fee_pkr": delivery_fee_pkr, "tax_pkr": tax_pkr, "corrected": corrected}
        return self._record("set_fees", args, self._set_fees(delivery_fee_pkr, tax_pkr, corrected))

    def _set_fees(self, fee: Decimal | None, tax: Decimal | None, corrected: bool = False) -> ToolResult:
        if self.state != "open":
            return _closed(self.state, "fees")
        if fee is None and tax is None:
            return ToolResult(False, "Refused: Give the delivery fee, the tax, or both, as the restaurant stated them. Leave out one they have not said.")
        for value in (fee, tax):
            if value is None:
                continue
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                return ToolResult(False, "Refused: fees must be numbers of zero or more. Ask the restaurant to repeat the delivery fee and tax (use 0 if there is none).")
        if not corrected:
            for label, old, new in (("delivery fee", self.delivery_fee_pkr, fee), ("tax", self.tax_pkr, tax)):
                if new is not None and old != 0 and new != old:
                    return ToolResult(False, f"Refused: The restaurant already said the {label} is {_fmt(old)} PKR. Do not change fees to make a total match. Ask the restaurant to read out the delivery fee and tax; if they clearly say a fee changed, call set_fees with corrected=true.")
        new_fee = self.delivery_fee_pkr if fee is None else fee
        new_tax = self.tax_pkr if tax is None else tax
        new_total = self._items_total() + new_fee + new_tax
        if new_total > self.brief.budget_pkr:
            return self._over_budget(f"a delivery fee of {_fmt(new_fee)} and tax of {_fmt(new_tax)}", new_total)
        self.delivery_fee_pkr, self.tax_pkr = new_fee, new_tax
        self._fee_known = self._fee_known or fee is not None
        self._tax_known = self._tax_known or tax is not None
        self._fees_set = self._fee_known and self._tax_known
        recorded = ", ".join(f"{label} {_fmt(value)} PKR" for label, value in (("delivery", fee), ("tax", tax)) if value is not None)
        missing = ""
        if not self._fee_known:
            missing = "The delivery fee is not recorded yet: ask the restaurant for it ('including delivery' is not a fee). "
        elif not self._tax_known:
            missing = "The tax is not recorded yet: ask the restaurant whether there is any. "
        return ToolResult(True, f"Fees recorded: {recorded}. " + missing + self._total_text() + self._minimum_hint())

    def set_minimum_order(self, minimum_pkr: Decimal) -> ToolResult:
        return self._record("set_minimum_order", {"minimum_pkr": minimum_pkr}, self._set_minimum_order(minimum_pkr))

    def _set_minimum_order(self, minimum: Decimal) -> ToolResult:
        if self.state != "open":
            return _closed(self.state, "the minimum order")
        if not isinstance(minimum, Decimal) or not minimum.is_finite() or minimum <= 0:
            return ToolResult(False, "Refused: the minimum order must be a number greater than zero. Ask the restaurant to repeat the minimum.")
        self.minimum_order_pkr = minimum
        return ToolResult(True, f"Minimum order recorded: {_fmt(minimum)} PKR of food (before delivery fee and tax). Food subtotal is now {_fmt(self._items_total())} PKR." + self._minimum_hint())

    def missing_lines(self) -> list[str]:
        out = []
        for line in self.brief.wanted:
            have = self._filled(line.item)
            if not line.optional and have < line.quantity:
                out.append(f"{line.item}: need {line.quantity}, have {have}")
        return out

    def confirm_order(self, quoted_total_pkr: Decimal, delivery_minutes: int, restaurant_items: list[tuple[str, int]] | None = None) -> ToolResult:
        args = {"quoted_total_pkr": quoted_total_pkr, "delivery_minutes": delivery_minutes}
        if restaurant_items is not None:
            args["restaurant_items"] = restaurant_items
        return self._record("confirm_order", args, self._confirm_order(quoted_total_pkr, delivery_minutes, restaurant_items))

    def _readback_differences(self, restaurant_items: list[tuple[str, int]]) -> list[str]:
        """Differences between what the restaurant read back and the cart, as '<item>: restaurant n, order m'."""
        held: dict[frozenset[str], list] = {}
        for item in self.items:
            held.setdefault(normalise(item.name), [item.name, 0])[1] += item.quantity
        said: dict[frozenset[str], list] = {}  # cart line key (or the name's own words if unmatched) -> [display name, quantity]
        for name, quantity in restaurant_items:
            words = normalise(name)
            if words in held:
                key = words
            else:
                near = [k for k in held if words and (words <= k or k <= words)]
                key = near[0] if len(near) == 1 else words
            said.setdefault(key, [held[key][0] if key in held else name, 0])[1] += quantity
        out = []
        for key in [*held, *(k for k in said if k not in held)]:
            name = held[key][0] if key in held else said[key][0]
            heard, ordered = said.get(key, [name, 0])[1], held.get(key, [name, 0])[1]
            if heard != ordered:
                out.append(f"{name}: restaurant {heard}, order {ordered}")
        return out

    def _confirm_order(self, quoted: Decimal, minutes: int, restaurant_items: list[tuple[str, int]] | None = None) -> ToolResult:
        if self.state != "open":
            return _closed(self.state, "the order")
        if not isinstance(quoted, Decimal) or not quoted.is_finite() or quoted <= 0:
            return ToolResult(False, "Refused: the quoted total must be a number greater than zero. Ask the restaurant to repeat the total.")
        if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 1:
            return ToolResult(False, "Refused: delivery time must be a whole number of minutes, at least 1 (use the latest end of a range). Ask the restaurant how long it will take.")

        if restaurant_items is not None:
            differences = self._readback_differences(restaurant_items)
            if differences:
                return ToolResult(False, f"Refused: the restaurant's read-back does not match your order ({'; '.join(differences)}). Politely correct the restaurant with your order's items and quantities. Do not change the order to match; then confirm again with their read-back. If they will not correct it, end the call as not_ordered.")

        missing = self.missing_lines()
        if missing:
            return ToolResult(False, f"Refused: the order is incomplete: {'; '.join(missing)}. Add the missing items (or their listed substitutes); if they can't be had, end the call as not_ordered.")

        if self.minimum_order_pkr is not None and self._has_unpriced():
            return ToolResult(False, f"Refused: a {_fmt(self.minimum_order_pkr)} PKR minimum order applies to the food, but not every item has a price, so it cannot be checked. Ask the restaurant for each item's price to check the minimum order, record each with set_price, then confirm again.")

        excess = self._unneeded_excess()
        if excess:
            return ToolResult(False, f"Refused: the cart holds more than your brief wants ({excess}) and the minimum order doesn't need the extra. Use remove_item to drop the extra, then confirm.")

        total_only = not self.cart_total_known()
        total = self.cart_total()
        if total_only:
            # Nothing honest to sum: hold the restaurant's own total to the budget (and the deadline below),
            # and it cannot be lower than what is already recorded.
            if quoted < total:
                return ToolResult(False, f"Refused: The restaurant's total (Rs {_fmt(quoted)}) is less than the prices already recorded. Ask them to check the total.")
            if quoted > self.brief.budget_pkr:
                return ToolResult(False, f"Refused: the restaurant's total of {_fmt(quoted)} PKR is over your budget of {_fmt(self.brief.budget_pkr)} PKR. Ask whether something can be cheaper; otherwise end the call as not_ordered.")
        elif quoted != total:
            return ToolResult(False, TOTAL_MISMATCH)

        if self._below_minimum():
            return ToolResult(False, self._minimum_refusal())

        start = self.brief.call_time or self.now
        eta = start + timedelta(minutes=minutes)
        deadline = datetime.combine(start.date(), self.brief.deliver_by)
        if eta > deadline:
            return ToolResult(False, f"Refused: delivery in {minutes} minutes means {eta:%H:%M}, after the {self.brief.deliver_by:%H:%M} deadline. Ask whether it can be faster; if not, end the call as not_ordered.")

        self.state = "confirmed"
        self.quoted_total_pkr = quoted
        self.confirmed_at_total_only = total_only
        self.delivery_eta = eta
        return ToolResult(True, f"Order confirmed at {_fmt(quoted)} PKR, delivery by about {eta:%H:%M}. Thank the restaurant and call end_call with outcome 'ordered'.")

    def _unneeded_excess(self) -> str:
        """Describe over-filled lines if the minimum doesn't need the extra, else ''."""
        parts, excess_value = [], Decimal(0)
        for line in self.brief.wanted:
            over = self._filled(line.item) - line.quantity
            if over <= 0:
                continue
            parts.append(f"{line.item}: wanted {line.quantity}, have {line.quantity + over}")
            prices = sorted((i.unit_price_pkr for i in self.items if i.line_item == line.item and i.unit_price_pkr is not None for _ in range(i.quantity)), reverse=True)
            excess_value += sum(prices[:over], Decimal(0))
        if not parts:
            return ""
        minimum = self.minimum_order_pkr
        if minimum is not None and self._items_total() - excess_value < minimum:
            return ""
        return "; ".join(parts)

    def _minimum_refusal(self) -> str:
        shortfall = self.minimum_order_pkr - self._items_total()
        optional = [l.item for l in self.brief.wanted if l.optional]
        wanted = [l.item for l in self.brief.wanted if not l.optional]
        options = []
        if optional:
            options.append(f"optional items ({', '.join(optional)})")
        options.append(f"extra quantity of wanted items ({', '.join(wanted)})")
        return (
            f"Refused: the food subtotal is {_fmt(self._items_total())} PKR, {_fmt(shortfall)} PKR short of the restaurant's "
            f"{_fmt(self.minimum_order_pkr)} PKR minimum (delivery fee and tax don't count). You may add {' or '.join(options)} "
            "to reach it, staying within budget; otherwise end the call as not_ordered." + self._minimum_hint()
        )

    def end(self, outcome: Literal["ordered", "not_ordered"], reason: str) -> ToolResult:
        return self._record("end", {"outcome": outcome, "reason": reason}, self._end(outcome, reason))

    def _end(self, outcome: str, reason: str) -> ToolResult:
        if self.state == "ended":
            return ToolResult(False, "Refused: the call has already ended; nothing more to do.")
        if outcome not in ("ordered", "not_ordered"):
            return ToolResult(False, "Refused: outcome must be 'ordered' or 'not_ordered'.")
        if outcome == "ordered" and self.state != "confirmed":
            return ToolResult(False, "Refused: you can only end as 'ordered' after confirm_order succeeds. Confirm the order with the restaurant first, or end as not_ordered if you can't.")
        if outcome == "not_ordered" and self.state == "confirmed":
            return ToolResult(False, "Refused: the order is already confirmed, so it can't end as not_ordered. End with outcome 'ordered'.")
        self.state = "ended"
        return ToolResult(True, f"Call ended as {outcome}: {reason}")
