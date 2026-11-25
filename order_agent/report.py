"""Call report: JSON for machines, one plain-English paragraph for humans.

No Pipecat imports here.
"""

import dataclasses
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from order_agent.rules import OrderSession


class TranscriptLine(BaseModel):
    role: Literal["agent", "restaurant"]
    text: str
    at: datetime


class CallReport(BaseModel):
    outcome: Literal["ordered", "not_ordered", "call_dropped"]
    reason: str
    items: list[dict]
    delivery_fee_pkr: Decimal
    tax_pkr: Decimal
    cart_total_pkr: Decimal | None  # None when an item has no price or fees were never recorded
    quoted_total_pkr: Decimal | None
    delivery_eta: datetime | None
    fees_set: bool = True  # False when set_fees was never called (the 0s above are then 'unknown')
    total_only: bool = False  # confirmed against the restaurant's total, not an itemised cart
    tool_events: list[dict]
    transcript: list[TranscriptLine]
    started_at: datetime
    ended_at: datetime


def _plain(value: Any) -> Any:
    """Make a value JSON-safe so a saved report reads back equal to the original."""
    if isinstance(value, Decimal):
        return f"{value:f}"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def build_report(
    session: OrderSession,
    outcome: Literal["ordered", "not_ordered", "call_dropped"],
    reason: str,
    transcript: list[TranscriptLine],
    started_at: datetime,
    ended_at: datetime,
) -> CallReport:
    return CallReport(
        outcome=outcome,
        reason=reason,
        items=[_plain(dataclasses.asdict(i)) for i in session.items],
        delivery_fee_pkr=session.delivery_fee_pkr,
        tax_pkr=session.tax_pkr,
        cart_total_pkr=session.cart_total() if session.cart_total_known() else None,
        quoted_total_pkr=session.quoted_total_pkr,
        delivery_eta=session.delivery_eta,
        fees_set=session._fees_set,
        total_only=session.confirmed_at_total_only,
        tool_events=[_plain(dataclasses.asdict(e)) for e in session.events],
        transcript=transcript,
        started_at=started_at,
        ended_at=ended_at,
    )


def _money(amount: Decimal) -> str:
    return f"{amount:f} PKR"


def summarise(report: CallReport) -> str:
    items = ", ".join(
        f"{i['quantity']} x {i['name']}" + (f" at {i['unit_price_pkr']} PKR each" if i.get("unit_price_pkr") is not None else "")
        for i in report.items
    )
    if report.outcome == "ordered" and report.cart_total_pkr is None and report.quoted_total_pkr is not None:
        unpriced = any(i.get("unit_price_pkr") is None for i in report.items)
        why = "prices not itemised by the restaurant" if unpriced else "delivery fee and tax not recorded"
        text = (
            f"The call ended with the order placed (ordered): {items} "
            f"({why}; confirmed at their total Rs {report.quoted_total_pkr:f})."
        )
        if report.delivery_eta:
            text += f" Delivery is expected by {report.delivery_eta:%H:%M}."
        return f"{text} Reason: {report.reason}"
    if report.outcome == "ordered":
        text = (
            f"The call ended with the order placed (ordered): {items}. "
            f"Delivery fee {_money(report.delivery_fee_pkr)}, tax {_money(report.tax_pkr)}, "
            f"total {_money(report.cart_total_pkr)}"
        )
        if report.quoted_total_pkr is not None:
            text += f" (the restaurant quoted {_money(report.quoted_total_pkr)})"
        text += "."
        if report.delivery_eta:
            text += f" Delivery is expected by {report.delivery_eta:%H:%M}."
        return f"{text} Reason: {report.reason}"
    if report.outcome == "not_ordered":
        return f"The call ended without an order (not_ordered). Reason: {report.reason}"
    if report.quoted_total_pkr is not None:
        eta = f" (delivery ETA {report.delivery_eta:%H:%M})" if report.delivery_eta else ""
        return (
            f"The call dropped after the order was confirmed at Rs {report.quoted_total_pkr:f}{eta} "
            f"(call_dropped). Reason: {report.reason}"
        )
    return (
        "The call dropped before it was finished (call_dropped); no order was confirmed. "
        f"Reason: {report.reason}"
    )


def write_report(report: CallReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{report.started_at:%Y%m%d-%H%M%S}"
    json_path = out_dir / f"{stem}.json"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (out_dir / f"{stem}.txt").write_text(summarise(report) + "\n", encoding="utf-8")
    return json_path
