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
    cart_total_pkr: Decimal
    quoted_total_pkr: Decimal | None
    delivery_eta: datetime | None
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
        cart_total_pkr=session.cart_total(),
        quoted_total_pkr=session.quoted_total_pkr,
        delivery_eta=session.delivery_eta,
        tool_events=[_plain(dataclasses.asdict(e)) for e in session.events],
        transcript=transcript,
        started_at=started_at,
        ended_at=ended_at,
    )


def _money(amount: Decimal) -> str:
    return f"{amount:f} PKR"


def summarise(report: CallReport) -> str:
    items = ", ".join(f"{i['quantity']} x {i['name']} at {i['unit_price_pkr']} PKR each" for i in report.items)
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
